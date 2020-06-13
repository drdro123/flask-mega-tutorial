import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
import os

from elasticsearch import Elasticsearch
from flask import current_app, Flask, request
from flask_babel import Babel, lazy_gettext as _l
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_mail import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from config import Config

login = LoginManager()
login.login_view = "auth.login"
login.login_message = _l("Please log in to access this page.")
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
boostrap = Bootstrap()
moment = Moment()
babel = Babel()


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(current_app.config["LANGUAGES"])


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

    # Elastic Search
    app.elasticsearch = (
        Elasticsearch(hosts=[app.config["ELASTICSEARCH_URL"]])
        if app.config["ELASTICSEARCH_URL"]
        else None
    )

    # Plugins
    login.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    boostrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)

    # Blueprints
    from app.auth import bp as auth_bp  # noqa: F402,F401

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.errors import bp as errors_bp  # noqa: F402,F401

    app.register_blueprint(errors_bp)

    from app.main import bp as main_bp  # noqa: F402,F401

    app.register_blueprint(main_bp)

    if not app.debug and not app.testing:
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

        if app.config["LOG_TO_STDOUT"]:
            # Stream handler for when hosted on ephemeral filesystems (e.g. Heroku)
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
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

    return app


from app import models  # noqa: F402,F401
