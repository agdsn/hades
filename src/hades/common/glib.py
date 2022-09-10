from __future__ import annotations
# noinspection PyPackageRequirements
import contextlib
import sys
import typing

# noinspection PyUnresolvedReferences
from gi.repository import Gio, GLib

from hades.common.util import qualified_name


class TypedGLibError(Exception):
    """Base GLib exception"""
    domains: typing.Dict[int, typing.Type[TypedGLibError]] = {}
    codes: typing.Dict[Gio.DBusError, typing.Type[TypedGLibError]] = {}
    domain: int = None
    code: Gio.DBusError = None

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        domain = cls.domain
        if domain is None:
            raise TypeError("domain must be set")
        if cls.code is None:
            domain_cls = TypedGLibError.domains.setdefault(domain, cls)
            if domain_cls is not cls:
                raise TypeError(
                    f"Exception {qualified_name(domain_cls)} already "
                    f"registered for error domain {domain} "
                    f"({GLib.quark_to_string(cls.domain)})"
                )
        else:
            try:
                domain_cls = TypedGLibError.domains[domain]
            except KeyError:
                raise TypeError(
                    f"No base class registered for error domain {domain} "
                    f"({GLib.quark_to_string(cls.domain)})"
                )
            if domain_cls.codes.setdefault(cls.code, cls) is not cls:
                code_cls = domain_cls.codes[cls.code]
                raise TypeError(
                    f"Exception {qualified_name(code_cls)} already registered "
                    f"for error code {cls.code.value_name} of domain {domain} "
                    f"({GLib.quark_to_string(cls.domain)})"
                )

    @classmethod
    def from_exception(cls, exc: GLib.Error):
        """
        Convert untyped :class:`GLib.Error` exceptions into a proper exception
        hierarchy based on domain and code of the error.
        """
        subclass = cls.domains.get(exc.domain, TypedGLibError)
        typed_exc = subclass.from_code(exc).with_traceback(exc.__traceback__)
        return typed_exc

    @classmethod
    def from_code(cls, exc: GLib.Error):
        subclass = cls.codes.get(exc.code, cls)
        return subclass(exc)

    def __init__(self, exc: GLib.Error) -> None:
        super().__init__(exc.message)
        self.untyped = exc


class DBusError(TypedGLibError):
    """Indicates an error during a DBus operation."""
    domain = Gio.dbus_error_quark()


class DBusTimeout(Exception):
    """Indicates a timeout during a DBus operation."""
    pass


class DBusErrorTimedOut(DBusError, DBusTimeout):
    code = Gio.DBusError.TIMED_OUT


class DBusErrorTimeout(DBusError, DBusTimeout):
    code = Gio.DBusError.TIMEOUT


class DBusErrorNoReply(DBusError, DBusTimeout):
    code = Gio.DBusError.NO_REPLY


class DBusErrorServiceUnknown(DBusError):
    """The bus doesn't know how to launch a service to supply the bus name you
     wanted."""
    code = Gio.DBusError.SERVICE_UNKNOWN


class DBusErrorUnknownObject(DBusError):
    """Object you invoked a method on isn’t known."""
    code = Gio.DBusError.UNKNOWN_OBJECT


@contextlib.contextmanager
def typed_glib_error():
    try:
        yield
    except GLib.Error as e:
        # Inspired by trio's MultiErrorCatcher
        typed = TypedGLibError.from_exception(e)
        old_context = e.__context__
        try:
            raise typed
        finally:
            tp, val, tb = sys.exc_info()
            assert val is e
            val.__context__ = old_context
            # Remove any potential circular references
            # See https://cosmicpercolator.com/2016/01/13/exception-leaks-in-python-2-and-3/
            del e, tp, val, tb, typed, old_context
