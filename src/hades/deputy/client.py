"""
Provides the client-side API for the deputy daemon.
"""
import logging

import netaddr
from pydbus import SystemBus

from hades import constants
from hades.common.glib import typed_glib_error

logger = logging.getLogger(__name__)


def signal_refresh(timeout: int = 1) -> None:
    """Signal the deputy to perform a refresh."""
    logger.debug("Signaling refresh on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Refresh')
    with typed_glib_error():
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.Refresh(timeout=timeout)


def signal_cleanup(timeout: int = 1) -> None:
    """Signal the deputy to perform a cleanup."""
    logger.debug("Signaling cleanup on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Cleanup')
    with typed_glib_error():
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.Cleanup(timeout=timeout)


def signal_auth_dhcp_lease_release(
    client_ip: netaddr.IPAddress,
    timeout: int = 1,
) -> None:
    """
    Signal the deputy to release a auth DHCP lease.
    """
    logger.debug(
        "Signaling auth DHCP lease release for IP %s on DBus: %s.%s",
        client_ip,
        constants.DEPUTY_DBUS_NAME,
        "Refresh",
    )
    with typed_glib_error():
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.ReleaseAuthDhcpLease(str(client_ip), timeout=timeout)


def signal_unauth_dhcp_lease_release(
    client_ip: netaddr.IPAddress,
    timeout: int = 1,
) -> None:
    """
    Signal the deputy to release a auth DHCP lease.
    """
    logger.debug(
        "Signaling unauth DHCP lease release for IP %s on DBus: %s.%s",
        client_ip,
        constants.DEPUTY_DBUS_NAME,
        "Refresh",
    )
    with typed_glib_error():
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.ReleaseUnauthDhcpLease(str(client_ip), timeout=timeout)
