import contextlib
import getpass
import logging
import os

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def dropped_privileges(passwd, group):
    """
    Context manager for temporarily switching real and effective UID and real
    and effective GID.
    """
    logger.debug("Dropping privileges temporary to user %s and group %s",
                 passwd.pw_name, group.gr_name)
    # To handle multiple users with the same UID correctly, we obtain the
    # current user name with getpass
    saved_user = getpass.getuser()
    saved_uid = os.geteuid()
    saved_gid = os.getegid()
    os.setresgid(group.gr_gid, group.gr_gid, saved_gid)
    os.initgroups(passwd.pw_name, group.gr_gid)
    os.setresuid(passwd.pw_uid, passwd.pw_uid, saved_uid)
    yield
    os.seteuid(saved_uid)
    os.setreuid(saved_uid, saved_uid)
    os.setregid(saved_gid, saved_gid)
    os.initgroups(saved_user, saved_gid)
    logger.debug("Restoring previous privileges as user %s", saved_user)
