import logging

from hades.agent import app
from hades.common.db import (
    get_auth_attempts as do_get_auth_attempts, get_sessions as do_get_sessions)
from hades.common.maintenance import (
    cleanup as do_cleanup, refresh as do_refresh)

logger = logging.getLogger(__name__)


@app.task(acks_late=True)
def refresh():
    do_refresh()


@app.task(acks_late=True)
def cleanup():
    do_cleanup()


@app.task(acks_late=True)
def get_sessions(mac):
    return list(do_get_sessions(mac))


@app.task(acks_late=True)
def get_auth_attempts(mac):
    return list(do_get_auth_attempts(mac))
