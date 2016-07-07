import collections
import grp
import os
import pwd
import socket

import netaddr
from pyroute2.iproute import IPRoute

from hades.config.base import ConfigError


class OptionCheckError(ConfigError):
    pass


def qualified_name(type_):
    if type_.__module__ is None or type_.__module__ == 'builtins':
        return type_.__qualname__
    else:
        return type_.__module__ + '.' + type_.__qualname__


def check_option(config, option, value, runtime_checks=False):
    name = option.__name__
    if option.type is not None and not isinstance(value, option.type):
        expected = qualified_name(option.type)
        got = qualified_name(type(value))
        raise OptionCheckError("Must be a subtype of {}, was {}"
                               .format(expected, got), option=name)
    if option.static_check:
        option.static_check(config, name, value)
    if runtime_checks and option.runtime_check:
        option.runtime_check(config, name, value)


def greater_than(threshold):
    def checker(config, name, value):
        if value <= threshold:
            raise OptionCheckError("Must be greater than {}".format(threshold),
                                   option=name)
    return checker


def between(low, high):
    def checker(config, name, value):
        if not (low <= value <= high):
            raise OptionCheckError("Must be between {} and {} inclusively"
                                   .format(low, high), option=name)
    return checker


def mapping(key_check=None, value_check=None):
    def f(config, name, value):
        for k, v in value.items():
            try:
                if key_check is not None:
                    key_check(config, name, k)
                if value_check is not None:
                    value_check(config, name, v)
            except ConfigError as e:
                raise OptionCheckError("Error in key {}: {}"
                                       .format(k, e.args[0]), option=name)
    return f


def type_is(types):
    def f(config, name, value):
        if not isinstance(value, types):
            raise OptionCheckError("Must be an instance of {}"
                                   .format(', '.join(types)), option=name)
    return f


def not_empty(config, name, value):
    if len(value) <= 0:
        raise OptionCheckError("Must not be empty", option=name)


def all(*checks):
    def f(config, name, value):
        for check in checks:
            check(config, name, value)
    return f


def network_ip(config, name, value):
    if value.ip == value.value:
        raise OptionCheckError("The host part of {} is the network address of "
                               "the subnet. Must be an IP of the subnet."
                               .format(value), option=name)
    # Prefix length 31 is special, see RFC 3021
    if value.prefixlen != 31 and value.ip == value.broadcast:
        raise OptionCheckError("The host part of {} is the broadcast address "
                               "of the subnet. Must be an IP of the subnet."
                               .format(value), option=name)


def directory_exists(config, name, value):
    if not os.path.exists(value):
        raise OptionCheckError("Directory {} does not exists".format(value),
                               option=name)
    if not os.path.isdir(value):
        raise OptionCheckError("{} is not a directory".format(value),
                               option=name)


def file_exists(config, name, value):
    if not os.path.exists(value):
        raise OptionCheckError("File {} does not exists".format(value),
                               option=name)
    if not os.path.isfile(value):
        raise OptionCheckError("{} is not a file".format(value), option=name)


def file_creatable(config, name, value):
    parent = os.path.dirname(value)
    directory_exists(config, name, parent)


def interface_exists(config, name, value):
    try:
        socket.if_nametoindex(value)
    except OSError:
        raise OptionCheckError("Interface {} not found".format(value),
                               option=name)


def address_exists(config, name, value):
    ip = IPRoute()
    if value.version == 4:
        family = socket.AF_INET
    elif value.version == 6:
        family = socket.AF_INET6
    else:
        raise AssertionError("Unknown version {}".format(value.version))
    if ip.get_addr(family=family, address=value.ip, prefixlen=value.prefixlen):
        raise OptionCheckError("No such address {}".format(value), option=name)


def ip_range_in_network(network_config):
    def checker(config, name, value):
        network = config[network_config]
        first = netaddr.IPAddress(value.first)
        last = netaddr.IPAddress(value.last)
        if first not in network or last not in network:
            raise OptionCheckError("Range not contained in network {}"
                                   .format(network), option=name)
    return checker


def user_exists(config, name, value):
    try:
        return pwd.getpwnam(value)
    except KeyError:
        raise OptionCheckError("User {} does not exists".format(value),
                               option=name)


def group_exists(config, name, value):
    try:
        return grp.getgrnam(value)
    except KeyError:
        raise OptionCheckError("Group {} does not exists".format(value),
                               option=name)


def has_key(name, value, *keys):
    obj = value
    path = []
    for key in keys:
        if not isinstance(obj, collections.Mapping):
            raise OptionCheckError("{} is not a Mapping type"
                                   .format('->'.join(path)), option=name)
        path.append(key)
        try:
            obj = obj.get(key)
        except KeyError:
            raise OptionCheckError("Missing key {}".format('->'.join(path)),
                                   option=name)


def user_mapping_for_user_exists(user_option_name):
    def checker(config, name, value):
        user_name = config[user_option_name]
        if 'PUBLIC' in config[user_option_name]:
            return
        if user_name not in value:
            raise OptionCheckError("No mapping for user {} defined in option {}"
                                   .format(user_name, user_option_name),
                                   option=name)
    return checker
