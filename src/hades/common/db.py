import logging
import operator

from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData, String, Table, select,
    and_, create_engine)
from sqlalchemy.dialects.postgresql import INET, MACADDR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from hades.config.loader import CheckWrapper, get_config


logger = logging.getLogger(__name__)
config = CheckWrapper(get_config())
engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
metadata = MetaData(bind=engine)

dhcphost = Table(
    'dhcphost', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('mac', MACADDR, nullable=False),
    Column('ipaddress', INET, nullable=False),
)

nas = Table(
    'nas', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('nasname', String(128), nullable=False),
    Column('shortname', String(32), nullable=False),
    Column('type', String(30), default='other', nullable=False),
    Column('ports', Integer),
    Column('secret', String(60), nullable=False),
    Column('server', String(64)),
    Column('community', String(50)),
    Column('description', String(200)),
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
)

radcheck = Table(
    'radcheck', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddress', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
)

radgroupcheck = Table(
    'radgroupcheck', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
)

radgroupreply = Table(
    'radgroupreply', metadata,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
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
    Column('id', Integer, primary_key=True, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddress', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), default='=', nullable=False),
    Column('value', String(253), nullable=False),
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


def refresh_materialized_views():
    logger.info("Refreshing materialized views")
    connection = get_connection()
    with connection.begin():
        connection.execute("REFRESH MATERIALIZED VIEW dhcphost")
        # TODO: After updating the nas table, we have to restart (reload?)
        # the freeradius server. Currently, this must be done manually.
        connection.execute("REFRESH MATERIALIZED VIEW nas")
        connection.execute("REFRESH MATERIALIZED VIEW radcheck")
        connection.execute("REFRESH MATERIALIZED VIEW radgroupcheck")
        connection.execute("REFRESH MATERIALIZED VIEW radgroupreply")
        connection.execute("REFRESH MATERIALIZED VIEW radusergroup")


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
