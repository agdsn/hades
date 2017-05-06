import grp
import logging
import os
import pwd
import sys

from sqlalchemy import exists, null, select
from sqlalchemy.exc import DBAPIError

from hades import constants
from hades.common import db
from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.common.privileges import dropped_privileges
from hades.config.loader import load_config

logger = logging.getLogger(__package__)


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
    setup_cli_logging(parser.prog, args)
    load_config(args.config, True)
    try:
        engine = db.get_engine()
        engine.dispose()
        agent_pwd = pwd.getpwnam(constants.AGENT_USER)
        agent_grp = grp.getgrnam(constants.AGENT_GROUP)
        with dropped_privileges(agent_pwd, agent_grp):
            check_database(agent_pwd.pw_name, (db.radacct, db.radpostauth))
        engine.dispose()
        portal_pwd = pwd.getpwnam(constants.PORTAL_USER)
        portal_grp = grp.getgrnam(constants.PORTAL_GROUP)
        with dropped_privileges(portal_pwd, portal_grp):
            check_database(portal_pwd.pw_name,
                           (db.radacct, db.radpostauth, db.radusergroup))
        engine.dispose()
        radius_pwd = pwd.getpwnam(constants.RADIUS_USER)
        radius_grp = grp.getgrnam(constants.RADIUS_GROUP)
        with dropped_privileges(radius_pwd, radius_grp):
            check_database(radius_pwd.pw_name,
                           (db.radacct, db.radgroupcheck, db.radgroupreply,
                            db.radpostauth, db.radreply, db.radusergroup))
    except DBAPIError:
        return os.EX_TEMPFAIL
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
