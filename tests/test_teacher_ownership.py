# -*- coding: utf-8 -*-
"""Teacher ownership isolation and its schema migration."""

import io
import os
import sqlite3
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from db_domains import courses as courses_db  # noqa: E402
from db_domains import reviews  # noqa: E402
from db_domains import teaching  # noqa: E402
from db_domains.users import register_user  # noqa: E402
from db_seed_accounts import seed_demo_accounts  # noqa: E402
from db_schema import apply_schema  # noqa: E402


class TeacherOwnershipMigrationTest(unittest.TestCase):
    def test_fresh_demo_seed_assigns_roster_rows_to_the_demo_teacher(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        apply_schema(cursor)
        seed_demo_accounts(cursor)

        rows = cursor.execute(
            "SELECT id, teacher_id FROM students ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(row["id"], row["teacher_id"]) for row in rows],
            [("STU001", "teacher_demo"), ("STU002", "teacher_demo")],
        )
        conn.close()

    def test_legacy_rows_gain_teacher_scope_and_demo_data_stays_usable(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        apply_schema(cursor)
        cursor.execute(
            "INSERT INTO users (username, password_hash, name, role) "
            "VALUES ('teacher_demo', 'x', '演示教师', 'teacher')"
        )
        cursor.execute("DROP TABLE students")
        cursor.execute(
            "CREATE TABLE students ("
            "id TEXT PRIMARY KEY, user_id TEXT DEFAULT '', name TEXT NOT NULL, "
            "class_name TEXT DEFAULT '', direction TEXT DEFAULT '', "
            "progress INTEGER DEFAULT 0, status TEXT DEFAULT 'active', "
            "created_at TEXT DEFAULT '', extra TEXT NOT NULL DEFAULT '{}')"
        )
        cursor.execute(
            "INSERT INTO students (id, user_id, name) "
            "VALUES ('STU900', 'student_demo', '演示学员')"
        )
        cursor.execute("DROP TABLE announcements")
        cursor.execute(
            "CREATE TABLE announcements ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "content TEXT NOT NULL, category TEXT DEFAULT '通知', "
            "pinned INTEGER DEFAULT 0, created_at TEXT DEFAULT '', "
            "extra TEXT NOT NULL DEFAULT '{}')"
        )
        cursor.execute(
            "INSERT INTO announcements (title, content) VALUES ('演示公告', '正文')"
        )

        apply_schema(cursor)
        apply_schema(cursor)

        student_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(students)")
        }
        announcement_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(announcements)")
        }
        self.assertIn("teacher_id", student_cols)
        self.assertIn("teacher_id", announcement_cols)
        self.assertEqual(
            cursor.execute(
                "SELECT teacher_id FROM students WHERE id = 'STU900'"
            ).fetchone()[0],
            "teacher_demo",
        )
        self.assertEqual(
            cursor.execute(
                "SELECT teacher_id FROM announcements WHERE title = '演示公告'"
            ).fetchone()[0],
            "teacher_demo",
        )
        conn.close()


class TeacherOwnershipApiTest(unittest.TestCase):
    TEACHER_A = "teacher_demo"
    TEACHER_B = "__t_owner_teacher"
    STUDENT = "__t_owner_student"
    PREFIX = "__T_OWNER_"

    def setUp(self):
        from app import app

        self.app = app
        self.app.config["TESTING"] = True
        self.client = app.test_client()
        register_user(self.TEACHER_B, "123456", "隔离教师", "teacher")
        self.session_a = self._login(self.TEACHER_A)
        self.session_b = self._login(self.TEACHER_B)
        self.headers_a = {"X-Session-Id": self.session_a}
        self.headers_b = {"X-Session-Id": self.session_b}

    def tearDown(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, file_path FROM course_materials "
            "WHERE course_id IN (SELECT id FROM courses WHERE title LIKE ?)",
            (self.PREFIX + "%",),
        ).fetchall()
        for row in rows:
            path = os.path.join(REPO_ROOT, row["file_path"])
            if os.path.exists(path):
                os.remove(path)
        conn.execute(
            "DELETE FROM assignment_submissions WHERE student_id = ?",
            (self.STUDENT,),
        )
        conn.execute(
            "DELETE FROM assignments WHERE title LIKE ?",
            (self.PREFIX + "%",),
        )
        conn.execute(
            "DELETE FROM notifications WHERE title LIKE ? OR content LIKE ?",
            (self.PREFIX + "%", self.PREFIX + "%"),
        )
        conn.execute(
            "DELETE FROM announcements WHERE title LIKE ?",
            (self.PREFIX + "%",),
        )
        course_ids = [
            row[0] for row in conn.execute(
                "SELECT id FROM courses WHERE title LIKE ?",
                (self.PREFIX + "%",),
            )
        ]
        conn.commit()
        conn.close()
        for course_id in course_ids:
            reviews.delete_reviews_for('course', course_id)
        conn = get_connection()
        conn.execute(
            "DELETE FROM courses WHERE title LIKE ?",
            (self.PREFIX + "%",),
        )
        conn.execute(
            "DELETE FROM students WHERE name LIKE ?",
            (self.PREFIX + "%",),
        )
        conn.execute(
            "DELETE FROM user_sessions WHERE user_id IN (?, ?)",
            (self.TEACHER_A, self.TEACHER_B),
        )
        conn.execute(
            "DELETE FROM users WHERE username IN (?, ?)",
            (self.TEACHER_B, self.STUDENT),
        )
        conn.commit()
        conn.close()

    def _login(self, username, password="123456"):
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.get_json()["session_id"]

    def _create_student(self):
        response = self.client.post(
            "/api/teacher/students/add",
            json={
                "name": self.PREFIX + "学员",
                "new_username": self.STUDENT,
                "new_password": "123456",
            },
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.get_json()["student_id"]

    def test_roster_detail_and_mutations_are_teacher_scoped(self):
        student_id = self._create_student()

        visible_a = self.client.get(
            "/api/teacher/students", headers=self.headers_a
        ).get_json()["students"]
        visible_b = self.client.get(
            "/api/teacher/students", headers=self.headers_b
        ).get_json()["students"]
        self.assertIn(student_id, [row["id"] for row in visible_a])
        self.assertNotIn(student_id, [row["id"] for row in visible_b])

        detail = self.client.get(
            "/api/teacher/students/%s" % student_id,
            headers=self.headers_b,
        ).get_json()
        self.assertFalse(detail["success"])
        self.assertEqual(detail["message"], "未找到学员")

        for method, payload in (
            ("PUT", {"name": self.PREFIX + "越权改名"}),
            ("DELETE", None),
        ):
            response = self.client.open(
                "/api/teacher/students/%s" % student_id,
                method=method,
                json=payload,
                headers=self.headers_b,
            )
            self.assertFalse(response.get_json()["success"])

        linked = self.client.post(
            "/api/teacher/students/%s/link" % student_id,
            json={"username": ""},
            headers=self.headers_b,
        )
        self.assertFalse(linked.get_json()["success"])

    def test_announcements_dashboard_analytics_and_trainings_are_scoped(self):
        student_id = self._create_student()
        announcement = self.client.post(
            "/api/teacher/announcements",
            json={
                "title": self.PREFIX + "公告",
                "content": "只给本教师的学员",
            },
            headers=self.headers_a,
        ).get_json()
        self.assertTrue(announcement["success"])

        announcements_b = self.client.get(
            "/api/teacher/announcements", headers=self.headers_b
        ).get_json()["announcements"]
        self.assertNotIn(announcement["id"], [row["id"] for row in announcements_b])
        deleted = self.client.delete(
            "/api/teacher/announcements/%d" % announcement["id"],
            headers=self.headers_b,
        ).get_json()
        self.assertFalse(deleted["success"])

        dashboard_b = self.client.get(
            "/api/teacher/dashboard", headers=self.headers_b
        ).get_json()["dashboard"]["stats"]
        analytics_b = self.client.get(
            "/api/teacher/analytics", headers=self.headers_b
        ).get_json()["analytics"]
        self.assertEqual(dashboard_b["total_students"], 0)
        self.assertEqual(analytics_b["roster_count"], 0)

        assignment_id = teaching.get_or_create_training_assignment(
            self.PREFIX + "产品", "live"
        )
        submission_id, _ = teaching.save_live_training(
            assignment_id,
            self.STUDENT,
            {"product": self.PREFIX + "产品", "script": "测试话术"},
            80,
        )
        trainings_b = self.client.get(
            "/api/teacher/trainings", headers=self.headers_b
        ).get_json()["trainings"]
        self.assertNotIn(submission_id, [row["id"] for row in trainings_b])

        denied_grade = self.client.post(
            "/api/teacher/assignments/grade",
            json={
                "submission_id": submission_id,
                "score": 99,
                "feedback": "越权批改",
            },
            headers=self.headers_b,
        )
        self.assertFalse(denied_grade.get_json()["success"])
        conn = get_connection()
        score = conn.execute(
            "SELECT score FROM assignment_submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()[0]
        conn.close()
        self.assertIsNone(score)

        allowed_grade = self.client.post(
            "/api/teacher/assignments/grade",
            json={
                "submission_id": submission_id,
                "score": 88,
                "feedback": "本人批改",
            },
            headers=self.headers_a,
        )
        self.assertTrue(allowed_grade.get_json()["success"])

    def test_student_announcement_feed_only_returns_the_linked_teachers_items(self):
        self._create_student()
        announcement = self.client.post(
            "/api/teacher/announcements",
            json={
                "title": self.PREFIX + "学员公告",
                "content": "只给本人名册的学员",
            },
            headers=self.headers_a,
        ).get_json()
        self.assertTrue(announcement["success"])

        anonymous = self.client.get("/api/student/announcements").get_json()
        self.assertTrue(anonymous["success"])
        self.assertNotIn(
            announcement["id"],
            [row["id"] for row in anonymous["announcements"]],
        )

        other_teacher = self.client.get(
            "/api/student/announcements",
            headers=self.headers_b,
        ).get_json()
        self.assertNotIn(
            announcement["id"],
            [row["id"] for row in other_teacher["announcements"]],
        )

        student_session = self._login(self.STUDENT)
        linked_student = self.client.get(
            "/api/student/announcements",
            headers={"X-Session-Id": student_session},
        ).get_json()
        self.assertIn(
            announcement["id"],
            [row["id"] for row in linked_student["announcements"]],
        )

    def test_super_admin_announcements_remain_platform_wide(self):
        self._create_student()
        admin_session = self._login("admin_demo", "admin123")
        announcement = self.client.post(
            "/api/teacher/announcements",
            json={
                "title": self.PREFIX + "平台公告",
                "content": "面向全部教师名册",
            },
            headers={"X-Session-Id": admin_session},
        ).get_json()
        self.assertTrue(announcement["success"])

        teacher_b = self.client.get(
            "/api/teacher/announcements",
            headers=self.headers_b,
        ).get_json()["announcements"]
        self.assertIn(
            announcement["id"],
            [row["id"] for row in teacher_b],
        )

        student_session = self._login(self.STUDENT)
        student_feed = self.client.get(
            "/api/student/announcements",
            headers={"X-Session-Id": student_session},
        ).get_json()["announcements"]
        self.assertIn(
            announcement["id"],
            [row["id"] for row in student_feed],
        )

        conn = get_connection()
        notification = conn.execute(
            "SELECT 1 FROM notifications "
            "WHERE user_id = ? AND type = 'announcement' AND content = ?",
            (self.STUDENT, self.PREFIX + "平台公告"),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(notification)

    def test_course_and_material_writes_require_the_owning_teacher(self):
        course = self.client.post(
            "/api/teacher/courses",
            json={"title": self.PREFIX + "课程", "description": "正文"},
            headers=self.headers_a,
        ).get_json()
        course_id = course["id"]

        courses_b = self.client.get(
            "/api/teacher/courses", headers=self.headers_b
        ).get_json()["courses"]
        self.assertNotIn(course_id, [row["id"] for row in courses_b])
        for method, payload in (
            ("PUT", {"title": self.PREFIX + "越权课程"}),
            ("DELETE", None),
        ):
            response = self.client.open(
                "/api/teacher/courses/%d" % course_id,
                method=method,
                json=payload,
                headers=self.headers_b,
            )
            self.assertEqual(response.status_code, 403)

        self.assertEqual(
            self.client.get(
                "/api/teacher/courses/%d/materials" % course_id,
                headers=self.headers_b,
            ).status_code,
            403,
        )
        upload = self.client.post(
            "/api/teacher/courses/%d/materials" % course_id,
            data={"file": (io.BytesIO(b"material"), "notes.txt")},
            content_type="multipart/form-data",
            headers=self.headers_b,
        )
        self.assertEqual(upload.status_code, 403)

        upload_a = self.client.post(
            "/api/teacher/courses/%d/materials" % course_id,
            data={"file": (io.BytesIO(b"material"), "notes.txt")},
            content_type="multipart/form-data",
            headers=self.headers_a,
        )
        self.assertEqual(upload_a.status_code, 200, upload_a.data)
        material_id = upload_a.get_json()["id"]
        denied_delete = self.client.delete(
            "/api/teacher/materials/%d" % material_id,
            headers=self.headers_b,
        )
        self.assertEqual(denied_delete.status_code, 403)
        allowed_delete = self.client.delete(
            "/api/teacher/materials/%d" % material_id,
            headers=self.headers_a,
        )
        self.assertTrue(allowed_delete.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
