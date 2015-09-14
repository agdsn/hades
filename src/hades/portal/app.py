from flask import request

from hades.config.loader import get_config
from hades.portal import app, babel

app.config.from_object(get_config())
babel.init_app(app)

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


from hades.portal import views

application = app


if __name__ == '__main__':
    app.run(debug=True)
