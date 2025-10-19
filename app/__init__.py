# app/__init__.py
from flask import Flask
from config import Config
from .models import db
from flask_migrate import Migrate
from flask_sock import Sock
import datetime

sock = Sock()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)
    sock.init_app(app)

    # Import and register the blueprint
    from . import routes
    app.register_blueprint(routes.bp)

    # --- ADD THIS FUNCTION ---
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.datetime.now().year}
    # -------------------------

    return app