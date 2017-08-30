"""
Deputy daemon that provides a service via DBus for performing privileged
operations.

Some operations, such as generating configuration files, sending signals to
other processes etc. needs certain privileges. The Deputy service runs as root
and provides a very simple service over DBus.
"""
import contextlib
import io
import logging
import os
import pwd
import re
import stat
import string
import subprocess
import textwrap
from functools import partial

import netaddr
import pkg_resources
from gi.repository import GLib
from pydbus import SystemBus
from sqlalchemy import null
from sqlalchemy.pool import StaticPool

from hades import constants
from hades.common import db
from hades.common.privileges import dropped_privileges
from hades.config.loader import get_config

logger = logging.getLogger(__name__)
auth_dhcp_pwd = pwd.getpwnam(constants.AUTH_DHCP_USER)
database_pwd = pwd.getpwnam(constants.DATABASE_USER)
radius_pwd = pwd.getpwnam(constants.RADIUS_USER)


def reload_systemd_unit(bus: Bus, unit: str, timeout: int = 100) -> None:
    """
    Instruct systemd to reload a given unit.
    :param bus: A DBus Bus
    :param unit: The name of the systemd unit
    :param timeout: Timeout in milliseconds
    """
    logger.debug("Instructing systemd to reload unit %s", unit)
    systemd = bus.get('org.freedesktop.systemd1', timeout=timeout)
    systemd.ReloadUnit(unit, 'fail', timeout=timeout)


def restart_systemd_unit(bus: Bus, unit: str, timeout: int = 100) -> None:
    """
    Instruct systemd to restart a given unit.
    :param bus: A DBus Bus
    :param unit: The name of the systemd unit
    :param timeout: Timeout in milliseconds
    """
    logger.debug("Instructing systemd to restart unit %s", unit)
    systemd = bus.get('org.freedesktop.systemd1', timeout=timeout)
    systemd.RestartUnit(unit, 'fail', timeout=timeout)


def generate_dhcp_host_reservations(hosts):
    for mac, ip in hosts:
        mac = netaddr.EUI(mac)
        mac.dialect=netaddr.mac_unix_expanded
        yield "{0},{1}\n".format(mac, ip)


def generate_dhcp_hosts_file(hosts):
    file_name = constants.AUTH_DHCP_HOSTS_FILE
    logger.info("Generating DHCP hosts file %s", file_name)
    try:
        with open(file_name, mode='w', encoding='ascii') as f:
            fd = f.fileno()
            os.fchown(fd, auth_dhcp_pwd.pw_uid, auth_dhcp_pwd.pw_gid)
            os.fchmod(fd, stat.S_IRUSR | stat.S_IRGRP)
            f.writelines(generate_dhcp_host_reservations(hosts))
    except OSError as e:
        logger.error("Error writing %s: %s", file_name, e.strerror)


def generate_ipset_swap(ipset_name, tmp_ipset_name, ips):
    yield 'create {} hash:ip -exist\n'.format(tmp_ipset_name)
    yield 'flush {}\n'.format(tmp_ipset_name)
    yield from map(partial('add {} {}\n'.format, tmp_ipset_name), ips)
    yield 'swap {} {}\n'.format(ipset_name, tmp_ipset_name)
    yield 'destroy {}\n'.format(tmp_ipset_name)


def update_alternative_dns_ipset(ips):
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


def generate_radius_clients(clients):
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


def generate_radius_clients_file(clients):
    logger.info("Generating freeRADIUS clients configuration")
    file_name = constants.RADIUS_CLIENTS_FILE
    try:
        with open(file_name, mode='w', encoding='ascii') as f:
            fd = f.fileno()
            os.fchown(fd, radius_pwd.pw_uid, radius_pwd.pw_gid)
            os.fchmod(fd, stat.S_IRUSR | stat.S_IRGRP)
            f.writelines(generate_radius_clients(clients))
    except OSError as e:
        logger.exception("Error writing %s: %s", file_name, e.strerror)


class HadesDeputyService(object):
    dbus = pkg_resources.resource_string(
        __package__, 'interface.xml').decode('utf-8')

    def __init__(self, bus, config):
        self.bus = bus
        self.config = config
        self.engine = db.create_engine(config, poolclass=StaticPool)
        original_creator = self.engine.pool._creator

        def creator(connection_record=None):
            """Create a connection as the database user"""
            with dropped_privileges(database_pwd):
                connection = original_creator(connection_record)
            return connection

        self.engine.pool._creator = creator

    def Refresh(self, force):
        """
        Refresh the materialized views.
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
                    db.refresh_materialized_view(connection, db.dhcphost)
                    db.refresh_materialized_view(connection, db.nas)
                    db.refresh_materialized_view(connection, db.alternative_dns)
                logger.info("Forcing reload of DHCP hosts, NAS clients and "
                            "alternative DNS clients")
                reload_dhcp_host = True
                reload_nas = True
                reload_alternative_dns = True
                hosts = db.get_all_dhcp_hosts(connection)
                clients = db.get_all_nas_clients(connection)
                ips = db.get_all_alternative_dns_ips(connection)
            else:
                dhcphost_diff = db.refresh_and_diff_materialized_view(
                    connection, db.dhcphost, db.temp_dhcphost, [null()])
                if dhcphost_diff != ([], [], []):
                    logger.info('DHCP host reservations changed '
                                '(%d added, %d deleted, %d modified).',
                                *map(len, dhcphost_diff))
                    hosts = db.get_all_dhcp_hosts(connection)
                    reload_dhcp_host = True
                else:
                    reload_dhcp_host = False

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

        if reload_dhcp_host:
            generate_dhcp_hosts_file(hosts)
            reload_systemd_unit(self.bus, 'hades-auth-dhcp.service')
        if reload_nas:
            generate_radius_clients_file(clients)
            restart_systemd_unit(self.bus, 'hades-radius.service')
        if reload_alternative_dns:
            update_alternative_dns_ipset(ips)
        return "OK"

    def Cleanup(self):
        """
        Clean up old records in the radacct and radpostauth tables.
        :return: 
        """
        logger.info("Cleaning up old records")
        interval = self.config.HADES_RETENTION_INTERVAL
        with contextlib.closing(self.engine.connect()) as connection:
            db.delete_old_sessions(connection, interval)
            db.delete_old_auth_attempts(connection, interval)
        return "OK"


def run_event_loop():
    bus = SystemBus()
    logger.debug('Publishing interface %s on DBus', constants.DEPUTY_DBUS_NAME)
    config = get_config()
    bus.publish(constants.DEPUTY_DBUS_NAME, HadesDeputyService(bus, config))
    loop = GLib.MainLoop()
    loop.run()
