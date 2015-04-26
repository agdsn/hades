from datetime import datetime, timedelta
import operator
from sqlalchemy import Column, Integer, String, Table, select, and_, DateTime
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from hades_portal import sqlalchemy, app

radusergroup = Table(
    'radusergroup', sqlalchemy.metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('groupname', String(64), nullable=False),
)

radpostauth = Table(
    'radpostauth', sqlalchemy.metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('packettype', String(64), nullable=False),
    Column('replymessage', String(253), nullable=False),
    Column('authdate', String(64), nullable=False),
)

GROUP_SEPARATOR = ":"


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


def get_connection():
    return sqlalchemy.engine.connect()


def get_groups(mac):
    """
    Get the groups of a user.

    :param mac: MAC address
    :return:
    :rtype: [str]
    """

    connection = get_connection()
    results = connection.execute(select([radusergroup.c.groupname])
                                 .where(radusergroup.c.username == mac))
    return list(map(operator.itemgetter(0), results))


def get_latest_auth_attempt(mac):
    """
    Get all authentication attempts of a MAC address in the last 24 hours.

    :param str mac: MAC address
    :return: A list of (accepted, [groups], when) tuples.
    :rtype: [(bool, [str], datetime)]
    """
    connection = get_connection()
    interval = timedelta(
        seconds=2 * app.config['HADES_REAUTHENTICATION_INTERVAL'])
    result = connection.execute(
        select([radpostauth.c.replymessage, radpostauth.c.authdate])
        .where(and_(
            radpostauth.c.username == mac,
            radpostauth.c.authdate >= (utcnow() - interval),
            radpostauth.c.packettype == 'Access-Accept',
        ))
        .order_by(radpostauth.c.authdate.desc()).limit(1)
    ).first()
    if result:
        m, d = result
        return m.strip(GROUP_SEPARATOR).split(GROUP_SEPARATOR), d
    return None
