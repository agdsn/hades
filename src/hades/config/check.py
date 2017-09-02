import collections
import grp
import os
import pwd
import socket

import netaddr
from pyroute2.iproute import IPRoute

from hades.config.base import ConfigError, OptionCheckError, coerce


def greater_than(threshold):
    # noinspection PyDecorator,PyUnusedLocal
    @classmethod
    def checker(cls, config, value):
        if value <= threshold:
            raise OptionCheckError("Must be greater than {}".format(threshold),
                                   option=cls.__name__)
    return checker


def between(low, high):
    # noinspection PyDecorator,PyUnusedLocal
    @classmethod
    def checker(cls, config, value):
        if not (low <= value <= high):
            raise OptionCheckError("Must be between {} and {} inclusively"
                                   .format(low, high), option=cls.__name__)
    return checker


def sequence(element_check):
    # noinspection PyDecorator
    @classmethod
    def f(cls, config, value):
        for i, v in enumerate(value):
            try:
                element_check.__get__(None, cls)(config, v)
            except ConfigError as e:
                raise OptionCheckError("Error at index {:d}: {}"
                                       .format(i, e.args[0]),
                                       option=cls.__name__)
    return f


def mapping(key_check=None, value_check=None):
    # noinspection PyDecorator
    @classmethod
    def f(cls, config, value):
        for k, v in value.items():
            try:
                if key_check is not None:
                    key_check.__get__(None, cls)(config, k)
                if value_check is not None:
                    value_check.__get__(None, cls)(config, v)
            except ConfigError as e:
                raise OptionCheckError("Error in key {}: {}"
                                       .format(k, e.args[0]),
                                       option=cls.__name__)
    return f


def type_is(types):
    # noinspection PyDecorator,PyUnusedLocal
    @classmethod
    def f(cls, config, value):
        if not isinstance(value, types):
            raise OptionCheckError("Must be an instance of {}"
                                   .format(', '.join(types)),
                                   option=cls.__name__)
    return f


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def not_empty(cls, config, value):
    if len(value) <= 0:
        raise OptionCheckError("Must not be empty", option=cls.__name__)


def satisfy_all(*checks):
    # noinspection PyDecorator
    @classmethod
    def f(cls, config, value):
        for check in checks:
            check.__get__(None, cls)(config, value)
    return f


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def network_ip(cls, config, value):
    if value.ip == value.value:
        raise OptionCheckError("The host part of {} is the network address of "
                               "the subnet. Must be an IP of the subnet."
                               .format(value), option=cls.__name__)
    # Prefix length 31 is special, see RFC 3021
    if value.prefixlen != 31 and value.ip == value.broadcast:
        raise OptionCheckError("The host part of {} is the broadcast address "
                               "of the subnet. Must be an IP of the subnet."
                               .format(value), option=cls.__name__)


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def directory_exists(cls, config, value):
    if not os.path.exists(value):
        raise OptionCheckError("Directory {} does not exists".format(value),
                               option=cls.__name__)
    if not os.path.isdir(value):
        raise OptionCheckError("{} is not a directory".format(value),
                               option=cls.__name__)


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def file_exists(cls, config, value):
    if not os.path.exists(value):
        raise OptionCheckError("File {} does not exists".format(value),
                               option=cls.__name__)
    if not os.path.isfile(value):
        raise OptionCheckError("{} is not a file".format(value),
                               option=cls.__name__)


# noinspection PyDecorator
@classmethod
def file_creatable(cls, config, value):
    parent = os.path.dirname(value)
    directory_exists.__get__(None, cls)(config, parent)


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def interface_exists(cls, config, value):
    try:
        socket.if_nametoindex(value)
    except OSError:
        raise OptionCheckError("Interface {} not found".format(value),
                               option=cls.__name__)


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def address_exists(cls, config, value):
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


def ip_range_in_networks(other_option):
    other_option = coerce(other_option)

    # noinspection PyDecorator
    @classmethod
    def checker(cls, config, value):
        networks = config[other_option]
        first = netaddr.IPAddress(value.first)
        last = netaddr.IPAddress(value.last)
        contained = any(first in network and last in network
                        for network in networks)
        if not contained:
            raise OptionCheckError("Range not contained in any of the "
                                   "networks {}"
                                   .format(', '.join(networks)),
                                   option=cls.__name__)
    return checker


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def user_exists(cls, config, value):
    try:
        return pwd.getpwnam(value)
    except KeyError:
        raise OptionCheckError("User {} does not exists".format(value),
                               option=cls.__name__)


# noinspection PyDecorator,PyUnusedLocal
@classmethod
def group_exists(cls, config, value):
    try:
        return grp.getgrnam(value)
    except KeyError:
        raise OptionCheckError("Group {} does not exists".format(value),
                               option=cls.__name__)


def has_keys(*keys):
    # noinspection PyDecorator,PyUnusedLocal
    @classmethod
    def f(cls, config, value):
        obj = value
        checked = []

        for key in keys:
            if not isinstance(obj, collections.Mapping):
                path = cls.__name__ + ''.join(map('[{!r}]'.format, checked))
                raise OptionCheckError("must be a mapping type like dict",
                                       option=path)
            checked.append(key)
            try:
                obj = obj[key]
            except KeyError:
                path = cls.__name__ + ''.join(map('[{!r}]'.format, checked))
                raise OptionCheckError("Missing key", option=path) from None
    return f


def user_mapping_for_user_exists(user_name):

    # noinspection PyDecorator
    @classmethod
    def checker(cls, config, value):
        if 'PUBLIC' not in value and user_name not in value:
            raise OptionCheckError("No mapping for user {}".format(user_name),
                                   option=cls.__name__)
    return checker
