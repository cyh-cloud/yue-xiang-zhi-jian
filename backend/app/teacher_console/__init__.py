from app.teacher_console.providers import (
    DatabaseTeacherCourseProvider,
    install_default_teacher_console_services,
)
from app.teacher_console.routes import (
    register_teacher_console_error_handlers,
    teacher_console_bp,
    teacher_media_bp,
)


__all__ = [
    "DatabaseTeacherCourseProvider",
    "install_default_teacher_console_services",
    "register_teacher_console_error_handlers",
    "teacher_console_bp",
    "teacher_media_bp",
]
