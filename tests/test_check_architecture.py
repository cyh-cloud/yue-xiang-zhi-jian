# -*- coding: utf-8 -*-
"""tools/check_architecture.py 的自检测试。

全部用例都在临时目录里搭假模块结构，不依赖仓库当前形态，也不碰真实代码。
覆盖：空跑通过、三类违规（领域间 import 边、共享层 import 领域、超行数）、
多种 import 写法、领域内自引用合法、真实仓库空跑通过。
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import check_architecture as checker


def blueprint_module(name):
    """一个最小可用的领域路由模块：定义了 Flask Blueprint。"""
    return (
        "from flask import Blueprint\n"
        "\n"
        "bp = Blueprint('%s', __name__)\n"
        "\n"
        "@bp.route('/ping')\n"
        "def ping():\n"
        "    return 'ok'\n" % name
    )


class CheckArchitectureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def check(self, **kwargs):
        return checker.check(self.root, **kwargs)

    def kinds(self, report):
        return [violation.kind for violation in report.violations]

    # ---- 按能力表判权（T02）----

    # 一份最小的能力表，形状与 backend/core/permissions.py 的 CAPABILITIES 一致。
    # 测试各自改这一份，用来验证「能力表变了判定就跟着变」。
    CAPABILITY_TABLE = {
        'farming.read': (),
        'farming.manage': ('operator', 'super_admin'),
        'policy.read': (),
        'policy.manage': ('government',),
        'teaching.read': ('teacher', 'super_admin'),
        'teaching.manage': ('teacher', 'super_admin'),
        'user.read': ('super_admin',),
        'user.manage': ('super_admin',),
    }

    def capabilities_table(self, changes=None):
        table = dict(self.CAPABILITY_TABLE)
        if changes:
            table.update(changes)
        return table

    def build_content_domain(self, name='pest'):
        self.write("domains/%s/__init__.py" % name, "from .routes import bp\n")
        self.write("domains/%s/routes.py" % name, blueprint_module(name))

    def test_domain_importing_public_data_module_is_allowed(self):
        self.build_content_domain()
        self.write("db_domains/farming.py", "CAPABILITY = 'farming'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.farming import get_farming_products\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertTrue(report.ok, checker.format_report(report))

    def test_domain_importing_guarded_data_module_is_reported(self):
        self.build_content_domain()
        self.write("db_domains/users.py", "CAPABILITY = 'user'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.users import delete_user_by_admin\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        violation = report.violations[0]
        self.assertEqual(violation.source, "domains/pest/routes.py")
        self.assertEqual(violation.target, "db_domains/users.py")
        self.assertIn("user.manage", violation.message)
        text = checker.format_report(report)
        self.assertIn("domains/pest/routes.py", text)
        self.assertIn("db_domains/users.py", text)

    def test_domain_holding_the_capability_may_import_its_data_module(self):
        self.write(
            "domains/government/routes.py",
            blueprint_module("government")
            + "\nfrom core.permissions import require_capability\n"
            + "\n@require_capability('policy.manage')\n"
            + "def publish():\n"
            + "    return 'ok'\n"
            + "\nfrom db_domains.policies import list_policies\n",
        )
        self.write("db_domains/policies.py", "CAPABILITY = 'policy'\n")

        report = self.check(capabilities=self.capabilities_table())

        self.assertTrue(report.ok, checker.format_report(report))

    def test_capability_declared_in_one_module_covers_the_whole_domain(self):
        self.write("domains/teaching_support/__init__.py", "from .routes import bp\n")
        self.write(
            "domains/teaching_support/routes.py",
            blueprint_module("teaching_support")
            + "\nfrom core.permissions import require_capability\n"
            + "\n@require_capability('teaching.manage')\n"
            + "def grade():\n"
            + "    return 'ok'\n",
        )
        self.write(
            "domains/teaching_support/queries.py",
            "from db_domains.teaching import list_submissions\n",
        )
        self.write("db_domains/teaching.py", "CAPABILITY = 'teaching'\n")

        report = self.check(capabilities=self.capabilities_table())

        self.assertTrue(report.ok, checker.format_report(report))

    def test_route_importing_route_is_still_reported(self):
        self.build_content_domain('pest')
        self.build_content_domain('crafts')
        self.write("db_domains/farming.py", "CAPABILITY = 'farming'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest")
            + "\nfrom domains.crafts.routes import crafts_bp\n"
            + "\nfrom db_domains.farming import get_farming_products\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        violation = report.violations[0]
        self.assertEqual(violation.source, "domains/pest/routes.py")
        self.assertEqual(violation.target, "domains/crafts/routes.py")

    def test_data_module_without_capability_declaration_is_reported(self):
        self.build_content_domain()
        self.write("db_domains/mystery.py", "def read_all():\n    return []\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.mystery import read_all\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        violation = report.violations[0]
        self.assertEqual(violation.target, "db_domains/mystery.py")
        self.assertIn("CAPABILITY", violation.message)

    def test_narrow_interface_owning_no_capability_is_allowed(self):
        self.build_content_domain('employment_profile')
        self.write("db_domains/profile_sources.py", "CAPABILITY = ''\n")
        self.write(
            "domains/employment_profile/routes.py",
            blueprint_module("employment_profile")
            + "\nfrom db_domains.profile_sources import get_profile_basic\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertTrue(report.ok, checker.format_report(report))

    def test_capability_table_change_flips_the_verdict(self):
        self.build_content_domain()
        self.write("db_domains/farming.py", "CAPABILITY = 'farming'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.farming import get_farming_products\n",
        )

        public = self.check(capabilities=self.capabilities_table())
        self.assertTrue(public.ok, checker.format_report(public))

        guarded = self.check(
            capabilities=self.capabilities_table({'farming.read': ('super_admin',)})
        )
        self.assertEqual(self.kinds(guarded), [checker.KIND_CROSS_DOMAIN])
        self.assertIn("farming.manage", guarded.violations[0].message)

    def test_capability_domain_absent_from_the_table_is_reported(self):
        """能力域整条不在表里时判越界，不默认放行。

        拼错能力名（db_domains 写 'farm'、表里写 'farming'）不能变成暗门，
        所以这里 fail-closed：read 与 manage 双双缺席，没人声明得了 manage。
        """
        self.build_content_domain()
        self.write("db_domains/farming.py", "CAPABILITY = 'farm'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.farming import get_farming_products\n",
        )

        report = self.check(capabilities=self.capabilities_table())

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        violation = report.violations[0]
        self.assertEqual(violation.target, "db_domains/farming.py")
        self.assertIn("farm.manage", violation.message)

    def test_route_importing_its_own_data_module_is_allowed(self):
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest")
            + "\nfrom core.permissions import require_capability\n"
            + "\n@require_capability('pest.manage')\n"
            + "def create():\n"
            + "    return 'ok'\n"
            + "\nfrom db_domains.pest import list_pests\n",
        )
        self.write("db_domains/pest.py", "CAPABILITY = 'pest'\n")

        report = self.check(capabilities=self.capabilities_table(
            {'pest.read': ('operator', 'super_admin'), 'pest.manage': ('super_admin',)}
        ))

        self.assertTrue(report.ok, checker.format_report(report))

    def test_default_capabilities_come_from_the_real_permissions_module(self):
        backend = str(REPO_ROOT / 'backend')
        if backend not in sys.path:
            sys.path.insert(0, backend)
        from core.permissions import CAPABILITIES

        self.assertEqual(checker.load_capabilities(), CAPABILITIES)

        self.build_content_domain()
        self.write("db_domains/users.py", "CAPABILITY = 'user'\n")
        self.write(
            "domains/pest/routes.py",
            blueprint_module("pest") + "\nfrom db_domains.users import delete_user_by_admin\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])

    def build_agriculture_domain(self):
        self.write("domains/agriculture/__init__.py", "from .routes import bp\n")
        self.write("domains/agriculture/routes.py", blueprint_module("agriculture"))

    def test_repo_without_domain_modules_passes(self):
        self.write("app.py", "from flask import Flask\n\napp = Flask(__name__)\n")
        self.write("database.py", "def get_connection():\n    return None\n")

        report = self.check()

        self.assertTrue(report.ok)
        self.assertEqual(report.domains, [])
        self.assertIn("未发现领域路由模块", checker.format_report(report))

    def test_cross_domain_import_is_reported(self):
        self.build_agriculture_domain()
        self.write(
            "domains/jobs/routes.py",
            blueprint_module("jobs") + "\nfrom domains.agriculture.routes import bp\n",
        )

        report = self.check()

        self.assertFalse(report.ok)
        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        violation = report.violations[0]
        self.assertEqual(violation.source, "domains/jobs/routes.py")
        self.assertEqual(violation.target, "domains/agriculture/routes.py")
        self.assertEqual(violation.line, 9)
        text = checker.format_report(report)
        self.assertIn("domains/jobs/routes.py", text)
        self.assertIn("domains/agriculture/routes.py", text)

    def test_importing_domain_package_is_reported(self):
        self.build_agriculture_domain()
        self.write(
            "domains/jobs/routes.py",
            blueprint_module("jobs") + "\nfrom domains.agriculture import bp\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        self.assertEqual(report.violations[0].target, "domains/agriculture/__init__.py")

    def test_flat_layout_keeps_domains_separate(self):
        self.write("domains/__init__.py", "")
        self.write("domains/agriculture.py", blueprint_module("agriculture"))
        self.write(
            "domains/jobs.py",
            blueprint_module("jobs") + "\nfrom domains import agriculture\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        self.assertEqual(report.violations[0].source, "domains/jobs.py")
        self.assertEqual(report.violations[0].target, "domains/agriculture.py")

    def test_shared_module_importing_domain_is_reported(self):
        self.build_agriculture_domain()
        self.write("shared/core.py", "from domains.agriculture.routes import bp\n")

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_SHARED_TO_DOMAIN])
        self.assertEqual(report.violations[0].source, "shared/core.py")
        self.assertEqual(report.violations[0].target, "domains/agriculture/routes.py")

    def test_flat_shared_module_importing_domain_is_reported(self):
        self.build_agriculture_domain()
        self.write("ai.py", "from domains.agriculture.routes import bp\n")

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_SHARED_TO_DOMAIN])
        self.assertEqual(report.violations[0].source, "ai.py")

    def test_domain_importing_shared_is_allowed(self):
        self.write("shared/core.py", "def session_user():\n    return None\n")
        self.write(
            "domains/agriculture/routes.py",
            blueprint_module("agriculture") + "\nfrom shared.core import session_user\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_domain_importing_plain_module_is_allowed(self):
        self.write("database.py", "def get_connection():\n    return None\n")
        self.write(
            "domains/agriculture/routes.py",
            blueprint_module("agriculture") + "\nimport database\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_intra_domain_import_is_allowed(self):
        self.write(
            "domains/live/routes.py",
            blueprint_module("live")
            + "\nfrom .analysis import score\n"
            + "from domains.live.scoring import grade\n",
        )
        self.write("domains/live/analysis.py", "def score():\n    return 1\n")
        self.write("domains/live/scoring.py", "def grade():\n    return 2\n")

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))
        self.assertEqual(len(report.domains), 1)

    def test_domain_package_init_counts_as_domain_module(self):
        self.write("domains/agriculture/__init__.py", "from .routes import bp\n")
        self.write("domains/agriculture/routes.py", blueprint_module("agriculture"))
        self.write(
            "domains/jobs/__init__.py",
            "from .routes import bp\nfrom domains.agriculture import bp as agri\n",
        )
        self.write("domains/jobs/routes.py", blueprint_module("jobs"))

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_DOMAIN])
        self.assertEqual(report.violations[0].source, "domains/jobs/__init__.py")
        self.assertIn("domains/agriculture/__init__.py", report.domains[0].files)

    def test_container_init_is_not_a_domain_module(self):
        self.write("domains/__init__.py", "from domains.agriculture import bp\n")
        self.write("domains/agriculture/routes.py", blueprint_module("agriculture"))
        self.write("domains/jobs/routes.py", blueprint_module("jobs"))

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_app_entry_registering_domains_is_not_flagged(self):
        self.build_agriculture_domain()
        self.write(
            "app.py",
            "from flask import Flask\n"
            "\n"
            "def create_app():\n"
            "    app = Flask(__name__)\n"
            "    from domains.agriculture import bp\n"
            "    app.register_blueprint(bp)\n"
            "    return app\n"
            "\n"
            "\n"
            "app = create_app()\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_every_import_form_is_detected(self):
        self.build_agriculture_domain()
        cases = [
            ("plain", "import domains.agriculture.routes\n"),
            ("package", "import domains.agriculture\n"),
            ("from_module", "from domains.agriculture import bp\n"),
            ("from_submodule", "from domains.agriculture.routes import bp\n"),
            ("aliased", "import domains.agriculture.routes as agri\n"),
            ("relative_parent", "from ..agriculture import bp\n"),
            ("relative_submodule", "from ..agriculture.routes import bp\n"),
            ("relative_grandparent", "from ...agriculture import bp\n"),
        ]
        for name, statement in cases:
            with self.subTest(statement=statement):
                holder = "domains/%s/routes.py" % name
                if name == "relative_grandparent":
                    holder = "domains/%s/inner/routes.py" % name
                self.write(holder, blueprint_module(name) + "\n" + statement)

        report = self.check()

        self.assertEqual(len(report.violations), len(cases))
        self.assertEqual(set(self.kinds(report)), {checker.KIND_CROSS_DOMAIN})
        sources = {violation.source for violation in report.violations}
        self.assertEqual(
            sources,
            {
                "domains/plain/routes.py",
                "domains/package/routes.py",
                "domains/from_module/routes.py",
                "domains/from_submodule/routes.py",
                "domains/aliased/routes.py",
                "domains/relative_parent/routes.py",
                "domains/relative_submodule/routes.py",
                "domains/relative_grandparent/inner/routes.py",
            },
        )

    def test_third_party_imports_are_ignored(self):
        self.write(
            "domains/agriculture/routes.py",
            "import os\n"
            "import json\n"
            "from datetime import datetime\n"
            "from flask import Blueprint, jsonify\n"
            + blueprint_module("agriculture"),
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_files_outside_domain_roots_are_ignored(self):
        self.write("tests/test_something.py", blueprint_module("helper"))
        self.write("tools/local_tool.py", blueprint_module("tool"))
        self.build_agriculture_domain()

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))
        self.assertEqual(len(report.domains), 1)

    def test_domain_route_file_over_line_limit_is_reported(self):
        self.write("domains/agriculture/routes.py", self._module_with_lines(601))

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_TOO_LONG])
        violation = report.violations[0]
        self.assertEqual(violation.source, "domains/agriculture/routes.py")
        self.assertIn("601", violation.detail)
        self.assertIn("600", violation.detail)

    def test_domain_route_file_at_line_limit_passes(self):
        self.write("domains/agriculture/routes.py", self._module_with_lines(600))
        self.write("domains/jobs/routes.py", blueprint_module("jobs"))

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_domain_helper_file_over_line_limit_is_reported(self):
        self.write("domains/agriculture/routes.py", blueprint_module("agriculture"))
        self.write("domains/agriculture/analysis.py", self._module_with_lines(650))

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_TOO_LONG])
        self.assertEqual(report.violations[0].source, "domains/agriculture/analysis.py")

    def test_unparsable_file_is_reported(self):
        self.build_agriculture_domain()
        self.write("domains/agriculture/broken.py", "def broken(:\n")

        report = self.check()

        self.assertFalse(report.ok)
        self.assertEqual(self.kinds(report), [checker.KIND_UNPARSABLE])
        self.assertEqual(report.violations[0].source, "domains/agriculture/broken.py")

    def test_command_line_run_on_real_repo_passes(self):
        import os

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "check_architecture.py")],
            capture_output=True,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")

        self.assertEqual(result.returncode, 0, stdout)
        # 领域路由目录是随仓库形态增长的：T07 起首页/静态兜底与手工技艺已成为蓝图，
        # 于是这里断言的是「退出码 0 且输出自洽」，而不是某一种具体形态。
        self.assertTrue(
            "架构检查通过" in stdout or "未发现领域路由模块" in stdout,
            "输出既未报告通过也未说明没有领域路由模块：%s" % stdout,
        )
        if "发现" in stdout and "领域路由目录" in stdout:
            self.assertIn("共享层模块", stdout)

    def _module_with_lines(self, total):
        head = blueprint_module("agriculture")
        filler = total - head.count("\n")
        self.assertGreaterEqual(filler, 0)
        return head + "".join("# filler %d\n" % index for index in range(filler))


if __name__ == "__main__":
    unittest.main()
