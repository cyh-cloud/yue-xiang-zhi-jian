# -*- coding: utf-8 -*-
"""静态媒体域与手工技艺域的路由行为测试。

这两个域是「蓝图模式第一次端到端落地」的验证对象：首页与静态兜底从 app.py 搬进
domains/static_files/，技艺列表与详情搬进 domains/crafts/，改由 core.app_factory
注册蓝图。T24 收口后，Flask 只提供 API 与 uploads/images 媒体，不再伺服旧 MPA；
本文件锁住这条运行边界与静态白名单的防护效果。

断言全部基于 HTTP 行为，不测模块怎么划分。拆分不产生新行为，为结构写测试只会
把实现细节钉死（见 spec 的 Testing Decisions）。
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import repo_paths  # noqa: E402


class StaticDomainTest(unittest.TestCase):
    """静态媒体域：仅 uploads/images 可取，旧页面与根级资源不可取。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def test_flask_root_is_not_a_frontend_entry(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.data),
            {"success": False, "code": "not_found", "message": "文件不存在"},
        )

    def test_retired_root_level_static_assets_are_not_served(self):
        for path in ('/index.html', '/styles.css', '/portal.css', '/portal.js',
                     '/crafts.html', '/sw.js', '/js/core.js'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)

    def test_uploaded_files_under_uploads_are_served(self):
        """uploads/ 按目录整体放行：教师上传的课程材料与 3D 模型必须原路取回。"""
        path = '/uploads/models_3d/guangxiu_xiubeng.glb'
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'glTF'), '取回的不是原文件')

    def test_rejected_path_returns_uniform_json_404(self):
        """白名单拒绝一律返回带 code 的 JSON，不暴露文件是否存在。"""
        response = self.client.get('/.env')
        self.assertEqual(response.status_code, 404)
        self.assertIn('application/json', response.content_type)
        self.assertEqual(json.loads(response.data),
                         {"success": False, "code": "not_found", "message": "文件不存在"})

    def test_missing_but_allowed_path_is_404(self):
        """过白名单却不存在的文件仍由 send_from_directory 兜 404（搬迁前后同形）。"""
        response = self.client.get('/images/definitely-not-here.jpg')
        self.assertEqual(response.status_code, 404)


class StaticDenylistTest(unittest.TestCase):
    """静态白名单的防护效果不得因搬迁而削弱。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _assert_denied(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404, '%s 应当 404，实际 %s' % (path, response.status_code))
        payload = json.loads(response.data)
        self.assertEqual(payload, {"success": False, "code": "not_found", "message": "文件不存在"})

    def test_env_files_are_not_servable(self):
        for path in ('/.env', '/.env.example'):
            self._assert_denied(path)

    def test_source_files_are_not_servable(self):
        for path in ('/app.py', '/database.py', '/db_schema.py', '/repo_paths.py',
                     '/test_app.py', '/run.py', '/core/app_factory.py',
                     '/tools/check_architecture.py'):
            self._assert_denied(path)

    def test_database_files_are_not_servable(self):
        for path in ('/data/yuexiang.db', '/database.db', '/data/grill_baseline.db'):
            self._assert_denied(path)

    def test_sensitive_directories_are_refused_wholesale(self):
        for path in ('/data/', '/data', '/db_domains/', '/__pycache__/'):
            self._assert_denied(path)

    def test_path_traversal_is_refused(self):
        for path in ('/images/../app.py', '/data/../.env', '/js/../../app.py'):
            self._assert_denied(path)

    def test_forbidden_extensions_are_refused_even_in_allowed_dirs(self):
        for path in ('/js/core.py', '/uploads/models_3d/x.py',
                     '/images/pest/dump.sql', '/uploads/secret.pem'):
            self._assert_denied(path)

    def test_every_denial_shares_one_response_shape(self):
        """所有被拒路径给出同一个响应体，不暴露文件是否存在。"""
        denied = [self.client.get(path).data for path in
                  ('/.env', '/.env.example', '/app.py', '/data/yuexiang.db',
                   '/js/core.py', '/data/', '/js/../../app.py')]
        self.assertEqual(len(set(denied)), 1, '被拒响应形状不一致：%r' % (set(denied),))

    def test_allowlist_sets_are_intact(self):
        from domains import static_files
        self.assertIn('uploads', static_files._ALLOWED_STATIC_DIRS)
        self.assertIn('images', static_files._ALLOWED_STATIC_DIRS)
        self.assertEqual(
            set(static_files._ALLOWED_STATIC_DIRS),
            {'uploads', 'images'},
        )
        self.assertIn('.py', static_files._FORBIDDEN_STATIC_EXTS)
        self.assertIn('.env', static_files._FORBIDDEN_STATIC_EXTS)
        self.assertIn('.db', static_files._FORBIDDEN_STATIC_EXTS)
        self.assertIn('.sql', static_files._FORBIDDEN_STATIC_EXTS)
        self.assertIn('.key', static_files._FORBIDDEN_STATIC_EXTS)
        for name in ('data', 'db', 'api', 'logs', '__pycache__', '.venv'):
            self.assertIn(name, static_files._FORBIDDEN_STATIC_DIRS)

    def test_static_root_stays_the_repository_root(self):
        from domains import static_files
        from core.app_factory import BASE_DIR
        self.assertIs(static_files.BASE_DIR, BASE_DIR)
        self.assertEqual(BASE_DIR, repo_paths.REPO_ROOT)


class BlueprintRegistrationTest(unittest.TestCase):
    """蓝图注册顺序：静态兜底排在最后，且不吞掉任何 API 路由。"""

    def test_static_catch_all_is_registered_after_every_other_blueprint(self):
        from app import app
        rules = [str(rule) for rule in app.url_map.iter_rules()]
        catch_all = '/<path:filename>'
        self.assertIn(catch_all, rules)
        # Flask 自带的 /static/<path:filename> 也在表里，真正的顺序是：
        # 自带 static -> 各领域蓝图 -> 静态兜底。
        # 注册序的唯一真相是 app.blueprints 的键顺序：url_map.iter_rules() 会按
        # 权重重排，末尾那条并不对应最后注册的蓝图（见 T08 的同名断言）。
        self.assertIn('static_files', app.blueprints)
        self.assertEqual(list(app.blueprints)[-1], 'static_files', list(app.blueprints))
        for rule in rules:
            if rule not in (catch_all, '/static/<path:filename>'):
                self.assertTrue(rule.startswith('/api/') or rule == '/', rules[:8])

    def test_api_routes_are_not_swallowed_by_the_catch_all(self):
        from app import app
        client = app.test_client()
        for path in ('/api/crafts/list', '/api/crafts/embroidery', '/api/health',
                     '/api/agriculture/products', '/api/home/stats'):
            response = client.get(path)
            self.assertIn(response.status_code, (200, 401, 403), path)
            self.assertNotIn(u'文件不存在'.encode('utf-8'), response.data, path)

    def test_blueprints_come_from_the_domain_packages(self):
        from domains import crafts_bp, static_bp
        from app import app
        self.assertEqual(crafts_bp.name, 'crafts')
        self.assertEqual(static_bp.name, 'static_files')
        self.assertIn(crafts_bp.name, app.blueprints)
        self.assertIn(static_bp.name, app.blueprints)


class CraftsDomainTest(unittest.TestCase):
    """手工技艺域：列表与详情。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def test_list_returns_four_crafts(self):
        response = self.client.get('/api/crafts/list')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual([c['id'] for c in data['crafts']],
                         ['embroidery', 'woodcarving', 'ceramics', 'lacquer'])
        self.assertEqual([c['name'] for c in data['crafts']],
                         [u'广绣', u'潮汕木雕', u'石湾陶艺', u'阳江漆器'])

    def test_detail_returns_knowledge_entry(self):
        response = self.client.get('/api/crafts/embroidery')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['name'], u'广绣')
        self.assertEqual(data['data']['origin'], u'广州')
        self.assertIn('steps', data['data'])
        self.assertIn('purchase_guide', data['data'])

    def test_every_listed_id_resolves_to_a_detail(self):
        listed = json.loads(self.client.get('/api/crafts/list').data)['crafts']
        for craft in listed:
            response = self.client.get('/api/crafts/%s' % craft['id'])
            self.assertEqual(response.status_code, 200, craft['id'])
            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertEqual(data['data']['name'], craft['name'])

    def test_unknown_craft_id_returns_200_with_success_false(self):
        """既有契约：未知 id 不返回 404，而是 200 + success=False。"""
        response = self.client.get('/api/crafts/no-such-craft')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data, {"success": False, "message": u"未找到该手工艺信息"})

    def test_crafts_knowledge_is_the_domain_single_source(self):
        """技艺目录只有一处真相源：crafts 表，代码里不再有 CRAFTS_KNOWLEDGE 副本。"""
        import domains.crafts.routes as routes_module
        self.assertFalse(hasattr(routes_module, 'CRAFTS_KNOWLEDGE'),
                         'routes.py 仍持有 CRAFTS_KNOWLEDGE 副本')
        body = json.loads(self.client.get('/api/crafts/list').data)
        self.assertEqual({c['id'] for c in body['crafts']},
                         {'embroidery', 'woodcarving', 'ceramics', 'lacquer'})
        for craft in body['crafts']:
            self.assertTrue(craft['name'], craft['id'])


if __name__ == '__main__':
    unittest.main()
