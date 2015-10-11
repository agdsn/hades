import collections
from itertools import chain
import logging
import sys

import netaddr
from pyroute2 import netlink
from pyroute2.netlink import rtnl
from pyroute2.netlink.rtnl import rtmsg
import pyroute2.iproute

from hades.config.loader import get_config
from hades.common.util import frozendict

RT_TABLE_UNSPEC = 0
RT_TABLE_MAIN = 254

logger = logging.getLogger('hades.vrrp.notify')


def freeze(value):
    """
    Recursively convert dicts, lists and sets to their immutable counterparts
    Objects that are already hashable are returned as is
    :raises TypeError: if object can not be converted.
    """
    if isinstance(value, collections.Hashable):
        return value
    if isinstance(value, dict):
        return frozendict((k, freeze(v)) for k, v in value.items())
    if isinstance(value, list):
        return tuple(map(freeze, value))
    if isinstance(value, set):
        return frozenset(map(freeze, value))
    raise TypeError("Can not freeze type {}".format(type(value)))


def unfreeze(value):
    """Recursively convert immutable containers to mutable containers."""
    if isinstance(value, frozendict):
        return {k: unfreeze(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return list(map(unfreeze, value))
    if isinstance(value, frozenset):
        return set(map(unfreeze, value))
    return value


Route = collections.namedtuple('BaseRoute', ('family', 'dst_len', 'src_len',
                                             'tos', 'proto', 'scope', 'type',
                                             'attributes', 'flags'))
INCLUDED_ATTRIBUTES = {
    'RTA_DST', 'RTA_SRC', 'RTA_OIF', 'RTA_GATEWAY', 'RTA_PRIORITY',
    'RTA_PREFSRC', 'RTA_MULTIPATH', 'RTA_METRICS', 'RTA_FLOW', 'RTA_VIA',
    'RTA_NEWDST', 'RTA_PREF',
}


def route_from_rtmsg(rtmsg):
    """
    Convert an rtmsg to a Route object

    rtmsg objects consist of dicts and lists which are not hashable and
    therefore can not be used as elements of sets. Furthermore only a subset of
    the attributes of the rtmsg objects should be used for equality comparisons.

    :param netaddr.netlink.rtnl.rtmsg.rtmsg: rtmsg object
    """
    attributes = frozendict({k: freeze(v) for k, v in rtmsg['attrs']
                             if k in INCLUDED_ATTRIBUTES})
    return Route(rtmsg['family'], rtmsg['dst_len'], rtmsg['src_len'],
                 rtmsg['tos'], rtmsg['proto'], rtmsg['scope'], rtmsg['type'],
                 freeze(attributes), rtmsg['flags'])


def rtmsg_from_route(route, table):
    """
    Convert a Route back to an rtmsg object
    :param Route route: Route object
    :param int table: route table
    """
    msg = rtmsg.rtmsg()
    msg['family'] = route.family
    msg['dst_len'] = route.dst_len
    msg['src_len'] = route.src_len
    msg['tos'] = route.tos
    msg['proto'] = route.proto
    msg['scope'] = route.scope
    msg['type'] = route.type
    msg['flags'] = route.flags
    msg["table"] = table if table < 256 else RT_TABLE_UNSPEC
    msg['attrs'] = [[k, unfreeze(v)] for k, v in route.attributes.items()]
    msg['attrs'].append(['RTA_TABLE', table])
    return msg


def get_routes(ip, table):
    """
    Obtain all routes from a routing table
    :param pyroute2.iproute.IPRoute ip: IPRoute object
    :param int table: routing table
    """
    return map(route_from_rtmsg, ip.get_routes(table=table))


def add_routes(ip, table, routes):
    """
    Add routes to a routing table
    :param pyroute2.iproute.IPRoute ip: IPRoute object
    :param int table: routing table
    :param Iterable[Route] routes: Routes to add
    """
    flags = netlink.NLM_F_REQUEST | netlink.NLM_F_ACK | netlink.NLM_F_CREATE
    for route in routes:
        msg = rtmsg_from_route(route, table)
        ip.nlm_request(msg, msg_type=rtnl.RTM_NEWROUTE, msg_flags=flags)


def delete_routes(ip, table, routes):
    """
    Delete routes from a routing table
    :param pyroute2.iproute.IPRoute ip: IPRoute object
    :param int table: routing table
    :param Iterable[Route] routes: Routes to delete
    """
    flags = netlink.NLM_F_REQUEST | netlink.NLM_F_ACK
    for route in routes:
        msg = rtmsg_from_route(route, table)
        ip.nlm_request(msg, msg_type=rtnl.RTM_DELROUTE, msg_flags=flags)


def copy_routes(from_table, to_table, excludes):
    """
    Copy entries between routing tables

    :param int from_table: Source table
    :param int to_table: Destination table
    :param collections.Sequence[netaddr.IPNetwork] excludes: Routes with
    destination equal to or in these networks will be skipped
    """
    new_routes = set()
    with pyroute2.iproute.IPRoute() as ip:
        for route in get_routes(ip, from_table):
            dst = route.attributes.get('RTA_DST')
            if dst is None:
                continue
            dst_net = netaddr.IPNetwork("{}/{}".format(dst, route.dst_len))
            if any(dst_net in network for network in excludes):
                continue
            new_routes.add(route)
        existing_routes = set(get_routes(ip, to_table))
        delete_routes(ip, to_table, existing_routes - new_routes)
        add_routes(ip, to_table, new_routes - existing_routes)


def main(args):
    config = get_config()
    excludes = tuple(chain(config['HADES_USER_NETWORKS'].values(),
                           (config['HADES_UNAUTH_LISTEN'],)))
    table = config['HADES_AUTH_ROUTING_TABLE']
    copy_routes(RT_TABLE_MAIN, table, excludes)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
