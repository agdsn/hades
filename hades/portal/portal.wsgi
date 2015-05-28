import os
import random
import string

from flask import request

import hades
from hades.portal import app, babel

config_path = os.path.join(os.path.dirname(hades.__file__), "config.py")
app.config.from_pyfile(config_path)
# Generate a secret key
app.config['SECRET_KEY'] = ''.join(random.choice(string.printable)
                                   for i in range(64))
babel.init_app(app)

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


from hades.portal import views

application = app


if __name__ == '__main__':
    app.run(debug=True)
