#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件系统路径基准的回归测试（后端按领域拆分 T02）。

锁住一条约束：上传落盘目录、数据库目录、静态资源根目录、环境变量文件位置都以
**仓库根**为基准推导，而不是以各自模块文件所在目录为基准。模块日后搬进子目录时，
这些路径不得跟着漂移 —— 否则会出现「上传的文件存得下、静态路由却取不回」
（静态白名单放行仓库根的 uploads/，模块却写进子目录的 uploads/）。

手法：把 database.py / app.py 复制进仓库内的临时子目录再加载，模拟拆分后模块
搬了家的位置；从子目录里读出来的路径必须仍然指向仓库根。
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

# 探针复制的是 database.py 与 app.py，它们在 backend/ 下，故基准指向 backend/。
# repo_paths.REPO_ROOT 仍是仓库根，两者不要混：前者是「后端代码在哪」，
# 后者是「data/、uploads/、.env 在哪」。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import repo_paths  # noqa: E402


# database.py 在 T04 之后是聚合模块，import 时会拉进 db_connection 等兄弟模块。
# 这些兄弟模块把 DB_DIR / DB_PATH 在**导入时**算好，所以每份探针都必须先把它们
# 从 sys.modules 里踢掉重新求值，否则前一条用例设的环境变量不会生效，
# 探针会读到上一条用例留下的路径（表现为按用例顺序时红时绿）。

# 只踢数据层基础设施模块，不踢 database 本身：app.py 在 import 时就绑定了
# database 这个模块对象，把它踢掉会让 app.py 继续用旧的（指向 data/yuexiang.db）
# 那一份，而新探针写的是另一份库，表现为「上传落盘了但静态路由取不回」。
INFRA_MODULES = ('db_connection', 'db_credentials', 'db_schema')


def _snapshot_infra_modules():
    """记下基础设施模块的当前模块对象，供探针跑完后原样放回。"""
    return {name: sys.modules.get(name) for name in INFRA_MODULES}


def _restore_infra_modules(snapshot):
    """把基础设施模块恢复成探针之前的**同一个**模块对象。

    不能图省事写成「踢掉再 import」：重新 import 会产生新的函数对象，
    database.get_connection 仍指向旧的那个，于是 database 与 db_connection
    的同一个函数变成两个身份，后续用例会连到两份不同的库上。
    """
    for name, module in snapshot.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _evict_infra_modules():
    for name in INFRA_MODULES:
        sys.modules.pop(name, None)


def load_copy(probe_dir, filename, module_name):
    """把仓库内的模块复制进 probe_dir 后按 module_name 加载，模拟模块搬家后的位置。"""
    snapshot = _snapshot_infra_modules()
    target = os.path.join(probe_dir, filename)
    shutil.copyfile(os.path.join(REPO_ROOT, filename), target)
    _evict_infra_modules()
    spec = importlib.util.spec_from_file_location(module_name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
        # 探针跑完把基础设施模块原样放回，避免后续用例拿到被踢掉的半成品，
        # 同时不改变 database.get_connection 这些已绑定符号的身份。
        _restore_infra_modules(snapshot)
    return module


class RepoRootPathBaselineTest(unittest.TestCase):
    """四处文件系统路径都必须从仓库根推导，且不随模块位置与 cwd 改变。"""

    def setUp(self):
        # 探针目录放在仓库内：只有「同属一个仓库的子目录」才是拆分后模块的真实位置。
        self.probe_dir = tempfile.mkdtemp(prefix='_t02_path_probe_', dir=REPO_ROOT)
        self.addCleanup(shutil.rmtree, self.probe_dir, ignore_errors=True)

    @staticmethod
    def _restore_env(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_project_root_is_the_repository_root(self):
        """REPO_ROOT 必须是仓库根，不能因为后端搬进 backend/ 就跟着变成 backend/。

        这是本次搬迁最容易踩的坑：data/、uploads/、.env 都还在仓库根，
        REPO_ROOT 一旦指向 backend/，数据库和上传目录就会整体搬家，
        而静态路由放行的仍是仓库根的 uploads/，症状是「上传成功但取不回」。
        """
        self.assertTrue(os.path.isabs(repo_paths.REPO_ROOT))
        # repo_paths.py 现在住在 backend/ 下，所以仓库根是它祖父目录
        self.assertEqual(repo_paths.REPO_ROOT,
                         os.path.dirname(os.path.dirname(
                             os.path.abspath(repo_paths.__file__))))
        # 后端代码的标记文件在 backend/ 下
        for marker in ('app.py', 'database.py', 'repo_paths.py'):
            self.assertTrue(
                os.path.isfile(os.path.join(repo_paths.REPO_ROOT, 'backend', marker)),
                '%s 不在 %s 下' % (marker, repo_paths.REPO_ROOT))
        # 配置与依赖清单仍在仓库根
        for marker in ('requirements.txt', '.env.example'):
            self.assertTrue(
                os.path.isfile(os.path.join(repo_paths.REPO_ROOT, marker)),
                '%s 不在 %s 下' % (marker, repo_paths.REPO_ROOT))

    def test_database_dir_follows_repo_root_not_module_location(self):
        probe = load_copy(self.probe_dir, 'database.py', 'database_probe_moved')
        self.assertNotEqual(os.path.dirname(probe.__file__), repo_paths.REPO_ROOT,
                            '探针必须真的位于子目录里，否则这条用例没有意义')
        self.assertEqual(probe.DB_DIR, os.path.join(repo_paths.REPO_ROOT, 'data'))
        self.assertEqual(probe.DB_PATH,
                         os.path.join(repo_paths.REPO_ROOT, 'data', 'yuexiang.db'))

    def test_database_dir_ignores_the_working_directory(self):
        elsewhere = tempfile.mkdtemp(prefix='t02_cwd_')
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        previous_cwd = os.getcwd()
        os.chdir(elsewhere)
        self.addCleanup(os.chdir, previous_cwd)
        probe = load_copy(self.probe_dir, 'database.py', 'database_probe_cwd')
        self.assertEqual(probe.DB_DIR, os.path.join(repo_paths.REPO_ROOT, 'data'))
        self.assertEqual(probe.DB_PATH,
                         os.path.join(repo_paths.REPO_ROOT, 'data', 'yuexiang.db'))

    def test_serverless_database_dir_stays_in_tmp(self):
        original = os.environ.get('VERCEL')
        os.environ['VERCEL'] = '1'
        self.addCleanup(self._restore_env, 'VERCEL', original)
        probe = load_copy(self.probe_dir, 'database.py', 'database_probe_vercel')
        self.assertEqual(probe.DB_DIR, '/tmp')
        self.assertEqual(probe.DB_PATH, os.path.join('/tmp', 'yuexiang.db'))

    def test_yuexiang_db_override_still_wins(self):
        scratch = tempfile.mkdtemp(prefix='t02_db_')
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        isolated = os.path.join(scratch, 'isolated.db')
        original = os.environ.get('YUEXIANG_DB')
        os.environ['YUEXIANG_DB'] = isolated
        self.addCleanup(self._restore_env, 'YUEXIANG_DB', original)
        probe = load_copy(self.probe_dir, 'database.py', 'database_probe_override')
        self.assertEqual(probe.DB_PATH, isolated)
        conn = probe.get_connection()
        conn.close()
        self.assertTrue(os.path.isfile(isolated), 'YUEXIANG_DB 指定的库没有被创建')

    def test_app_static_root_and_env_file_follow_repo_root(self):
        probe = load_copy(self.probe_dir, 'app.py', 'app_probe_moved')
        self.assertNotEqual(os.path.dirname(probe.__file__), repo_paths.REPO_ROOT,
                            '探针必须真的位于子目录里，否则这条用例没有意义')
        self.assertEqual(probe._BASE_DIR, repo_paths.REPO_ROOT)
        self.assertEqual(repo_paths.ENV_FILE, os.path.join(repo_paths.REPO_ROOT, '.env'))

    def test_env_file_is_loaded_from_the_repo_root(self):
        """环境变量文件位置以仓库根为基准：从任意 cwd 导入都要读到同一份 .env。"""
        from dotenv import find_dotenv, load_dotenv
        elsewhere = tempfile.mkdtemp(prefix='t02_env_cwd_')
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        previous_cwd = os.getcwd()
        os.chdir(elsewhere)
        self.addCleanup(os.chdir, previous_cwd)
        self.assertEqual(find_dotenv(usecwd=True), '')
        self.assertEqual(repo_paths.ENV_FILE, os.path.join(repo_paths.REPO_ROOT, '.env'))
        self.assertTrue(os.path.isfile(repo_paths.ENV_FILE))
        load_dotenv(repo_paths.ENV_FILE)
        self.assertEqual(os.getenv('AI_MODEL'), os.environ['AI_MODEL'])
        self.assertTrue(os.getenv('SECRET_KEY'),
                        '仓库根的 .env 应提供 SECRET_KEY，否则会话签名每次启动都变')

    def test_static_allowlist_covers_the_upload_root(self):
        import app
        self.assertIn('uploads', app._ALLOWED_STATIC_DIRS)
        self.assertEqual(app._BASE_DIR, repo_paths.REPO_ROOT)

    def test_uploaded_files_round_trip_through_the_static_route(self):
        """上传落盘目录与静态放行目录必须指向同一处：存得下，也要原路取回。"""
        import database
        from app import app

        client = app.test_client()
        login = client.post('/api/auth/login', data=json.dumps(
            {'username': 'teacher_demo', 'password': '123456'}),
            content_type='application/json')
        self.assertEqual(login.status_code, 200)
        session_id = json.loads(login.data)['session_id']
        headers = {'X-Session-Id': session_id}

        course_id = 990001
        material_bytes = b'%PDF-1.4 T02 repo-root path probe\n'
        model_bytes = b'glTF T02 repo-root path probe'
        written = []
        material_id = model_id = None
        try:
            uploaded = client.post(
                '/api/teacher/courses/%d/materials' % course_id,
                data={'file': (io.BytesIO(material_bytes), 't02_probe_material.pdf')},
                headers=headers)
            self.assertEqual(uploaded.status_code, 200)
            material_id = json.loads(uploaded.data)['id']
            row = next(r for r in database.get_course_materials(course_id)
                       if r['id'] == material_id)
            self._assert_round_trip(client, row['file_path'], material_bytes, written)

            model = client.post(
                '/api/teacher/models-3d',
                data={'file': (io.BytesIO(model_bytes), 't02_probe_model.glb'),
                      'title': 'T02路径基准探针', 'description': 'probe',
                      'craft_type': '广绣'},
                headers=headers)
            self.assertEqual(model.status_code, 200)
            model_id = json.loads(model.data)['id']
            conn = database.get_connection()
            model_row = conn.execute(
                "SELECT file_path FROM models_3d WHERE id = ?", (model_id,)).fetchone()
            conn.close()
            self._assert_round_trip(client, model_row['file_path'], model_bytes, written)
        finally:
            if material_id:
                client.delete('/api/teacher/materials/%d' % material_id, headers=headers)
            if model_id:
                client.delete('/api/teacher/models-3d/%d' % model_id, headers=headers)
            conn = database.get_connection()
            conn.execute("DELETE FROM course_materials WHERE course_id = ?", (course_id,))
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()
            uploads_root = os.path.join(repo_paths.REPO_ROOT, 'uploads')
            for path in written:
                if os.path.isfile(path):
                    os.remove(path)
                directory = os.path.dirname(path)
                while len(directory) > len(uploads_root) and directory.startswith(uploads_root):
                    try:
                        os.rmdir(directory)
                    except OSError:
                        break
                    directory = os.path.dirname(directory)

    def _assert_round_trip(self, client, relative_path, payload, written):
        on_disk = os.path.join(repo_paths.REPO_ROOT, relative_path)
        self.assertTrue(os.path.isfile(on_disk),
                        '上传文件没有落在仓库根的上传目录下: %s' % on_disk)
        with open(on_disk, 'rb') as handle:
            self.assertEqual(handle.read(), payload)
        fetched = client.get('/' + relative_path.replace('\\', '/'))
        self.assertEqual(fetched.status_code, 200, '静态路由取不到刚上传的文件')
        self.assertEqual(fetched.data, payload)
        # send_from_directory 打开的文件句柄由响应持有，显式关闭避免 ResourceWarning 噪音
        fetched.close()
        written.append(on_disk)


if __name__ == '__main__':
    unittest.main()
