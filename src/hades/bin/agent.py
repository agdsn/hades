#!/usr/bin/env python3
"""Hades frontend for the ``celery`` command.

Loads the Hades configuration and transfers control to Celery.
"""
import argparse
import inspect
import logging
import sys
import typing
from argparse import Action

import celery.apps.worker
import celery.concurrency.solo

from hades import constants
from hades.agent import create_app
from hades.common.cli import (
    ArgumentParser,
    common_parser,
    reset_cli_logging,
    setup_cli_logging,
)
from hades.common.exc import handles_setup_errors
from hades.config import load_config


logger = logging.getLogger(__name__)


class Formatter(argparse.HelpFormatter):
    def add_usage(
        self,
        usage: str,
        actions: typing.Iterable[Action],
        groups: typing.Iterable,
        prefix: typing.Optional[str] = None,
    ) -> None:
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


@handles_setup_errors(logger=logger)
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config)
    app = create_app(config)
    log_level = logging.root.level
    reset_cli_logging()
    worker: celery.apps.worker.Worker = app.Worker(
        app=app,
        pool_cls=celery.concurrency.solo.TaskPool,
        hostname=config.HADES_CELERY_WORKER_HOSTNAME,
        statedb=config.HADES_CELERY_STATE_DB,
        pidfile=args.pid_file,
        loglevel=log_level
    )
    worker.start()
    return typing.cast(int, worker.exitcode)


if __name__ == '__main__':
    sys.exit(main())
