#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 — Vercel Serverless Function 入口
将所有 /api/* 请求转发到 Flask 应用
"""

import sys
import os

BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, BASE_DIR)

# 初始化数据库（建表 + 种子数据）
# 在 Vercel 中每次 cold start 都会执行，init_db 内部有去重逻辑。
# noqa: E402 是因为 backend/ 必须在 import 之前插入 sys.path，这是本文件存在的
# 全部理由；`# noqa` 同时告诉 IDE 的静态分析「这两个名字由上面的 sys.path 提供」，
# 否则它会报「No module named database / unresolved reference app」。
import database  # noqa: E402
database.init_db()

# 导入 Flask 应用
# Vercel Python Runtime 会自动检测 app 变量并将其作为 WSGI 应用
from app import app  # noqa: E402
