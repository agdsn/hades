import os
import sys

from hades.common.cli import ArgumentParser, parser as common_parser
from hades.common.maintenance import refresh
from hades.config.loader import load_config


def main():
    parser = ArgumentParser(parents=[common_parser],
                            description="Refresh materialized views and notify "
                                        "daemons if their configuration has "
                                        "changed.")
    args = parser.parse_args()
    load_config(args.config)
    refresh()
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
