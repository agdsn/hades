import contextlib
from datetime import datetime, timezone
from itertools import starmap
from typing import Any, List, Optional, Tuple, Union

import netaddr
from celery.signals import import_modules
from celery.utils.log import get_task_logger

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


@app.task(acks_late=True)
def refresh():
    signal_refresh()


@app.task(acks_late=True)
def cleanup():
    signal_cleanup()


def check_str(string: Any) -> str:
    return str(string)


def check_mac(mac: Any) -> netaddr.EUI:
    try:
        return netaddr.EUI(mac)
    except netaddr.AddrFormatError as e:
        raise ValueError("Invalid MAC address: {}".format(mac)) from e


def check_ip_address(ip_address: Any) -> netaddr.IPAddress:
    try:
        return netaddr.IPAddress(ip_address)
    except netaddr.AddrFormatError as e:
        raise ValueError("Invalid IP address: {}".format(ip_address)) from e


def check_timestamp(timestamp: Any) -> datetime:
    try:
        return datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as e:
        raise ValueError("Invalid timestamp: {}".format(timestamp)) from e


def check_int(number: Any) -> int:
    try:
        return int(number)
    except (ValueError, TypeError) as e:
        raise ValueError("Invalid integer: {}".format(number)) from e


def check_positive_int(number: Any) -> int:
    number = check_int(number)
    if number < 0:
        raise ValueError("Not a positive number: {:d}".format(number))
    return number


@app.task(acks_late=True)
def get_sessions_of_mac(mac: str, until: Optional[Union[int, float]]=None,
                        limit: Optional[int]=100) -> Optional[
        List[Tuple[str, str, float, float]]]:
    try:
        mac = check_mac(mac)
        if until is not None:
            until = check_timestamp(until)
        if limit is not None:
            limit = check_positive_int(limit)
    except ValueError:
        logger.exception("Invalid argument")
        return
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, start, stop:
                (str(nas_ip), nas_port, start.timestamp(), stop.timestamp()),
            do_get_sessions_of_mac(connection, mac, until, limit)))


@app.task(acks_late=True)
def get_auth_attempts_of_mac(mac: str, until: Optional[Union[int, float]]=None,
                             limit: Optional[int]=100) -> Optional[List[
        Tuple[str, str, str, Tuple[str], Tuple[Tuple[str, str]], float]]]:
    try:
        mac = check_mac(mac)
        if until is not None:
            until = check_timestamp(until)
        if limit is not None:
            limit = check_positive_int(limit)
    except ValueError:
        logger.exception("Invalid argument")
        return
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda nas_ip, nas_port, packet_type, groups, reply, auth_date:
                (str(nas_ip), nas_port, packet_type, groups, reply,
                 auth_date.timestamp()),
            do_get_auth_attempts_of_mac(connection, mac, until, limit)))


@app.task(acks_late=True)
def get_auth_attempts_at_port(nas_ip_address: str, nas_port_id: str,
                              until: Optional[Union[int, float]]=None,
                              limit: Optional[int]=100) -> Optional[
        List[Tuple[str, str, Tuple[str], Tuple[Tuple[str, str]], datetime]]]:
    try:
        nas_ip_address = check_ip_address(nas_ip_address)
        nas_port_id = check_str(nas_port_id)
        if until is not None:
            until = check_timestamp(until)
        if limit is not None:
            limit = check_positive_int(limit)
    except ValueError:
        logger.exception("Invalid argument")
        return
    with contextlib.closing(engine.connect()) as connection:
        return list(starmap(
            lambda user_name, packet_type, groups, reply, auth_date:
                (user_name, packet_type, groups, reply, auth_date.timestamp()),
            do_get_auth_attempts_at_port(connection, nas_ip_address,
                                         nas_port_id, until, limit)))
