import contextlib
import operator
import platform
import types
from datetime import datetime, timezone
from itertools import starmap
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import netaddr
import pkg_resources
from celery.signals import worker_process_init
from celery.utils.log import get_task_logger
from pydbus import SystemBus
from sqlalchemy.engine import Engine

from hades.agent import app
from hades.common.db import (
    Attributes, DatetimeRange, Groups, create_engine,
    get_all_auth_dhcp_leases as do_get_all_auth_dhcp_leases,
    get_auth_attempts_at_port as do_get_auth_attempts_at_port,
    get_auth_attempts_of_mac as do_get_auth_attempts_of_mac,
    get_auth_dhcp_lease_of_ip as do_get_auth_dhcp_lease_of_ip,
    get_auth_dhcp_leases_of_mac as do_get_auth_dhcp_leases_of_mac,
    get_sessions_of_mac as do_get_sessions_of_mac,
)
from hades.config.loader import get_config, is_config_loaded
from hades.deputy.client import (
    signal_cleanup,
    signal_auth_dhcp_lease_release,
    signal_refresh,
)

logger = get_task_logger(__name__)
engine: Optional[Engine] = None

TimestampRange = Tuple[Union[None, int, float], Union[None, int, float]]


# noinspection PyUnusedLocal
@worker_process_init.connect
def setup_engine(sender, *args, **kwargs):
    global engine
    config = get_config()
    engine = create_engine(config)


class ArgumentError(Exception):
    """Exception for illegal task arguments"""
    def __init__(self, argument: str, message: str):
        super().__init__(argument, message)
        self.argument = argument
        self.message = message


def rpc_task(*args, **kwargs):
    """
    A convenience decorator that invokes :func:`celery.Celery.task`, but sets
    the following options, if not explicitly overridden:

    ============= =========================================
    Option        Value
    ============= =========================================
    ``acks_late`` :python:`True`
    ``throws``    :python:`(ArgumentError,)`
    ``name``      :python:`'hades.agent.rpc.' + f.__name__`
    ============= =========================================
    """
    kwargs.setdefault('acks_late', True)
    kwargs.setdefault('throws', (ArgumentError,))

    def wrapper(f: types.FunctionType):
        kwargs.setdefault('name', 'hades.agent.rpc.' + f.__name__)
        return app.task(*args, **kwargs)(f)

    return wrapper


def check_str(argument: str, string: Any) -> str:
    """Try to convert the argument to a string.

    :param argument: Name of the argument
    :param string: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        return str(string)
    except ValueError as e:
        raise ArgumentError(argument, "Invalid string: "
                                      "{!r}".format(string)) from e


def check_mac(argument: str, mac: Any) -> netaddr.EUI:
    """Try to convert the argument to a MAC.

    :param argument: Name of the argument
    :param mac: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        return netaddr.EUI(mac)
    except (netaddr.AddrFormatError, TypeError) as e:
        raise ArgumentError(argument, "Invalid MAC address: "
                                      "{}".format(mac)) from e


def check_ip_address(argument: str, ip_address: Any) -> netaddr.IPAddress:
    """Try to convert the argument to an IP address.

    :param argument: Name of the argument
    :param ip_address: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        return netaddr.IPAddress(ip_address)
    except netaddr.AddrFormatError as e:
        raise ArgumentError(argument, "Invalid IP address: "
                                      "{}".format(ip_address)) from e


def check_ip_network(argument: str, ip_network: Any) -> netaddr.IPNetwork:
    """Try to convert the argument to an IP network.

    :param argument: Name of the argument
    :param ip_network: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        return netaddr.IPNetwork(ip_network)
    except netaddr.AddrFormatError as e:
        raise ArgumentError(
            argument, "Invalid IP address: {}".format(ip_network)
        ) from e


def check_timestamp_range(argument: str, timestamp_range: Any) -> DatetimeRange:
    """Try to convert the argument to a datetime range (tuple of
    :class:`datetime.datetime` objects or ``None``.

    :param argument: Name of the argument
    :param timestamp_range: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        low, high = timestamp_range[0:2]
        if low is not None:
            low = datetime.utcfromtimestamp(low).replace(tzinfo=timezone.utc)
        if high is not None:
            high = datetime.utcfromtimestamp(high).replace(tzinfo=timezone.utc)
        return low, high
    except (ValueError, TypeError) as e:
        raise ArgumentError(argument, "Invalid timestamp: "
                                      "{}".format(timestamp_range)) from e


def check_int(argument: str, number: Any) -> int:
    """Try to convert the argument to an integer.

    :param argument: Name of the argument
    :param number: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    try:
        return int(number)
    except (ValueError, TypeError) as e:
        raise ArgumentError(argument, "Invalid integer: "
                                      "{}".format(number)) from e


def check_positive_int(argument: str, number: Any) -> int:
    """Try to convert the argument to a positive integer.

    :param argument: Name of the argument
    :param number: The value to convert
    :raises ArgumentError: if the argument is invalid
    """
    number = check_int(argument, number)
    if number < 0:
        raise ArgumentError(argument, "Not a positive integer: "
                                      "{:d}".format(number))
    return number


@rpc_task()
def refresh():
    """Perform a refresh of all materialized views"""
    signal_refresh()


@rpc_task()
def cleanup():
    """Perform a database cleanup"""
    signal_cleanup()


@rpc_task()
def release_auth_dhcp_lease(ip: str):
    ip = check_ip_address("ip", ip)
    signal_auth_dhcp_lease_release(ip)


@rpc_task()
def get_sessions_of_mac(mac: str, when: Optional[TimestampRange] = None,
                        limit: Optional[int] = 100) -> Optional[
        List[Tuple[str, str, float, float]]]:
    """Get the session of a given MAC address ordered by ``Session-Start-Time``

    :param mac: The MAC address
    :param when: Interval where the ``Session-Start-Time`` must be within
    :param limit: The maximum number of sessions to return
    :return: A list of (NAS-IP-Address, NAS-Port, Session-Start-Time,
     Session-Stop-Time)-tuples
    :raises ArgumentError: if illegal arguments are provided
    """
    mac = check_mac("mac", mac)
    if when is not None:
        when = check_timestamp_range("when", when)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, start, stop:
                (str(nas_ip), nas_port, start.timestamp(), stop.timestamp()),
            do_get_sessions_of_mac(connection, mac, when, limit)))


@rpc_task()
def get_auth_attempts_of_mac(mac: str, when: Optional[TimestampRange] = None,
                             limit: Optional[int] = 100) -> Optional[
        List[Tuple[str, str, str, Groups, Attributes, float]]]:
    """Get the authentication attempts of a given MAC address ordered by
    ``Auth-Date``

    :param mac: The MAC address
    :param when: Interval where the ``Auth-Date`` must be within
    :param limit: The maximum number of attempts to return
    :return: A list of (NAS-IP-Address, NAS-Port, Packet-Type, Groups, Reply,
     Auth-Date)-tuples. Groups is a tuple of the RADIUS groups at the time of
     the authentication attempt. Reply is a tuple of attribute value pairs.
    :raises ArgumentError: if illegal arguments are provided
    """
    mac = check_mac("mac", mac)
    if when is not None:
        when = check_timestamp_range("when", when)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, packet_type, groups, reply, auth_date:
                (str(nas_ip), nas_port, packet_type, groups, reply,
                 auth_date.timestamp()),
            do_get_auth_attempts_of_mac(connection, mac, when, limit)))


@rpc_task()
def get_auth_attempts_at_port(nas_ip_address: str, nas_port_id: str,
                              when: Optional[TimestampRange] = None,
                              limit: Optional[int] = 100) -> Optional[
        List[Tuple[str, str, Groups, Attributes, float]]]:
    """Get the authentication attempts at a given port ordered by
    ``Auth-Date``

    :param nas_ip_address: The NAS-IP-Address of the NAS
    :param nas_port_id: The port id of the NAS
    :param when: Interval where the ``Auth-Date`` must be within
    :param limit: The maximum number of attempts to return
    :return: A list of (User-Name, Packet-Type, Groups, Reply,
     Auth-Date)-tuples. Groups is a tuple of the RADIUS groups at the time of
     the authentication attempt. Reply is a tuple of attribute value pairs.
    :raises ArgumentError: if illegal arguments are provided
    """
    nas_ip_address = check_ip_address("nas_ip_address", nas_ip_address)
    nas_port_id = check_str("nas_port_id", nas_port_id)
    if when is not None:
        when = check_timestamp_range("until", when)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda user_name, packet_type, groups, reply, auth_date:
                (user_name, packet_type, groups, reply, auth_date.timestamp()),
            do_get_auth_attempts_at_port(connection, nas_ip_address,
                                         nas_port_id, when, limit)))


@rpc_task()
def get_auth_dhcp_leases(
    subnet: Optional[str] = None,
    limit: Optional[int] = 100,
) -> Optional[List[Tuple[float, str, str, Optional[str]]]]:
    if subnet is not None:
        subnet = check_ip_network("subnet", subnet)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda expires_at, mac, ip, hostname:
                (expires_at.timestamp(), str(mac), str(ip), hostname),
            do_get_all_auth_dhcp_leases(connection, subnet, limit)))


@rpc_task()
def get_auth_dhcp_leases_of_ip(
    ip: str,
) -> Optional[Tuple[float, str, Optional[str], Optional[str]]]:
    ip = check_ip_address("ip", ip)
    with contextlib.closing(engine.connect()) as connection:
        result = do_get_auth_dhcp_lease_of_ip(connection, ip)
        if result is not None:
            expires_at, mac, hostname, client_id = result
            return expires_at.timestamp(), str(mac), hostname, client_id
        else:
            return None


@rpc_task()
def get_auth_dhcp_leases_of_mac(
    mac: str,
) -> Optional[List[Tuple[float, str, Optional[str]]]]:
    mac = check_mac("mac", mac)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda expires_at, ip, hostname:
                (expires_at.timestamp(), str(ip), hostname),
            do_get_auth_dhcp_leases_of_mac(connection, mac)))


def dict_from_attributes(obj: object,
                         attributes: Sequence[str]) -> Dict[str, Any]:
    """
    Get a given sequence of attributes from a given object and return the
    results as dictionary.

    :param obj: An object
    :param attributes: A sequence of attributes
    :return:
    """
    return dict(zip(attributes, operator.attrgetter(*attributes)(obj)))


unit_properties = (
    'Id', 'UnitFileState', 'ActiveEnterTimestamp',
    'ActiveExitTimestamp', 'ActiveState', 'AssertResult', 'AssertTimestamp',
    'ConditionResult', 'ConditionTimestamp', 'InactiveEnterTimestamp',
    'InactiveExitTimestamp', 'LoadError', 'LoadState', 'Names',
    'StateChangeTimestamp', 'SubState',
)
service_properties = (
    'ExecMainStartTimestamp', 'ExecMainExitTimestamp', 'ExecMainCode',
    'ExecMainStatus',
)
timer_properties = (
    'LastTriggerUSec', 'LastTriggerUSecMonotonic', 'NextElapseUSecMonotonic',
    'NextElapseUSecRealtime', 'Result', 'TimersCalendar', 'TimersMonotonic',
)


def get_unit_status(unit_name: str) -> Dict[str, Any]:
    """Get the status of a given systemd unit.

    :param unit_name: The name of the unit.
    :returns: A dictionary of the unit properties
    """
    bus = SystemBus()
    systemd = bus.get('org.freedesktop.systemd1')
    path = systemd.GetUnit(unit_name)
    unit = bus.get('org.freedesktop.systemd1', path)
    properties = dict_from_attributes(unit['org.freedesktop.systemd1.Unit'],
                                      unit_properties)
    if unit_name.endswith('.service'):
        properties.update(dict_from_attributes(
            unit['org.freedesktop.systemd1.Service'], service_properties))
    elif unit_name.endswith('.timer'):
        properties.update(dict_from_attributes(
            unit['org.freedesktop.systemd1.Timer'], timer_properties))
    return properties


units = (
    'hades-agent.service',
    'hades-auth-alternative-dns.service',
    'hades-auth-dhcp.service',
    'hades-auth-netns.service',
    'hades-auth-pristine-dns.service',
    'hades-auth-vrrp.service',
    'hades-cleanup.timer',
    'hades-database.service',
    'hades-deputy.service',
    'hades-forced-refresh.timer',
    'hades-radius.service',
    'hades-refresh.timer',
    'hades-root-netns.service',
    'hades-root-vrrp.service',
    'hades-unauth-dns.service',
    'hades-unauth-http.service',
    'hades-unauth-netns.service',
    'hades-unauth-portal.service',
    'hades-unauth-vrrp.service',
    'hades.service',
)
"""The Hades systemd units that should be reported by the
:func:`get_systemd_status` task."""


@rpc_task()
def get_systemd_status() -> Dict[str, Any]:
    """Return information about the status of the Hades systemd units."""
    return {
        'units': {
            unit_name: get_unit_status(unit_name) for unit_name in units
        },
    }


def get_distribution_metadata(
        distribution: pkg_resources.Distribution
) -> Dict[str, Any]:
    """
    Get metadata of a given distribution and all its dependencies.

    :param distribution: A distribution object
    :return: A metadata dictionary
    """
    return {
        'name':         distribution.project_name,
        'version':      distribution.version,
        'py_version':   distribution.py_version,
        'requirements': {
            requirement.project_name: get_distribution_metadata(requirement)
            for requirement in map(pkg_resources.get_distribution,
                                   distribution.requires())
        },
    }


platform_attributes = (
    'architecture', 'machine', 'node', 'processor', 'python_build',
    'python_compiler', 'python_branch', 'python_implementation',
    'python_revision', 'python_version', 'python_version_tuple',
    'release', 'system', 'version', 'uname',
)
"""The attributes of the Python platform, that should be return by the
:func:`get_system_information` task."""

task_attributes = (
    'name', 'max_retries', 'default_retry_delay', 'rate_limit', 'time_limit',
    'soft_time_limit', 'ignore_result', 'store_errors_even_if_ignored',
    'serializer', 'acks_late', 'track_started', 'expires',
)
"""The attributes of the Celery tasks, that should be returned by the
:func:`get_system_information` task."""


@rpc_task()
def get_system_information() -> Dict[str, Any]:
    """Return information about the Python platform, the Hades distribution and
    its dependencies and the Celery tasks of the agent."""
    hades = pkg_resources.get_distribution("hades")
    return {
        'distribution': get_distribution_metadata(hades),
        'platform':     {
            attr: getattr(platform, attr)() for attr in platform_attributes
        },
        'celery':       {
            'application_name': app.main,
            'tasks':            {
                name: dict_from_attributes(task, task_attributes)
                for name, task in app.tasks.items()
            }
        }
    }
