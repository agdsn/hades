from hades.config.loader import load_config
# noinspection PyUnresolvedReferences
from hades.portal import app, views


app.config.from_object(load_config(category='flask'))
application = app


def main():
    return app.run(debug=True)


if __name__ == '__main__':
    main()
