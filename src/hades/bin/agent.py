#!/usr/bin/env python3
"""Hades frontend for the ``celery`` command.

Loads the Hades configuration and transfers control to Celery.
"""
import argparse
import inspect
import os
import sys

from hades.agent import app
from hades.common.cli import (
    ArgumentParser, parser as common_parser, reset_cli_logging,
    setup_cli_logging,
)
from hades.config.base import ConfigError
from hades.config.loader import load_config, print_config_error
from hades.config.options import CeleryOption


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
    parser = ArgumentParser(description=description,
                            formatter_class=Formatter,
                            parents=[common_parser])
    parser.add_argument('-A', '--app', dest='app', help=argparse.SUPPRESS)
    parser.add_argument('command')
    return parser


def main() -> int:
    parser = create_parser()
    args, argv = parser.parse_known_args()
    setup_cli_logging(parser.prog, args)
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    reset_cli_logging()
    app.config_from_object(config.of_type(CeleryOption))
    if args.app:
        parser.error("You may not provide the -A/--app worker argument")
    argv.insert(0, parser.prog)
    argv.insert(1, args.command)
    argv.extend(['-A', 'hades.bin.agent:app'])
    if args.command == 'worker':
        argv.extend(['-n', config.HADES_CELERY_WORKER_HOSTNAME])
    return app.start(argv)


if __name__ == '__main__':
    sys.exit(main())
