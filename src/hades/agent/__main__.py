from datetime import timedelta
import logging
from sqlalchemy import select, and_
import sys

from hades.common.db import (get_connection, radacct, radpostauth, utcnow)
from hades.config.loader import get_config

logger = logging.getLogger(__name__)


def refresh():
    logger.info("Refreshing materialized views")
    connection = get_connection()
    with connection.begin() as trans:
        # TODO: After updating the nas table, we have to restart (reload?)
        # the freeradius server. Currently, this must be done manually.
        connection.execute("REFRESH MATERIALIZED VIEW nas")
        connection.execute("REFRESH MATERIALIZED VIEW radcheck")
        connection.execute("REFRESH MATERIALIZED VIEW radgroupcheck")
        connection.execute("REFRESH MATERIALIZED VIEW radgroupreply")
        connection.execute("REFRESH MATERIALIZED VIEW radusergroup")


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
