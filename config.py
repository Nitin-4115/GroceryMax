# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Loads variables from .env

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

    # New database URI format for SQLAlchemy
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{os.environ.get('DB_USER')}:"
        f"{os.environ.get('DB_PASSWORD')}@{os.environ.get('DB_HOST')}/"
        f"{os.environ.get('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False