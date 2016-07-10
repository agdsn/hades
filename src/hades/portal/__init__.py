from flask import Flask
from flask_babel import Babel

from hades.portal.session import NullSessionInterface

app = Flask(__name__)
app.session_interface = NullSessionInterface()
babel = Babel(app)
