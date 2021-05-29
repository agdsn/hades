"""
Checks for configuration option values
"""
import collections
import grp
import os
import pwd
import re
import socket
import textwrap
from typing import Sequence, Type, Union

import netaddr
from pyroute2.iproute import IPRoute

from hades.config.base import (
    Check, ConfigOptionError, OptionCheckError, coerce, option_reference,
)


class greater_than(Check):
    def __init__(self, threshold):
        super().__init__()
        self.threshold = threshold
        self.__doc__ = "Must be greater than :python:`{!r}`".format(threshold)

    def __call__(self, config, value):
        if value <= self.threshold:
            raise OptionCheckError("Must be greater than {!r}"
                                   .format(self.threshold),
                                   option=self.option.__name__)


class between(Check):
    def __init__(self, low, high):
        super().__init__()
        self.low = low
        self.high = high
        self.__doc__ = (
            "Must be between :python:`{!r}` and :python:`{!r}` inclusively"
            .format(low, high)
        )

    def __call__(self, config, value):
        if not (self.low <= value <= self.high):
            raise OptionCheckError("Must be between {!r} and {!r} inclusively"
                                   .format(self.low, self.high),
                                   option=self.option.__name__)


class match(Check):
    def __init__(self, expr, flags=0):
        super().__init__()
        self.expr = re.compile(expr, flags)
        self.__doc__ = "Must match regular expression: :python:`{!r}`".format(
            self.expr.pattern,
        )

    def __call__(self, config, value):
        if not self.expr.match(value):
            raise OptionCheckError("Does not match regular expression {!r}"
                                   .format(self.expr.pattern),
                                   option=self.option.name)


class sequence(Check):
    def __init__(self, element_check: Check):
        super().__init__()
        self.element_check = element_check
        self.__doc__ = "All elements must satisfy: {}".format(
            element_check.__doc__,
        )

    def __get__(self, instance, owner):
        if self.option is None:
            self.element_check = self.element_check.__get__(instance, owner)
        return super().__get__(instance, owner)

    def __call__(self, config, value):
        for i, v in enumerate(value):
            try:
                self.element_check(config, v)
            except ConfigOptionError as e:
                raise OptionCheckError("Error at index {:d}: {}"
                                       .format(i, e.args[0]),
                                       option=self.option.__name__)


class mapping(Check):
    def __init__(self, key_check: Check = None, value_check: Check = None):
        super().__init__()
        if key_check is None and value_check is None:
            raise ValueError()
        self.key_check = key_check
        self.value_check = value_check
        s = []
        if self.key_check is not None:
            s.append("All keys must satisfy: {}"
                     .format(self.key_check.__doc__))
        if self.value_check is not None:
            s.append("All values must satisfy: {}"
                     .format(self.value_check.__doc__))
        if self.key_check is not None and self.value_check is not None:
            self.__doc__ = textwrap.indent("\n".join(s), "- ")
        else:
            self.__doc__ = s[0]

    def __get__(self, instance, owner):
        if self.option is None:
            if self.key_check is not None:
                self.key_check = self.key_check.__get__(instance, owner)
            if self.value_check is not None:
                self.value_check = self.value_check.__get__(instance, owner)
        return super().__get__(instance, owner)

    def __call__(self, config, value):
        for k, v in value.items():
            try:
                if self.key_check is not None:
                    self.key_check(config, k)
                if self.value_check is not None:
                    self.value_check(config, v)
            except ConfigOptionError as e:
                raise OptionCheckError("Error in key {}: {}"
                                       .format(k, e.args[0]),
                                       option=self.option.__name__)


class type_is(Check):
    def __init__(self, types: Union[Type, Sequence[Type]]):
        super().__init__()
        if isinstance(types, collections.Sequence):
            self.types = tuple(types)
        else:
            self.types = (types,)
        if len(self.types) > 1:
            self.__doc__ = "Type must be one of {}".format(", ".join(
                ":class:`{}`".format(type_.__qualname__)
                for type_ in self.types
            ))
        else:
            self.__doc__ = "Type must be :class:`{}`".format(
                self.types[0].__qualname__
            )

    def __call__(self, config, value):
        if not isinstance(value, self.types):
            raise OptionCheckError("Must be an instance of {}"
                                   .format(', '.join([type_.__qualname__ for type_ in self.types])),
                                   option=self.option.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def not_empty(option, config, value):
    """Must not be empty"""
    if len(value) <= 0:
        raise OptionCheckError("Must not be empty", option=option.__name__)


class satisfy_all(Check):
    def __init__(self, *checks: Check):
        super().__init__()
        self.checks = checks
        self.__doc__ = "Must satisfy all of the following:\n\n{}".format(
            textwrap.indent("\n".join([c.__doc__ for c in checks]), "- "),
        )

    def __get__(self, instance, owner):
        if self.option is None:
            self.checks = [check.__get__(instance, owner)
                           for check in self.checks]
        return super().__get__(instance, owner)

    def __call__(self, config, value):
        for check in self.checks:
            check(config, value)


# noinspection PyDecorator,PyUnusedLocal
@Check.decorate
def network_ip(option, config, value):
    """Must not be network or broadcast address (except if /31)"""
    if value.ip == value.value:
        raise OptionCheckError("The host part of {} is the network address of "
                               "the subnet. Must be an IP of the subnet."
                               .format(value), option=option.__name__)
    # Prefix length 31 is special, see RFC 3021
    if value.prefixlen != 31 and value.ip == value.broadcast:
        raise OptionCheckError("The host part of {} is the broadcast address "
                               "of the subnet. Must be an IP of the subnet."
                               .format(value), option=option.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def directory_exists(cls, config, value):
    """Must be an existing directory"""
    if not os.path.exists(value):
        raise OptionCheckError("Directory {} does not exists".format(value),
                               option=cls.__name__)
    if not os.path.isdir(value):
        raise OptionCheckError("{} is not a directory".format(value),
                               option=cls.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def file_exists(cls, config, value):
    """Must be an existing file"""
    if not os.path.exists(value):
        raise OptionCheckError("File {} does not exists".format(value),
                               option=cls.__name__)
    if not os.path.isfile(value):
        raise OptionCheckError("{} is not a file".format(value),
                               option=cls.__name__)


@Check.decorate
def file_creatable(option, config, value):
    """Must be a creatable file name"""
    parent = os.path.dirname(value)
    directory_exists(option, config, parent)


# noinspection PyUnusedLocal
@Check.decorate
def interface_exists(option, config, value):
    """Network interface must exists"""
    try:
        socket.if_nametoindex(value)
    except OSError:
        raise OptionCheckError("Interface {} not found".format(value),
                               option=option.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def address_exists(cls, config, value):
    """IP address must be configured"""
    ip = IPRoute()
    if value.version == 4:
        family = socket.AF_INET
    elif value.version == 6:
        family = socket.AF_INET6
    else:
        raise AssertionError("Unknown version {}".format(value.version))
    if ip.get_addr(family=family, address=value.ip, prefixlen=value.prefixlen):
        raise OptionCheckError("No such address {}".format(value),
                               option=cls.__name__)


class ip_range_in_networks(Check):
    def __init__(self, other_option):
        super().__init__()
        self.other_option = coerce(other_option)
        self.__doc__ = (
            "Must be contained in the networks configured with {}"
            .format(option_reference(self.other_option))
        )

    def __call__(self, config, value):
        networks = config[self.other_option]
        first = netaddr.IPAddress(value.first)
        last = netaddr.IPAddress(value.last)
        contained = any(first in network and last in network
                        for network in networks)
        if not contained:
            raise OptionCheckError("Range not contained in any of the "
                                   "networks {}"
                                   .format(', '.join(networks)),
                                   option=self.option.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def user_exists(option, config, value):
    """Must be a valid UNIX user"""
    try:
        return pwd.getpwnam(value)
    except KeyError:
        raise OptionCheckError("User {} does not exists".format(value),
                               option=option.__name__)


# noinspection PyUnusedLocal
@Check.decorate
def group_exists(option, config, value):
    """Must be a valid UNIX group"""
    try:
        return grp.getgrnam(value)
    except KeyError:
        raise OptionCheckError("Group {} does not exists".format(value),
                               option=option.__name__)


class has_keys(Check):
    def __init__(self, *keys):
        super().__init__()
        self.keys = keys
        self.__doc__ = "Must contain {}".format(
            " -> ".join("{!r}".format(key) for key in self.keys),
        )

    def __call__(self, config, value):
        obj = value
        checked = []

        for key in self.keys:
            if not isinstance(obj, collections.Mapping):
                path = ''.join(map('[{!r}]'.format, checked))
                raise OptionCheckError("must be a mapping type like dict"
                                       option=self.option.name + path)
            checked.append(key)
            try:
                obj = obj[key]
            except KeyError:
                path = ''.join(map('[{!r}]'.format, checked))
                raise OptionCheckError("Missing key",
                                       option=self.option.name + path) from None


class user_mapping_for_user_exists(Check):
    def __init__(self, user_name):
        super().__init__()
        self.user_name = user_name
        self.__doc__ = "Must have contain a mapping for {} or PUBLIC".format(
            self.user_name,
        )

    def __call__(self, config, value):
        if 'PUBLIC' not in value and self.user_name not in value:
            raise OptionCheckError("No mapping for user {}"
                                   .format(self.user_name),
                                   option=self.option.__name__)
