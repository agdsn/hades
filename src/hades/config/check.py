import collections
import grp
import os
import pwd
import socket

import netaddr
from pyroute2.iproute import IPRoute


class ConfigError(Exception):
    def __init__(self, name, *args, **kwargs):
        super(ConfigError, self).__init__(*args, **kwargs)
        self.name = name

    def __str__(self):
        return "{}: {}".format(self.name, super(ConfigError, self).__str__())


def check_option(config, option, value, runtime_checks=False):
    name = option.__name__
    if option.type is not None and not isinstance(value, option.type):
        got = type(value).__name__
        if option.type.__module__ == 'builtins':
            expected = option.type.__name__
        else:
            expected = option.type.__module__ + '.' + option.type.__name__
        raise ConfigError(name, "Must be a subtype of {}, was {}"
                          .format(expected, got))
    if option.static_check:
        option.static_check(config, name, value)
    if runtime_checks and option.runtime_check:
        option.runtime_check(config, name, value)


def greater_than(threshold):
    def checker(config, name, value):
        if value <= threshold:
            raise ConfigError(name, "Must be greater than {}".format(threshold))
    return checker


def between(low, high):
    def checker(config, name, value):
        if not (low <= value <= high):
            raise ConfigError(name, "Must be between {} and {} inclusively"
                              .format(low, high))
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
                raise ConfigError(name, "Error in key {}: {}"
                                  .format(k, e.args[0]))
    return f


def type_is(types):
    def f(config, name, value):
        if not isinstance(value, types):
            raise ConfigError(name, "Must be an instance of {}"
                              .format(', '.join(types)))
    return f


def not_empty(config, name, value):
    if len(value) <= 0:
        raise ConfigError(name, "Must not be empty")


def all(*checks):
    def f(config, name, value):
        for check in checks:
            check(config, name, value)
    return f


def network_ip(config, name, value):
    if value.ip == value.value:
        raise ConfigError(name, "The host part of {} is the network "
                                "address of the subnet. Must be an IP of the "
                                "subnet."
                          .format(value))
    # Prefix length 31 is special, see RFC 3021
    if value.prefixlen != 31 and value.ip == value.broadcast:
        raise ConfigError(name, "The host part of {} is the broadcast "
                                "address of the subnet. Must be an IP of the "
                                "subnet."
                          .format(value))


def directory_exists(config, name, value):
    if not os.path.exists(value):
        raise ConfigError(name, "Directory {} does not exists".format(value))
    if not os.path.isdir(value):
        raise ConfigError(name, "{} is not a directory".format(value))


def file_exists(config, name, value):
    if not os.path.exists(value):
        raise ConfigError(name, "File {} does not exists".format(value))
    if not os.path.isfile(value):
        raise ConfigError(name, "{} is not a file".format(value))


def file_creatable(config, name, value):
    parent = os.path.dirname(value)
    directory_exists(config, name, parent)


def interface_exists(config, name, value):
    try:
        socket.if_nametoindex(value)
    except OSError:
        raise ConfigError(name, "Interface {} not found".format(value))


def address_exists(config, name, value):
    ip = IPRoute()
    if value.version == 4:
        family = socket.AF_INET
    elif value.version == 6:
        family = socket.AF_INET6
    else:
        raise AssertionError("Unknown version {}".format(value.version))
    if ip.get_addr(family=family, address=value.ip, prefixlen=value.prefixlen):
        raise ConfigError(name, "No such address {}".format(value))


def ip_range_in_network(network_config):
    def checker(config, name, value):
        network = config[network_config]
        first = netaddr.IPAddress(value.first)
        last = netaddr.IPAddress(value.last)
        if first not in network or last not in network:
            raise ConfigError(name, "Range not contained in network {}"
                              .format(network))
    return checker


def user_exists(config, name, value):
    try:
        return pwd.getpwnam(value)
    except KeyError:
        raise ConfigError(name, "User {} does not exists".format(value))


def group_exists(config, name, value):
    try:
        return grp.getgrnam(value)
    except KeyError:
        raise ConfigError(name, "Group {} does not exists".format(value))


def has_key(name, value, *keys):
    obj = value
    path = []
    for key in keys:
        if not isinstance(obj, collections.Mapping):
            raise ConfigError(name, "{} is not a Mapping type"
                              .format('->'.join(path)))
        path.append(key)
        try:
            obj = obj.get(key)
        except KeyError:
            raise ConfigError(name, "Missing key {}".format('->'.join(path)))


def user_mapping_for_user_exists(user_option_name):
    def checker(config, name, value):
        user_name = config[user_option_name]
        if 'PUBLIC' in config[user_option_name]:
            return
        if user_name not in value:
            raise ConfigError(name, "No mapping for user {} defined in "
                                    "option {}"
                              .format(user_name, user_option_name))
    return checker
