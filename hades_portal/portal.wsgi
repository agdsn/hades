from flask import request
import random
import string
from hades_portal import app, babel, sqlalchemy

app.config.from_pyfile("config.py")
app.config['SECRET_KEY'] = ''.join(random.choice(string.printable)
                                   for i in range(64))
babel.init_app(app)
sqlalchemy.init_app(app)

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


import hades_portal.views


application = app


if __name__ == '__main__':
    app.run(debug=True)