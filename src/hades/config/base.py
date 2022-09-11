from __future__ import annotations
import functools
import logging
import os
import re
from typing import Any, Callable, Dict, Optional, Type, Union
from logging import Logger

from hades.common.util import qualified_name
from hades.common.exc import SetupError


logger = logging.getLogger(__name__)
option_name_regex = re.compile(r'\A[A-Z][A-Z0-9_]*\Z', re.ASCII)


def is_option_name(name: str) -> bool:
    """
    Check if a given object is a valid option name.

    Valid option names are restricted to ASCII, start with an uppercase letter
    followed by uppercase letters (A-Z), digits (0-9) or the underscore (_).

    :param name: Name
    :return: True, if name is string and a valid option name, False otherwise
    """
    return isinstance(name, str) and option_name_regex.match(name)


def option_reference(option: Union[Type[Option], str]):
    option = coerce(option)
    return ":hades:option:`{}`".format(option)


# noinspection PyUnresolvedReferences
class OptionMeta(type):
    """
    Metaclass for options.

    Classes with this metaclass, which are named not declared abstract by
    setting the abstract keyword argument are added to the :attr:`.options`
    dictionary.
    """
    options: Dict[str, Any] = {}
    option_cls: Optional[Type[Option]] = None

    # class variables of classes using this as a meta class
    default: Callable  # Can't type this properly due to circular import
    has_default: bool
    required: bool
    type: Optional[Type]
    runtime_check: Any
    static_check: Any

    def __new__(mcs, name, bases, attributes, abstract=False):
        if name in mcs.options:
            raise TypeError("option named {} already defined as {}."
                            .format(name, qualified_name(mcs.options[name])))
        if not abstract and not is_option_name(name):
            raise TypeError('not a valid option name')
        if not abstract and 'default' in attributes:
            attributes['has_default'] = True
        cls = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
        if mcs.option_cls is None:
            # noinspection PyTypeChecker
            mcs.option_cls = cls
        elif not issubclass(cls, mcs.option_cls):
            raise TypeError(
                f"{qualified_name(cls)} is not a subclass of "
                f"{qualified_name(mcs.option_cls)}"
            )
        if cls.has_default and cls.required:
            raise TypeError("required options can't have defaults")
        if not abstract:
            mcs.options[name] = cls
        return cls

    # noinspection PyUnusedLocal
    def __init__(cls, name, bases, attributes, abstract=False):
        super().__init__(name, bases, attributes)

    @classmethod
    def get_defaults(mcs):
        return {name: option.default
                for name, option in mcs.options.items()
                if option.has_default}

    @classmethod
    def check_config(mcs, config, runtime_checks=False):
        for name, option in mcs.options.items():
            if option.required and name not in config:
                raise MissingOptionError("Required option missing", option=name)
        for name, value in config.items():
            option = mcs.options.get(name)
            if option:
                option.check_option(config, value,
                                    runtime_checks=runtime_checks)

    def check_option(self, config, value, runtime_checks=False):
        if self.type is not None and not isinstance(value, self.type):
            expected = qualified_name(self.type)
            got = qualified_name(type(value))
            raise OptionCheckError("Must be a subtype of {}, was {}"
                                   .format(expected, got), option=self.__name__)
        if self.static_check:
            self.static_check(config, value)
        if runtime_checks and self.runtime_check:
            self.runtime_check(config, value)


class Option(object, metaclass=OptionMeta, abstract=True):
    has_default = False
    required = False
    default: Callable  # Can't type this properly due to circular import
    type: Optional[Type] = None
    runtime_check: Any = None
    static_check: Any = None


class ConfigError(SetupError):
    """Base class for all config related errors."""

    exit_code = os.EX_CONFIG

    def __init__(self, *a, **kw):
        self.logger = kw.get("logger", logger)
        super().__init__(*a, **kw)


class ConfigOptionError(ConfigError):
    """Base class for errors related to processing a specific option"""

    def __init__(self, *args, option: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.option = option

    def report_error(self, fallback_logger: Logger) -> None:
        logger = self.logger or fallback_logger
        logger.critical(
            "Configuration error with option %s: %s", self.option, self
        )


class MissingOptionError(ConfigOptionError):
    """Indicates that a required option is missing"""


class OptionCheckError(ConfigOptionError):
    """Indicates that an option check failed"""


def coerce(value: Union[Type[Option], str]) -> str:
    if isinstance(value, type) and issubclass(value, Option):
        return value.__name__
    elif isinstance(value, str):
        return value
    else:
        raise TypeError(
            f"value must be a string or an Option class, not {value!r}"
        )


class OptionDescriptor:
    @classmethod
    def decorate(cls: Type[OptionDescriptor], f):
        """
        Convert regular functions into an :class:`OptionDescriptor`.

        The function will be called with the option as its first argument.

        Functions are automatically decorated with :class:`classmethod`, if they
        are not already an instance of :class:`classmethod` or
        :class:`staticmethod`.

        :param f: The function
        """
        # Ensure that we have a static or class method
        if not isinstance(f, (classmethod, staticmethod)):
            m = classmethod(f)
        else:
            m = f  # type: ignore

        # noinspection PyPep8Naming
        @functools.wraps(f, updated=())
        class Wrapper(cls):  # type: ignore  # see #mypy/5865
            """Descriptor, that binds the given function in addition to an
            option"""
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.bound = None

            def __call__(self, *args, **kwargs):
                return self.bound(*args, **kwargs)

            def __get__(self, instance, owner):
                if self.option is None:
                    self.bound = m.__get__(instance, owner)
                return super().__get__(instance, owner)

        # Unfortunately `functools.wraps` is not sufficient, as `staticmethod`
        # and `classmethod` are not propagating the original `__doc__` until
        # Python 3.10.
        # See https://bugs.python.org/issue43682#msg390496.
        Wrapper.__doc__ = m.__func__.__doc__

        return Wrapper()

    def __init__(self):
        self.option = None

    def __get__(self, instance, owner):
        if self.option is None:
            self.option = owner
        return self


class Check(OptionDescriptor):
    """Base class for descriptors, that check the value of options"""

    def __call__(self, config, value):
        """Check the ``value`` of an option given ``config``.

        :param config: The fully expanded config
        :param value: The value of the Option
        :raises OptionCheckError: if the value of the option is illegal
        """
        raise NotImplementedError()


class Compute(OptionDescriptor):
    """Base class for descriptors, that compute the value of options."""

    def __call__(self, config):
        """Compute the value of the option using ``config``.

        :param config: An potentially not fully expanded config object
        :raises OptionCheckError: if the value can't be computed
        """
        raise NotImplementedError()
