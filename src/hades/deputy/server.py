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
import pwd
import re
import signal
import stat
import string
import subprocess
import textwrap
from functools import partial
from typing import Iterable, Optional, Tuple

import netaddr
from gi.repository import GLib
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
)
from hades.common.glib import typed_glib_error
from hades.common.privileges import dropped_privileges
from hades.common.signals import install_handler
from hades.config.loader import Config, get_config
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


def generate_auth_dhcp_hosts_file(
    hosts: Iterable[Tuple[netaddr.EUI, netaddr.IPAddress, Optional[str]]],
) -> None:
    """Generate the dnsmasq hosts file for authenticated users"""
    file_name = constants.AUTH_DHCP_HOSTS_FILE
    logger.info("Generating DHCP hosts file %s", file_name)
    auth_dhcp_pwd = pwd.getpwnam(constants.AUTH_DHCP_USER)
    try:
        fd = os.open(file_name, os.O_CREAT | os.O_WRONLY | os.O_CLOEXEC,
                     stat.S_IRUSR | stat.S_IRGRP)
        with open(fd, mode='w', encoding='ascii') as f:
            os.fchown(fd, auth_dhcp_pwd.pw_uid, auth_dhcp_pwd.pw_gid)
            os.fchmod(fd, stat.S_IRUSR | stat.S_IRGRP)
            f.writelines(generate_dhcp_host_reservations(hosts))
    except OSError as e:
        logger.error("Error writing %s: %s", file_name, e.strerror)


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
    """DBus object introspection specification"""

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

        If necessary depended config files are regenerate and the corresponding
        services are reloaded.
        """
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
                hosts = db.get_all_auth_dhcp_hosts(connection)
                clients = db.get_all_nas_clients(connection)
                ips = db.get_all_alternative_dns_ips(connection)
            else:
                auth_dhcp_host_diff = db.refresh_and_diff_materialized_view(
                    connection,
                    db.auth_dhcp_host,
                    db.temp_auth_dhcp_host,
                    [null()],
                )
                if auth_dhcp_host_diff != ([], [], []):
                    logger.info(
                        "Auth DHCP host reservations changed "
                        "(%d added, %d deleted, %d modified).",
                        *map(len, auth_dhcp_host_diff)
                    )
                    hosts = db.get_all_auth_dhcp_hosts(connection)
                    reload_auth_dhcp_host = True
                else:
                    reload_auth_dhcp_host = False

                nas_diff = db.refresh_and_diff_materialized_view(
                    connection, db.nas, db.temp_nas, [null()])

                if nas_diff != ([], [], []):
                    logger.info('RADIUS clients changed '
                                '(%d added, %d deleted, %d modified).',
                                *map(len, nas_diff))
                    clients = db.get_all_nas_clients(connection)
                    reload_nas = True
                else:
                    reload_nas = False

                alternative_dns_diff = db.refresh_and_diff_materialized_view(
                    connection, db.alternative_dns, db.temp_alternative_dns,
                    [null()])

                if alternative_dns_diff != ([], [], []):
                    logger.info('Alternative auth DNS clients changed '
                                '(%d added, %d deleted, %d modified).',
                                *map(len, alternative_dns_diff))
                    ips = db.get_all_alternative_dns_ips(connection)
                    reload_alternative_dns = True
                else:
                    reload_alternative_dns = False

        if reload_auth_dhcp_host:
            generate_auth_dhcp_hosts_file(hosts)
            reload_systemd_unit(self.bus, 'hades-auth-dhcp.service')
        if reload_nas:
            generate_radius_clients_file(clients)
            restart_systemd_unit(self.bus, 'hades-radius.service')
        if reload_alternative_dns:
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
            auth_dhcp_lease, self.config.HADES_AUTH_LISTEN[0], client_ip
        )

    def ReleaseUnauthDhcpLease(self, client_ip: str) -> str:
        """
        Release an auth DHCP lease
        :return:
        """
        logger.info("Releasing unauth DHCP lease for client %s", client_ip)
        return self._release_dhcp_lease(
            unauth_dhcp_lease, self.config.HADES_UNAUTH_LISTEN[0], client_ip
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
