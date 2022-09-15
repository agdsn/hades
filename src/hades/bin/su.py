import argparse
import grp
import logging
import os
import pwd
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.common.privileges import drop_privileges

logger = logging.getLogger(__name__)


def main() -> int:
    parser = ArgumentParser(parents=[common_parser])
    parser.add_argument("-a", "--argv0")
    parser.add_argument('user')
    parser.add_argument('command')
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    try:
        passwd = pwd.getpwnam(args.user)
        group = grp.getgrgid(passwd.pw_gid)
    except KeyError:
        logger.critical("No such user or group")
        return os.EX_NOUSER
    try:
        drop_privileges(passwd, group)
    except PermissionError:
        logging.exception("Can't drop privileges")
        return os.EX_NOPERM
    filename = args.command
    argv = [filename if args.argv0 is None else args.argv0]
    argv.extend(args.arguments)
    try:
        os.execvp(filename, argv)
    except (FileNotFoundError, PermissionError):
        logger.critical("Could not execute %s", filename)
        return os.EX_NOINPUT
    except OSError:
        logger.exception("An OSError occurred")
        return os.EX_OSERR
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
