from celery import Celery
from celery.datastructures import DictAttribute
from celery.loaders.base import BaseLoader
from datetime import timedelta
from sqlalchemy import select, and_
from ..db import get_connection, radacct, radpostauth, utcnow


class Loader(BaseLoader):
    def read_configuration(self, fail_silently=False):
        try:
            config = self._import_config_module('hades.config')
        except ImportError:
            raise
        self.configured = True
        return DictAttribute(config)


app = Celery('agent', loader=Loader)


@app.task(rate_limit='1/m')
def refresh():
    connection = get_connection()
    connection.execute("REFRESH MATERIALIZED VIEW radcheck")
    connection.execute("REFRESH MATERIALIZED VIEW radgroupcheck")
    connection.execute("REFRESH MATERIALIZED VIEW radgroupreply")
    connection.execute("REFRESH MATERIALIZED VIEW radusergroup")


@app.task(rate_limit='1/m')
def delete_old():
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
