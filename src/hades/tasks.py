import logging

import contextlib
from datetime import datetime
from typing import Optional, Union, Any

import netaddr
from celery import Celery
from celery.signals import import_modules
from sqlalchemy import create_engine

from hades.common.db import (
    get_auth_attempts_at_port as do_get_auth_attempts_at_port,
    get_auth_attempts_of_mac as do_get_auth_attempts_of_mac,
    get_sessions as do_get_sessions,
)
from hades.config.loader import get_config
from hades.deputy import signal_cleanup, signal_refresh

logger = logging.getLogger(__name__)
app = Celery(__name__)
engine = None


# noinspection PyUnusedLocal
@import_modules.connect
def import_modules(sender, *args, **kwargs):
    global engine
    config = get_config()
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)


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
        return datetime.fromtimestamp(timestamp)
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
def get_sessions(mac: str, until: Optional[Union[int, float]]=None,
                 limit: Optional[int]=100):
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
        return list(do_get_sessions(connection, mac, until, limit))


@app.task(acks_late=True)
def get_auth_attempts_of_mac(mac: str, until: Optional[Union[int, float]]=None,
                             limit: Optional[int]=100):
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
        return list(do_get_auth_attempts_of_mac(connection, mac, until, limit))


@app.task(acks_late=True)
def get_auth_attempts_at_port(nas_ip_address: str, nas_port_id: str,
                              until: Optional[Union[int, float]]=None,
                              limit: Optional[int]=100):
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
        return list(do_get_auth_attempts_at_port(connection, nas_ip_address,
                                                 nas_port_id, until, limit))
