from flask import Flask
from flask.ext.babel import Babel
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
babel = Babel(app)
sqlalchemy = SQLAlchemy(app)
