import os
import sys

from hades.common.cli import ArgumentParser, parser as common_parser
from hades.common.maintenance import cleanup
from hades.config.loader import load_config


def main():
    parser = ArgumentParser(parents=[common_parser],
                            description="Cleanup old authentication attempts "
                                        "and sessions")
    args = parser.parse_args()
    load_config(args.config)
    cleanup()
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
