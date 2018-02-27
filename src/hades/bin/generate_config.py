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
from hades.config.generate import ConfigGenerator
from hades.config.loader import load_config

logger = logging.getLogger()
template_dir = pathlib.Path(constants.templatedir).resolve()


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


def path(value: str) -> pathlib.Path:
    p = pathlib.Path(value)
    if p.is_absolute():
        raise argparse.ArgumentTypeError("Path must be relative")
    try:
        (template_dir / p).resolve().relative_to(template_dir)
    except ValueError:
        argparse.ArgumentTypeError("Must be within {}".format(template_dir))
    return p


def main():
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
    parser.add_argument(dest='source', type=path, metavar='SOURCE',
                        help="Template file name or template directory name")
    parser.add_argument(dest='destination', metavar='DESTINATION', nargs='?',
                        help="Destination file or directory (default is stdout"
                             "for files; required for directories)")
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config)
    generator = ConfigGenerator(template_dir, config, args.mode, args.group)
    source = template_dir / args.source
    if source.is_dir():
        generator.generate_directory(args.source, args.destination)
    elif source.is_file():
        generator.generate_file(args.source, args.destination)
    else:
        logger.critical("No such file or directory %s in %s",
                        args.source, template_dir)
        return os.EX_NOINPUT


if __name__ == '__main__':
    sys.exit(main())
