import logging
import operator
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Iterable, List, Optional, Tuple

import netaddr
import psycopg2.extensions
from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, MetaData,
    PrimaryKeyConstraint, String, Table, Text, TypeDecorator, UniqueConstraint,
    and_, column, create_engine as sqa_create_engine, func, null, or_, select,
    table,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, MACADDR
from sqlalchemy.engine import Connection
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
    Column('IPAddress', IPAddress, nullable=False),
    UniqueConstraint('IPAddress'),
)
temp_alternative_dns = as_copy(alternative_dns, 'temp_alternative_dns')

dhcphost = Table(
    'dhcphost', metadata,
    Column('MAC', MACAddress, nullable=False),
    Column('IPAddress', IPAddress, nullable=False),
    UniqueConstraint('MAC'),
    UniqueConstraint('IPAddress'),
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
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text),
    Column('NASPortType', Text),
    Column('AcctStartTime', DateTime(timezone=True)),
    Column('AcctUpdateTime', DateTime(timezone=True)),
    Column('AcctStopTime', DateTime(timezone=True)),
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
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIPAddress', 'NASPortId', 'Priority'),
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
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text),
    Column('PacketType', Text, nullable=False),
    Column('Groups', ARRAY(Text, as_tuple=True, zero_indexes=True,
                           dimensions=1)),
    Column('Reply', ARRAY(Text, as_tuple=True, zero_indexes=True,
                          dimensions=2)),
    Column('AuthDate', DateTime(timezone=True), nullable=False),
)

radreply = Table(
    'radreply', metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), default='=', nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIPAddress', 'NASPortId', 'Priority'),
)
temp_radreply = as_copy(radreply, 'temp_radreply')

radusergroup = Table(
    'radusergroup', metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('GroupName', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIPAddress', 'NASPortId', 'Priority'),
)
temp_radusergroup = as_copy(radusergroup, 'temp_radusergroup')


class utcnow(expression.FunctionElement):
    type = DateTime()


# noinspection PyUnusedLocal
@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"


class UTCTZInfoFactory(tzinfo):
    """
    A tzinfo factory compatible with :class:`psycopg2.tz.FixedOffsetTimezone`,
    that checks if the provided UTC offset is zero and returns
    :attr:`datetime.timezone.utc`. If the offset is not zero an
    :exc:`psycopg2.DataError` is raised.

    This class is implemented as a singleton that always returns the same
    instance.
    """
    def __new__(cls, offset):
        if offset != 0:
            raise psycopg2.DataError("UTC Offset is not zero: " + offset)
        return timezone.utc


class UTCTZInfoCursorFactory(psycopg2.extensions.cursor):
    """
    A Cursor factory that sets the
    :attr:`psycopg2.extensions.cursor.tzinfo_factory` to
    :class:`UTCTZInfoFactory`.

    The C implementation of the cursor class does not use the proper Python
    attribute lookup, therefore we have to set the instance variable rather
    than use a class attribute.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tzinfo_factory = UTCTZInfoFactory


def create_engine(config, **kwargs):
    kwargs.setdefault('connect_args', {}).update(
        options="-c TimeZone=UTC", cursor_factory=UTCTZInfoCursorFactory
    )
    return sqa_create_engine(config.SQLALCHEMY_DATABASE_URI, **kwargs)


def lock_table(connection: Connection, target_table: Table):
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


def create_temp_copy(connection: Connection, source: Table, destination: Table):
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


def diff_tables(connection: Connection, master: Table, copy: Table,
                result_columns: Iterable[Column]
                ) -> Tuple[List[Tuple], List[Tuple], List[Tuple]]:
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
    ).fetchall() if other_column_names else []
    logger.debug('Diff found %d added, %d deleted, and %d modified records',
                 len(added), len(deleted), len(modified))
    return added, deleted, modified


def refresh_materialized_view(connection: Connection, view: Table):
    logger.debug('Refreshing materialized view "%s"', view.name)
    preparer = connection.dialect.identifier_preparer
    connection.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY {view}'
                       .format(view=preparer.format_table(view)))


def refresh_and_diff_materialized_view(
        connection: Connection, view: Table, copy: Table,
        result_columns: Iterable[Column]) -> Tuple[
        List[Tuple], List[Tuple], List[Tuple]]:
    with connection.begin():
        lock_table(connection, view)
        create_temp_copy(connection, view, copy)
        refresh_materialized_view(connection, view)
        return diff_tables(connection, view, copy, result_columns)


def delete_old_sessions(connection: Connection, interval: timedelta):
    logger.debug('Deleting sessions in table "%s" older than "%s"',
                 radacct.name, interval)
    connection.execute(radacct.delete().where(and_(
        radacct.c.AcctUpdateTime < utcnow() - interval
    )))


def delete_old_auth_attempts(connection: Connection, interval: timedelta):
    logger.debug('Deleting auth attempts in table "%s" older than "%s"',
                 radpostauth.name, interval)
    connection.execute(radpostauth.delete().where(and_(
        radpostauth.c.AuthDate < utcnow() - interval
    )))


def get_groups(connection: Connection, mac: netaddr.EUI) -> Iterable[
        Tuple[netaddr.IPAddress, str, str]]:
    """
    Get the groups of a user.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-Id, Group-Name)-
    tuples
    """
    logger.debug('Getting groups of MAC "%s"', mac)
    results = connection.execute(select([radusergroup.c.NASIPAddress,
                                         radusergroup.c.NASPortId,
                                         radusergroup.c.GroupName])
                                 .where(radusergroup.c.UserName == mac))
    return iter(results)


def get_latest_auth_attempt(connection: Connection,
                            mac: netaddr.EUI) -> Optional[Tuple[
        netaddr.IPAddress, str, Tuple[str], Tuple[Tuple[str]], datetime]]:
    """
    Get the latest auth attempt of a MAC address that occurred within twice the
    reauthentication interval.

    :param connection: A SQLAlchemy connection
    :param str mac: MAC address
    :return: A (NAS-IP-Address, NAS-Port-Id, Groups, Reply, Auth-Date) tuple
    or None if no attempt was found. Groups is an tuple of group names and Reply
    is a tuple of (Attribute, Value)-pairs that were sent in the Access-Accept
    response.
    """
    logger.debug('Getting latest auth attempt for MAC "%s"', mac)
    config = get_config(runtime_checks=True)
    interval = config.HADES_REAUTHENTICATION_INTERVAL
    return connection.execute(
        select([radpostauth.c.NASIPAddress, radpostauth.c.NASPortId,
                radpostauth.c.Groups, radpostauth.c.Reply,
                radpostauth.c.AuthDate])
        .where(and_(
            radpostauth.c.UserName == mac,
            radpostauth.c.AuthDate >= (utcnow() - interval),
            radpostauth.c.PacketType == 'Access-Accept',
        ))
        .order_by(radpostauth.c.AuthDate.desc()).limit(1)
    ).first()


def get_all_dhcp_hosts(connection: Connection) -> Iterable[
        Tuple[netaddr.EUI, netaddr.IPAddress]]:
    """
    Return all DHCP host configurations.

    :param connection: A SQLAlchemy connection
    :return: An iterable that yields (mac, ip)-tuples
    """
    logger.debug("Getting all DHCP hosts")
    result = connection.execute(select([dhcphost.c.MAC, dhcphost.c.IPAddress]))
    return iter(result)


def get_all_nas_clients(connection: Connection) -> Iterable[
        Tuple[str, str, str, int, str, str, str, str]]:
    """
    Return all NAS clients.

    :param connection: A SQLAlchemy connection
    :return: An iterable that yields (shortname, nasname, type, ports, secret,
    server, community, description)-tuples
    """
    result = connection.execute(
        select([nas.c.ShortName, nas.c.NASName, nas.c.Type, nas.c.Ports,
                nas.c.Secret, nas.c.Server, nas.c.Community, nas.c.Description])
    )
    return iter(result)


def get_sessions_of_mac(connection: Connection, mac: netaddr.EUI,
                        until: Optional[datetime]=None,
                        limit: Optional[int]=None) -> Iterable[
        Tuple[netaddr.IPAddress, str, datetime, datetime]]:
    """
    Return accounting sessions of a particular MAC address ordered by
    Session-Start-Time descending.

    :param connection: A SQLAlchemy connection
    :param str mac: MAC address
    :param until: Maximum Session-Start-Time of the records
    :param limit: Maximum number of records
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-Id,
    Session-Start-Time, Session-Stop-Time)-tuples ordered by Session-Start-Time
    descending
    """
    logger.debug('Getting all sessions for MAC "%s"', mac)
    query = (
        select([radacct.c.NASIPAddress, radacct.c.NASPortId,
                radacct.c.AcctStartTime,
                radacct.c.AcctStopTime])
        .where(and_(radacct.c.UserName == mac))
        .order_by(radacct.c.AcctStartTime.desc())
    )
    if until is not None:
        query.where(radacct.c.AcctStartTime <= until)
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_auth_attempts_of_mac(connection: Connection, mac: netaddr.EUI,
                             until: Optional[datetime]=None,
                             limit: Optional[int]=None) -> Iterable[
        Tuple[netaddr.IPAddress, str, str, Tuple[str], Tuple[Tuple[str, str]],
              datetime]]:
    """
    Return auth attempts of a particular MAC address order by Auth-Date
    descending.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :param until: Maximum Auth-Date of the records
    :param limit: Maximum number of records
    :return: An iterable that yields (NAS-IP-Address, NAS-Port-Id, Packet-Type,
    Groups, Reply, Auth-Date)-tuples ordered by Auth-Date descending
    """
    logger.debug('Getting all auth attempts of MAC %s', mac)
    query = (
        select([radpostauth.c.NASIPAddress, radpostauth.c.NASPortId,
                radpostauth.c.PacketType, radpostauth.c.Groups,
                radpostauth.c.Reply, radpostauth.c.AuthDate])
        .where(and_(radpostauth.c.UserName == mac))
        .order_by(radpostauth.c.AuthDate.desc())
    )
    if until is not None:
        query.where(radpostauth.c.AuthDate <= until)
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_auth_attempts_at_port(connection: Connection,
                              nas_ip_address: netaddr.IPAddress,
                              nas_port_id: str, until: Optional[datetime]=None,
                              limit: Optional[int]=None)-> Iterable[
        Tuple[str, str, Tuple[str], Tuple[Tuple[str, str]], datetime]]:
    """
    Return auth attempts at a particular port of an NAS ordered by Auth-Date
    descending.

    :param connection: A SQLAlchemy connection
    :param nas_ip_address: NAS IP address
    :param nas_port_id: NAS Port ID
    :param until: Maximum Auth-Date of the records
    :param limit: Maximum number of records
    :return: An iterable that yields (User-Name, Packet-Type, Groups, Reply,
             Auth-Date)-tuples ordered by Auth-Date descending
    """
    logger.debug('Getting all auth attempts at port %2$s of %1$s',
                 nas_ip_address, nas_port_id)
    query = (
        select([radpostauth.c.UserName, radpostauth.c.PacketType,
                radpostauth.c.Groups, radpostauth.c.Reply,
                radpostauth.c.AuthDate])
        .where(and_(radpostauth.c.NASIPAddress == nas_ip_address,
                    radpostauth.c.NASPortId == nas_port_id))
        .order_by(radpostauth.c.AuthDate.desc())
    )
    if until is not None:
        query.where(radpostauth.c.AuthDate <= until)
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_all_alternative_dns_ips(connection: Connection) -> Iterable[
        netaddr.IPAddress]:
    """
    Return all IPs for alternative DNS configuration.

    :param connection: A SQLAlchemy connection
    :return: An iterable that yields ip addresses
    """
    logger.debug("Getting all alternative DNS clients")
    result = connection.execute(select([alternative_dns.c.IPAddress]))
    return map(operator.itemgetter(0), result)
