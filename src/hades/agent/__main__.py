import logging
import sys
from datetime import timedelta

from sqlalchemy import select, and_

from hades.common.db import (
    get_connection, radacct, radpostauth, refresh_materialized_views, utcnow)
from hades.config.loader import get_config
from hades.dnsmasq.util import (
    generate_dhcp_hosts_file, reload_auth_dnsmasq)

logger = logging.getLogger(__name__)


def refresh():
    refresh_materialized_views()
    generate_dhcp_hosts_file()
    reload_auth_dnsmasq()


def delete_old():
    logger.info("Deleting old records")
    conf = get_config()
    connection = get_connection()
    with connection.begin() as trans:
        result = connection.execute(radacct.delete().where(and_(
            radacct.c.acctstoptime < utcnow() - conf["HADES_RETENTION_INTERVAL"]
        )))
        result = connection.execute(radpostauth.delete().where(and_(
            radpostauth.c.authdate < utcnow() - timedelta(days=1)
        )))


def get_sessions(self, mac):
    connection = get_connection()
    results = connection.execute(
        select([radacct.c.nasipaddress, radacct.c.nasportid,
                radacct.c.acctstarttime, radacct.c.acctstoptime,
                radacct.c.acctstartdelay, radacct.c.acctstopdelay])
        .where(and_(radacct.c.username == mac,
                    radacct.c.acctstarttime >= utcnow() - timedelta(days=1))))
    return results.fetchall()


if __name__ == '__main__':
    logger.info('Hades Agent was invoked')
    failure = False

    try:
        refresh()
    except:
        failure = True
        logger.exception('Error while refreshing materialized views')

    try:
        delete_old()
    except:
        failure = True
        logger.exception('Error while deleting old records')

    if failure:
        sys.exit(1)
