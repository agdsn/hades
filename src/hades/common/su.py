import logging
import os
import sys
import pwd
import grp

logger = logging.getLogger(__name__)


def drop_privileges(passwd, group):
    if os.geteuid() != 0:
        logger.error("Can't drop privileges (EUID != 0)")
        return
    os.setgid(group.gr_gid)
    os.initgroups(passwd.pw_name, group.gr_gid)
    os.setuid(passwd.pw_uid)


def main(args):
    if len(args) < 3:
        print("Usage: hades.common.su USER COMMANDS [ARGS...]")
        return os.EX_USAGE
    try:
        passwd = pwd.getpwnam(args[1])
        group = grp.getgrgid(passwd.pw_gid)
    except KeyError:
        print("No such user or group")
        return os.EX_NOUSER
    filename = args[2]
    try:
        drop_privileges(passwd, group)
        os.execvp(filename, args[2:])
    except (FileNotFoundError, PermissionError):
        print("Could not execute {}".format(filename), file=sys.stderr)
        return os.EX_NOINPUT
    except OSError:
        logger.exception("An OSError occurred")
        return os.EX_OSERR


if __name__ == '__main__':
    sys.exit(main(sys.argv))
