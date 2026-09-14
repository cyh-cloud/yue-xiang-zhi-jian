from __future__ import annotations

import re


USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,31}$")
SELF_REGISTER_ROLES = {"student", "teacher"}


def validate_registration(payload: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    role = payload.get("role")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    confirmation = str(payload.get("confirm_password", ""))
    name = str(payload.get("name", "")).strip()

    if role not in SELF_REGISTER_ROLES:
        errors["role"] = "该角色不支持自助注册"
    if not username:
        errors["username"] = "用户名不能为空"
    elif not USERNAME_PATTERN.fullmatch(username):
        errors["username"] = "用户名格式不正确"
    if not password:
        errors["password"] = "密码不能为空"
    elif len(password) < 8:
        errors["password"] = "密码长度不能少于8位"
    if confirmation != password:
        errors["confirm_password"] = "两次输入的密码不一致"
    if not name:
        errors["name"] = "姓名不能为空"
    return errors
