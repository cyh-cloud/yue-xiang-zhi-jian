#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - 测试文件
"""

import unittest
import json
from app import app

class TestYueXiangApp(unittest.TestCase):
    """测试粤乡智匠应用"""

    def setUp(self):
        """测试前准备"""
        self.app = app
        self.client = app.test_client()
        self.app.config['TESTING'] = True

    def test_index_page(self):
        """测试主页"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_health_check(self):
        """测试健康检查"""
        response = self.client.get('/api/health')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['healthy'])

    def test_get_products(self):
        """测试获取农产品列表"""
        response = self.client.get('/api/agriculture/products')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['products']), 0)

    def test_get_crafts(self):
        """测试获取手工艺列表"""
        response = self.client.get('/api/crafts/list')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['crafts']), 0)

    def test_get_dialects(self):
        """测试获取方言列表"""
        response = self.client.get('/api/resources/dialects')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['dialects']), 0)

    def test_get_success_cases(self):
        """测试获取成功案例"""
        response = self.client.get('/api/resources/cases')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['cases']), 0)

    def test_get_policies(self):
        """测试获取政策信息"""
        response = self.client.get('/api/resources/policies')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['policies']), 0)

    def test_get_jobs(self):
        """测试获取就业岗位"""
        response = self.client.get('/api/employment/jobs')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['jobs']), 0)

    def test_login(self):
        """测试登录功能"""
        # 测试正确登录
        response = self.client.post('/api/auth/login',
            data=json.dumps({
                'username': 'teacher_demo',
                'password': '123456',
                'role': 'teacher'
            }),
            content_type='application/json'
        )
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('session_id', data)

    def test_login_wrong_password(self):
        """测试错误密码登录"""
        response = self.client.post('/api/auth/login',
            data=json.dumps({
                'username': 'teacher_demo',
                'password': 'wrong_password'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_generate_script(self):
        """测试生成带货话术"""
        response = self.client.post('/api/ecommerce/script',
            data=json.dumps({'product': 'lychee'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('script', data)

    def test_diagnose_pest(self):
        """测试病虫害诊断"""
        response = self.client.post('/api/simulation/diagnose',
            data=json.dumps({'image': 'test.jpg'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('diagnosis', data)

    def test_get_teacher_dashboard(self):
        """测试教师仪表板"""
        response = self.client.get('/api/teacher/dashboard')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('dashboard', data)

    def test_get_students(self):
        """测试获取学员列表"""
        response = self.client.get('/api/teacher/students')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('students', data)


if __name__ == '__main__':
    unittest.main()