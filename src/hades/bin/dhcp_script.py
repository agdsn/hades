import argparse
import codecs
import grp
import itertools
import logging
import os
import pwd
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, TypeVar, Sequence, TextIO, \
    Mapping

import netaddr
from sqlalchemy import text
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine.result import RowProxy

from hades import constants
from hades.common.cli import (
    ArgumentParser,
    parser as parent_parser,
    setup_cli_logging,
)
from hades.common.db import (
    auth_dhcp_lease,
    create_engine,
    get_all_auth_dhcp_leases,
)
from hades.common.privileges import drop_privileges
from hades.config.loader import load_config

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
) -> str:
    """
    Generate lines in dnsmasq leasefile format from an iterable.
    :param leases: An iterable that yields (ExpiresAt, MAC, IPAddress,
        Hostname, ClientID)-tuples
    :return: An iterable of strings
    """
    for expires_at, mac, ip, hostname, client_id in leases:
        mac = netaddr.EUI(mac)
        mac.dialect = netaddr.mac_unix_expanded
        if client_id is None:
            client_id = "*"
        else:
            it = iter(client_id.hex())
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
        args,
        environ: Dict[str, str],
        environb: Dict[bytes, bytes],
        engine: Engine,
) -> int:
    """Print all leases in dnsmasq leasefile format"""
    connection = engine.connect()
    with connection.begin():
        leases = get_all_auth_dhcp_leases(connection)
    sys.stdout.writelines(generate_leasefile_lines(leases))
    return os.EX_OK


def get_env_safe(environ: Dict[str, str], name: str) -> Optional[str]:
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
    environ: Dict[str, str],
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


def obtain_user_classes(environ: Dict[str, str]) -> str:
    """Gather all user classes from environment variables."""
    for number in itertools.count():
        user_class = get_env_safe(environ, "DNSMASQ_USER_CLASS" + str(number))
        if user_class is None:
            return
        yield user_class


def obtain_tuple(
    environ: Dict[str, str],
    name: str,
    sep: str,
    func: Callable[[Any], T] = lambda x: x,
) -> Optional[Tuple[T]]:
    """Obtain a tuple of values from the environment"""
    value = get_env_safe(environ, name)
    if value is not None:
        try:
            value = tuple(func(v) for v in value.split(sep) if v)
        except ValueError as e:
            raise ValueError(
                "Environment variable {} contains illegal value {}".format(
                    name, value
                )
            ) from e
    return value


@dataclass
class LeaseArguments:
    mac: netaddr.EUI
    ip: netaddr.IPAddress
    hostname: Optional[str]

    @classmethod
    def from_anonymous_args(cls, args):
        return cls(
            mac=args.mac,
            ip=args.ip,
            hostname=args.hostname,
        )


def obtain_lease_info(
    args: LeaseArguments,
    environ: Dict[str, str],
    environb: Dict[bytes, bytes],
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
    expires_at = obtain_and_convert(environ, "DNSMASQ_LEASE_EXPIRES", int)
    time_remaining = obtain_and_convert(environ, "DNSMASQ_TIME_REMAINING", int)
    if time_remaining is None:
        time_remaining = 0
    if expires_at is None:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        expires_at = now + timedelta(seconds=time_remaining)
    else:
        expires_at = datetime.utcfromtimestamp(expires_at).replace(
            tzinfo=timezone.utc
        )

    client_id = environb.get(b"DNSMASQ_CLIENT_ID")
    if client_id is not None:
        try:
            client_id = codecs.decode(client_id.replace(b":", b""), "hex")
        except ValueError as e:
            raise ValueError(
                "Environment variable DNSMASQ_CLIENT_ID contains "
                "illegal value {}".format(environ.get("DNSMASQ_CLIENT_ID"))
            ) from e

    values = {
        "IPAddress": args.ip,
        "MAC": args.mac,
        "ClientID": client_id,
        "ExpiresAt": expires_at,
    }

    def set_value(key, value):
        if value is not None or missing_as_none:
            values[key] = value

    hostname = args.hostname
    if hostname is not None or "DNSMASQ_OLD_HOSTNAME" in environ:
        values["Hostname"] = hostname

    set_value(
        "SuppliedHostname", get_env_safe(environ, "DNSMASQ_SUPPLIED_HOSTNAME")
    )
    set_value("Tags", obtain_tuple(environ, "DNSMASQ_TAGS", " "))
    set_value("Domain", get_env_safe(environ, "DNSMASQ_DOMAIN"))
    set_value("CircuitID", environb.get(b"DNSMASQ_CIRCUIT_ID"))
    set_value("SubscriberID", environb.get(b"DNSMASQ_SUBSCRIBER_ID"))
    set_value("RemoteID", environb.get(b"DNSMASQ_REMOTE_ID"))
    set_value("VendorClass", get_env_safe(environ, "DNSMASQ_VENDOR_CLASS"))

    user_classes = tuple(obtain_user_classes(environ))
    user_classes = user_classes if user_classes != () else None
    set_value("UserClasses", user_classes)
    set_value(
        "RelayIPAddress",
        obtain_and_convert(environ, "DNSMASQ_RELAY_ADDRESS", netaddr.IPAddress),
    )
    set_value(
        "RequestedOptions",
        obtain_tuple(environ, "DNSMASQ_REQUESTED_OPTIONS", ",", int),
    )

    return values


def query_lease_for_update(
    connection: Connection,
    ip: netaddr.IPAddress,
) -> Optional[RowProxy]:
    query = auth_dhcp_lease.select(
        auth_dhcp_lease.c.IPAddress == ip
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
    ip: netaddr.IPAddress,
    mac: netaddr.EUI,
    old: RowProxy,
    new: Dict[str, Any],
):
    changes = {k: v for k, v in new.items() if old[k] != v}
    if not changes:
        return
    query = auth_dhcp_lease.update(values=changes).where(
        auth_dhcp_lease.c.IPAddress == ip
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
        args,
        environ: Dict[str, str],
        environb: Dict[bytes, bytes],
        engine: Engine,
) -> int:
    connection = engine.connect()
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        environ, environb,
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
    with connection.begin():
        # TODO: Use INSERT ON CONFLICT UPDATE on newer SQLAlchemy (>= 1.1)
        old_values = query_lease_for_update(connection, ip)
        if old_values is None:
            connection.execute(auth_dhcp_lease.insert(values=values))
        else:
            logger.warning("Lease for IP %s and MAC %s already exists", ip, mac)
            perform_lease_update(connection, ip, mac, old_values, values)
    return os.EX_OK


def delete_lease(
        args,
        environ: Dict[str, str],
        environb: Dict[bytes, bytes],
        engine: Engine,
) -> int:
    connection = engine.connect()
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        environ, environb,
        missing_as_none=False
    )
    ip, mac = values["IPAddress"], values["MAC"]
    logger.debug("Deleting lease for IP %s and MAC %s", ip, mac)
    query = auth_dhcp_lease.delete().where(auth_dhcp_lease.c.IPAddress == ip)
    with connection.begin():
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
        args,
        environ: Dict[str, str],
        environb: Dict[bytes, bytes],
        engine: Engine,
) -> int:
    connection = engine.connect()
    values = obtain_lease_info(
        LeaseArguments.from_anonymous_args(args),
        environ, environb,
        missing_as_none=False
    )
    values.setdefault('UpdatedAt', text('DEFAULT'))
    ip, mac = values["IPAddress"], values["MAC"]
    logger.debug("Updating lease for IP %s and MAC %s", ip, mac)
    with connection.begin():
        # TODO: Use INSERT ON CONFLICT UPDATE on newer SQLAlchemy (>= 1.1)
        old_values = query_lease_for_update(connection, ip)
        if old_values is None:
            connection.execute(auth_dhcp_lease.insert(values=values))
        else:
            perform_lease_update(connection, ip, mac, old_values, values)
    return os.EX_OK


# noinspection PyUnusedLocal
def do_nothing(
        args,
        environ: Dict[str, str],
        environb: Dict[bytes, bytes],
        engine: Engine,
) -> int:
    logger.warning("Unknown command %s", args.original_command)
    return os.EX_OK


def add_lease_command(sub_parsers, action, action_help):
    sub_parser = sub_parsers.add_parser(action, help=action_help)
    sub_parser.add_argument("mac", type=netaddr.EUI, help="MAC address")
    sub_parser.add_argument("ip", type=netaddr.IPAddress, help="IP address")
    sub_parser.add_argument("hostname", nargs="?", help="Hostname")
    return sub_parser


def create_parser(standalone: bool = True) -> ArgumentParser:
    class Parser(ArgumentParser):
        def parse_known_args(self, args=None, namespace=None):
            if namespace is None:
                namespace = argparse.Namespace()

            # The dnsmasq man page states, that the dhcp-script should handle
            # unknown commands, we therefore have to convert unknown commands
            # into the no-op command, for argparse to parse it properly.
            # argparse uses the type parameter of actions to convert values
            # before parsing it, but in the case of sub-parsers it parses all
            # positional arguments.
            def type_func(x):
                commands.type = None
                namespace.original_command = x
                return x if x in commands.choices else "no-op"

            commands.type = type_func
            return super().parse_known_args(args, namespace)

    parser = Parser(
        description="dnsmasq leasefile dhcp-script to store leases in the "
        "Hades database",
        parents=[parent_parser] if not standalone else [],
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


def main(
        argv: Sequence[str],
        stdin: TextIO, stdout: TextIO, stderr: TextIO,
        environ: Mapping[str, str], environb: Mapping[bytes, bytes],
        standalone: bool = True,
        engine: Engine = None,
):
    if standalone:
        logger.warning("Running in standalone mode. This is meant for development purposes only.")
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
    parser = create_parser(standalone=standalone)

    # type: Dict[str, Callable[[Any, Dict[str, str], Dict[bytes, bytes], Engine], int]]
    funcs = {
        "init": print_leases,
        "add": add_lease,
        "del": delete_lease,
        "old": update_lease,
        "no-op": do_nothing,
    }

    args = parser.parse_args(argv[1:])
    setup_cli_logging(parser.prog, args)
    try:
        engine = engine or engine_from_config(args.config)
        return funcs[args.command](args, environ, environb, engine)
    except ValueError as e:
        logger.fatal(str(e), exc_info=e)
        return os.EX_USAGE


if __name__ == "__main__":
    sys.exit(main(
        sys.argv,
        sys.stdin, sys.stdout, sys.stderr,
        os.environ, os.environb,
    ))
