from flask import Flask
from flask_babel import Babel
from pkg_resources import resource_filename

from hades.portal.session import NullSessionInterface

app = Flask(
    __name__,
    static_url_path='assets',
    template_folder=resource_filename(__package__, 'templates'),
    static_folder=resource_filename(__package__, 'assets'),
)
app.session_interface = NullSessionInterface()
babel = Babel(app)
