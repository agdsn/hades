import logging
import os
import signal

import netaddr

from hades.config.loader import CheckWrapper, get_config

logger = logging.getLogger(__name__)
config = CheckWrapper(get_config())


def reload_auth_dnsmasq():
    pid_file = config['HADES_AUTH_DNSMASQ_PID_FILE']
    try:
        with open(pid_file) as f:
            pid = int(f.readline())
            if pid < 1:
                raise ValueError("PID must be > 0: %d", pid)
    except OSError as e:
        logger.error("Could not read PID file %s: %s", pid_file, e.strerror)
        return
    except (ValueError, OverflowError) as e:
        logger.error("Could not convert into PID: %s", str(e))
        return
    try:
        os.kill(pid, signal.SIGHUP)
    except OSError as e:
        logger.error("Can't send SIGHUP to pid %d: %s", pid, e.strerror)


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
