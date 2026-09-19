from __future__ import annotations

from flask import Flask, jsonify, request

from app.agri_skills import install_default_agri_services
from app.agri_skills.messaging_provider import AgriMessagingProvider
from app.agri_skills.routes import agri_skills_bp
from app.auth.routes import auth_bp
from app.config import build_config
from app.courses.routes import student_courses_bp
from app.db import close_db, init_db
from app.ecommerce_training.routes import (
    ecommerce_training_bp,
    register_ecommerce_training_error_handlers,
)
from app.enterprise_console import (
    enterprise_console_bp,
    install_default_enterprise_services,
    register_enterprise_console_error_handlers,
)
from app.enterprise_console.messaging_provider import (
    EnterpriseMessagingProvider,
)
from app.government_console import install_default_government_services
from app.government_console.routes import government_bp
from app.handcraft_inheritance import install_default_handcraft_services
from app.handcraft_inheritance.routes import (
    handcraft_inheritance_bp,
    register_handcraft_inheritance_error_handlers,
)
from app.job_matching import (
    install_default_job_matching_services,
    job_matching_bp,
)
from app.messaging.routes import messages_bp
from app.messaging.source_provider import register_messaging_source_provider
from app.onboarding.routes import onboarding_bp
from app.profiles.routes import student_profile_bp
from app.session_manager import load_session
from app.tags.routes import interest_tags_bp
from app.teacher_console import (
    install_default_teacher_console_services,
    register_teacher_console_error_handlers,
    teacher_console_bp,
    teacher_media_bp,
)


PROTECTED_API_PREFIXES = (
    "/api/student",
    "/api/teacher",
    "/api/enterprise",
    "/api/job-matching",
    "/api/government",
    "/api/admin",
    "/api/onboarding",
    "/api/messages",
    "/api/agri-skills",
    "/api/ecommerce-training",
    "/api/handcraft-inheritance",
)

INTERNAL_API_PREFIXES = (
    "/api/handcraft-inheritance/internal/",
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(build_config())
    if test_config:
        app.config.update(test_config)

    install_default_teacher_console_services(app)
    install_default_agri_services(app)
    install_default_handcraft_services(app)
    install_default_enterprise_services(app)
    install_default_job_matching_services(app)
    install_default_government_services(app)
    existing_messaging_provider = app.extensions.get("messaging_source_provider")
    register_messaging_source_provider(
        app,
        AgriMessagingProvider(existing_messaging_provider),
    )
    register_messaging_source_provider(
        app,
        EnterpriseMessagingProvider(),
    )
    app.teardown_appcontext(close_db)

    @app.get("/api/health")
    def health():
        return jsonify(success=True, status="ok")

    @app.before_request
    def require_active_portal_session():
        path = request.path.rstrip("/") or "/"
        if any(
            path.startswith(prefix)
            for prefix in INTERNAL_API_PREFIXES
        ):
            return None
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
    app.register_blueprint(agri_skills_bp)
    app.register_blueprint(ecommerce_training_bp)
    app.register_blueprint(enterprise_console_bp)
    app.register_blueprint(job_matching_bp)
    app.register_blueprint(handcraft_inheritance_bp)
    app.register_blueprint(government_bp)
    app.register_blueprint(teacher_console_bp)
    app.register_blueprint(teacher_media_bp)
    register_ecommerce_training_error_handlers(app)
    register_enterprise_console_error_handlers(app)
    register_handcraft_inheritance_error_handlers(app)
    register_teacher_console_error_handlers(app)

    with app.app_context():
        init_db()

    return app
