from gi.repository import Gio, GLib


class DBusError(Exception):
    def __init__(self, exc: GLib.Error):
        super().__init__(exc)


class DBusTimeout(DBusError):
    pass


def handle_glib_error(exc: GLib.Error):
    if (exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.TIMED_OUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.TIMED_OUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.TIMEOUT)
            or exc.matches(Gio.dbus_error_quark(), Gio.DBusError.NO_REPLY)):
        raise DBusTimeout(exc) from exc
    raise DBusError(exc) from exc
