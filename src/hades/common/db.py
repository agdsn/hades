import logging
import operator

from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData, PrimaryKeyConstraint,
    String, Table, UniqueConstraint, and_, cast, column, create_engine, func,
    null, or_, select, table)
from sqlalchemy.dialects.postgresql import INET, INTERVAL, MACADDR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from hades.config.loader import get_config


logger = logging.getLogger(__name__)
metadata = MetaData()


def as_copy(original_table, new_name):
    return Table(new_name, original_table.metadata,
                 *(Column(col.name, col.type)
                   for col in original_table.columns))


dhcphost = Table(
    'dhcphost', metadata,
    Column('mac', MACADDR, nullable=False),
    Column('ipaddress', INET, nullable=False),
    UniqueConstraint('mac'),
    UniqueConstraint('ipaddress'),
)
temp_dhcphost = as_copy(dhcphost, 'temp_dhcphost')

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
temp_nas = as_copy(nas, 'temp_nas')

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
temp_radcheck = as_copy(radcheck, 'temp_radcheck')

radgroupcheck = Table(
    'radgroupcheck', metadata,
    Column('priority', Integer, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('groupname', 'priority'),
)
temp_radgroupcheck = as_copy(radgroupcheck, 'temp_radgroupcheck')

radgroupreply = Table(
    'radgroupreply', metadata,
    Column('priority', Integer, nullable=False),
    Column('groupname', String(64), nullable=False),
    Column('attribute', String(64), nullable=False),
    Column('op', String(2), nullable=False),
    Column('value', String(253), nullable=False),
    UniqueConstraint('groupname', 'priority'),
)
temp_radgroupreply = as_copy(radgroupreply, 'temp_radgroupreply')

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
temp_radreply = as_copy(radreply, 'temp_radreply')

radusergroup = Table(
    'radusergroup', metadata,
    Column('priority', Integer, nullable=False),
    Column('username', String(64), nullable=False),
    Column('nasipaddres', INET, nullable=False),
    Column('nasportid', String(15), nullable=False),
    Column('groupname', String(64), nullable=False),
    UniqueConstraint('username', 'groupname', 'priority'),
)
temp_radusergroup = as_copy(radusergroup, 'temp_radusergroup')


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


def get_connection():
    config = get_config(True)
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
    return engine.connect()


def lock_table(connection, target_table):
    """
    Lock a table using a PostgreSQL advisory lock

    The OID of the table in the pg_class relation is used as lock id.
    :param connection: DB connection
    :param target_table: Table object
    """
    oid = connection.execute(select([column("oid")])
                             .select_from(table("pg_class"))
                             .where((column("relname") == target_table.name))
                             ).scalar()
    connection.execute(select([func.pg_advisory_xact_lock(oid)])).scalar()


def create_temp_copy(connection, source, destination):
    """
    Create a temporary table as a copy of a source table that will be dropped
    at the end of the running transaction.
    :param connection: DB connection
    :param source: Source table
    :param destination: Destination table
    """
    if not connection.in_transaction():
        raise RuntimeError("must be executed in a transaction to have any "
                           "effect")
    connection.execute(
        'CREATE TEMPORARY TABLE "{destination}" ON COMMIT DROP AS '
        'SELECT * FROM "{source}"'.format(source=source.name,
                                          destination=destination.name)
    )


def diff_tables(connection, master, copy, result_columns):
    """
    Compute the differences in the contents of two tables with identical
    columns.

    The master table must have at least one PrimaryKeyConstraint or
    UniqueConstraint with only non-null columns defined.

    If there are multiple constraints defined the constraints that contains the
    least number of columns are used.
    :param connection: DB connection
    :param master: Master table
    :param copy: Copy of master table
    :param result_columns: columns to return
    :return: True, if the contents differ, otherwise False
    """
    result_columns = tuple(result_columns)
    unique_columns = min(
        (constraint.columns
         for constraint in master.constraints
         if isinstance(constraint, (UniqueConstraint, PrimaryKeyConstraint)) and
         constraint.columns and not any(map(operator.attrgetter('nullable'),
                                            constraint.columns))),
        key=len, default=[])
    if not unique_columns:
        raise AssertionError("To diff table {} it must have at least one "
                             "PrimaryKeyConstraint/UniqueConstraint with only "
                             "NOT NULL columns defined on it."
                             .format(master.name))
    unique_column_names = tuple(col.name for col in unique_columns)
    other_column_names = tuple(col.name for col in master.c
                               if col.name not in unique_column_names)
    on_clause = and_(*(getattr(master.c, column_name) ==
                       getattr(copy.c, column_name)
                       for column_name in unique_column_names))
    added = connection.execute(
        select(result_columns)
        .select_from(master.outerjoin(copy, on_clause))
        .where(or_(*(getattr(copy.c, column_name).is_(null())
                     for column_name in unique_column_names)))
    ).fetchall()
    deleted = connection.execute(
        select(result_columns)
        .select_from(copy.outerjoin(master, on_clause))
        .where(or_(*(getattr(master.c, column_name).is_(null())
                     for column_name in unique_column_names)))
    ).fetchall()
    modified = connection.execute(
        select(result_columns)
        .select_from(master.join(copy, on_clause))
        .where(or_(*(getattr(master.c, column_name) !=
                     getattr(copy.c, column_name)
                     for column_name in other_column_names)))
    ).fetchall()
    return added, deleted, modified


def refresh_materialized_view(transaction, view):
    transaction.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY "{view}"'
                        .format(view=view.name))


def refresh_and_diff_materialized_view(connection, view, copy, result_columns):
    with connection.begin():
        lock_table(connection, view)
        create_temp_copy(connection, view, copy)
        refresh_materialized_view(connection, view)
        return diff_tables(connection, view, copy, result_columns)


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
    :rtype: ([str], datetime)|None
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
        message, date = result
        return message.strip().split(), date
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
