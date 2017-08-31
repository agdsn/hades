import contextlib
import operator
import platform
import types
from datetime import datetime, timezone
from itertools import starmap
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import netaddr
import pkg_resources
from celery.signals import import_modules
from celery.utils.log import get_task_logger
from pydbus import SystemBus

from hades.agent import app
from hades.common.db import (
    create_engine,
    get_auth_attempts_at_port as do_get_auth_attempts_at_port,
    get_auth_attempts_of_mac as do_get_auth_attempts_of_mac,
    get_sessions_of_mac as do_get_sessions_of_mac,
)
from hades.config.loader import get_config, is_config_loaded
from hades.deputy.client import signal_cleanup, signal_refresh

logger = get_task_logger(__name__)
engine = None


if not is_config_loaded() and not app.configured:
    raise RuntimeError("Please load a config before importing this module")


# noinspection PyUnusedLocal
@import_modules.connect
def import_modules(sender, *args, **kwargs):
    global engine
    config = get_config()
    engine = create_engine(config)


class ArgumentError(Exception):
    def __init__(self, argument: str, message: str):
        super().__init__(argument, message)
        self.argument = argument
        self.message = message


def rpc_task(*args, **kwargs):
    kwargs.setdefault('acks_late', True)
    kwargs.setdefault('throws', (ArgumentError,))

    def wrapper(f: types.FunctionType):
        kwargs.setdefault('name', 'hades.agent.rpc.' + f.__name__)
        return app.task(*args, **kwargs)(f)
    return wrapper


@rpc_task()
def refresh():
    signal_refresh()


@rpc_task()
def cleanup():
    signal_cleanup()


def check_str(argument: str, string: Any) -> str:
    try:
        return str(string)
    except ValueError as e:
        raise ArgumentError(argument, "Invalid string: "
                                      "{!r}".format(string)) from e


def check_mac(argument: str, mac: Any) -> netaddr.EUI:
    try:
        return netaddr.EUI(mac)
    except (netaddr.AddrFormatError, TypeError) as e:
        raise ArgumentError(argument, "Invalid MAC address: "
                                      "{}".format(mac)) from e


def check_ip_address(argument: str, ip_address: Any) -> netaddr.IPAddress:
    try:
        return netaddr.IPAddress(ip_address)
    except netaddr.AddrFormatError as e:
        raise ArgumentError(argument, "Invalid IP address: "
                                      "{}".format(ip_address)) from e


def check_timestamp(argument: str, timestamp: Any) -> datetime:
    try:
        return datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as e:
        raise ArgumentError(argument, "Invalid timestamp: "
                                      "{}".format(timestamp)) from e


def check_int(argument: str, number: Any) -> int:
    try:
        return int(number)
    except (ValueError, TypeError) as e:
        raise ArgumentError(argument, "Invalid integer: "
                                      "{}" .format(number)) from e


def check_positive_int(argument: str, number: Any) -> int:
    number = check_int(argument, number)
    if number < 0:
        raise ArgumentError(argument, "Not a positive integer: "
                                      "{:d}".format(number))
    return number


@rpc_task()
def get_sessions_of_mac(mac: str, until: Optional[Union[int, float]]=None,
                        limit: Optional[int]=100) -> Optional[
        List[Tuple[str, str, float, float]]]:
    mac = check_mac("mac", mac)
    if until is not None:
        until = check_timestamp("until", until)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, start, stop:
                (str(nas_ip), nas_port, start.timestamp(), stop.timestamp()),
            do_get_sessions_of_mac(connection, mac, until, limit)))


@rpc_task()
def get_auth_attempts_of_mac(mac: str, until: Optional[Union[int, float]]=None,
                             limit: Optional[int]=100) -> Optional[List[
        Tuple[str, str, str, Tuple[str], Tuple[Tuple[str, str]], float]]]:
    mac = check_mac("mac", mac)
    if until is not None:
        until = check_timestamp("until", until)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, packet_type, groups, reply, auth_date:
                (str(nas_ip), nas_port, packet_type, groups, reply,
                 auth_date.timestamp()),
            do_get_auth_attempts_of_mac(connection, mac, until, limit)))


@rpc_task()
def get_auth_attempts_at_port(nas_ip_address: str, nas_port_id: str,
                              until: Optional[Union[int, float]]=None,
                              limit: Optional[int]=100) -> Optional[
        List[Tuple[str, str, Tuple[str], Tuple[Tuple[str, str]], datetime]]]:
    nas_ip_address = check_ip_address("nas_ip_address", nas_ip_address)
    nas_port_id = check_str("nas_port_id", nas_port_id)
    if until is not None:
        until = check_timestamp("until", until)
    if limit is not None:
        limit = check_positive_int("limit", limit)
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda user_name, packet_type, groups, reply, auth_date:
                (user_name, packet_type, groups, reply, auth_date.timestamp()),
            do_get_auth_attempts_at_port(connection, nas_ip_address,
                                         nas_port_id, until, limit)))


def dict_from_attributes(
        obj: object, attributes: Sequence[str]
) -> Dict[str, Any]:
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
    'hades-auth-pristine-dns.service',
    'hades-auth-vrrp.service',
    'hades-cleanup.timer',
    'hades-database.service',
    'hades-deputy.service',
    'hades-forced-refresh.timer',
    'hades-network.service',
    'hades-radius-vrrp.service',
    'hades-radius.service',
    'hades-refresh.timer',
    'hades-unauth-dns.service',
    'hades-unauth-http.service',
    'hades-unauth-portal.service',
    'hades-unauth-vrrp.service',
    'hades.target',
)


@rpc_task()
def get_systemd_status() -> Dict[str, Any]:
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
        'name': distribution.project_name,
        'version': distribution.version,
        'py_version': distribution.py_version,
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
task_attributes = (
    'name', 'max_retries', 'default_retry_delay', 'rate_limit', 'time_limit',
    'soft_time_limit', 'ignore_result', 'store_errors_even_if_ignored',
    'serializer', 'acks_late', 'track_started', 'expires',

)


@rpc_task()
def get_system_information() -> Dict[str, Any]:
    hades = pkg_resources.get_distribution("hades")
    return {
        'distribution': get_distribution_metadata(hades),
        'platform': {
            attr: getattr(platform, attr)() for attr in platform_attributes
        },
        'celery': {
            'application_name': app.main,
            'tasks': {
                name: dict_from_attributes(task, task_attributes)
                for name, task in app.tasks.items()
            }
        }
    }
