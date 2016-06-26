import logging
import sys
import os
import pwd
import contextlib

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from hades.common.cli import ArgumentParser, parser as common_parser
from . import db
from hades.config.loader import load_config

logger = logging.getLogger(__package__)


@contextlib.contextmanager
def user(user_name):
    db.engine.dispose()
    uid = pwd.getpwnam(user_name).pw_uid
    os.seteuid(uid)
    yield user_name
    db.engine.dispose()
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
    conn.execute(select([func.count()]).select_from(table)).scalar()


def main():
    parser = ArgumentParser(parents=[common_parser])
    args = parser.parse_args()
    config = load_config(args.config, runtime_checks=True)
    try:
        with user(config['HADES_AGENT_USER']) as user_name:
            check_database(user_name, db.metadata.tables.values())
        with user(config['HADES_PORTAL_USER']) as user_name:
            check_database(user_name, (db.radacct, db.radpostauth,
                                       db.radusergroup))
        with user(config['HADES_RADIUS_USER']) as user_name:
            check_database(user_name, (db.nas, db.radacct, db.radgroupcheck,
                                       db.radgroupreply, db.radpostauth,
                                       db.radreply, db.radusergroup))
    except DBAPIError:
        return os.EX_TEMPFAIL
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
