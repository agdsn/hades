#!/usr/bin/env python3
"""Run the Hades captive-portal Flask WSGI application in debug mode if executed
as a command-line application.

Also export the app object for use by WSGI application servers, if imported as
an ordinary Python module.
"""
from hades.config import FlaskOption, load_config
# noinspection PyUnresolvedReferences
from hades.portal import app, views

application = app


def configure_app() -> None:
    app.config.from_object(load_config(option_cls=FlaskOption))


def main() -> int:
    configure_app()
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
