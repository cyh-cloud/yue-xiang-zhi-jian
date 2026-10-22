# -*- coding: utf-8 -*-
"""T11 视图等价性测试用的探针：在隔离库上打接口，把响应 JSON 打到 stdout。

单独成文件的理由与 db_schema_probe.py 相同：DB_PATH 在 import db_connection 时
就定下来了，同进程里改 os.environ 不会改变它，只会让用例悄悄打到
data/yuexiang.db 上把真实数据写脏。所以本探针由 tests/test_cross_domain_views.py
以子进程方式调用，用环境变量 YUEXIANG_DB 把库指到临时目录。

探针自己造确定性种子数据，然后打 5 个接口，把响应体原样打印（JSON）。
"""

import json
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, BACKEND)


def main():
    provided_db = os.environ.get("YUEXIANG_DB")
    tmp = None if provided_db else tempfile.mkdtemp(prefix="t11_probe_")
    db = provided_db or os.path.join(tmp, "yuexiang.db")
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    shutil.copy(os.path.join(REPO, "data", "yuexiang.db"), db)

    from db_connection import get_connection
    from db_init import init_db
    from db_domains import reviews as reviews_db

    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM job_applications WHERE user_id = 'student_demo'")
    conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
    conn.execute("DELETE FROM job_listings WHERE title LIKE '__T11%'")
    conn.execute("DELETE FROM models_3d WHERE title LIKE '__T11%'")
    conn.commit()
    conn.execute(
        "INSERT INTO job_listings (title, company, salary, requirements, description,"
        " location, category, enterprise_id, review_status)"
        " VALUES ('__T11岗位__', '测试公司', '5K', '[]', 'desc', '广州',"
        " '电商运营', 'enterprise_demo', 'approved')")
    job_id = conn.execute(
        "SELECT id FROM job_listings WHERE title = '__T11岗位__'").fetchone()[0]
    conn.execute(
        "INSERT INTO job_applications (user_id, job_id) VALUES ('student_demo', ?)",
        (job_id,))
    conn.execute(
        "INSERT INTO resumes (user_id, title, region, education, work_years, phone,"
        " email, self_eval, skills, experience)"
        " VALUES ('student_demo', '__T11简历__', '广州', '本科', '3', '138', 'a@b.c',"
        " '自评', '技能', '[]')")
    conn.execute(
        "INSERT INTO models_3d (title, description, craft_type, file_path, file_name,"
        " file_size, teacher_id, review_status, is_published)"
        " VALUES ('__T11模型__', 'd', '', 'p.glb', 'p.glb', 1, 'teacher_demo',"
        " 'pending', 0)")
    # 三样「别的东西」，让边界用例不必 skip
    if not conn.execute(
            "SELECT 1 FROM job_listings WHERE enterprise_id != 'enterprise_demo' LIMIT 1"
    ).fetchone():
        conn.execute(
            "INSERT INTO job_listings (title, company, salary, requirements,"
            " description, location, category, enterprise_id, review_status)"
            " VALUES ('__T11别家岗位__', '别家公司', '4K', '[]', 'desc', '深圳',"
            " '电商运营', 'other_enterprise_demo', 'pending')")
    if not conn.execute(
            "SELECT 1 FROM notifications WHERE user_id != 'student_demo' LIMIT 1"
    ).fetchone():
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, content)"
            " VALUES ('teacher_demo', 'system', '__T11别人的通知__', '正文')")
    if not conn.execute("SELECT 1 FROM assignments LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO assignments (title, description, direction)"
            " VALUES ('__T11作业__', 'desc', 'ecommerce')")
    conn.commit()
    model_id = conn.execute(
        "SELECT id FROM models_3d WHERE title = '__T11模型__'").fetchone()[0]
    conn.close()
    review_id = reviews_db.create_content_review("model_3d", model_id, "teacher_demo")

    from app import app
    client = app.test_client()

    def login(username, password="123456"):
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json")
        return json.loads(response.data).get("session_id")

    enterprise = login("enterprise_demo")
    admin = login("admin_demo", "admin123")
    teacher = login("teacher_demo")
    student = login("student_demo")

    out = {
        "home_stats": json.loads(client.get("/api/home/stats").data),
        "enterprise_applications": json.loads(client.get(
            "/api/enterprise/applications",
            headers={"X-Session-Id": enterprise}).data),
        "enterprise_stats": json.loads(client.get(
            "/api/enterprise/stats", headers={"X-Session-Id": enterprise}).data),
        "admin_reviews": json.loads(client.get(
            "/api/admin/reviews?content_type=model_3d",
            headers={"X-Session-Id": admin}).data),
        "teacher_trainings": json.loads(client.get(
            "/api/teacher/trainings", headers={"X-Session-Id": teacher}).data),
        "review_id": review_id,
    }

    # 批改链路：自造一条提交，打批改接口，回读分数与通知
    conn = get_connection()
    conn.execute(
        "DELETE FROM assignment_submissions WHERE assignment_id IN "
        "(SELECT id FROM assignments WHERE title = '__T11批改作业__')"
    )
    conn.execute("DELETE FROM assignments WHERE title = '__T11批改作业__'")
    conn.execute(
        "INSERT INTO assignments (title, description, direction) "
        "VALUES ('__T11批改作业__', 'desc', 'ecommerce')"
    )
    assignment = conn.execute(
        "SELECT id FROM assignments WHERE title = '__T11批改作业__'"
    ).fetchone()
    conn.execute(
        "INSERT INTO assignment_submissions (assignment_id, student_id, content)"
        " VALUES (?, 'student_demo', '{}')", (assignment["id"],))
    conn.commit()
    submission = conn.execute(
        "SELECT id, student_id, assignment_id FROM assignment_submissions"
        " ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    response = client.post(
        "/api/teacher/assignments/grade",
        data=json.dumps({"submission_id": submission["id"], "score": 91,
                         "feedback": "T11 批改"}),
        content_type="application/json", headers={"X-Session-Id": teacher})
    out["grade"] = json.loads(response.data)
    conn = get_connection()
    row = conn.execute(
        "SELECT score, feedback, status FROM assignment_submissions WHERE id = ?",
        (submission["id"],)).fetchone()
    note = conn.execute(
        "SELECT title, content, link_type, link_id FROM notifications"
        " WHERE user_id = ? AND type = 'grade' ORDER BY id DESC LIMIT 1",
        (submission["student_id"],)).fetchone()
    conn.execute("DELETE FROM assignment_submissions WHERE id = ?", (submission["id"],))
    conn.execute("DELETE FROM assignments WHERE id = ?", (assignment["id"],))
    conn.execute("DELETE FROM notifications WHERE type = 'grade' AND content = '得分：91'")
    conn.commit()
    conn.close()
    out["graded_row"] = dict(row) if row else None
    out["grade_note"] = dict(note) if note else None

    # 通知单条已读：命中与未命中两条分支
    conn = get_connection()
    mine = conn.execute(
        "SELECT id FROM notifications WHERE user_id = 'student_demo' AND is_read = 0"
        " ORDER BY id DESC LIMIT 1").fetchone()
    if not mine:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, content)"
            " VALUES ('student_demo', 'system', 'T11 已读测试', '正文')")
        conn.commit()
        mine = conn.execute(
            "SELECT id FROM notifications WHERE user_id = 'student_demo'"
            " ORDER BY id DESC LIMIT 1").fetchone()
    other = conn.execute(
        "SELECT id FROM notifications WHERE user_id != 'student_demo'"
        " ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    out["own_notification_id"] = mine["id"]
    out["other_notification_id"] = other["id"] if other else None
    out["read_one_hit"] = _post_read_one(client, student, mine["id"])
    out["read_one_miss"] = _post_read_one(client, student, 999999)
    out["read_one_other"] = (
        _post_read_one(client, student, other["id"]) if other else None)

    # 企业删岗位：审核记录跟着消失
    conn = get_connection()
    conn.execute(
        "INSERT INTO job_listings (title, company, salary, requirements, description,"
        " location, category, enterprise_id, review_status)"
        " VALUES ('__T11待删岗位__', '测试公司', '5K', '[]', 'desc', '广州',"
        " '电商运营', 'enterprise_demo', 'pending')")
    conn.commit()
    doomed = conn.execute(
        "SELECT id FROM job_listings WHERE title = '__T11待删岗位__'").fetchone()[0]
    conn.close()
    reviews_db.create_content_review("job", doomed, "enterprise_demo")
    response = client.delete(
        "/api/enterprise/jobs/%d" % doomed, headers={"X-Session-Id": enterprise})
    out["delete_job"] = {"status": response.status_code,
                         "body": json.loads(response.data)}
    conn = get_connection()
    out["doomed_job_rows"] = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE id = ?", (doomed,)).fetchone()[0]
    conn.close()
    out["doomed_review"] = reviews_db.get_review_by_content("job", doomed)

    print(json.dumps(out, ensure_ascii=False, sort_keys=True, default=str))
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)


def _post_read_one(client, session, ref_id):
    response = client.post(
        "/api/notifications/read-one",
        data=json.dumps({"user_id": "student_demo", "source": "notifications",
                         "ref_id": str(ref_id)}),
        content_type="application/json", headers={"X-Session-Id": session})
    return {"status": response.status_code, "body": json.loads(response.data)}


if __name__ == "__main__":
    main()
