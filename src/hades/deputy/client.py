import logging

from pydbus import SystemBus

from hades import constants

logger = logging.Logger(__name__)


def signal_refresh():
    """
    Signal the deputy to perform a refresh.
    """
    logger.debug("Signaling refresh on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Refresh')
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME)
    deputy.Refresh()


def signal_cleanup():
    logger.debug("Signaling cleanup on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Cleanup')
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME)
    deputy.Cleanup()
