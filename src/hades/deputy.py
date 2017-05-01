import contextlib
import getpass
import grp
import io
import logging
import os
import pwd
import string
import subprocess
from functools import partial

import netaddr
import pkg_resources
from gi.repository import GLib
from pydbus import SystemBus

from hades import constants
from hades.common import db
from hades.config.loader import get_config

logger = logging.getLogger(__name__)
database_pwd = pwd.getpwnam(constants.DATABASE_USER)
database_grp = grp.getgrnam(constants.DATABASE_GROUP)


@contextlib.contextmanager
def dropped_privileges(passwd, group):
    logger.debug("Dropping privileges temporary to user %s and group",
                 passwd.pw_name, group.gr_name)
    # To handle multiple users with the same UID correctly, we obtain the
    # current user name with getpass
    saved_user = getpass.getuser()
    saved_uid = os.geteuid()
    saved_gid = os.getegid()
    os.setresgid(group.gr_gid, group.gr_gid, saved_gid)
    os.initgroups(passwd.pw_name, group.gr_gid)
    os.setresuid(passwd.pw_uid, passwd.pw_uid, saved_uid)
    yield
    os.seteuid(saved_uid)
    os.setreuid(saved_uid, saved_uid)
    os.setregid(saved_gid, saved_gid)
    os.initgroups(saved_user, saved_gid)
    logger.debug("Restoring previous privileges as user %s", saved_user)


def reload_systemd_unit(bus, unit):
    logger.debug("Instructing systemd to reload unit %s", unit)
    systemd = bus.get('org.freedesktop.systemd1')
    systemd.ReloadUnit(unit, 'fail')


def generate_dhcp_host_reservations(hosts):
    for mac, ip in hosts:
        try:
            mac = netaddr.EUI(mac, dialect=netaddr.mac_unix_expanded)
        except netaddr.AddrFormatError:
            logger.error("Invalid MAC address %s", mac)
            continue
        try:
            ip = netaddr.IPAddress(ip)
        except netaddr.AddrFormatError:
            logger.error("Invalid IP address %s", ip)
            continue
        yield "{0},{1}\n".format(mac, ip)


def generate_dhcp_hosts_file():
    file_name = constants.AUTH_DHCP_HOSTS_FILE
    logger.info("Generating DHCP hosts file %s", file_name)
    with dropped_privileges(database_pwd, database_grp):
        hosts = db.get_all_dhcp_hosts()
    try:
        with open(file_name, mode='w', encoding='ascii') as f:
            f.writelines(generate_dhcp_host_reservations(hosts))
    except OSError as e:
        logger.error("Error writing %s: %s", file_name, e.strerror)


def generate_ipset_swap(ipset_name, tmp_ipset_name, ips):
    yield 'create {} hash:ip -exist\n'.format(tmp_ipset_name)
    yield 'flush {}\n'.format(tmp_ipset_name)
    yield from map(partial('add {} {}\n'.format, tmp_ipset_name), ips)
    yield 'swap {} {}\n'.format(ipset_name, tmp_ipset_name)
    yield 'destroy {}\n'.format(tmp_ipset_name)


def update_alternative_dns_ipset():
    conf = get_config()
    ipset_name = conf['HADES_AUTH_DNS_ALTERNATIVE_IPSET']
    tmp_ipset_name = 'tmp_' + ipset_name
    with dropped_privileges(database_pwd, database_grp):
        ips = db.get_all_alternative_dns_ips()
    logger.info("Updating alternative_dns ipset (%s)", ipset_name)
    commands = io.TextIOWrapper(io.BytesIO(), 'ascii')
    commands.writelines(generate_ipset_swap(ipset_name, tmp_ipset_name, ips))
    commands.flush()
    subprocess.run(
        [constants.IP, 'netns', 'exec', 'auth', constants.IPSET, 'restore'],
        input=commands.buffer.getvalue())


def generate_radius_clients(clients):
    template = string.Template("""
    client $nasname {
        shortname = $shortname
        secret = $secret
        require_message_authenticator = no
        nastype = $type
        coa_server $nasname
    }
    home_server $nasname {
        type = coa
        coa {
            irt = 2
            mrt = 16
            mrc = 5
            mrd = 30
        }
    }
    """)
    for shortname, nasname, type, ports, secret, server, community, description in clients:
        yield template.substitute()


def generate_radius_clients_file():
    logger.info("Generating freeRADIUS clients configuration")
    with dropped_privileges(database_pwd, database_grp):
        clients = db.get_all_nas_clients()
    file_name = constants.RADIUS_CLIENTS_FILE
    try:
        with open(file_name, mode='w', encoding='ascii') as f:
            f.writelines(generate_radius_clients(clients))
    except OSError as e:
        logger.error("Error writing %s: %s", file_name, e.strerror)


class HadesDeputyService(object):
    dbus = pkg_resources.resource_string(
        __package__, 'deputy-interface.xml').decode('utf-8')

    def __init__(self, bus):
        self.bus = bus

    def ReloadAuthDhcpHosts(self):
        """
        Generate a new DHCP hosts file and reload the service.
        """
        generate_dhcp_hosts_file()
        reload_systemd_unit(self.bus, 'hades-auth-dhcp.service')

    def ReloadRadiusClients(self):
        """
        Generate a new RADIUS clients file and reload the service.
        """
        generate_radius_clients_file()
        reload_systemd_unit(self.bus, 'hades-radius.service')

    def ReloadAlternativeAuthDnsClients(self):
        """
        Reload the ipset for IP addresses, that which to use alternative DNS
        information. 
        """
        update_alternative_dns_ipset()


def run_event_loop():
    bus = SystemBus()
    logger.debug('Publishing interface %s on DBus', constants.DEPUTY_DBUS_NAME)
    bus.publish(constants.DEPUTY_DBUS_NAME, HadesDeputyService(bus))
    loop = GLib.MainLoop()
    loop.run()