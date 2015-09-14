import os
import socket
import grp
import pwd

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
        if option.type.__module__ == 'builtins':
            type_name = option.type.__name__
        else:
            type_name = option.type.__module__ + '.' + option.type
        raise ConfigError(name, "Must be of type {}".format(type_name))
    if option.static_check:
        option.static_check(config, name, value)
    if runtime_checks and option.runtime_check:
        option.runtime_check(config, name, value)


def greater_than(threshold):
    def checker(config, name, value):
        if value <= threshold:
            raise ConfigError(name, "Must be greater than {}".format(threshold))
    return checker


def gateway_network_dict(config, name, value):
    if not value:
        raise ConfigError(name, "No networks specified")

    for key, network in value.items():
        if not isinstance(key, str):
            raise ConfigError(name, "Keys must be strings")
        if not isinstance(network, netaddr.IPNetwork):
            raise ConfigError(name, "Values must be of type {}"
                              .format(netaddr.IPNetwork))
        if network.ip == network.network:
            raise ConfigError(name, "The host part of {} is the network "
                                    "address of the subnet. Must be the IP "
                                    "address of the default gateway"
                              .format(network))
        if network.ip == network.broadcast:
            raise ConfigError(name, "The host part of {} is the broadcast "
                                    "address of the subnet. Must be the IP "
                                    "address of the default gateway."
                              .format(network))


def directory_exists(config, name, value):
    if os.path.exists(value):
        raise ConfigError(name, "Directory %s does not exists".format(value))
    if os.path.isdir(value):
        raise ConfigError(name, "%s is not a directory".format(value))


def file_exists(config, name, value):
    if os.path.exists(value):
        raise ConfigError(name, "File %s does not exists".format(value))
    if os.path.isfile(value):
        raise ConfigError(name, "%s is not a file".format(value))


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
            raise ConfigError(name, "Range not contained in network {}".format(network))
    return checker


def user_exists(name, value):
    try:
        return pwd.getpwnam(value)
    except KeyError:
        raise ConfigError(name, "User {} does not exists".format(value))


def group_exists(name, value):
    try:
        return grp.getgrnam(value)
    except KeyError:
        raise ConfigError(name, "Group {} does not exists".format(value))


