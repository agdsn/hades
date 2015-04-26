from flask import Flask, request
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy

app = Flask("Hades")
babel = Babel(app)
sqlalchemy = SQLAlchemy(app)
