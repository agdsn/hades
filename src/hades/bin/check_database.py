#!/usr/bin/env python3
"""Check the status of the Hades database.

Try to select data as the different hades users from the database to check if
the database is running and accessible.
"""
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
from hades.config.base import ConfigError
from hades.config.loader import load_config, print_config_error

logger = logging.getLogger('hades.bin.check_database')


def check_database(engine: Engine, user: pwd.struct_passwd,
                   tables: Iterable[Table]):
    """Check a set of tables as a user.

    :param engine: The SQLAlchemy engine
    :param user: The user to switch to
    :param tables: The tables to check
    :raises DBAPIError: if errors occur.
    """
    logger.info("Checking database access as user %s", user.pw_name)
    try:
        conn = engine.connect()
    except DBAPIError as e:
        logger.critical("Could not connect to database as %s: %s",
                        user.pw_name, exc_info=e)
        raise
    with contextlib.closing(conn):
        for table in tables:
            try:
                check_table(conn, table)
            except DBAPIError as e:
                logger.critical("Query check for table %s as user %s failed: "
                                "%s", table.name, user.pw_name, exc_info=e)
                raise


def check_table(conn, table):
    """Perform :sql:`SELECT NULL` on a given table."""
    conn.execute(select([exists(select([null()]).select_from(table))])).scalar()


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(parents=[common_parser])
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    try:
        engine = db.create_engine(config, poolclass=NullPool)
        agent_pwd: pwd.struct_passwd = pwd.getpwnam(constants.AGENT_USER)
        with dropped_privileges(agent_pwd):
            check_database(engine, agent_pwd,
                           (db.radacct, db.radpostauth))
        portal_pwd: pwd.struct_passwd = pwd.getpwnam(constants.PORTAL_USER)
        with dropped_privileges(portal_pwd):
            check_database(engine, portal_pwd,
                           (db.radacct, db.radpostauth, db.radusergroup))
        radius_pwd: pwd.struct_passwd = pwd.getpwnam(constants.RADIUS_USER)
        with dropped_privileges(radius_pwd):
            check_database(engine, radius_pwd,
                           (db.radacct, db.radgroupcheck, db.radgroupreply,
                            db.radpostauth, db.radreply, db.radusergroup))
    except DBAPIError:
        return os.EX_TEMPFAIL
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
