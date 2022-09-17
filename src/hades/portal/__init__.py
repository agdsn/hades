import importlib.resources

from flask import Flask
from flask_babel import Babel

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
