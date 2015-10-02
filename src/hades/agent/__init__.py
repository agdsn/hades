from celery import Celery
from datetime import timedelta
import logging
from sqlalchemy import select, and_

from hades.common.db import (get_connection, radacct, radpostauth, utcnow)
from hades.config.loader import get_config

logger = logging.getLogger(__name__)
app = Celery(__name__)
app.config_from_object(get_config())


@app.task(rate_limit='1/m')
def refresh():
    logger.info("Refreshing materialized views")
    connection = get_connection()
    connection.execute("REFRESH MATERIALIZED VIEW radcheck")
    connection.execute("REFRESH MATERIALIZED VIEW radgroupcheck")
    connection.execute("REFRESH MATERIALIZED VIEW radgroupreply")
    connection.execute("REFRESH MATERIALIZED VIEW radusergroup")


@app.task(rate_limit='1/m')
def delete_old():
    logger.info("Deleting old records")
    connection = get_connection()
    result = connection.execute(radacct.delete().where(and_(
        radacct.c.acctstoptime < utcnow() - app.conf["HADES_RETENTION_INTERVAL"]
    )))
    result = connection.execute(radpostauth.delete().where(and_(
        radpostauth.c.authdate < utcnow() - timedelta(days=1)
    )))


@app.task(bind=True)
def get_sessions(self, mac):
    connection = get_connection()
    results = connection.execute(
        select([radacct.c.nasipaddress, radacct.c.nasportid,
                radacct.c.acctstarttime, radacct.c.acctstoptime,
                radacct.c.acctstartdelay, radacct.c.acctstopdelay])
        .where(and_(radacct.c.username == mac,
                    radacct.c.acctstarttime >= utcnow() - timedelta(days=1))))
    return results.fetchall()
