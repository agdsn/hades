import logging

from celery import Celery

from hades.common.db import (
    get_auth_attempts_at_port as do_get_auth_attempts_at_port,
    get_auth_attempts_of_mac as do_get_auth_attempts_of_mac,
    get_sessions as do_get_sessions,
)
from hades.deputy import signal_cleanup, signal_refresh

logger = logging.getLogger(__name__)
app = Celery(__name__)


@app.task(acks_late=True)
def refresh():
    signal_refresh()


@app.task(acks_late=True)
def cleanup():
    signal_cleanup()


@app.task(acks_late=True)
def get_sessions(mac):
    return list(do_get_sessions(mac))


@app.task(acks_late=True)
def get_auth_attempts_of_mac(mac):
    return list(do_get_auth_attempts_of_mac(mac))


@app.task(acks_late=True)
def get_auth_attempts_at_port(nas_ip_address, nas_port_id):
    return list(do_get_auth_attempts_at_port(nas_ip_address, nas_port_id))
