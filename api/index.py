#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 — Vercel Serverless Function 入口
将所有 /api/* 请求转发到 Flask 应用
"""

import sys
import os

# 将项目根目录添加到 Python 路径
# api/index.py 在 api/ 子目录中，需要访问同级的 app.py、database.py 等
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 初始化数据库（建表 + 种子数据）
# 在 Vercel 中每次 cold start 都会执行，init_db 内部有去重逻辑
import database
database.init_db()

# 导入 Flask 应用
# Vercel Python Runtime 会自动检测 app 变量并将其作为 WSGI 应用
from app import app
