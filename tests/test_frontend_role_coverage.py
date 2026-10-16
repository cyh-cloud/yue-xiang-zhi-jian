# -*- coding: utf-8 -*-
"""主站前端（script.js）的角色表必须覆盖后端全部角色。

为什么需要：角色表是前端各自维护的字面量，后端加一个角色时前端不会报错，只会
静默少一块。operator 就是这么漏的：ROLE_NAV / ROLE_DEFAULT / ROLE_LABELS 都还
只有五个角色，`hasMainSitePanel` 因此判断它不是后台角色，登录后既不跳
operator.html，导航里也没有入口，用户卡在主站。

这里用后端 core.permissions.ROLES 当唯一真相源，逐项检查前端有没有跟上。
"""

import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
if os.path.join(REPO_ROOT, 'backend') not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, 'backend'))

from core.permissions import ROLES  # noqa: E402

SCRIPT_JS = os.path.join(REPO_ROOT, 'script.js')

# 每个角色都要在下面这些前端表里出现
REQUIRED_MAPS = ('ROLE_NAV', 'ROLE_DEFAULT', 'ROLE_LABELS')
# 登录与注册两处角色分流：除学员外每个角色都得有明确去向
DISPATCH_VARS = {'login': '_role', 'register': '_r'}


def _object_body(source, name):
    """取 `const NAME = { ... }` 的对象字面量正文（按花括号配对，不靠正则）。"""
    marker = 'const %s = {' % name
    start = source.index(marker) + len(marker) - 1
    depth = 0
    for offset in range(start, len(source)):
        char = source[offset]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[start + 1:offset]
    raise AssertionError('script.js 里找不到 %s 的对象字面量' % name)


def _top_level_keys(body):
    """取对象字面量第一层的键名（嵌套对象的键不算）。"""
    keys = []
    depth = 0
    for match in re.finditer(r'([{}])|([A-Za-z_$][\w$]*)\s*:', body):
        if match.group(1) == '{':
            depth += 1
        elif match.group(1) == '}':
            depth -= 1
        elif depth == 0 and match.group(2):
            keys.append(match.group(2))
    return keys


class FrontendRoleCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCRIPT_JS, encoding='utf-8') as handle:
            cls.source = handle.read()

    def test_every_backend_role_appears_in_the_frontend_role_maps(self):
        for name in REQUIRED_MAPS:
            keys = _top_level_keys(_object_body(self.source, name))
            missing = [role for role in ROLES if role not in keys]
            self.assertEqual(missing, [],
                             'script.js 的 %s 漏了这些角色：%s' % (name, missing))

    def test_every_role_default_points_at_a_real_page(self):
        pages = _top_level_keys(_object_body(self.source, 'TAB_PAGES'))
        defaults = _object_body(self.source, 'ROLE_DEFAULT')
        for role in ROLES:
            match = re.search(r'\b%s\s*:\s*\'([^\']+)\'' % role, defaults)
            self.assertIsNotNone(match, 'ROLE_DEFAULT 里没有 %s' % role)
            tab = match.group(1)
            self.assertIn(tab, pages,
                          'ROLE_DEFAULT[%s] 指向的 %s 不在 TAB_PAGES 里' % (role, tab))

    def test_login_and_register_route_every_non_student_role(self):
        for label, variable in DISPATCH_VARS.items():
            missing = [role for role in ROLES
                       if role != 'student'
                       and ("%s === '%s'" % (variable, role)) not in self.source]
            self.assertEqual(missing, [],
                             '%s 的角色分流漏了这些角色：%s' % (label, missing))

    def test_every_portal_card_points_at_an_existing_page(self):
        portal = _object_body(self.source, 'ROLE_PORTAL')
        pages = re.findall(r"page:\s*'([^']+)'", portal)
        self.assertTrue(pages, 'ROLE_PORTAL 里没有 page 字段')
        for page in pages:
            self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, page)),
                            'ROLE_PORTAL 指向的 %s 不存在' % page)


if __name__ == '__main__':
    unittest.main()
