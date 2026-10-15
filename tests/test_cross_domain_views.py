# -*- coding: utf-8 -*-
"""T11：5 处跨域查询改走视图，13 处直连 SQL 收进数据层。

测试 seam 是 API 层（Flask test client）。断言分三类：

1. **视图等价性**：改造前后响应结构逐字段一致。口径不是「字段还在」而是
   「不多不少」，所以断言的是键集合本身，不是逐个 assertIn；
2. **行为未变**：批改仍写分并给学员发通知、单条已读命中/未命中/他人的三条
   分支、企业删岗位连带删审核记录；
3. **结构收敛**：`DELETE FROM content_reviews` 在仓库里只剩一处，且域路由层
   零 `get_connection()`。

⚠️ 为什么跑子进程：DB_PATH 在 import db_connection 时就定下来了，同进程里改
os.environ 不会改变它，只会让用例悄悄打到 data/yuexiang.db 上把真实数据写脏
（与 test_db_schema.py / test_db_infrastructure.py 同一套理由）。所以打接口的
用例都调 backend/t11_view_probe.py 那个子进程，父进程只做不碰库的静态检查。
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

PROBE = os.path.join(BACKEND, "t11_view_probe.py")

# 改造前（直连 SQL）四个接口下发的键集合，逐字段锁死。
APPLICATION_KEYS = [
    'applicant_bio', 'applicant_email', 'applicant_name', 'applicant_phone',
    'applied_at', 'id', 'job_id', 'job_title', 'resume_education',
    'resume_email', 'resume_experience', 'resume_phone', 'resume_region',
    'resume_self_eval', 'resume_skills', 'resume_title', 'resume_updated_at',
    'resume_work_years', 'status', 'user_id']
STATS_KEYS = {'total_jobs', 'pending_jobs', 'total_applications'}
HOME_KEYS = {'farmers', 'courses', 'jobs'}
MODEL_DETAIL_KEYS = [
    'craft_type', 'created_at', 'description', 'extra', 'file_name', 'file_path',
    'file_size', 'id', 'is_published', 'review_status', 'teacher_id',
    'thumbnail_url', 'title']


class ViewEquivalenceTest(unittest.TestCase):
    """5 处视图改造后，响应结构与改造前一致。"""

    @classmethod
    def setUpClass(cls):
        # 只跑一次探针：15 个用例共用同一份响应。每个用例各跑一遍会把
        # 2.5MB 的库复制 15 次，还会和其它测试抢同一个 SQLite 文件的 WAL 锁。
        tmp = tempfile.mkdtemp(prefix="t11_views_")
        cls.addClassCleanup(_rmtree, tmp)
        db = os.path.join(tmp, "yuexiang.db")
        env = dict(os.environ)
        env["YUEXIANG_DB"] = db
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run([sys.executable, PROBE], cwd=REPO, env=env,
                                capture_output=True)
        assert result.returncode == 0, (
            "探针失败：\n%s\n%s" % (result.stdout.decode("utf-8", "replace"),
                                   result.stderr.decode("utf-8", "replace")))
        cls.data = json.loads(result.stdout.decode("utf-8"))

    def test_enterprise_applications_keys_are_unchanged(self):
        rows = self.data["enterprise_applications"]["applications"]
        mine = [a for a in rows if a["job_title"] == "__T11岗位__"]
        self.assertEqual(len(mine), 1)
        self.assertEqual(sorted(mine[0]), APPLICATION_KEYS)
        # 四个来源表的值都要真的取到，不是 JOIN 丢了某张表
        self.assertEqual(mine[0]["resume_title"], "__T11简历__")
        self.assertEqual(mine[0]["resume_education"], "本科")
        self.assertEqual(mine[0]["resume_work_years"], "3")
        self.assertEqual(mine[0]["resume_skills"], "技能")
        self.assertEqual(mine[0]["resume_self_eval"], "自评")
        self.assertEqual(mine[0]["user_id"], "student_demo")
        self.assertTrue(mine[0]["applied_at"])
        self.assertTrue(mine[0]["applicant_name"])

    def test_enterprise_applications_are_ordered_by_applied_at_desc(self):
        rows = self.data["enterprise_applications"]["applications"]
        stamps = [a["applied_at"] for a in rows]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_enterprise_stats_keys_are_unchanged(self):
        self.assertEqual(set(self.data["enterprise_stats"]["stats"]), STATS_KEYS)

    def test_home_stats_keys_are_unchanged(self):
        self.assertEqual(set(self.data["home_stats"]["stats"]), HOME_KEYS)

    def test_home_stats_counts_are_real_numbers(self):
        stats = self.data["home_stats"]["stats"]
        for key in HOME_KEYS:
            self.assertIsInstance(stats[key], int, key)
            self.assertGreaterEqual(stats[key], 0, key)

    def test_review_detail_keeps_every_model_column(self):
        reviews = self.data["admin_reviews"]["reviews"]
        row = next(r for r in reviews if r["id"] == self.data["review_id"])
        self.assertEqual(sorted(row["detail"]), MODEL_DETAIL_KEYS)
        self.assertEqual(row["detail"]["id"], row["content_id"])
        self.assertEqual(row["detail"]["review_status"], "pending")
        self.assertEqual(row["detail"]["is_published"], 0)

    def test_trainings_list_shape_is_unchanged(self):
        """实训列表的形状不变（库里可能恰好没有提交，此时只校验容器类型）。"""
        trainings = self.data["teacher_trainings"]["trainings"]
        self.assertIsInstance(trainings, list)
        self.assertIsInstance(self.data["teacher_trainings"]["pending_regrade"], int)
        self.assertEqual(self.data["teacher_trainings"]["pending_regrade"],
                         sum(1 for t in trainings if t["regrade_needed"]))
        for row in trainings:
            for key in ("id", "student_id", "student_name", "assignment_id",
                        "assignment_title", "kind", "product", "attempts", "score",
                        "rule_score", "script", "transcript", "meta", "script_len",
                        "feedback", "status", "status_label", "submitted_at",
                        "graded_at", "regrade_needed"):
                self.assertIn(key, row)

    def test_grading_still_writes_score_and_notifies_the_student(self):
        self.assertTrue(self.data["grade"]["success"])
        self.assertEqual(self.data["graded_row"],
                         {"score": 91, "feedback": "T11 批改", "status": "graded"})
        note = self.data["grade_note"]
        self.assertIsNotNone(note, "批改必须给学员发通知")
        self.assertEqual(note["link_type"], "assignment")
        self.assertIn("91", note["content"])

    def test_read_one_hit_marks_the_notification(self):
        self.assertEqual(self.data["read_one_hit"],
                         {"status": 200, "body": {"success": True}})

    def test_read_one_miss_is_404(self):
        self.assertEqual(self.data["read_one_miss"]["status"], 404)
        self.assertFalse(self.data["read_one_miss"]["body"]["success"])

    def test_read_one_rejects_another_users_notification(self):
        """只允许标自己的：拿别人的通知 id 乱标必须失败。"""
        if self.data["other_notification_id"] is None:
            self.skipTest("库里没有别人的通知")
        self.assertEqual(self.data["read_one_other"]["status"], 404)

    def test_deleting_a_job_removes_its_review(self):
        self.assertEqual(self.data["delete_job"]["status"], 200)
        self.assertTrue(self.data["delete_job"]["body"]["success"])
        self.assertEqual(self.data["doomed_job_rows"], 0)
        self.assertIsNone(self.data["doomed_review"])


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


class SingleEntryForContentReviewsDeletionTest(unittest.TestCase):
    """验收标准 3：`DELETE FROM content_reviews` 在仓库里只出现一次。"""

    def _hits(self):
        """扫产品代码与测试里真正送进 SQL 执行的跨域删除语句。

        判据与 test_db_domain_boundaries.py 一致：只收 conn.execute(...) 的首个
        字符串实参，注释与文档字符串里提到表名不算。仓库根散落的历史一次性脚本
        不属于本次收敛范围，故只扫 backend/、tests/ 与根级 test_*.py。
        """
        import ast

        roots = [os.path.join(REPO, "backend")]
        for name in sorted(os.listdir(REPO)):
            full = os.path.join(REPO, name)
            if os.path.isdir(full) and name == "tests":
                roots.append(full)
            elif os.path.isfile(full) and name.startswith("test_") and name.endswith(".py"):
                roots.append(full)

        offenders = []
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for filename in sorted(filenames):
                    if not filename.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, filename)
                    rel = os.path.relpath(path, REPO).replace(os.sep, "/")
                    with io.open(path, encoding="utf-8") as handle:
                        source = handle.read()
                    tree = ast.parse(source, filename=rel)
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Call):
                            continue
                        func = node.func
                        called = func.attr if isinstance(func, ast.Attribute) else (
                            func.id if isinstance(func, ast.Name) else "")
                        if called != "execute" or not node.args:
                            continue
                        first = node.args[0]
                        if not (isinstance(first, ast.Constant)
                                and isinstance(first.value, str)):
                            continue
                        if re.search(r"DELETE\s+FROM\s+content_reviews",
                                     first.value, re.IGNORECASE):
                            offenders.append("%s:%d" % (rel, node.lineno))
        return offenders


    def test_only_reviews_module_deletes_content_reviews(self):
        offenders = self._hits()
        # reviews.py 的两行：按 (类型, id) 删的 delete_reviews_for，与按 id 删的
        # delete_review_by_id。同属 reviews 域（content_reviews 的属主），
        # 是全仓库唯一出现这条 SQL 的地方。
        # 按文件聚合：行号会随注释增减漂移，钉死它只会制造无意义的重跑。
        files = sorted(set(o.split(":")[0] for o in offenders))
        self.assertEqual(
            files, ["backend/db_domains/reviews.py"],
            "DELETE FROM content_reviews 必须只在 db_domains/reviews.py 出现，"
            "实际：%s" % files)
        self.assertEqual(len(offenders), 2,
                         "reviews 域只应有两条删除出口（按类型+id、按 id）：%s" % offenders)

    def test_every_content_domain_deletes_reviews_through_one_entry(self):
        """每个要删审核记录的内容域都调 reviews 域的删除入口，而不是自己写 SQL。

        T15 补上案例（content.py 的 delete_case），因为案例要过审才对学员端可见
        （db_domains.resources.get_success_cases），删正文时必须一并清掉审核记录，
        否则审核列表里留下看不到内容的孤儿卡片。
        """
        callers = []
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, "backend")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, REPO).replace(os.sep, "/")
                with io.open(path, encoding="utf-8") as handle:
                    for lineno, line in enumerate(handle, 1):
                        stripped = line.strip()
                        # 只收真正的调用行：注释里提到这个名字不算调用点
                        if (stripped.startswith("delete_reviews_for(")
                                or stripped.startswith("reviews.delete_reviews_for(")
                                or stripped.startswith("reviews_db.delete_reviews_for(")):
                            callers.append("%s:%d" % (rel, lineno))
        # 按文件聚合：行号会随注释增减漂移，钉死它只会制造无意义的重跑。
        self.assertEqual(
            sorted(set(o.split(":")[0] for o in callers)),
            ["backend/db_domains/content.py",
             "backend/db_domains/courses.py",
             "backend/db_domains/procurements.py",
             "backend/domains/enterprise/routes.py"],
            "delete_reviews_for 的调用点变了：%s" % sorted(callers))
        self.assertEqual(len(callers), 5,
                         "课程删两处 + 求购删一处 + 企业删岗位一处 + 案例删一处，共五个调用点：%s" % sorted(callers))


class DomainRoutesNeverTouchTheConnectionFactoryTest(unittest.TestCase):
    """验收标准 1：域路由层零直连 get_connection()，全部经数据层。"""

    def test_no_domain_route_imports_or_calls_get_connection(self):
        import ast
        offenders = []
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, "backend", "domains")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, REPO).replace(os.sep, "/")
                with io.open(path, encoding="utf-8") as handle:
                    source = handle.read()
                tree = ast.parse(source, filename=rel)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.ImportFrom)
                            and node.module == "db_connection"):
                        offenders.append("%s:%d import 了连接工厂" % (rel, node.lineno))
                    elif (isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Name)
                          and node.func.id == "get_connection"):
                        offenders.append("%s:%d 直连 get_connection()" % (rel, node.lineno))
        self.assertEqual(offenders, [],
                         "域路由层仍有直连连接工厂的代码：\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
