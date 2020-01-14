from hades.config.loader import load_config
from hades.config.options import FlaskOption
# noinspection PyUnresolvedReferences
from hades.portal import app, views

application = app


def configure_app():
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
