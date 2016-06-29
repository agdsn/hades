import argparse
import collections
import logging
import os
import re
import sys

import netaddr

from hades.common.cli import ArgumentParser, parser as parent_parser
from hades.config.loader import load_config

logger = logging.getLogger('hades.config.export')
shell_types = (int, str, bool, netaddr.IPAddress, netaddr.IPNetwork)
pattern = re.compile(r'([^a-zA-Z0-9_])')
replacement = r'\\\1'


def escape(value):
    """
    Escape a string for shell argument use.
    shlex.quote breaks unfortunately on certain strings
    """
    return pattern.sub(replacement, str(value))


def main():
    parser = ArgumentParser(description='Export options as shell '
                                                 'variables',
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
    config = load_config(args.config)
    mappings = args.format in ('bash', 'ksh', 'zsh')
    sequences = args.format in ('bash', 'ksh', 'zsh')
    for name, value in config.items():
        name = escape(name)
        if isinstance(value, shell_types):
            print("{}={}".format(name, escape(value)), file=args.file)
        elif isinstance(value, collections.Mapping) and mappings:
            if args.format == 'bash':
                print("declare -A {}".format(name), file=args.file)
            if args.format in ('ksh', 'zsh'):
                print("typeset -A {}".format(name), file=args.file)
            value = ' '.join("[{}]={}".format(escape(k), escape(v))
                             for k, v in value.items()
                             if isinstance(k, shell_types) and
                             isinstance(v, shell_types))
            print("{}=({})".format(name, value), file=args.file)
        elif isinstance(value, collections.Sequence) and sequences:
            value = ' '.join(escape(v) for v in value
                             if isinstance(v, shell_types))
            print("{}=({})".format(name, value), file=args.file)
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
