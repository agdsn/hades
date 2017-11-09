"""
Provides the client-side API for the deputy daemon.
"""
import logging

import netaddr
# noinspection PyPackageRequirements
from gi.repository import GLib
from pydbus import SystemBus

from hades import constants
from hades.common.dbus import handle_glib_error

logger = logging.Logger(__name__)


def signal_refresh(timeout: int = 1) -> None:
    """Signal the deputy to perform a refresh."""
    logger.debug("Signaling refresh on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Refresh')
    try:
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.Refresh(timeout=timeout)
    except GLib.Error as e:
        handle_glib_error(e)


def signal_cleanup(timeout: int = 1) -> None:
    """Signal the deputy to perform a cleanup."""
    logger.debug("Signaling cleanup on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Cleanup')
    try:
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.Cleanup(timeout=timeout)
    except GLib.Error as e:
        handle_glib_error(e)


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
    try:
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy_interface = deputy[constants.DEPUTY_DBUS_NAME]
        deputy_interface.ReleaseAuthDhcpLease(str(client_ip), timeout=timeout)
    except GLib.Error as e:
        handle_glib_error(e)
