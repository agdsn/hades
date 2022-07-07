#!/usr/bin/env python3
"""Hades frontend for the ``celery`` command.

Loads the Hades configuration and transfers control to Celery.
"""
import argparse
import inspect
import logging
import os
import sys

import celery.apps.worker

from hades import constants
from hades.agent import create_app
from hades.common.cli import (
    ArgumentParser,
    common_parser,
    reset_cli_logging,
    setup_cli_logging,
)
from hades.config import ConfigError, load_config, print_config_error


class Formatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        actions = list(actions)
        actions.append(argparse.Action([], dest='worker_options',
                                       metavar='worker options', nargs='?'))
        super().add_usage(usage, actions, groups, prefix)


def create_parser() -> ArgumentParser:
    description = inspect.cleandoc(
        """
        Run the celery command configured for Hades.

        All arguments except -c/--config and -A/--app are passed to the Celery
        celery as is. You may not provide the -A/--app argument.
        """
    )
    parser = ArgumentParser(
        description=description,
        formatter_class=Formatter,
        parents=[common_parser],
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default=f"{constants.pkgrunstatedir}/agent/agent.pid",
    )
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
    app = create_app(config)
    log_level = logging.root.level
    reset_cli_logging()
    worker: celery.apps.worker.Worker = app.Worker(
        app=app,
        hostname=config.HADES_CELERY_WORKER_HOSTNAME,
        statedb=config.HADES_CELERY_STATE_DB,
        pidfile=args.pid_file,
        loglevel=log_level
    )
    worker.start()
    return worker.exitcode


if __name__ == '__main__':
    sys.exit(main())
