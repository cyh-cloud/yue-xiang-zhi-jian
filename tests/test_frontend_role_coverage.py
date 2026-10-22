# -*- coding: utf-8 -*-
"""Vue SPA role maps must cover every role in the backend capability table."""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from core.permissions import ROLES  # noqa: E402


def _read(*parts):
    with open(os.path.join(REPO_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _object_keys(source, name):
    marker = "%s: Record<" % name
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for offset in range(brace, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                body = source[brace + 1:offset]
                return set(re.findall(r"^\s*([a-z_]+):\s*\{", body, re.MULTILINE))
    raise AssertionError("找不到 %s" % name)


class FrontendRoleCoverageTest(unittest.TestCase):
    def test_every_backend_role_has_one_central_fact_record(self):
        source = _read("frontend", "src", "shared", "roles.ts")
        keys = _object_keys(source, "ROLE_FACTS")
        self.assertEqual(keys, set(ROLES))
        for role in ROLES:
            with self.subTest(role=role):
                self.assertRegex(
                    source,
                    r"\b%s:\s*\{[^}]*defaultPath:\s*\"/" % re.escape(role),
                )

    def test_every_backoffice_role_has_a_shell_configuration(self):
        source = _read("frontend", "src", "layouts", "BackofficeLayout.vue")
        keys = _object_keys(source, "ROLE_CONFIG")
        self.assertEqual(keys, set(ROLES) - {"student"})

    def test_role_labels_and_options_come_from_the_central_fact_record(self):
        public_shell = _read(
            "frontend", "src", "components", "public", "PublicShell.vue"
        )
        admin_users = _read("frontend", "src", "views", "admin", "AdminUsersView.vue")
        self.assertIn("labelForRole(session.role)", public_shell)
        self.assertIn("ROLE_OPTIONS", admin_users)
        self.assertNotIn("const roleLabels", public_shell)
        self.assertNotIn("const ROLE_OPTIONS", admin_users)

    def test_only_self_service_roles_are_registerable(self):
        source = _read("frontend", "src", "api", "types.ts")
        marker = "export interface RegisterPayload"
        start = source.index(marker)
        body = source[start:source.index("}", start)]
        self.assertIn('role: "student" | "teacher" | "enterprise"', body)


if __name__ == "__main__":
    unittest.main()
