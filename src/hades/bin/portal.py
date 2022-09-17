#!/usr/bin/env python3
"""Run the Hades captive-portal Flask WSGI application in debug mode if executed
as a command-line application.

Also export the app object for use by WSGI application servers, if imported as
an ordinary Python module.
"""
import typing

from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.config import Config, FlaskOption, load_config
# noinspection PyUnresolvedReferences
from hades.portal import app, views

application = app


def configure_app(config: typing.Optional[Config] = None) -> None:
    if config is None:
        config = load_config(runtime_checks=True)
    app.config.from_object(config.of_type(FlaskOption))


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Run development server of captive-portal",
        parents=[common_parser],
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    configure_app(load_config(args.config))
    app.run(debug=True)
    return 0


if __name__ == '__main__':
    main()
else:
    try:
        import uwsgi
    except ImportError:
        pass
    else:
        configure_app()
