"""
Common maintenance functionality
"""
import logging

from hades.common.db import (
    delete_old_auth_attempts, delete_old_sessions, get_connection,
    refresh_materialized_views)
from hades.config.loader import get_config
from hades.dnsmasq.util import (
    generate_dhcp_hosts_file, reload_auth_dnsmasq)

logger = logging.getLogger(__name__)


def refresh():
    logger.info("Refreshing")
    refresh_materialized_views()
    generate_dhcp_hosts_file()
    reload_auth_dnsmasq()


def cleanup():
    logger.info("Cleaning up old records")
    conf = get_config()
    connection = get_connection()
    with connection.begin():
        delete_old_sessions(connection, conf["HADES_RETENTION_INTERVAL"])
        delete_old_auth_attempts(connection, conf["HADES_RETENTION_INTERVAL"])
