import logging
import operator

from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData, String, Table,
    UniqueConstraint, and_, cast, create_engine, select)
from sqlalchemy.dialects.postgresql import INET, INTERVAL, MACADDR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from hades.config.loader import get_config


logger = logging.getLogger(__name__)
metadata = MetaData()

dhcphost = Table(
    'dhcphost', metadata,
    Column('mac', MACADDR, nullable=False),
    Column('ipaddress', INET, nullable=False),
    UniqueConstraint('mac'),
    UniqueConstraint('ipaddress'),
)

nas = Table(
    'nas', metadata,
    Column('id', Integer, unique=True, nullable=False),
    Column('nasname', String(128), unique=True, nullable=False),
    Column('shortname', String(32), unique=True, nullable=False),
    Column('type', String(30), default='other', nullable=False),
    Column('ports', Integer),
    Column('secret', String(60), nullable=False),
    Column('server', String(64)),
    Column('community', String(50)),
    Column('description', String(200)),
    UniqueConstraint('id'),
    UniqueConstraint('nasname'),
    UniqueConstraint('shortname'),
)

radacct = Table(
    'radacct', metadata,
    Column('radacctid', Integer, nullable=False),
    Column('acctsessionid', String(64), nullable=False),
    Column('acctuniqueid', String(32), nullable=False),
    Column('username', String(253)),
    Column('groupname', String(253)),
    Column('realm', String(64)),
    Column('nasipaddress', INET, nullable=False),
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
    Column('lastupdatetime', DateTime, nullable=False),
)

radcheck = Table(
    'radcheck', metadata,
    Column('priority', Integer, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddress', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('username', 'nasipaddress', 'nasportid', 'priority'),
)

radgroupcheck = Table(
    'radgroupcheck', metadata,
    Column('priority', Integer, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('groupname', 'priority'),
)

radgroupreply = Table(
    'radgroupreply', metadata,
    Column('priority', Integer, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('groupname', 'priority'),
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

radreply = Table(
    'radreply', metadata,
    Column('priority', Integer, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddress', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), default='=', nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('username', 'nasipaddress', 'nasportid', 'priority'),
)

radusergroup = Table(
    'radusergroup', metadata,
    Column('priority', Integer, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('groupname', String(64), nullable=False),
    UniqueConstraint('username', 'groupname', 'priority'),
)


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


def get_connection():
    config = get_config(True)
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
    return engine.connect()


def refresh_materialized_view(transaction, view):
    transaction.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY "{view}"'
                        .format(view=view.name))


def refresh_materialized_views():
    logger.info("Refreshing materialized views")
    connection = get_connection()
    with connection.begin():
        refresh_materialized_view(connection, dhcphost)
        # TODO: After updating the nas table, we have to restart (reload?)
        # the freeradius server. Currently, this must be done manually.
        refresh_materialized_view(connection, nas)
        refresh_materialized_view(connection, radcheck)
        refresh_materialized_view(connection, radgroupcheck)
        refresh_materialized_view(connection, radgroupreply)
        refresh_materialized_view(connection, radusergroup)


def delete_old_sessions(transaction, interval):
    transaction.execute(radacct.delete().where(and_(
        radacct.c.lastupdatetime < utcnow() - interval
    )))


def delete_old_auth_attempts(transaction, interval):
    transaction.execute(radpostauth.delete().where(and_(
        radpostauth.c.authdate < utcnow() - interval
    )))


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
    config = get_config(True)
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
    """
    Return all DHCP host configurations.

    :return: An iterable that yields (mac, ip)-tuples
    :rtype: iterable[(str, str)]
    """
    connection = get_connection()
    result = connection.execute(select([dhcphost.c.mac, dhcphost.c.ipaddress]))
    return iter(result)


def get_sessions(mac):
    """
    Return all sessions of a particular MAC address.

    :param str mac: MAC address
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-ID,
    Session-Start-Time, Session-Stop-Time)-tuples ordered by Session-Start-Time
    descending
    :rtype: iterable[(str, str, datetime, datetime)]
    """
    connection = get_connection()
    result = connection.execute(
        select([radacct.c.nasipaddress, radacct.c.nasportid,
                radacct.c.acctstarttime + cast(radacct.c.acctstartdelay,
                                               INTERVAL),
                radacct.c.acctstoptime + cast(radacct.c.acctstopdelay,
                                              INTERVAL)])
        .where(and_(radacct.c.username == mac))
        .order_by(radacct.c.acctstarttime.desc()))
    return iter(result)


def get_auth_attempts(mac):
    """
    Return all auth attempts of a particular MAC address.

    :param str mac: MAC address
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-ID, Packet-Type,
    Reply-Message, Auth-Date)-tuples ordered by Auth-Date descending
    :rtype: iterable[(str, str, str, str, datetime)]
    """
    connection = get_connection()
    result = connection.execute(
        select([radpostauth.c.nasipaddress, radpostauth.c.nasportid,
                radpostauth.c.packettype, radpostauth.c.replymessage,
                radpostauth.c.authdate])
        .where(and_(radpostauth.c.username == mac))
        .order_by(radpostauth.c.authdate.desc()))
    return iter(result)
