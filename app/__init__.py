import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
import os

from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from app.config import Config

app = Flask(__name__)
app.config.from_object(Config)

login = LoginManager(app)
login.login_view = "login"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

mail = Mail(app)

from app import errors, routes, models  # noqa: F402,F401


if not app.debug:
    if app.config["MAIL_SERVER"]:
        # If set, we assume emails should be sent for errors

        auth = None
        if app.config["MAIL_USERNAME"] or app.config["MAIL_PASSWORD"]:
            auth = (app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])

        secure = None
        if app.config["MAIL_USE_TLS"]:
            secure = ()

        mail_handler = SMTPHandler(
            mailhost=(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]),
            fromaddr=f"no-reply@{app.config['MAIL_SERVER']}",
            toaddrs=app.config["ADMINS"],
            subject="Microblog Failure",
            credentials=auth,
            secure=secure,
        )

        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

    # File handler set in all (non-debug) circumstances
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = RotatingFileHandler(
        filename="logs/microblog.log", backupCount=10, maxBytes=10240
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    # Finally, configure stream handler (default)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Microblog started.")
