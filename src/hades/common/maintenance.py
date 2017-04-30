"""
Common maintenance functionality
"""
import logging

from pydbus import SystemBus
from sqlalchemy import null

import hades.common.db as db
from hades import constants
from hades.config.loader import get_config

logger = logging.getLogger(__name__)


def signal_auth_dhcp_hosts_reload():
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME)
    deputy.ReloadAuthDhcpHosts()


def signal_radius_clients_reload():
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME)
    deputy.ReloadRadiusClients()


def signal_alternative_auth_dns_clients_reload():
    bus = SystemBus()
    deputy = bus.get(constants.DEPUTY_DBUS_NAME)
    deputy.ReloadAlternativeAuthDnsClients()


def refresh():
    logger.info("Refreshing materialized views")
    connection = db.get_connection()
    result = db.refresh_and_diff_materialized_view(connection, db.dhcphost,
                                                   db.temp_dhcphost, [null()])
    if result != ([], [], []):
        logger.info('DHCP host reservations changed. Signaling reload.')
        signal_auth_dhcp_hosts_reload()
    result = db.refresh_and_diff_materialized_view(connection, db.nas,
                                                   db.temp_nas, [null()])
    if result != ([], [], []):
        logger.info('RADIUS clients changed. Signaling reload.')
        signal_radius_clients_reload()
    result = db.refresh_and_diff_materialized_view(connection, db.alternative_dns,
                                                   db.temp_alternative_dns, [null()])
    if result != ([], [], []):
        logger.info('Alternative auth DNS clients changed. Signaling reload.')
        signal_alternative_auth_dns_clients_reload()
    db.refresh_materialized_view(connection, db.radcheck)
    db.refresh_materialized_view(connection, db.radgroupcheck)
    db.refresh_materialized_view(connection, db.radgroupreply)
    db.refresh_materialized_view(connection, db.radusergroup)


def cleanup():
    logger.info("Cleaning up old records")
    conf = get_config()
    interval = conf["HADES_RETENTION_INTERVAL"]
    connection = db.get_connection()
    with connection.begin():
        db.delete_old_sessions(connection, interval)
        db.delete_old_auth_attempts(connection, interval)
