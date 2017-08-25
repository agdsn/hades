import sys

from hades.common.cli import (
    ArgumentParser, parser as common_parser, setup_cli_logging,
)
from hades.config.loader import load_config
from hades.deputy.server import run_event_loop


def main():
    parser = ArgumentParser(
        description='Provides a DBus API to perform privileged operations',
        parents=[common_parser])
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    load_config(args.config)
    run_event_loop()


if __name__ == '__main__':
    sys.exit(main())
