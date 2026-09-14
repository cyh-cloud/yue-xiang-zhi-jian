from __future__ import annotations

from flask import Flask, jsonify

from app.auth.routes import auth_bp
from app.config import build_config
from app.db import close_db, init_db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(build_config())
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)

    @app.get("/api/health")
    def health():
        return jsonify(success=True, status="ok")

    app.register_blueprint(auth_bp)

    with app.app_context():
        init_db()

    return app
