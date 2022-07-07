#!/usr/bin/env python3
"""Export Hades options in a format suitable for various tools, such as shells.

Exports the subset of Hades options, that can be represented in the target
format in a format that can be sourced by the target tool. POSIX shells or
systemd don't support arrays for example, whereas advanced shells like ``bash``
or ``zsh`` do.
"""
import argparse
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config.base import ConfigError
from hades.config.export import export
from hades.config.loader import load_config, print_config_error


def create_parser():
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


def main():
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    export(config, args.format, args.file)
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
