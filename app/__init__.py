import os

import click
from flask import Flask, send_from_directory

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import cors, db, migrate
from app.routes import api_bp
from app.utils.http import success

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False


def create_app(config_override=None):
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    upload_folder = app.config["UPLOAD_FOLDER"]
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.abspath(upload_folder)
        app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(upload_folder, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from app import models  # noqa: F401

    register_error_handlers(app)
    app.register_blueprint(api_bp)

    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        return success({"status": "ok"})

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-db")
    @click.option("--reset", is_flag=True, help="Drop and recreate tables before seeding.")
    def seed_db_command(reset):
        from app.services.seed import seed_database

        if reset:
            click.confirm("This will drop all tables. Continue?", abort=True)
        db.create_all()
        result = seed_database(reset=reset)
        click.echo(result)

    return app
