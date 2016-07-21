import os.path

from flask import Flask
from flask_babel import Babel

from hades import constants
from hades.portal.session import NullSessionInterface

app = Flask(
    __name__,
    static_url_path='assets',
    template_folder=os.path.join(constants.TEMPLATESDIR, 'portal'),
    static_folder=constants.ASSETSDIR,
)
app.session_interface = NullSessionInterface()
babel = Babel(app)
