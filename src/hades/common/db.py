import logging
import operator

import netaddr
from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData,
    PrimaryKeyConstraint, String, Table, Text, TypeDecorator, UniqueConstraint,
    and_, column, create_engine, func, null, or_, select, table,
)
from sqlalchemy.dialects.postgresql import INET, MACADDR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression

from hades.config.loader import get_config

logger = logging.getLogger(__name__)
metadata = MetaData()


def as_copy(original_table, new_name):
    return Table(new_name, original_table.metadata,
                 *(Column(col.name, col.type)
                   for col in original_table.columns),
                 info={'temporary': True})


class MACAddress(TypeDecorator):
    impl = MACADDR
    python_type = netaddr.EUI

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(netaddr.EUI(value, dialect=netaddr.mac_pgsql))

    process_literal_param = process_bind_param

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return netaddr.EUI(value, dialect=netaddr.mac_pgsql)


class IPAddress(TypeDecorator):
    impl = INET
    python_type = netaddr.IPAddress

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    process_literal_param = process_bind_param

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return netaddr.IPAddress(value)


alternative_dns = Table(
    'alternative_dns', metadata,
    Column('IpAddress', IPAddress, nullable=False),
    UniqueConstraint('IpAddress'),
)
temp_alternative_dns = as_copy(alternative_dns, 'temp_alternative_dns')

dhcphost = Table(
    'dhcphost', metadata,
    Column('Mac', MACAddress, nullable=False),
    Column('IpAddress', IPAddress, nullable=False),
    UniqueConstraint('Mac'),
    UniqueConstraint('IpAddress'),
)
temp_dhcphost = as_copy(dhcphost, 'temp_dhcphost')

nas = Table(
    'nas', metadata,
    Column('Id', Integer, unique=True, nullable=False),
    Column('NASName', Text, unique=True, nullable=False),
    Column('ShortName', Text, unique=True, nullable=False),
    Column('Type', Text, default='other', nullable=False),
    Column('Ports', Integer),
    Column('Secret', Text, nullable=False),
    Column('Server', Text),
    Column('Community', Text),
    Column('Description', Text),
    UniqueConstraint('Id'),
    UniqueConstraint('NASName'),
    UniqueConstraint('ShortName'),
)
temp_nas = as_copy(nas, 'temp_nas')

radacct = Table(
    'radacct', metadata,
    Column('RadAcctId', BigInteger, primary_key=True, nullable=False),
    Column('AcctSessionId', Text, nullable=False),
    Column('AcctUniqueId', Text, unique=True, nullable=False),
    Column('UserName', Text),
    Column('GroupName', Text),
    Column('Realm', Text),
    Column('NASIpAddress', IPAddress, nullable=False),
    Column('NASPortId', Text),
    Column('NASPortType', Text),
    Column('AcctStartTime', DateTime),
    Column('AcctUpdateTime', DateTime),
    Column('AcctStopTime', DateTime),
    Column('AcctInterval', BigInteger),
    Column('AcctSessionTime', BigInteger),
    Column('AcctAuthentic', Text),
    Column('ConnectInfo_start', Text),
    Column('ConnectInfo_stop', Text),
    Column('AcctInputOctets', BigInteger),
    Column('AcctOutputOctets', BigInteger),
    Column('CalledStationId', Text),
    Column('CallingStationId', Text),
    Column('AcctTerminateCause', Text),
    Column('ServiceType', Text),
    Column('FramedProtocol', Text),
    Column('FramedIPAddress', IPAddress),
)

radcheck = Table(
    'radcheck', metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIpAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIpAddress', 'NASPortId', 'Priority'),
)
temp_radcheck = as_copy(radcheck, 'temp_radcheck')

radgroupcheck = Table(
    'radgroupcheck', metadata,
    Column('Priority', Integer, nullable=False),
    Column('GroupName', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('GroupName', 'Priority'),
)
temp_radgroupcheck = as_copy(radgroupcheck, 'temp_radgroupcheck')

radgroupreply = Table(
    'radgroupreply', metadata,
    Column('Priority', Integer, nullable=False),
    Column('GroupName', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('GroupName', 'Priority'),
)
temp_radgroupreply = as_copy(radgroupreply, 'temp_radgroupreply')

radpostauth = Table(
    'radpostauth', metadata,
    Column('Id', BigInteger, primary_key=True, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIpAddress', IPAddress, nullable=False),
    Column('NASPortId', Text),
    Column('PacketType', Text, nullable=False),
    Column('ReplyMessage', Text),
    Column('AuthDate', Text, nullable=False),
)

radreply = Table(
    'radreply', metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIpAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), default='=', nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIpAddress', 'NASPortId', 'Priority'),
)
temp_radreply = as_copy(radreply, 'temp_radreply')

radusergroup = Table(
    'radusergroup', metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIpAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('GroupName', Text, nullable=False),
    UniqueConstraint('UserName', 'GroupName', 'Priority'),
)
temp_radusergroup = as_copy(radusergroup, 'temp_radusergroup')


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


def get_engine():
    """
    Get a SQLAlchemy database engine that allows connections to the database.
    :return: SQLAlchemy database engine
    """
    config = get_config(True)
    return create_engine(config.SQLALCHEMY_DATABASE_URI)


def get_connection():
    """
    Obtain a SQLAlchemy connection to the database
    :return: SQLAlchemy database connection
    """
    return get_engine().connect()


def lock_table(connection, target_table):
    """
    Lock a table using a PostgreSQL advisory lock

    The OID of the table in the pg_class relation is used as lock id.
    :param connection: DB connection
    :param target_table: Table object
    """
    logger.debug('Locking table "%s"', target_table.name)
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
    logger.debug('Creating temporary table "%s" as copy of "%s"',
                 destination.name, source.name)
    if not connection.in_transaction():
        raise RuntimeError("must be executed in a transaction to have any "
                           "effect")
    preparer = connection.dialect.identifier_preparer
    connection.execute(
        'CREATE TEMPORARY TABLE {destination} ON COMMIT DROP AS '
        'SELECT * FROM {source}'.format(
            source=preparer.format_table(source),
            destination=preparer.format_table(destination),
        )
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
    logger.debug('Calculating diff between "%s" and "%s"',
                 master.name, copy.name)
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
    logger.debug('Diff found %d added, %d deleted, and %d modified records',
                 len(added), len(deleted), len(modified))
    return added, deleted, modified


def refresh_materialized_view(connection, view):
    logger.debug('Refreshing materialized view "%s"', view.name)
    preparer = connection.dialect.identifier_preparer
    connection.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY {view}'
                        .format(view=preparer.format_table(view)))


def refresh_and_diff_materialized_view(connection, view, copy, result_columns):
    with connection.begin():
        lock_table(connection, view)
        create_temp_copy(connection, view, copy)
        refresh_materialized_view(connection, view)
        return diff_tables(connection, view, copy, result_columns)


def delete_old_sessions(transaction, interval):
    logger.debug('Deleting sessions in table "%s" older than "%s"',
                 radacct.name, interval)
    transaction.execute(radacct.delete().where(and_(
        radacct.c.AcctUpdateTime < utcnow() - interval
    )))


def delete_old_auth_attempts(transaction, interval):
    logger.debug('Deleting auth attempts in table "%s" older than "%s"',
                 radpostauth.name, interval)
    transaction.execute(radpostauth.delete().where(and_(
        radpostauth.c.AuthDate < utcnow() - interval
    )))


def get_groups(mac):
    """
    Get the groups of a user.

    :param mac: MAC address
    :return: A list of group names
    :rtype: [str]
    """
    logger.debug('Getting groups of MAC "%s"', mac)
    connection = get_connection()
    results = connection.execute(select([radusergroup.c.GroupName])
                                 .where(radusergroup.c.UserName == mac))
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
    logger.debug('Getting latest auth attempt for MAC "%s"', mac)
    connection = get_connection()
    config = get_config(True)
    interval = config.HADES_REAUTHENTICATION_INTERVAL
    result = connection.execute(
        select([radpostauth.c.ReplyMessage, radpostauth.c.AuthDate])
        .where(and_(
            radpostauth.c.UserName == mac,
            radpostauth.c.AuthDate >= (utcnow() - interval),
            radpostauth.c.PacketType == 'Access-Accept',
        ))
        .order_by(radpostauth.c.AuthDate.desc()).limit(1)
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
    logger.debug("Getting all DHCP hosts")
    connection = get_connection()
    result = connection.execute(select([dhcphost.c.Mac, dhcphost.c.IpAddress]))
    return iter(result)


def get_all_nas_clients():
    """
    Return all NAS clients.

    :return: An iterable that yields (shortname, nasname, type, ports, secret,
    server, community, description)-tuples
    :rtype: iterable[(str, str, str, int, str, str, str, str)]
    """
    connection = get_connection()
    result = connection.execute(
        select([nas.c.ShortName, nas.c.NASName, nas.c.Type, nas.c.Ports,
                nas.c.Secret, nas.c.Server, nas.c.Community, nas.c.Description])
    )
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
    logger.debug('Getting all sessions for MAC "%s"', mac)
    connection = get_connection()
    result = connection.execute(
        select([radacct.c.NASIpAddress, radacct.c.NASPortId,
                radacct.c.AcctStartTime,
                radacct.c.AcctStopTime])
        .where(and_(radacct.c.UserName == mac))
        .order_by(radacct.c.AcctStartTime.desc()))
    return iter(result)


def get_auth_attempts(mac):
    """
    Return all auth attempts of a particular MAC address.

    :param str mac: MAC address
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-ID, Packet-Type,
    Reply-Message, Auth-Date)-tuples ordered by Auth-Date descending
    :rtype: iterable[(str, str, str, str, datetime)]
    """
    logger.debug('Getting all auth attempts for MAC "%s"', mac)
    connection = get_connection()
    result = connection.execute(
        select([radpostauth.c.NASIpAddress, radpostauth.c.NASPortId,
                radpostauth.c.PacketType, radpostauth.c.ReplyMessage,
                radpostauth.c.AuthDate])
        .where(and_(radpostauth.c.UserName == mac))
        .order_by(radpostauth.c.AuthDate.desc()))
    return iter(result)


def get_all_alternative_dns_ips():
    """
    Return all IPs for alternative DNS configuration.

    :return: An iterable that yields ip addresses
    :rtype: iterable[str]
    """
    logger.debug("Getting all alternative DNS clients")
    connection = get_connection()
    result = connection.execute(select([alternative_dns.c.IpAddress]))
    return map(operator.itemgetter(0), result)
