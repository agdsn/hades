# -*- coding: utf-8 -*-
"""hades-lease-server entrypoint"""
import logging
import os
import socket
import sys

from sqlalchemy.exc import DBAPIError
from systemd.daemon import listen_fds, is_socket_unix

from hades import constants
from hades.common import db

from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.config.base import ConfigError
from hades.config.loader import load_config, print_config_error
from hades.leases.server import Server


logger = logging.Logger(__name__)


def main():
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
    args = parser.parse_args()
    SCRIPT_SOCKET = args.socket
    setup_cli_logging(parser.prog, args)
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    fds = listen_fds()
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
        logger.info("Using systemd activation socket")
        sock = fds[0]
        if not is_socket_unix(sock, socket.SOCK_STREAM):
            logger.critical(
                "Passed socket is not an AF_UNIX SOCK_STREAM socket"
            )
            return os.EX_USAGE
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

    server = Server(sock, engine)
    server.serve_forever()
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())