#!/usr/bin/env python3
"""Run the Hades captive-portal Flask WSGI application in debug mode if executed
as a command-line application.

Also export the app object for use by WSGI application servers, if imported as
an ordinary Python module.
"""
import os
import sys

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config import load_config
from hades.portal.views import configure_app



def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Run development server of captive-portal",
        parents=[common_parser],
    )
    parser.add_argument(
        "--host", "-h", default="127.0.0.1", help="The address to bind to."
    )
    parser.add_argument(
        "--port", "-p", default=5000, help="The port to bind to."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug mode."
    )
    parser.add_argument(
        "-t", "--threads", default=4, help="Number of threads."
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    app = configure_app(load_config(args.config))
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        load_dotenv=False,
        threaded=args.threads,
    )
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
else:
    try:
        import uwsgi
    except ImportError:
        pass
    else:
        application = configure_app()
