import logging

from pydbus import SystemBus

from hades import constants

logger = logging.Logger(__name__)


def signal_refresh(timeout: int = 1) -> None:
    """
    Signal the deputy to perform a refresh.
    """
    logger.debug("Signaling refresh on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Refresh')
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
    deputy.Refresh(timeout=timeout)


def signal_cleanup(timeout: int = 1) -> None:
    logger.debug("Signaling cleanup on DBus: %s.%s",
                 constants.DEPUTY_DBUS_NAME, 'Cleanup')
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME, timeout=timeout)
    deputy.Cleanup(timeout=timeout)
