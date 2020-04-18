from flask import Flask
from app.config import Config

app = Flask(__name__)

from app import routes  # noqa: F402,F401

app.config.from_object(Config)
