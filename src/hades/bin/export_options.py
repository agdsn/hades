import argparse
import os
import sys

from hades.common.cli import (
    ArgumentParser, parser as parent_parser, setup_cli_logging,
)
from hades.config.base import ConfigError
from hades.config.export import export
from hades.config.loader import load_config, print_config_error


def main():
    parser = ArgumentParser(description='Export options as shell variables',
                            epilog='Python sequence and mapping types will '
                                   'only be exported, if the destination '
                                   'format support it',
                            parents=[parent_parser])
    parser.add_argument('--format', choices=('systemd', 'posix', 'bash', 'ksh',
                                             'zsh'),
                        default='systemd', help='Export format.')
    parser.add_argument('file', type=argparse.FileType('wb'), metavar='FILE',
                        default='-', nargs='?',
                        help='Output destination (default: stdout)')
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
