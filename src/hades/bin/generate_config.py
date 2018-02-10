import argparse
import logging
import os
import pathlib
import sys

from hades import constants
from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.config.generate import ConfigGenerator
from hades.config.loader import load_config

logger = logging.getLogger()
template_dir = pathlib.Path(constants.templatedir).resolve()


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
    parser.add_argument(dest='source', type=path, metavar='SOURCE',
                        help="Template file name or template directory name")
    parser.add_argument(dest='destination', metavar='DESTINATION', nargs='?',
                        help="Destination file or directory (default is stdout"
                             "for files; required for directories)")
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    config = load_config(args.config)
    generator = ConfigGenerator(template_dir, config)
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
