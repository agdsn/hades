import logging

from gi.repository import GLib
from pydbus import SystemBus

from hades import constants
from hades.common.dbus import handle_glib_error

logger = logging.Logger(__name__)


def signal_refresh(timeout: int = 1) -> None:
    """
    Signal the deputy to perform a refresh.
    """
    logger.debug("Signaling refresh on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Refresh')
    try:
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy.Refresh(timeout=timeout)
    except GLib.Error as e:
        handle_glib_error(e)


def signal_cleanup(timeout: int = 1) -> None:
    logger.debug("Signaling cleanup on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Cleanup')
    try:
        bus = SystemBus()
        deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
        deputy.Cleanup(timeout=timeout)
    except GLib.Error as e:
        handle_glib_error(e)
