from pathlib import Path

from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    with app.app_context():
        from app.services.auth import init_auth_db

        init_auth_db()

    from app.routes import bp

    app.register_blueprint(bp)
    return app
