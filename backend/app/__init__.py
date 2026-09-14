from __future__ import annotations

from flask import Flask, jsonify, request

from app.auth.routes import auth_bp
from app.config import build_config
from app.db import close_db, init_db
from app.session_manager import load_session


PROTECTED_API_PREFIXES = (
    "/api/student",
    "/api/teacher",
    "/api/enterprise",
    "/api/government",
    "/api/admin",
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(build_config())
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)

    @app.get("/api/health")
    def health():
        return jsonify(success=True, status="ok")

    @app.before_request
    def require_active_portal_session():
        path = request.path.rstrip("/") or "/"
        if any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in PROTECTED_API_PREFIXES
        ):
            load_session(required=True, allowed_states={"active"})

    app.register_blueprint(auth_bp)

    with app.app_context():
        init_db()

    return app
