import os
from urllib.parse import urlparse

import click
from flask import Flask, request, send_from_directory

from app.errors import register_error_handlers
from app.extensions import cors, db, migrate
from app.routes import api_bp
from app.routes.auth import bp as auth_bp
from app.routes.care_requests import bp as care_requests_bp
from app.routes.caregiver_applications import bp as caregiver_applications_bp
from app.routes.caregivers import bp as caregivers_bp
from app.routes.catalog import bp as catalog_bp
from app.routes.conversations import bp as conversations_bp
from app.routes.family import bp as family_bp
from app.routes.notifications import bp as notifications_bp
from app.routes.payments import bp as payments_bp
from app.utils.http import success

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False


def create_app(config_override=None):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    load_dotenv(os.path.join(project_root, ".env"), override=True, encoding="utf-8-sig")

    from app.config import Config

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
    cors.init_app(app, resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}})
    register_cors_fallback(app)

    from app import models  # noqa: F401

    register_error_handlers(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp, name="auth_compat")
    app.register_blueprint(catalog_bp, name="catalog_compat")
    app.register_blueprint(family_bp, name="family_compat")
    app.register_blueprint(care_requests_bp, name="care_requests_compat")
    app.register_blueprint(caregivers_bp, name="caregivers_compat")
    app.register_blueprint(caregiver_applications_bp, name="caregiver_applications_compat")
    app.register_blueprint(notifications_bp, name="notifications_compat")
    app.register_blueprint(conversations_bp, name="conversations_compat")
    app.register_blueprint(payments_bp, name="payments_compat")

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


def register_cors_fallback(app):
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if not origin or not is_allowed_cors_origin(app, origin):
            return response

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers",
            "Authorization, Content-Type",
        )
        response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response


def is_allowed_cors_origin(app, origin):
    if origin in app.config["CORS_ORIGINS"] or "*" in app.config["CORS_ORIGINS"]:
        return True

    if not app.config["CORS_ALLOW_LOCALHOST"]:
        return False

    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
