#!/usr/bin/env python3
"""Switch user (``su``) helper.

The ``su`` utility, that comes with *util-linux* does a lot more than
necessary. In particular, it starts a new PAM session, forks and keeps running
in the background until the command it invoked exits.

In addition to being a minor nuisance, it breaks some features such as running
systemd services that follow the ``Type=forking`` model. For these services,
systemd can't detect the correct main process.
"""
import grp
import logging
import os
import pwd
import sys

from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)

logger = logging.getLogger(__name__)


def drop_privileges(passwd: pwd.struct_passwd, group: grp.struct_group):
    os.setgid(group.gr_gid)
    os.initgroups(passwd.pw_name, group.gr_gid)
    os.setuid(passwd.pw_uid)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(parents=[common_parser])
    parser.add_argument('user')
    parser.add_argument('command')
    parser.add_argument('arguments', nargs='*')
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    try:
        passwd = pwd.getpwnam(args.user)
        group = grp.getgrgid(passwd.pw_gid)
    except KeyError:
        logger.critical("No such user or group")
        return os.EX_NOUSER
    filename = args.command
    try:
        drop_privileges(passwd, group)
    except PermissionError:
        logging.exception("Can't drop privileges")
        return os.EX_NOPERM
    try:
        os.execvp(filename, [filename] + args.arguments)
    except (FileNotFoundError, PermissionError):
        logger.critical("Could not execute %s", filename)
        return os.EX_NOINPUT
    except OSError:
        logger.exception("An OSError occurred")
        return os.EX_OSERR


if __name__ == '__main__':
    sys.exit(main())
