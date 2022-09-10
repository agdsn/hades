#!/usr/bin/env python3
"""Run the Hades DBus daemon for privileged operations.

"""
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config import ConfigError, load_config, print_config_error
from hades.deputy.server import run_event_loop


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description='Provides a DBus API to perform privileged operations',
        parents=[common_parser])
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    try:
        load_config(args.config)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    run_event_loop()
    # never reached, but to satisfy mypy. probably fixed in https://github.com/python/mypy/pull/13575
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
