from datetime import timedelta

from sqlalchemy import select, and_

from hades.common.db import (
    get_connection, radacct, radpostauth, utcnow)


def get_sessions(self, mac):
    connection = get_connection()
    results = connection.execute(
        select([radacct.c.nasipaddress, radacct.c.nasportid,
                radacct.c.acctstarttime, radacct.c.acctstoptime,
                radacct.c.acctstartdelay, radacct.c.acctstopdelay])
        .where(and_(radacct.c.username == mac,
                    radacct.c.acctstarttime >= utcnow() - timedelta(days=1))))
    return results.fetchall()


