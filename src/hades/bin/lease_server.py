# -*- coding: utf-8 -*-
"""hades-lease-server entrypoint"""
import logging
import os
import socket
import sys
from typing import List

from sqlalchemy.exc import DBAPIError
from systemd.daemon import listen_fds, is_socket_unix, notify

from hades import constants
from hades.common import db

from hades.common.cli import (
    ArgumentParser, common_parser, setup_cli_logging,
)
from hades.common.db import auth_dhcp_lease, unauth_dhcp_lease
from hades.common.exc import handles_setup_errors
from hades.config.loader import load_config
from hades.leases.server import Server


logger = logging.getLogger(__name__)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Listens for commands as output by `hades-dhcp-script`.",
        epilog=f"""\
            This server listens on a socket for commands communicating lease events.
            For detailed information about the functionality see `hades-dhcp-script --help`.
            It is the server component for what could have been a single python program,
            however because of performance reasons, it was necessary to circumvent the need
            for a complete python interpreter startup every time such a notification happens.\
        """,
        parents=[common_parser],
    )
    parser.add_argument('--socket', nargs='?',
                        default=constants.AUTH_DHCP_SCRIPT_SOCKET,
                        help=f"Socket to listen on. Default: {constants.AUTH_DHCP_SCRIPT_SOCKET}")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth", action="store_true")
    group.add_argument("--unauth", action="store_false")
    return parser


@handles_setup_errors(logger)
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    SCRIPT_SOCKET = args.socket
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config)
    fds: List[int] = listen_fds()
    sock: socket.socket
    if len(fds) == 0:
        logger.info(
            "Opening UNIX socket at %s.", SCRIPT_SOCKET,
        )
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        try:
            os.unlink(SCRIPT_SOCKET)
        except FileNotFoundError:
            pass
        sock.bind(SCRIPT_SOCKET)
        sock.listen(Server.request_queue_size)
    elif len(fds) == 1:
        [fd] = fds
        logger.info("Using systemd activation socket (fd/%d)", fd)
        sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
        if not is_socket_unix(sock, socket.SOCK_STREAM):
            logger.critical(
                "Passed socket is not an AF_UNIX SOCK_STREAM socket"
            )
            return os.EX_USAGE
        sock.listen(Server.request_queue_size)
    else:
        logger.critical(
            "More than one (%d) socket passed via socket activation", len(fds),
        )
        return os.EX_USAGE
    engine = db.create_engine(
        config, pool_size=1, max_overflow=2, pool_pre_ping=True,
        pool_reset_on_return='rollback',
    )
    try:
        engine.connect()
    except DBAPIError as e:
        logger.critical("Could not connect to database", exc_info=e)
        return os.EX_TEMPFAIL

    server = Server(
        sock,
        engine,
        dhcp_lease_table=auth_dhcp_lease if args.auth else unauth_dhcp_lease
    )
    # if the status notification could not be sent (i.e. if this script is run directly as opposed
    # to being run by systemd), this just returns `False` and can be ignored
    notify("READY=1")
    server.serve_forever()
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
