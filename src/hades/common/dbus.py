# noinspection PyPackageRequirements
from gi.repository import Gio, GLib


class DBusError(Exception):
    """Indicates an error during a DBus operation."""
    def __init__(self, exc: GLib.Error):
        super().__init__(exc)


class DBusTimeout(DBusError):
    """Indicates a timeout during a DBus operation."""
    pass


def handle_glib_error(exc: GLib.Error):
    """Convert :class:`GLib.Error` exceptions into :exc:`DBusError`.

    If the error code indicates a timeout, return the specialized
    :exc:`DBusTimeout`. The original :class:`GLib.Error` is set as the cause of
    the new exception."""
    if (exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.TIMED_OUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.TIMEOUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.NO_REPLY)):
        raise DBusTimeout(exc) from exc
    raise DBusError(exc) from exc
