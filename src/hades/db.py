import operator

from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData, String, Table, select,
    and_, create_engine)
from sqlalchemy.dialects.postgresql import INET, MACADDR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from hades.config.loader import CheckWrapper, get_config


config = CheckWrapper(get_config())
engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
metadata = MetaData(bind=engine)

dhcphost = Table(
    'dhcphost', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('mac', MACADDR, nullable=False),
    Column('ipaddress', INET, nullable=False),
)

radacct = Table(
    'radacct', metadata,
    Column('radacctid', Integer, nullable=False),
    Column('acctsessionid', String(64), nullable=False),
    Column('acctuniqueid', String(32), nullable=False),
    Column('username', String(253)),
    Column('groupname', String(253)),
    Column('realm', String(64)),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15)),
    Column('nasporttype', String(32)),
    Column('acctstarttime', DateTime),
    Column('acctstoptime', DateTime),
    Column('acctsessiontime', BigInteger),
    Column('acctauthentic', String(32)),
    Column('connectinfo_start', String(50)),
    Column('connectinfo_stop', String(50)),
    Column('acctinputoctets', BigInteger),
    Column('acctoutputoctets', BigInteger),
    Column('calledstationid', String(50)),
    Column('callingstationid', String(50)),
    Column('acctterminatecause', String(32)),
    Column('servicetype', String(32)),
    Column('xascendsessionsvrkey', String(10)),
    Column('framedprotocol', String(32)),
    Column('framedipaddress', INET),
    Column('acctstartdelay', Integer),
    Column('acctstopdelay', Integer),
)

radpostauth = Table(
    'radpostauth', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('packettype', String(64), nullable=False),
    Column('replymessage', String(253), nullable=False),
    Column('authdate', String(64), nullable=False),
)

radusergroup = Table(
    'radusergroup', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('groupname', String(64), nullable=False),
)


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


def get_connection():
    return engine.connect()


def get_groups(mac):
    """
    Get the groups of a user.

    :param mac: MAC address
    :return: A list of group names
    :rtype: [str]
    """
    connection = get_connection()
    results = connection.execute(select([radusergroup.c.groupname])
                                 .where(radusergroup.c.username == mac))
    return list(map(operator.itemgetter(0), results))


def get_latest_auth_attempt(mac):
    """
    Get the latest auth attempt of a MAC address that occurred within twice the
    reauthentication interval.

    :param str mac: MAC address
    :return: A pair of list of group names and when or None if no attempt was
    found..
    :rtype: [([str], datetime)]|None
    """
    connection = get_connection()
    interval = config.HADES_REAUTHENTICATION_INTERVAL
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
        return m.strip().split(), d
    return None


def get_all_dhcp_hosts():
    connection = get_connection()
    result = connection.execute(select([dhcphost.c.mac, dhcphost.c.ipaddress]))
    return iter(result)
