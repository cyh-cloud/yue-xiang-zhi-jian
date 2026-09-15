from __future__ import annotations

from flask import Flask, jsonify, request

from app.agri_skills import install_default_agri_services
from app.agri_skills.messaging_provider import AgriMessagingProvider
from app.auth.routes import auth_bp
from app.config import build_config
from app.courses.routes import student_courses_bp
from app.db import close_db, init_db
from app.messaging.routes import messages_bp
from app.messaging.source_provider import register_messaging_source_provider
from app.onboarding.routes import onboarding_bp
from app.profiles.routes import student_profile_bp
from app.session_manager import load_session
from app.tags.routes import interest_tags_bp


PROTECTED_API_PREFIXES = (
    "/api/student",
    "/api/teacher",
    "/api/enterprise",
    "/api/government",
    "/api/admin",
    "/api/onboarding",
    "/api/messages",
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(build_config())
    if test_config:
        app.config.update(test_config)

    install_default_agri_services(app)
    existing_messaging_provider = app.extensions.get("messaging_source_provider")
    register_messaging_source_provider(
        app,
        AgriMessagingProvider(existing_messaging_provider),
    )
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
    app.register_blueprint(student_courses_bp)
    app.register_blueprint(interest_tags_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(student_profile_bp)
    app.register_blueprint(messages_bp)

    with app.app_context():
        init_db()

    return app
