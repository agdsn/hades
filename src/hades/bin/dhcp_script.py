from __future__ import annotations
import argparse
import codecs
import grp
import itertools
import logging
import os
import pwd
import typing
from argparse import _SubParsersAction
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, TypeVar, TextIO, \
    Mapping

import netaddr
import sqlalchemy
from sqlalchemy import text, Table
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine.result import RowProxy

from hades import constants
from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.common.db import (
    auth_dhcp_lease,
    create_engine,
    get_all_dhcp_leases,
)
from hades.common.privileges import drop_privileges
from hades.config import load_config

logger = logging.getLogger(__name__)


def engine_from_config(filename: str) -> Engine:
    config = load_config(filename)
    engine = create_engine(config, isolation_level="SERIALIZABLE")
    return engine


def generate_leasefile_lines(
    leases: Iterable[
        Tuple[
            datetime,
            netaddr.EUI,
            netaddr.IPAddress,
            Optional[str],
            Optional[bytes],
        ]
    ]
) -> typing.Iterator[str]:
    """
    Generate lines in dnsmasq leasefile format from an iterable.

    :param leases: An iterable that yields (ExpiresAt, MAC, IPAddress,
        Hostname, ClientID)-tuples
    :return: An iterable of strings
    """
    for expires_at, mac, ip, hostname, raw_client_id in leases:
        mac = netaddr.EUI(mac)
        mac.dialect = netaddr.mac_unix_expanded

        client_id: str
        if raw_client_id is None:
            client_id = "*"
        else:
            it = iter(raw_client_id.hex())
            client_id = ":".join(a + b for a, b in zip(it, it))

        yield "{expires_at:d} {mac} {ip} {hostname} {client_id}\n".format(
            expires_at=int(expires_at.timestamp()),
            mac=mac,
            ip=ip,
            hostname=hostname if hostname is not None else "*",
            client_id=client_id,
        )


# noinspection PyUnusedLocal
def print_leases(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    """Print all leases in dnsmasq leasefile format"""
    with engine.connect() as connection, connection.begin():
        leases = get_all_dhcp_leases(context.dhcp_lease_table, connection)
    context.stdout.writelines(generate_leasefile_lines(leases))
    return os.EX_OK


def get_env_safe(environ: Mapping[str, str], name: str) -> Optional[str]:
    """
    Try to get a string value from the environment and replace illegal
    characters using backslashreplace.

    See `here http://lucumr.pocoo.org/2013/7/2/the-updated-guide-to-unicode/`_
    for details.

    :param environ:
    :param name:
    :return:
    """
    value = environ.get(name, None)
    if value is not None:
        value = value.encode("utf-8", "backslashreplace").decode("utf-8")
    return value


T = TypeVar("T")


def obtain_and_convert(
    environ: Mapping[str, str],
    name: str,
    func: Callable[[Any], T],
) -> Optional[T]:
    """
    Obtain a value from the environment and try to convert it using a given
    function.
    """
    value = get_env_safe(environ, name)
    if value is None:
        return value
    try:
        return func(value)
    except ValueError as e:
        raise ValueError(
            "Environment variable {} contains an illegal value {}".format(
                name, value
            )
        ) from e


def obtain_user_classes(environ: Mapping[str, str]) -> typing.Iterator[str]:
    """Gather all user classes from environment variables."""
    for number in itertools.count():
        user_class = get_env_safe(environ, "DNSMASQ_USER_CLASS" + str(number))
        if user_class is None:
            return
        yield user_class


def obtain_tuple(
    environ: Mapping[str, str],
    name: str,
    sep: str,
    func: Callable[[Any], T] = lambda x: x,  # type: ignore
) -> Optional[Tuple[T]]:
    """Obtain a tuple of values from the environment"""
    value = get_env_safe(environ, name)
    if value is None:
        return None

    try:
        tup = tuple(func(v) for v in value.split(sep) if v)
    except ValueError as e:
        raise ValueError(
            f"Environment variable {name} contains illegal value {value}"
        ) from e
    return typing.cast(Tuple[T], tup)


@dataclass
class LeaseArguments:
    mac: netaddr.EUI
    ip: netaddr.IPAddress
    hostname: Optional[str]

    @classmethod
    def from_anonymous_args(cls, args: typing.Any) -> LeaseArguments:
        return cls(
            mac=args.mac,
            ip=args.ip,
            hostname=args.hostname,
        )


def obtain_lease_info(
    args: LeaseArguments,
    context: Context,
    *,
    missing_as_none: bool,
) -> Dict[str, Any]:
    """Obtain lease information from the CLI arguments and the environment.

    The IPAddress, MAC, Tags, Client-ID and ExpiresAt keys are always present
    in the returned dictionary, because these values should be known by the
    the DHCP Server during every client interaction. The Hostname key is present
    if the ``DNSMASQ_OLD_HOSTNAME`` environment variable is available.

    For other values, the ``missing_as_none`` parameter specifies if a missing
    environment variable should result in the corresponding key being present
    with value of None in the resulting dict or if the key should be absent.
    """
    expires_at_int = obtain_and_convert(context.environ, "DNSMASQ_LEASE_EXPIRES", int)
    time_remaining = obtain_and_convert(context.environ, "DNSMASQ_TIME_REMAINING", int)
    if time_remaining is None:
        time_remaining = 0
    if expires_at_int is None:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        expires_at = now + timedelta(seconds=time_remaining)
    else:
        expires_at = datetime.utcfromtimestamp(expires_at_int).replace(
            tzinfo=timezone.utc
        )

    client_id = context.environb.get(b"DNSMASQ_CLIENT_ID")
    if client_id is not None:
        try:
            client_id = codecs.decode(client_id.replace(b":", b""), "hex")
        except ValueError as e:
            raise ValueError(
                "Environment variable DNSMASQ_CLIENT_ID contains "
                f"illegal value {context.environ.get('DNSMASQ_CLIENT_ID')}"
            ) from e

    values = {
        "IPAddress": args.ip,
        "MAC": args.mac,
        "ClientID": client_id,
        "ExpiresAt": expires_at,
    }

    def set_value(key: str, value: typing.Any) -> None:
        if value is not None or missing_as_none:
            values[key] = value

    hostname = args.hostname
    if hostname is not None or "DNSMASQ_OLD_HOSTNAME" in context.environ:
        values["Hostname"] = hostname

    set_value(
        "SuppliedHostname", get_env_safe(context.environ, "DNSMASQ_SUPPLIED_HOSTNAME")
    )
    set_value("Tags", obtain_tuple(context.environ, "DNSMASQ_TAGS", " "))
    set_value("Domain", get_env_safe(context.environ, "DNSMASQ_DOMAIN"))
    set_value("CircuitID", context.environb.get(b"DNSMASQ_CIRCUIT_ID"))
    set_value("SubscriberID", context.environb.get(b"DNSMASQ_SUBSCRIBER_ID"))
    set_value("RemoteID", context.environb.get(b"DNSMASQ_REMOTE_ID"))
    set_value("VendorClass", get_env_safe(context.environ, "DNSMASQ_VENDOR_CLASS"))

    user_classes = tuple(obtain_user_classes(context.environ))
    user_classes = user_classes if user_classes != () else None
    set_value("UserClasses", user_classes)
    set_value(
        "RelayIPAddress",
        obtain_and_convert(context.environ, "DNSMASQ_RELAY_ADDRESS", netaddr.IPAddress),
    )
    set_value(
        "RequestedOptions",
        obtain_tuple(context.environ, "DNSMASQ_REQUESTED_OPTIONS", ",", int),
    )

    return values


def query_lease_for_update(
    connection: Connection,
    dhcp_lease_table: Table,
    ip: netaddr.IPAddress,
) -> Optional[RowProxy]:
    query = dhcp_lease_table.select(
        dhcp_lease_table.c.IPAddress == ip
    ).with_for_update()
    with closing(connection.execute(query)) as result:
        row = result.fetchone()
        if result.fetchone() is not None:
            logger.warning(
                "Querying database for lease with IP %s "
                "returned more than one row",
                ip,
            )
        return row


def perform_lease_update(
    connection: Connection,
    dhcp_lease_table: Table,
    ip: netaddr.IPAddress,
    mac: netaddr.EUI,
    old: RowProxy,
    new: Dict[str, Any],
) -> typing.Optional[sqlalchemy.engine.Result]:
    changes = {k: v for k, v in new.items() if old[k] != v}
    if not changes:
        return None
    query = dhcp_lease_table.update(values=changes).where(
        dhcp_lease_table.c.IPAddress == ip
    )
    result = connection.execute(query)
    if result.rowcount != 1:
        logger.warning(
            "Unexpected row count %d while updating lease for IP %s "
            "and MAC %s",
            result.rowcount,
            ip,
            mac,
        )
    return result


def add_lease(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        context,
        missing_as_none=True
    )
    values = {k: (v if v is not None else text('DEFAULT'))
              for k, v in values.items()}
    ip, mac = values["IPAddress"], values["MAC"]
    logger.debug(
        "Inserting new lease for IP %s and MAC %s",
        ip,
        mac,
    )
    with engine.connect() as connection, connection.begin():
        lease_table = context.dhcp_lease_table
        # TODO: Use INSERT ON CONFLICT UPDATE on newer SQLAlchemy (>= 1.1)
        old_values = query_lease_for_update(connection, lease_table, ip)
        if old_values is None:
            connection.execute(lease_table.insert(values=values))
        else:
            logger.warning("Lease for IP %s and MAC %s already exists", ip, mac)
            perform_lease_update(connection, lease_table, ip, mac, old_values, values)
    return os.EX_OK


def delete_lease(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        context,
        missing_as_none=False
    )
    ip, mac = values["IPAddress"], values["MAC"]
    logger.debug("Deleting lease for IP %s and MAC %s", ip, mac)
    lease_table = context.dhcp_lease_table
    query = lease_table.delete().where(lease_table.c.IPAddress == ip)
    with engine.connect() as connection, connection.begin():
        result = connection.execute(query)
    if result.rowcount != 1:
        logger.warning(
            "Unexpected row count %d while deleting lease for IP %s and MAC %s",
            result.rowcount,
            ip,
            mac,
        )
    return os.EX_OK


def update_lease(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        context,
        missing_as_none=False
    )
    values.setdefault('UpdatedAt', text('DEFAULT'))
    ip, mac = values["IPAddress"], values["MAC"]
    logger.debug("Updating lease for IP %s and MAC %s", ip, mac)
    with engine.connect() as connection, connection.begin():
        # TODO: Use INSERT ON CONFLICT UPDATE on newer SQLAlchemy (>= 1.1)
        lease_table = context.dhcp_lease_table
        old_values = query_lease_for_update(connection, lease_table, ip)
        if old_values is None:
            connection.execute(lease_table.insert(values=values))
        else:
            perform_lease_update(connection, lease_table, ip, mac, old_values, values)
    return os.EX_OK


# noinspection PyUnusedLocal
def do_nothing(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    logger.error("Unknown command %s", args.original_command)
    return os.EX_OK


def add_lease_command(
    sub_parsers: _SubParsersAction, action: str, action_help: str
) -> ArgumentParser:
    sub_parser = typing.cast(
        ArgumentParser, sub_parsers.add_parser(action, help=action_help)
    )
    sub_parser.add_argument("mac", type=netaddr.EUI, help="MAC address")
    sub_parser.add_argument("ip", type=netaddr.IPAddress, help="IP address")
    sub_parser.add_argument("hostname", nargs="?", help="Hostname")
    return sub_parser


def create_parser(standalone: bool = True) -> ArgumentParser:
    class Parser(ArgumentParser):
        def parse_known_args(
            self,
            args: typing.Optional[typing.Sequence[str]] = None,
            namespace: typing.Optional[typing.Any] = None,
        ) -> typing.Tuple[argparse.Namespace, typing.List[str]]:
            if namespace is None:
                namespace = argparse.Namespace()

            # The dnsmasq man page states, that the dhcp-script should handle
            # unknown commands, we therefore have to convert unknown commands
            # into the no-op command, for argparse to parse it properly.
            # argparse uses the type parameter of actions to convert values
            # before parsing it, but in the case of sub-parsers it parses all
            # positional arguments.
            def type_func(x: str) -> str:
                commands.type = None
                namespace.original_command = x
                return x if x in commands.choices else "no-op"

            commands.type = type_func
            return super().parse_known_args(args, namespace)

        def exit(self, *a: typing.Any, **kw: typing.Any) -> None:
            if standalone:
                super().exit(*a, **kw)
                return
            logger.warning("Unexpected call to argparsers exit(args=%r, kwargs=%r)", a, kw)

    parser = Parser(
        description="dnsmasq leasefile dhcp-script to store leases in the "
        "Hades database",
        parents=[common_parser] if standalone else [],
        exit_on_error=standalone,
    )
    commands = parser.add_subparsers(metavar="COMMAND", dest="command")
    commands.required = True
    commands.add_parser(
        "init",
        help="Print all leases in dnsmasq leasefile format"
    )
    commands.add_parser("no-op", help=argparse.SUPPRESS)
    add_lease_command(commands, "add", "Add a lease")
    add_lease_command(commands, "del", "Delete a lease")
    add_lease_command(commands, "old", "Update a lease")
    return parser


@dataclass
class Context:
    """Information relevant to the communication of the program"""
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    environ: Mapping[str, str]
    environb: Mapping[bytes, bytes]
    #: Can be either :ref:`hades.db.unauth_dhcp_leases` or :ref:`hades.db.auth_dhcp_leases`
    dhcp_lease_table: Table


def main() -> int:
    import sys
    logger.warning(
        "Running in standalone mode."
        " This is meant for development purposes, and only works with `auth-dhcp` leases."
    )
    # When dnsmasq starts, it calls init before dropping privileges
    if os.geteuid() == 0:
        try:
            passwd = pwd.getpwnam(constants.AUTH_DHCP_USER)
        except KeyError:
            logger.critical("No such user: {}".format(constants.AUTH_DHCP_USER))
            return os.EX_NOUSER
        try:
            group = grp.getgrgid(passwd.pw_gid)
        except KeyError:
            logger.critical("No such group: {:d}".format(passwd.pw_gid))
            return os.EX_NOUSER
        drop_privileges(passwd, group)
    parser = create_parser(standalone=True)
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    engine = engine_from_config(args.config)

    return dispatch_commands(
        args,
        Context(
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            environ=os.environ,
            environb=os.environb,
            # this is hardcoded because we don't really care about standalone mode anyway.
            dhcp_lease_table=auth_dhcp_lease,
        ),
        engine,
    )


def dispatch_commands(
    args: typing.Any,
    context: Context,
    engine: Engine,
) -> int:
    """"""
    funcs: Dict[str, Callable[[Any, Context, Engine], int]] = {
        "init": print_leases,
        "add": add_lease,
        "del": delete_lease,
        "old": update_lease,
        "no-op": do_nothing,
    }
    try:
        return funcs[args.command](args, context, engine)
    except ValueError as e:
        logger.fatal(str(e), exc_info=e)
        return os.EX_USAGE


if __name__ == "__main__":
    import sys
    sys.exit(main())
