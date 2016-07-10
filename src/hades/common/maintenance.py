"""
Common maintenance functionality
"""
import logging

from sqlalchemy import null

from hades.common.db import (
    delete_old_auth_attempts, delete_old_sessions, dhcphost, get_connection,
    nas, radcheck, radgroupcheck, radgroupreply, radusergroup,
    refresh_and_diff_materialized_view, refresh_materialized_view,
    temp_dhcphost)
from hades.config.loader import get_config
from hades.dnsmasq.util import (
    generate_dhcp_hosts_file, reload_auth_dnsmasq)

logger = logging.getLogger(__name__)


def refresh():
    logger.info("Refreshing materialized views")
    connection = get_connection()
    result = refresh_and_diff_materialized_view(connection, dhcphost,
                                                temp_dhcphost, [null()])
    if result != ([], [], []):
        generate_dhcp_hosts_file()
        reload_auth_dnsmasq()
    # TODO: After updating the nas table, we have to restart (reload?)
    # the freeradius server. Currently, this must be done manually.
    refresh_materialized_view(connection, nas)
    refresh_materialized_view(connection, radcheck)
    refresh_materialized_view(connection, radgroupcheck)
    refresh_materialized_view(connection, radgroupreply)
    refresh_materialized_view(connection, radusergroup)


def cleanup():
    logger.info("Cleaning up old records")
    conf = get_config()
    connection = get_connection()
    with connection.begin():
        delete_old_sessions(connection, conf["HADES_RETENTION_INTERVAL"])
        delete_old_auth_attempts(connection, conf["HADES_RETENTION_INTERVAL"])
