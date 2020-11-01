from flask import Flask
from flask_babel import Babel
from pkg_resources import resource_filename

from hades import constants
from hades.config.loader import get_config
from hades.portal.session import NullSessionInterface

app = Flask(
    __name__,
    static_url_path='/assets',
    template_folder=resource_filename(__package__, 'templates'),
    static_folder=resource_filename(__package__, 'assets'),
)
app.session_interface = NullSessionInterface()
babel = Babel(app)


@app.context_processor
def add_globals():
    """Add the configure constants and the config object as global variable to
    the web portal's Jinja2 templates"""
    return {'constants': constants, 'config': get_config(runtime_checks=True)}
