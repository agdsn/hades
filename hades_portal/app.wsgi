from flask import request
from hades_portal import app, babel, sqlalchemy

app.config.from_pyfile("config.py")
babel.init_app(app)
sqlalchemy.init_app(app)

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


import hades_portal.views


application = app


if __name__ == '__main__':
    app.run(debug=True)