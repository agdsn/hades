from hades.config.loader import load_config
# noinspection PyUnresolvedReferences
from hades.portal import app, views


app.config.update(load_config())
application = app


def main():
    return app.run(debug=True)


if __name__ == '__main__':
    main()
