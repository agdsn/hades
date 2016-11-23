import os
import sys

from hades import constants
from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.generate import ConfigGenerator
from hades.config.loader import load_config


def main():
    parser = ArgumentParser(parents=[common_parser])
    parser.add_argument(dest='source', metavar='SOURCE',
                        help="Template file name or template directory name")
    parser.add_argument(dest='destination', metavar='DESTINATION', nargs='?',
                        help="Destination file or directory (default is stdout"
                             "for files; required for directories)")
    args = parser.parse_args()
    config = load_config(args.config)
    template_dir = constants.templatesdir
    generator = ConfigGenerator(template_dir, config)
    source_path = os.path.join(template_dir, args.source)
    if os.path.isdir(source_path):
        generator.from_directory(args.source, args.destination)
    elif os.path.isfile(source_path):
        if args.destination is None:
            generator.from_file(args.source, sys.stdout)
        else:
            with open(args.destination, 'w', encoding='utf-8') as f:
                generator.from_file(args.source, f)
    else:
        print("No such file or directory {} in {}".format(args.source,
                                                          template_dir),
              file=sys.stderr)
        return os.EX_NOINPUT


if __name__ == '__main__':
    sys.exit(main())
