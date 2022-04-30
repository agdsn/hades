"""Database utilities"""
import logging
import operator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import (
    Collection,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Generic,
)

import netaddr
import psycopg2.extensions
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, Integer, LargeBinary,
    MetaData, PrimaryKeyConstraint, String, Table, Text, TypeDecorator,
    UniqueConstraint, and_, column, create_engine as sqa_create_engine, func,
    null, or_, select, table, literal,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, MACADDR
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression

from hades.config import Config, get_config

logger = logging.getLogger(__name__)
metadata = MetaData()

Groups = Tuple[str, ...]
Attributes = Tuple[Tuple[str, str], ...]
DatetimeRange = Tuple[Optional[datetime], Optional[datetime]]


def as_copy(
    original_table: Table,
    new_name: str,
    temporary: bool = True,
) -> Table:
    """Create a copy of a table definition with a different name

    :param original_table: The table to copy
    :param new_name: Name of the new table
    :param temporary: Should the new table be marked as ``temporary``
    :return: A new table
    """
    new_table = original_table.tometadata(
        original_table.metadata,
        name=new_name,
    )
    if temporary:
        new_table.info["temporary"] = True
    return new_table


class MACAddress(TypeDecorator):
    """Custom SQLAlchemy type for MAC addresses.

    Use the PostgreSQL ``macaddr`` type on the database side and
    :class:`netaddr.EUI` on the Python side.
    """
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
    """Custom SQLAlchemy type for IP addresses.

    Use the PostgreSQL ``inet`` type on the database side and
    :class:`netaddr.IPAddress` on the Python side.
    """
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


class TupleArray(ARRAY):
    """Convenience subclass for :class:`ARRAY` for zero-indexed tuples."""
    def __init__(self, item_type, dimensions=None):
        super().__init__(item_type, as_tuple=True, dimensions=dimensions,
                         zero_indexes=True)


alternative_dns = Table(
    "alternative_dns",
    metadata,
    Column('IPAddress', IPAddress, nullable=False),
    UniqueConstraint('IPAddress'),
)
temp_alternative_dns = as_copy(alternative_dns, 'temp_alternative_dns')

auth_dhcp_host = Table(
    "auth_dhcp_host",
    metadata,
    Column('MAC', MACAddress, nullable=False),
    Column('IPAddress', IPAddress, nullable=False),
    Column('Hostname', Text, nullable=True),
    UniqueConstraint('MAC'),
    UniqueConstraint('IPAddress'),
)
temp_auth_dhcp_host = as_copy(auth_dhcp_host, 'temp_auth_dhcp_host')

auth_dhcp_lease = Table(
    "auth_dhcp_lease",
    metadata,
    Column("MAC", MACAddress, nullable=False),
    Column("IPAddress", IPAddress, nullable=False, primary_key=True),
    Column("Hostname", Text),
    Column("Domain", Text),
    Column("SuppliedHostname", Text),
    Column("ExpiresAt", DateTime(timezone=True), nullable=False),
    Column(
        "CreatedAt",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "UpdatedAt",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("RelayIPAddress", IPAddress),
    Column(
        "Tags",
        TupleArray(Text, dimensions=1),
        nullable=False,
        server_default=literal((), type_=TupleArray(Text, dimensions=1)),
    ),
    Column("Domain", Text),
    Column("ClientID", LargeBinary),
    Column("CircuitID", LargeBinary),
    Column("SubscriberID", LargeBinary),
    Column("RemoteID", LargeBinary),
    Column("VendorClass", Text),
    Column(
        "RequestedOptions",
        TupleArray(Integer, dimensions=1),
        nullable=False,
        server_default=literal((), type_=TupleArray(Text, dimensions=1)),
    ),
    Column(
        "UserClasses",
        TupleArray(Text, dimensions=1),
        nullable=False,
        server_default=literal((), type_=TupleArray(Text, dimensions=1)),
    ),
    CheckConstraint(func.coalesce(func.array_ndims("Tags"), 1) == 1),
    CheckConstraint(
        func.coalesce(func.array_ndims("RequestedOptions"), 1) == 1,
    ),
    CheckConstraint(func.coalesce(func.array_ndims("UserClasses"), 1) == 1),
)

unauth_dhcp_lease = as_copy(auth_dhcp_lease, "unauth_dhcp_lease", False)

nas = Table(
    "nas",
    metadata,
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
    "radacct",
    metadata,
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
    "radcheck",
    metadata,
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
    "radgroupcheck",
    metadata,
    Column('Priority', Integer, nullable=False),
    Column('GroupName', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('GroupName', 'Priority'),
)
temp_radgroupcheck = as_copy(radgroupcheck, 'temp_radgroupcheck')

radgroupreply = Table(
    "radgroupreply",
    metadata,
    Column('Priority', Integer, nullable=False),
    Column('GroupName', Text, nullable=False),
    Column('Attribute', Text, nullable=False),
    Column('Op', String(2), nullable=False),
    Column('Value', Text, nullable=False),
    UniqueConstraint('GroupName', 'Priority'),
)
temp_radgroupreply = as_copy(radgroupreply, 'temp_radgroupreply')

radpostauth = Table(
    "radpostauth",
    metadata,
    Column('Id', BigInteger, primary_key=True, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text),
    Column('PacketType', Text, nullable=False),
    Column('Groups', TupleArray(Text, dimensions=1)),
    Column('Reply', TupleArray(Text, dimensions=2)),
    Column('AuthDate', DateTime(timezone=True), nullable=False),
    CheckConstraint(func.coalesce(func.array_ndims("Groups"), 1) == 1),
    CheckConstraint(
        func.coalesce(func.array_ndims("Reply"), 2) == 2
        and func.coalesce(func.array_length("Reply", 2), 2) == 2
    ),
)

radreply = Table(
    "radreply",
    metadata,
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
    "radusergroup",
    metadata,
    Column('Priority', Integer, nullable=False),
    Column('UserName', Text, nullable=False),
    Column('NASIPAddress', IPAddress, nullable=False),
    Column('NASPortId', Text, nullable=False),
    Column('GroupName', Text, nullable=False),
    UniqueConstraint('UserName', 'NASIPAddress', 'NASPortId', 'Priority'),
)
temp_radusergroup = as_copy(radusergroup, 'temp_radusergroup')


# noinspection PyPep8Naming,SpellCheckingInspection
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
    def __new__(cls, offset: int):
        if offset != 0:
            raise psycopg2.DataError(
                "UTC Offset is not zero: {}".format(offset)
            )
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


def create_engine(config: Config, **kwargs):
    kwargs.setdefault('connect_args', {}).update(
        options="-c TimeZone=UTC", cursor_factory=UTCTZInfoCursorFactory
    )
    clean_up_pyroute2_registrations()
    return sqa_create_engine(config.SQLALCHEMY_DATABASE_URI, **kwargs)


def clean_up_pyroute2_registrations():
    """Manually remove `pyroute2` registrations to `psycopg2.extensions.adapters`.

    a certain version of pyroute2 pollutes the psycopg2 adapters at import time.
    In particular, lists were forcefully rendered as strings, breaking `ARRAY[]` usage.
    We ensure the module is imported and throw out the aforementioned adapters.
    """
    # noinspection PyUnresolvedReferences
    import pyroute2  # noqa
    import psycopg2
    adapters = psycopg2.extensions.adapters
    bad_keys = [
        (type_, interface) for (type_, interface), adapter in adapters.items()
        if getattr(adapter, '__module__', '').startswith('pyroute2')
    ]
    logger.debug(
        "Had to delete %d global psycopg2 adapter registrations: %r",
        len(bad_keys),
        {k: adapters[k] for k in bad_keys},
    )

    for key in bad_keys:
        if key[0] == list:
            # restore the original `List` adapter, which we need
            adapters[key] = psycopg2._psycopg.List
        else:
            del adapters[key]


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


T = TypeVar("T")


@dataclass
class ObjectsDiff(Generic[T]):
    __slots__ = ("added", "deleted", "modified")
    added: List[T]
    deleted: List[T]
    modified: List[T]

    def __str__(self):
        return f"{len(self.added)} added, {len(self.deleted)} deleted, {len(self.modified)} modified"

    def __format__(self, spec):
        if spec == "l":
            return "\n".join(
                [
                    *(f"A {x}" for x in self.added),
                    *(f"D {x}" for x in self.deleted),
                    *(f"M {x}" for x in self.modified),
                ]
            )
        return str(self)

    def __bool__(self):
        return any((self.added, self.deleted, self.modified))


def diff_tables(
    connection: Connection,
    master: Table,
    copy: Table,
    result_columns: Iterable[Column],
    unique_columns: Optional[Collection[Column]] = None,
) -> ObjectsDiff[Tuple]:
    """
    Compute the differences in the contents of two tables with identical
    columns.

    The master table must have at least one :class:`PrimaryKeyConstraint` or
    :class:`UniqueConstraint` with only non-null columns defined.

    If there are multiple constraints defined the constraints that contains the
    least number of columns are used.

    :param connection: DB connection
    :param master: Master table
    :param copy: Copy of master table
    :param result_columns: columns to return
    :param unique_columns: The columns on which to base the diff. If not specified,
        will try to make a meaningful decision based on existing table constraints.
    :return: True, if the contents differ, otherwise False
    """
    logger.debug('Calculating diff between "%s" and "%s"',
                 master.name, copy.name)
    result_columns = tuple(result_columns)
    unique_columns = unique_columns or min(
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
    return ObjectsDiff(added, deleted, modified)


def refresh_materialized_view(connection: Connection, view: Table):
    """Execute :sql:`REFRESH MATERIALIZED VIEW CONCURRENTLY` for the given
    `view`.

    :param connection: A valid SQLAlchemy connection
    :param view: The view to refresh
    """
    logger.debug('Refreshing materialized view "%s"', view.name)
    preparer = connection.dialect.identifier_preparer
    connection.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY {view}'
                       .format(view=preparer.format_table(view)))


def refresh_and_diff_materialized_view(
    connection: Connection,
    view: Table,
    copy: Table,
    result_columns: Iterable[Column],
    unique_columns: Optional[Collection[Column]] = None,
) -> ObjectsDiff[Tuple]:
    """Lock the given `view` with an advisory lock, create a temporary table
    of the view, refresh the view and compute the difference.

    :param connection: A valid SQLAlchemy connection
    :param view: The view to refresh and diff
    :param copy: A temporary table to create and diff
    :param result_columns: The columns to return
    :param unique_columns: The columns on which to base the diff. If not specified,
        will try to make a meaningful decision based on existing table constraints.
    :return: A 3-tuple containing three lists of tuples of the `result_columns`
        of added, deleted and modified records due to the refresh.

    """
    with connection.begin():
        lock_table(connection, view)
        create_temp_copy(connection, view, copy)
        refresh_materialized_view(connection, view)
        return diff_tables(connection, view, copy, result_columns, unique_columns)


def delete_old_sessions(connection: Connection, interval: timedelta):
    """Delete old session from the ``radacct`` table."""
    logger.debug('Deleting sessions in table "%s" older than "%s"',
                 radacct.name, interval)
    connection.execute(radacct.delete().where(and_(
        radacct.c.AcctUpdateTime < utcnow() - interval
    )))


def delete_old_auth_attempts(connection: Connection, interval: timedelta):
    """Delete old authentication results from the ``radpostauth`` table."""
    logger.debug('Deleting auth attempts in table "%s" older than "%s"',
                 radpostauth.name, interval)
    connection.execute(radpostauth.delete().where(and_(
        radpostauth.c.AuthDate < utcnow() - interval
    )))


def get_groups(
    connection: Connection,
    mac: netaddr.EUI,
) -> Iterator[Tuple[netaddr.IPAddress, str, str]]:
    """
    Get the groups of a user.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :return: An iterator that yields (NAS-IP-Address, NAS-Port-Id, Group-Name)-
        tuples
    """
    logger.debug('Getting groups of MAC "%s"', mac)
    results = connection.execute(select([radusergroup.c.NASIPAddress,
                                         radusergroup.c.NASPortId,
                                         radusergroup.c.GroupName])
                                 .where(radusergroup.c.UserName == mac))
    return iter(results)


def get_latest_auth_attempt(
    connection: Connection,
    mac: netaddr.EUI,
) -> Optional[Tuple[netaddr.IPAddress, str, str, Groups, Attributes, datetime]]:
    """
    Get the latest auth attempt of a MAC address that occurred within twice the
    reauthentication interval.

    :param connection: A SQLAlchemy connection
    :param str mac: MAC address
    :return: A (NAS-IP-Address, NAS-Port-Id, Packet-Type, Groups, Reply,
        Auth-Date) tuple or None if no attempt was found. Groups is an tuple of
        group names and Reply is a tuple of (Attribute, Value)-pairs that were
        sent in Access-Accept responses.
    """
    logger.debug('Getting latest auth attempt for MAC "%s"', mac)
    config = get_config(runtime_checks=True)
    interval = config.HADES_REAUTHENTICATION_INTERVAL
    attempts = get_auth_attempts_of_mac(connection, mac, (interval, None), 1)
    try:
        return next(attempts)
    except StopIteration:
        return None


def get_all_auth_dhcp_hosts(
    connection: Connection,
) -> Iterator[Tuple[netaddr.EUI, netaddr.IPAddress, Optional[str]]]:
    """
    Return all DHCP host configurations.

    :param connection: A SQLAlchemy connection
    :return: An iterator that yields (mac, ip, hostname)-tuples
    """
    logger.debug("Getting all DHCP hosts")
    result = connection.execute(
        select(
            [
                auth_dhcp_host.c.MAC,
                auth_dhcp_host.c.IPAddress,
                auth_dhcp_host.c.Hostname,
            ]
        )
    )
    return iter(result)


def get_all_nas_clients(
    connection: Connection,
) -> Iterator[Tuple[str, str, str, int, str, str, str, str]]:
    """
    Return all NAS clients.

    :param connection: A SQLAlchemy connection
    :return: An iterator that yields (shortname, nasname, type, ports, secret,
        server, community, description)-tuples
    """
    result = connection.execute(
        select([nas.c.ShortName, nas.c.NASName, nas.c.Type, nas.c.Ports,
                nas.c.Secret, nas.c.Server, nas.c.Community, nas.c.Description])
    )
    return iter(result)


def get_sessions_of_mac(
    connection: Connection,
    mac: netaddr.EUI,
    when: Optional[DatetimeRange] = None,
    limit: Optional[int] = None,
) -> Iterator[Tuple[netaddr.IPAddress, str, datetime, datetime]]:
    """
    Return accounting sessions of a particular MAC address ordered by
    Session-Start-Time descending.

    :param connection: A SQLAlchemy connection
    :param str mac: MAC address
    :param when: Range in which Session-Start-Time must be within
    :param limit: Maximum number of records
    :return: An iterator that yields (NAS-IP-Address, NAS-Port-Id,
        Session-Start-Time, Session-Stop-Time)-tuples ordered by
        Session-Start-Time descending
    """
    logger.debug('Getting all sessions for MAC "%s"', mac)
    query = (
        select([radacct.c.NASIPAddress, radacct.c.NASPortId,
                radacct.c.AcctStartTime,
                radacct.c.AcctStopTime])
        .where(and_(radacct.c.UserName == mac))
        .order_by(radacct.c.AcctStartTime.desc())
    )
    if when is not None:
        query.where(radacct.c.AcctStartTime.op('<@') <= func.tstzrange(*when))
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_auth_attempts_of_mac(
    connection: Connection,
    mac: netaddr.EUI,
    when: Optional[DatetimeRange] = None,
    limit: Optional[int] = None,
) -> Iterator[Tuple[netaddr.IPAddress, str, str, Groups, Attributes, datetime]]:
    """
    Return auth attempts of a particular MAC address order by Auth-Date
    descending.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :param when: Range in which Auth-Date must be within
    :param limit: Maximum number of records
    :return: An iterator that yields (NAS-IP-Address, NAS-Port-Id, Packet-Type,
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
    if when is not None:
        query.where(radpostauth.c.AuthDate.op('<@') <= func.tstzrange(*when))
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_auth_attempts_at_port(
    connection: Connection,
    nas_ip_address: netaddr.IPAddress,
    nas_port_id: str,
    when: Optional[DatetimeRange] = None,
    limit: Optional[int] = None,
) -> Iterator[Tuple[str, str, Groups, Attributes, datetime]]:
    """
    Return auth attempts at a particular port of an NAS ordered by Auth-Date
    descending.

    :param connection: A SQLAlchemy connection
    :param nas_ip_address: NAS IP address
    :param nas_port_id: NAS Port ID
    :param when: Range in which Auth-Date must be within
    :param limit: Maximum number of records
    :return: An iterator that yields (User-Name, Packet-Type, Groups, Reply,
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
    if when is not None:
        query.where(radpostauth.c.AuthDate.op('<@') <= func.tstzrange(*when))
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_all_alternative_dns_ips(
    connection: Connection,
) -> Iterator[netaddr.IPAddress]:
    """
    Return all IPs for alternative DNS configuration.

    :param connection: A SQLAlchemy connection
    :return: An iterator that yields ip addresses
    """
    logger.debug("Getting all alternative DNS clients")
    result = connection.execute(select([alternative_dns.c.IPAddress]))
    return map(operator.itemgetter(0), result)


def get_all_dhcp_leases(
    dhcp_lease_table: Table,
    connection: Connection,
    subnet: Optional[netaddr.IPNetwork] = None,
    limit: Optional[int] = None,
) -> Iterator[
    Tuple[
        datetime,
        netaddr.EUI,
        netaddr.IPAddress,
        Optional[str],
        Optional[str],
    ]
]:
    """
    Return all dhcp leases.

    :param dhcp_lease_table: DHCP lease table
    :param connection: A SQLAlchemy connection
    :param subnet: Limit leases to subnet
    :param limit: Maximum number of leases
    :return: An iterator that yields (Expires-At, MAC, IP-Address, Hostname,
        Client-ID)-tuples
    """
    query = select(
        [
            dhcp_lease_table.c.ExpiresAt,
            dhcp_lease_table.c.MAC,
            dhcp_lease_table.c.IPAddress,
            dhcp_lease_table.c.Hostname,
            dhcp_lease_table.c.ClientID,
        ]
    ).order_by(dhcp_lease_table.c.IPAddress.asc())
    if subnet is not None:
        query = query.where(dhcp_lease_table.c.IPAddress.op('<<=') <= subnet)
    if limit is not None:
        query = query.limit(limit)
    return iter(connection.execute(query))


def get_dhcp_lease_of_ip(
    dhcp_lease_table: Table,
    connection: Connection,
    ip: netaddr.IPAddress,
) -> Optional[Tuple[datetime, netaddr.EUI, Optional[str], Optional[str]]]:
    """
    Get basic lease information for a given IP.

    :param dhcp_lease_table: DHCP lease table
    :param connection: A SQLAlchemy connection
    :param ip: IP address
    :return: An (Expiry-Time, MAC, Hostname, Client-ID)-tuple or None
    """
    query = select(
        [
            dhcp_lease_table.c.ExpiresAt,
            dhcp_lease_table.c.MAC,
            dhcp_lease_table.c.Hostname,
            dhcp_lease_table.c.ClientID,
        ]
    ).where(IPAddress=ip)
    return connection.execute(query).first()


def get_dhcp_leases_of_mac(
    dhcp_lease_table: Table,
    connection: Connection,
    mac: netaddr.EUI,
) -> Iterator[Tuple[datetime, netaddr.IPAddress, Optional[str], Optional[str]]]:
    """
    Get basic information about all leases of a given MAC.

    :param dhcp_lease_table: DHCP lease table
    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :return: An iterator of (Expiry-Time, IP-Address, Hostname,
        Client-ID)-tuples ordered by Expiry-Time descending
    """
    query = select(
        [
            dhcp_lease_table.c.ExpiresAt,
            dhcp_lease_table.c.IPAddress,
            dhcp_lease_table.c.Hostname,
            dhcp_lease_table.c.ClientID,
        ]
    ).where(MAC=mac).order_by(dhcp_lease_table.c.ExpiresAt.desc())
    return iter(connection.execute(query))


def get_all_auth_dhcp_leases(
    connection: Connection,
    subnet: Optional[netaddr.IPNetwork] = None,
    limit: Optional[int] = None,
) -> Iterator[
    Tuple[
        datetime,
        netaddr.EUI,
        netaddr.IPAddress,
        Optional[str],
        Optional[str],
    ]
]:
    """
    Return all auth leases.

    :param connection: A SQLAlchemy connection
    :param subnet: Limit leases to subnet
    :param limit: Maximum number of leases
    :return: An iterator that yields (Expires-At, MAC, IP-Address, Hostname,
        Client-ID)-tuples
    """
    logger.debug("Getting all auth DHCP leases")
    return get_all_dhcp_leases(auth_dhcp_lease, connection, subnet, limit)


def get_auth_dhcp_lease_of_ip(
    connection: Connection,
    ip: netaddr.IPAddress,
) -> Optional[Tuple[datetime, netaddr.EUI, Optional[str], Optional[str]]]:
    """
    Get basic auth lease information for a given IP.

    :param connection: A SQLAlchemy connection
    :param ip: IP address
    :return: An iterator of (Expiry-Time, MAC, Hostname, Client-ID)-tuples or
        None
    """
    logger.debug("Getting auth DHCP lease for IP %s", ip)
    return get_dhcp_lease_of_ip(auth_dhcp_lease, connection, ip)


def get_auth_dhcp_leases_of_mac(
    connection: Connection,
    mac: netaddr.EUI,
) -> Iterator[Tuple[datetime, netaddr.IPAddress, Optional[str], Optional[str]]]:
    """
    Get basic information about all auth leases of a given MAC.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :return: An iterator of (Expiry-Time, IP-Address, Hostname,
        Client-ID)-tuples ordered by Expiry-Time descending
    """
    logger.debug("Getting auth DHCP leases for MAC %s", mac)
    return get_dhcp_leases_of_mac(auth_dhcp_lease, connection, mac)


def get_all_unauth_dhcp_leases(
    connection: Connection,
    subnet: Optional[netaddr.IPNetwork] = None,
    limit: Optional[int] = None,
) -> Iterator[
    Tuple[
        datetime,
        netaddr.EUI,
        netaddr.IPAddress,
        Optional[str],
        Optional[str],
    ]
]:
    """
    Return all unauth leases

    :param connection: A SQLAlchemy connection
    :param subnet: Limit leases to subnet
    :param limit: Maximum number of leases
    :return: An iterator that yields (Expires-At, MAC, IP-Address, Hostname,
        Client-ID)-tuples
    """
    logger.debug("Getting all unauth DHCP leases")
    return get_all_dhcp_leases(unauth_dhcp_lease, connection, subnet, limit)


def get_unauth_dhcp_lease_of_ip(
    connection: Connection,
    ip: netaddr.IPAddress,
) -> Optional[Tuple[datetime, netaddr.EUI, Optional[str], Optional[str]]]:
    """
    Get basic unauth lease information for a given IP.

    :param connection: A SQLAlchemy connection
    :param ip: IP address
    :return: An (Expiry-Time, MAC, Hostname, Client-ID)-tuple or None
    """
    logger.debug("Getting unauth DHCP lease for IP %s", ip)
    return get_dhcp_lease_of_ip(unauth_dhcp_lease, connection, ip)


def get_unauth_dhcp_leases_of_mac(
    connection: Connection,
    mac: netaddr.EUI,
) -> Iterator[Tuple[datetime, netaddr.IPAddress, Optional[str], Optional[str]]]:
    """
    Get basic information about all unauth leases of a given MAC.

    :param connection: A SQLAlchemy connection
    :param mac: MAC address
    :return: An iterator of (Expiry-Time, IP-Address, Hostname, Client-ID)
        tuples ordered by Expiry-Time descending
    """
    logger.debug("Getting unauth DHCP leases for MAC %s", mac)
    return get_dhcp_leases_of_mac(unauth_dhcp_lease, connection, mac)


@dataclass(frozen=True)
class LeaseInfo:
    __slots__ = ("ip", "mac")
    ip: netaddr.IPAddress
    mac: netaddr.EUI

    def __str__(self):
        return f"{self.ip} / {self.mac}"


def get_all_invalid_auth_dhcp_leases(
    connection: Connection,
) -> Iterator[LeaseInfo]:
    """
    Get all auth DHCP leases which do not belong to a host reservation
    as given in ``auth_dhcp_lease``.

    :param connection: A SQLAlchemy connection
    :return: an iterator of (IPAddress, MAC) tuples.
    """
    logger.debug("Getting invalid auth DHCP leases")
    query = (
        select(
            [
                auth_dhcp_lease.c.IPAddress,
                auth_dhcp_lease.c.MAC,
            ]
        )
        .select_from(
            auth_dhcp_lease.outerjoin(
                auth_dhcp_host,
                and_(
                    auth_dhcp_lease.c.MAC == auth_dhcp_host.c.MAC,
                    auth_dhcp_lease.c.IPAddress == auth_dhcp_host.c.IPAddress,
                ),
            )
        )
        .where(auth_dhcp_host.c.MAC.is_(None))
    )
    return (LeaseInfo(ip, mac) for ip, mac in connection.execute(query))
