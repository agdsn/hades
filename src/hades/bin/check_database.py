import contextlib
import logging
import os
import pwd
import sys
from typing import Iterable

from sqlalchemy import Table, exists, null, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from hades import constants
from hades.common import db
from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.common.privileges import dropped_privileges
from hades.config.loader import load_config

logger = logging.getLogger(__package__)


def check_database(engine: Engine, user_name: pwd.struct_passwd,
                   tables: Iterable[Table]):
    logger.info("Checking database access as user %s", user_name)
    try:
        conn = engine.connect()
    except DBAPIError as e:
        logger.critical("Could not connect to database as %s: %s",
                        user_name, e)
        raise
    with contextlib.closing(conn):
        for table in tables:
            try:
                check_table(conn, table)
            except DBAPIError as e:
                logger.critical("Query check for table %s as user %s failed: "
                                "%s", table.name, user_name, e)
                raise


def check_table(conn, table):
    conn.execute(select([exists(select([null()]).select_from(table))])).scalar()


def main():
    parser = ArgumentParser(parents=[common_parser])
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config, runtime_checks=True)
    try:
        engine = db.create_engine(config, poolclass=NullPool)
        agent_pwd = pwd.getpwnam(constants.AGENT_USER)
        with dropped_privileges(agent_pwd):
            check_database(engine, agent_pwd.pw_name,
                           (db.radacct, db.radpostauth))
        portal_pwd = pwd.getpwnam(constants.PORTAL_USER)
        with dropped_privileges(portal_pwd):
            check_database(engine, portal_pwd.pw_name,
                           (db.radacct, db.radpostauth, db.radusergroup))
        radius_pwd = pwd.getpwnam(constants.RADIUS_USER)
        with dropped_privileges(radius_pwd):
            check_database(engine, radius_pwd.pw_name,
                           (db.radacct, db.radgroupcheck, db.radgroupreply,
                            db.radpostauth, db.radreply, db.radusergroup))
    except DBAPIError:
        return os.EX_TEMPFAIL
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
