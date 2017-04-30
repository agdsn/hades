import sys

from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.loader import load_config
from hades.deputy import run_event_loop


def main():
    parser = ArgumentParser(
        description='Provides a DBus API to perform privileged operations',
        parents=[common_parser])
    args = parser.parse_args()
    load_config(args.config)
    run_event_loop()


if __name__ == '__main__':
    sys.exit(main())
