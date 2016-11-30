import contextlib
import logging
import os
import pwd
import sys

from sqlalchemy import exists, null, select
from sqlalchemy.exc import DBAPIError

from hades import constants
from hades.common import db
from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.loader import load_config

logger = logging.getLogger(__package__)


@contextlib.contextmanager
def as_user(user_name):
    """
    Context manager for temporarily switching the effective UID
    :param user_name: Name of the user to switch to
    """
    uid = pwd.getpwnam(user_name).pw_uid
    os.seteuid(uid)
    yield user_name
    ruid, euid, suid = os.getresuid()
    os.seteuid(suid)


def check_database(user_name, tables):
    logger.info("Checking database access as user %s", user_name)
    try:
        conn = db.get_connection()
    except DBAPIError as e:
        logger.critical("Could not connect to database as %s: %s",
                        user_name, e)
        raise
    for table in tables:
        try:
            check_table(conn, table)
        except DBAPIError as e:
            logger.critical("Query check for table %s as user %s failed: %s",
                            table.name, user_name, e)
            raise


def check_table(conn, table):
    conn.execute(select([exists(select([null()]).select_from(table))])).scalar()


def main():
    parser = ArgumentParser(parents=[common_parser])
    args = parser.parse_args()
    load_config(args.config, True)
    try:
        engine = db.get_engine()
        engine.dispose()
        with as_user(constants.AGENT_USER) as user_name:
            check_database(user_name,
                           filter(lambda t: not t.info.get('temporary'),
                                  db.metadata.tables.values()))
        engine.dispose()
        with as_user(constants.PORTAL_USER) as user_name:
            check_database(user_name, (db.radacct, db.radpostauth,
                                       db.radusergroup))
        engine.dispose()
        with as_user(constants.RADIUS_USER) as user_name:
            check_database(user_name, (db.nas, db.radacct, db.radgroupcheck,
                                       db.radgroupreply, db.radpostauth,
                                       db.radreply, db.radusergroup))
    except DBAPIError:
        return os.EX_TEMPFAIL
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
