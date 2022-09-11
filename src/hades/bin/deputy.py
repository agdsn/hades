#!/usr/bin/env python3
"""Run the Hades DBus daemon for privileged operations.

"""
import logging
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config import load_config
from hades.common.exc import handles_setup_errors
from hades.deputy.server import run_event_loop


logger = logging.getLogger(__name__)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description='Provides a DBus API to perform privileged operations',
        parents=[common_parser])
    return parser


@handles_setup_errors(logger=logger)
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    load_config(args.config)
    run_event_loop()
    # never reached, but to satisfy mypy. probably fixed in https://github.com/python/mypy/pull/13575
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
