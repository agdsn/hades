import importlib.resources

from flask import Flask
from flask_babel import Babel

from hades import constants
from hades.config.loader import get_config
from hades.portal.session import NullSessionInterface

path = importlib.resources.files(__package__)
app = Flask(
    __name__,
    static_url_path="/assets",
    template_folder=str(path / "templates"),
    static_folder=str(path / "assets"),
)
app.session_interface = NullSessionInterface()
babel = Babel(app)


@app.context_processor
def add_globals():
    """Add the configure constants and the config object as global variable to
    the web portal's Jinja2 templates"""
    return {'constants': constants, 'config': get_config(runtime_checks=True)}
