#!/usr/bin/env python3
"""Generate configuration files from templates and directories.
"""
import argparse
import grp
import logging
import os
import pathlib
import stat
import sys

from hades import constants
from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.config.base import ConfigError
from hades.config.generate import ConfigGenerator, GeneratorError
from hades.config.loader import load_config, print_config_error

logger = logging.getLogger()


def mode(value: str) -> int:
    value = int(value, 8)
    if value & ~0o7777:
        raise argparse.ArgumentTypeError("Illegal mode: 0{:03o}".format(value))
    if stat.S_ISUID & value:
        raise argparse.ArgumentTypeError("setuid bit may not be set")
    return value


def group(value: str) -> grp.struct_group:
    try:
        return grp.getgrnam(value)
    except KeyError:
        pass
    try:
        return grp.getgrgid(int(value))
    except (KeyError, ValueError):
        raise argparse.ArgumentTypeError("No such group: {}".format(value))


def relative_path(value: str) -> pathlib.PurePath:
    p = pathlib.PurePath(value)
    if p.is_absolute():
        raise argparse.ArgumentTypeError("Path must be relative")
    return p


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(parents=[common_parser])
    parser.add_argument('-m', '--mode', type=mode, default=0o0750,
                        help="The mode of created files and directories. Only"
                             "read, write, setgid, and sticky bits are "
                             "respected. Files are never executable or setgid. "
                             "Directories are always executable if they are "
                             "readable and optionally have setgid and sticky "
                             "bits set.")
    parser.add_argument('-g', '--group', type=group, default=None,
                        metavar='GROUP | GID',
                        help="The group of created files and directories.")
    parser.add_argument(dest='source', type=relative_path, metavar='SOURCE',
                        help="Template file name or template directory name")
    parser.add_argument(dest='destination', metavar='DESTINATION', nargs='?',
                        help="Destination file or directory (default is stdout"
                             "for files; required for directories)")
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
    search_path = constants.templatepath.split(os.path.pathsep)
    generator = ConfigGenerator(search_path, config, args.mode,
                                args.group)
    try:
        generator.generate(args.source, args.destination)
    except GeneratorError as e:
        logger.critical(str(e))
        return os.EX_DATAERR


if __name__ == '__main__':
    sys.exit(main())
