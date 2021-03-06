"""Configuration variables"""
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    """Application configuration variables."""
    LOG_TO_STDOUT = os.getenv("LOG_TO_STDOUT")
    SECRET_KEY = os.getenv("SECRET_KEY", "test dev key")
    LANGUAGE_API_KEY = os.getenv("LANGUAGE_API_KEY")
    POSTS_PER_PAGE = 10
    LANGUAGES = ["en", "it"]
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://'

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or "sqlite:///" + os.path.join(
        basedir, "app.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")

    # Email Notifications
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = os.getenv("MAIL_PORT", 25)
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") is not None
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    ADMINS = ["somebody@example.com"]
