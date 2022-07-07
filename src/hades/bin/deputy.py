#!/usr/bin/env python3
"""Run the Hades DBus daemon for privileged operations.

"""
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config.base import ConfigError
from hades.config.loader import load_config, print_config_error
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


if __name__ == '__main__':
    sys.exit(main())
