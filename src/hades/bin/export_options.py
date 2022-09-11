#!/usr/bin/env python3
"""Export Hades options in a format suitable for various tools, such as shells.

Exports the subset of Hades options, that can be represented in the target
format in a format that can be sourced by the target tool. POSIX shells or
systemd don't support arrays for example, whereas advanced shells like ``bash``
or ``zsh`` do.
"""
import argparse
import logging
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.common.exc import handles_setup_errors
from hades.config import load_config
from hades.config.export import export


logger = logging.getLogger(__name__)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description='Export options as shell variables',
                            epilog='Python sequence and mapping types will '
                                   'only be exported, if the destination '
                                   'format support it',
                            parents=[common_parser])
    parser.add_argument('--format', choices=('systemd', 'posix', 'bash', 'ksh',
                                             'zsh'),
                        default='systemd', help='Export format.')
    parser.add_argument('file', type=argparse.FileType('wb'), metavar='FILE',
                        default='-', nargs='?',
                        help='Output destination (default: stdout)')
    return parser


@handles_setup_errors(logger)
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config)
    export(config, args.format, args.file)
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
