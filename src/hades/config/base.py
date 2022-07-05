import functools
import re
from typing import Any, Dict

option_name_regex = re.compile(r'\A[A-Z][A-Z0-9_]*\Z', re.ASCII)


def is_option_name(name):
    """
    Check if a given object is a valid option name.

    Valid option names are restricted to ASCII, start with an uppercase letter
    followed by uppercase letters (A-Z), digits (0-9) or the underscore (_).

    :param name: Name
    :return: True, if name is string and a valid option name, False otherwise
    :rtype: bool
    """
    return isinstance(name, str) and option_name_regex.match(name)


def qualified_name(type_):
    if type_.__module__ is None or type_.__module__ == 'builtins':
        return type_.__qualname__
    else:
        return type_.__module__ + '.' + type_.__qualname__


def option_reference(option):
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

    def __new__(mcs, name, bases, attributes, abstract=False):
        if name in mcs.options:
            raise TypeError("option named {} already defined as {}."
                            .format(name, qualified_name(mcs.options[name])))
        if not abstract and not is_option_name(name):
            raise TypeError('not a valid option name')
        if not abstract and 'default' in attributes:
            attributes['has_default'] = True
        cls = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
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
    default: Any = None
    type: Any = None
    runtime_check: Any = None
    static_check: Any = None


class ConfigError(Exception):
    """Base class for all config related errors."""


class ConfigOptionError(ConfigError):
    """Base class for errors related to processing a specific option"""
    def __init__(self, *args, option: str):
        super(ConfigOptionError, self).__init__(*args)
        self.option = option


class MissingOptionError(ConfigOptionError):
    """Indicates that a required option is missing"""


class OptionCheckError(ConfigOptionError):
    """Indicates that an option check failed"""


def coerce(value):
    if isinstance(value, type) and issubclass(value, Option):
        return value.__name__
    else:
        return value


class OptionDescriptor:
    @classmethod
    def decorate(cls, f):
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
            m = f
        # unfortunately, `functools.wraps` does not help us here since we're wrapping a staticmethod/classmethod;
        # it only propagates `classmethod.__doc__`.
        # We're unwrapping the classmethod descriptor to force the actual __doc__ onto what we return.
        # In python3.10, this workaround will be obsolete,
        # as staticmethod/classmethod will propagate `__doc__` themselves.
        # See https://bugs.python.org/issue43682#msg390496.
        inner_doc = m.__get__(None, object).__doc__

        @functools.wraps(f, updated=())
        class wrapper(cls):
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

        descriptor = wrapper()
        if inner_doc:
            descriptor.__doc__ = inner_doc
        return descriptor

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
        raise NotImplemented()


class Compute(OptionDescriptor):
    """Base class for descriptors, that compute the value of options."""

    def __call__(self, config):
        """Compute the value of the option using ``config``.

        :param config: An potentially not fully expanded config object
        :raises OptionCheckError: if the value can't be computed
        """
        raise NotImplemented()
