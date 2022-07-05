"""
Deputy daemon that provides a service via DBus for performing privileged
operations.

Some operations, such as generating configuration files, sending signals to
other processes etc. need certain privileges. The Deputy service runs as *root*
and provides a very simple service over DBus.
"""
import contextlib
import importlib.resources
import io
import logging
import os
import pathlib
import pwd
import re
import signal
import stat
import string
import subprocess
import tempfile
import textwrap
from functools import partial
from typing import Iterable, Optional, Tuple, Union, overload, Iterator, List

import netaddr
from gi.repository import GLib
from netaddr import EUI, IPAddress
from pydbus import SystemBus
from pydbus.bus import Bus
from sqlalchemy import null
from sqlalchemy.pool import StaticPool

from hades import constants
from hades.common import db
from hades.common.db import (
    auth_dhcp_lease,
    get_dhcp_lease_of_ip,
    unauth_dhcp_lease,
    ObjectsDiff, LeaseInfo,
)
from hades.common.glib import typed_glib_error
from hades.common.privileges import dropped_privileges
from hades.common.signals import install_handler
from hades.config import Config, get_config
from hades.deputy.dhcp import release_dhcp_lease

logger = logging.getLogger(__name__)


def reload_systemd_unit(bus: Bus, unit: str, timeout: int = 100) -> None:
    """Instruct systemd to reload a given unit.

    :param bus: A DBus Bus
    :param unit: The name of the systemd unit
    :param timeout: Timeout in milliseconds
    """
    logger.debug("Instructing systemd to reload unit %s", unit)
    with typed_glib_error():
        systemd = bus.get('org.freedesktop.systemd1', timeout=timeout)
        manager_interface = systemd['org.freedesktop.systemd1.Manager']
        manager_interface.ReloadUnit(unit, 'fail', timeout=timeout)


def restart_systemd_unit(bus: Bus, unit: str, timeout: int = 100) -> None:
    """Instruct systemd to restart a given unit.

    :param bus: A DBus Bus
    :param unit: The name of the systemd unit
    :param timeout: Timeout in milliseconds
    """
    logger.debug("Instructing systemd to restart unit %s", unit)
    with typed_glib_error():
        systemd = bus.get('org.freedesktop.systemd1', timeout=timeout)
        manager_interface = systemd['org.freedesktop.systemd1.Manager']
        manager_interface.RestartUnit(unit, 'fail', timeout=timeout)


def generate_dhcp_host_reservations(
    hosts: Iterable[Tuple[netaddr.EUI, netaddr.IPAddress, Optional[str]]],
) -> Iterable[str]:
    """Generate lines suitable for dnsmasq's ``--dhcp-hostsfile=`` option.

    :param hosts: The MAC address-IP address pairs of the hosts
    """
    for mac, ip, hostname in hosts:
        mac = netaddr.EUI(mac)
        mac.dialect = netaddr.mac_unix_expanded
        if hostname is not None:
            yield "{0},id:*,{1},{2}\n".format(mac, ip, hostname)
        else:
            yield "{0},id:*,{1}\n".format(mac, ip)


@overload
def replace_file(
    path: Union[os.PathLike, str],
    content: Union[Iterable[bytes], bytes],
    *,
    encoding: None = ...,
    owner: Optional[int] = ...,
    group: Optional[int] = ...,
    mode: Optional[int] = ...,
) -> None: ...


@overload
def replace_file(
    path: Union[os.PathLike, str],
    content: Union[Iterable[str], str],
    *,
    encoding: str = ...,
    owner: Optional[int] = ...,
    group: Optional[int] = ...,
    mode: Optional[int] = ...,
) -> None: ...


def replace_file(
    path: Union[os.PathLike, str],
    content: Union[Iterable[Union[bytes, str]], Union[bytes, str]],
    *,
    encoding: Optional[str] = None,
    owner: Optional[int] = None,
    group: Optional[int] = None,
    mode: Optional[int] = None,
) -> None:
    """
    Atomically replace a file with the given content.

    The directory of the file must exist and must be writeable. The content may
    either be a str or bytes object or an Iterable of such objects, in which
    case the content will be written via :func:`io.IO.writelines`.

    :param path: Path to the file
    :param content: The new content of the file
    :param encoding: The encoding for :class:`str` content
    :param owner: File owner
    :param group: File group
    :param mode: File mode
    :raises OSError: if file system operations fail
    """
    open_mode = "wb" if encoding is None else "w"
    path = pathlib.Path(path)
    parent = path.parent
    if encoding is None and isinstance(content, str):
        raise ValueError("encoding required for writing str content")
    with tempfile.NamedTemporaryFile(
        open_mode, encoding=encoding, dir=parent, delete=False
    ) as file:
        dir_fd = None
        try:
            dir_fd = os.open(
                parent, os.O_DIRECTORY | os.O_CLOEXEC | os.O_RDONLY, 0
            )
            fd = file.fileno()
            if (owner is None) ^ (group is None):
                stat_result = os.fstat(fd)
                if owner is None:
                    owner = stat_result.st_uid
                if group is None:
                    group = stat_result.st_gid
            if owner is not None:
                os.fchown(fd, owner, group)
            if mode is not None:
                os.fchmod(fd, mode)
            if isinstance(content, (bytes, str)):
                file.write(content)
            else:
                file.writelines(content)
            file.flush()
            os.fsync(fd)
            os.rename(file.name, path)
            os.fsync(dir_fd)
        except BaseException:
            os.unlink(file)
            raise
        finally:
            if dir_fd is not None:
                os.close(dir_fd)


def generate_auth_dhcp_hosts_file(
    hosts: Iterable[Tuple[netaddr.EUI, netaddr.IPAddress, Optional[str]]],
) -> None:
    """Generate the dnsmasq hosts file for authenticated users.

    This file is passed toh the dnsmasq via the ``--dhcp-hostsfile`` option.
    The lines are generated by :func:`generate_dhcp_host_reservations`.
    """
    file = pathlib.Path(constants.AUTH_DHCP_HOSTS_FILE)
    logger.info("Generating DHCP hosts file %s", file)
    # Use hades-auth-dhcp as owner not as root
    auth_dhcp_pwd = pwd.getpwnam(constants.AUTH_DHCP_USER)
    try:
        replace_file(
            file,
            generate_dhcp_host_reservations(hosts),
            encoding="ascii",
            owner=auth_dhcp_pwd.pw_uid,
            group=auth_dhcp_pwd.pw_gid,
            mode=stat.S_IRUSR | stat.S_IRGRP,
        )
    except OSError as e:
        logger.error(
            "Failed to replace DHCP hosts file %s: %s", file, e.strerror
        )


def generate_ipset_swap(ipset_name: str, tmp_ipset_name: str,
                        ips: Iterable[netaddr.IPAddress]) -> Iterable[str]:
    """Generate an ``ipset`` script, that replaces an existing ``hash:ip`` ipset
    with new contents.

    :param ipset_name: The ipset to replace
    :param tmp_ipset_name: Name of the temporary ipset
    :param ips: The new contents of the ipset
    """
    yield 'create {} hash:ip -exist\n'.format(tmp_ipset_name)
    yield 'flush {}\n'.format(tmp_ipset_name)
    yield from map(partial('add {} {}\n'.format, tmp_ipset_name), ips)
    yield 'swap {} {}\n'.format(ipset_name, tmp_ipset_name)
    yield 'destroy {}\n'.format(tmp_ipset_name)


def update_alternative_dns_ipset(ips: Iterable[netaddr.IPAddress]) -> None:
    """Update the *alternative DNS ipset* with the new IP addresses

    :param ips: The new IP addresses
    """
    conf = get_config()
    ipset_name = conf['HADES_AUTH_DNS_ALTERNATIVE_IPSET']
    tmp_ipset_name = 'tmp_' + ipset_name
    logger.info("Updating alternative_dns ipset (%s)", ipset_name)
    commands = io.TextIOWrapper(io.BytesIO(), 'ascii')
    commands.writelines(generate_ipset_swap(ipset_name, tmp_ipset_name, ips))
    commands.flush()
    subprocess.run(
        [constants.IP, 'netns', 'exec', 'auth', constants.IPSET, 'restore'],
        input=commands.buffer.getvalue())


def generate_radius_clients(
        clients: Iterable[Tuple[str, str, str, int, str, str, str, str]]
) -> Iterable[str]:
    """Generate the FreeRADIUS configuration for a given list of NAS clients in
    the ``clients.conf`` format.

    :param clients: An iterable of (Shortname, NAS-Name, NAS-Type, Port, Secret,
     Server, Community, Description)-tuples. Currently only shortname NAS-Name,
     NAS-Type and the Secret elements are used.
    :return: configuration snippets for the given NAS clients
    """
    escape_pattern = re.compile(r'(["\\])')
    replacement = r'\\\1'

    template = string.Template(textwrap.dedent("""
        client $shortname {
            shortname = "$shortname"
            ipaddr = "$nasname"
            secret = "$secret"
            require_message_authenticator = no
            nastype = $type
            coa_server = "$shortname"
        }
        home_server $shortname {
            type = coa
            ipaddr = "$nasname"
            port = 3799
            secret = "$secret"
            coa {
                irt = 2
                mrt = 16
                mrc = 5
                mrd = 30
            }
        }
    """))
    for shortname, nasname, type, ports, secret, server, community, description in clients:
        yield template.substitute(
            shortname=shortname, nasname=nasname, type=type, ports=ports,
            secret=escape_pattern.sub(replacement, secret), community=community,
            description=description)


def generate_radius_clients_file(
        clients: Iterable[Tuple[str, str, str, int, str, str, str, str]]
) -> None:
    """Generate a FreeRADIUS ``clients.conf`` file.

    :param clients: See :func:`generate_radius_clients` for a description
    """
    logger.info("Generating freeRADIUS clients configuration")
    file_name = constants.RADIUS_CLIENTS_FILE
    radius_pwd = pwd.getpwnam(constants.RADIUS_USER)
    try:
        with open(file_name, mode='w', encoding='ascii') as f:
            fd = f.fileno()
            os.fchown(fd, radius_pwd.pw_uid, radius_pwd.pw_gid)
            os.fchmod(fd, stat.S_IRUSR | stat.S_IRGRP)
            f.writelines(generate_radius_clients(clients))
    except OSError as e:
        logger.exception("Error writing %s: %s", file_name, e.strerror)


# noinspection PyPep8Naming
class HadesDeputyService(object):
    """Deputy DBus service

    This class implements a DBus service that exposes some privileged operations
    for use by the :mod:`hades.agent` or the periodic systemd timer services.

    For security reasons, the service doesn't accept data from the DBus clients
    and always queries the database itself, so that this service can't be
    misused.
    """
    dbus = importlib.resources.read_text(__package__, "interface.xml")
    """DBus object introspection specification

    :meta hide-value:
    """

    def __init__(self, bus: Bus, config: Config):
        """

        :param bus: The bus (typically the system bus)
        :param config: The configuration object
        """
        self.bus = bus
        self.config = config
        self.engine = db.create_engine(config, poolclass=StaticPool)
        database_pwd = pwd.getpwnam(constants.DATABASE_USER)
        original_creator = self.engine.pool._creator

        def creator(connection_record=None):
            """Create a connection as the database user"""
            with dropped_privileges(database_pwd):
                connection = original_creator(connection_record)
            return connection

        self.engine.pool._creator = creator

    def Refresh(self, force: bool) -> str:
        """Refresh the materialized views.

        If necessary depended config files are regenerated and the corresponding services are reloaded.

        The forced refresh is a little more aggressive in what it consolidates
        to achieve eventual consistency:

        * The host reservation file is regenerated regardless of whether the content
          of the ``auth_dhcp_host`` table has changed.
        * The radius config is regenerated regardless of whether the content
          of the ``nas`` table has changed.
        * The alternative DNS ipset is regenerated regardless of whether the content
          of the ``alternative_dns`` table has changed.
        * Instead of invalidating leases which were modified in the `auth_dhcp_hosts`
          reservation table, we invalidate every lease in `auth_dhcp_leases`
          which does not belong to a host reservation.

        :param force: Whether to use the forced refresh.
        """
        reload_auth_dhcp_host: bool  # if set, we want `hosts: List`
        hosts: Optional[Iterator[...]]  # set iff `reload_auth_dhcp_host`
        auth_leases_to_invalidate: List[LeaseInfo] = []

        reload_nas: bool  # if set, we want `clients: List`
        clients: Optional[Iterator[...]]  # set iff `reload_nas`

        reload_alternative_dns: bool  # if set, we want `ips: List`
        ips: Optional[Iterator[...]]

        logger.info("Refreshing materialized views")
        with contextlib.closing(self.engine.connect()) as connection:
            with connection.begin():
                db.refresh_materialized_view(connection, db.radcheck)
                db.refresh_materialized_view(connection, db.radreply)
                db.refresh_materialized_view(connection, db.radgroupcheck)
                db.refresh_materialized_view(connection, db.radgroupreply)
                db.refresh_materialized_view(connection, db.radusergroup)
            if force:
                with connection.begin():
                    db.refresh_materialized_view(connection, db.auth_dhcp_host)
                    db.refresh_materialized_view(connection, db.nas)
                    db.refresh_materialized_view(connection, db.alternative_dns)
                logger.info("Forcing reload of DHCP hosts, NAS clients and "
                            "alternative DNS clients")
                reload_auth_dhcp_host = True
                reload_nas = True
                reload_alternative_dns = True
                auth_leases_to_invalidate = list(
                    db.get_all_invalid_auth_dhcp_leases(connection)
                )
                hosts = db.get_all_auth_dhcp_hosts(connection)
                clients = db.get_all_nas_clients(connection)
                ips = db.get_all_alternative_dns_ips(connection)
            else:
                auth_dhcp_host_diff: ObjectsDiff[
                    Tuple[IPAddress, EUI, IPAddress, EUI]
                ] = db.refresh_and_diff_materialized_view(
                    connection,
                    db.auth_dhcp_host,
                    db.temp_auth_dhcp_host,
                    [
                        db.temp_auth_dhcp_host.c.IPAddress,  # old ip
                        db.temp_auth_dhcp_host.c.MAC,  # old mac
                        db.auth_dhcp_host.c.IPAddress,  # new ip
                        db.auth_dhcp_host.c.MAC,  # new mac
                    ],
                    unique_columns=(db.auth_dhcp_host.c.MAC, db.auth_dhcp_host.c.IPAddress),
                )
                if auth_dhcp_host_diff:
                    logger.info(
                        "Auth DHCP host reservations changed (%s).",
                        auth_dhcp_host_diff,
                    )
                    logger.debug(
                        "Full host reservations diff:\n%s",
                        f"{auth_dhcp_host_diff:l}",
                    )
                    hosts = db.get_all_auth_dhcp_hosts(connection)
                    auth_leases_to_invalidate = [
                        LeaseInfo(old_ip, old_mac)
                        for old_ip, old_mac, _, _
                        in auth_dhcp_host_diff.deleted + auth_dhcp_host_diff.modified
                    ]
                    reload_auth_dhcp_host = True
                else:
                    reload_auth_dhcp_host = False

                nas_diff = db.refresh_and_diff_materialized_view(
                    connection, db.nas, db.temp_nas, [null()])

                if nas_diff:
                    logger.info(
                        "RADIUS clients changed (%s).",
                        nas_diff,
                    )
                    clients = db.get_all_nas_clients(connection)
                    reload_nas = True
                else:
                    reload_nas = False

                alternative_dns_diff = db.refresh_and_diff_materialized_view(
                    connection, db.alternative_dns, db.temp_alternative_dns,
                    [null()])

                if alternative_dns_diff:
                    logger.info(
                        "Alternative auth DNS clients changed (%s).",
                        alternative_dns_diff,
                    )
                    ips = db.get_all_alternative_dns_ips(connection)
                    reload_alternative_dns = True
                else:
                    reload_alternative_dns = False

        if auth_leases_to_invalidate:
            logger.info(
                "Releasing %d invalid leases",
                len(auth_leases_to_invalidate),
            )
            server_ip = self.config.HADES_AUTH_LISTEN[0].ip
            for lease in auth_leases_to_invalidate:
                logger.debug("Releasing lease %s", lease)
                # potential optimization: batched packet sending
                release_dhcp_lease(server_ip, lease.ip, lease.mac)
        if reload_auth_dhcp_host:
            assert hosts is not None
            generate_auth_dhcp_hosts_file(hosts)
            reload_systemd_unit(self.bus, "hades-auth-dhcp.service")
        if reload_nas:
            assert clients is not None
            generate_radius_clients_file(clients)
            restart_systemd_unit(self.bus, 'hades-radius.service')
        if reload_alternative_dns:
            assert ips is not None
            update_alternative_dns_ipset(ips)
        return "OK"

    def Cleanup(self) -> str:
        """Clean up old records in the ``radacct`` and ``radpostauth`` tables.
        """
        logger.info("Cleaning up old records")
        interval = self.config.HADES_RETENTION_INTERVAL
        with contextlib.closing(self.engine.connect()) as connection:
            db.delete_old_sessions(connection, interval)
            db.delete_old_auth_attempts(connection, interval)
        return "OK"

    def _release_dhcp_lease(
        self, table, server_ip: netaddr.IPAddress, client_ip: str
    ) -> str:
        """
        Release an auth or unauth DHCP lease

        :return:
        """
        try:
            client_ip = netaddr.IPAddress(client_ip)
        except ValueError:
            return "ERROR: Illegal IP address %s" % client_ip
        with contextlib.closing(self.engine.connect()) as connection:
            lease_info = get_dhcp_lease_of_ip(table, connection, client_ip)
            if lease_info is None:
                logger.warning("No lease for %s found", client_ip)
                return "OK"
            expiry_time, mac, hostname, client_id = lease_info
            release_dhcp_lease(server_ip, client_ip, mac, client_id)
        return "OK"

    def ReleaseAuthDhcpLease(self, client_ip: str) -> str:
        """
        Release an auth DHCP lease

        :return:
        """
        logger.info("Releasing auth DHCP lease for client %s", client_ip)
        return self._release_dhcp_lease(
            auth_dhcp_lease, self.config.HADES_AUTH_LISTEN[0].ip, client_ip
        )

    def ReleaseUnauthDhcpLease(self, client_ip: str) -> str:
        """
        Release an auth DHCP lease

        :return:
        """
        logger.info("Releasing unauth DHCP lease for client %s", client_ip)
        return self._release_dhcp_lease(
            unauth_dhcp_lease, self.config.HADES_UNAUTH_LISTEN[0].ip, client_ip
        )


def run_event_loop():
    """Run the DBus :class:`HadesDeputyService` on the GLib event loop."""
    with contextlib.ExitStack() as stack:
        bus: Bus = stack.enter_context(SystemBus())
        logger.debug(
            "Publishing interface %s on DBus", constants.DEPUTY_DBUS_NAME
        )
        config = get_config()
        stack.enter_context(
            bus.publish(
                constants.DEPUTY_DBUS_NAME, HadesDeputyService(bus, config)
            )
        )
        loop = GLib.MainLoop()
        stack.enter_context(
            install_handler(
                (signal.SIGHUP, signal.SIGINT, signal.SIGTERM),
                lambda _sig, _frame: loop.quit(),
            )
        )
        loop.run()
