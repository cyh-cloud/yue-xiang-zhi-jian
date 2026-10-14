#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层唯一的连接工厂。

拆分前 `get_connection()` 住在 database.py 里，被 130+ 个函数复用。抽出来单独成模块，
让「数据层只有一个函数负责建立连接」成为可机械检查的事实：整个数据层只允许出现一次
`sqlite3.connect(`（由 test_db_infrastructure.py 逐文件扫描断言）。

三条 PRAGMA 是既有契约，一条都不能丢：
  - journal_mode=WAL：读写不互斥，否则并发写会频繁撞 "database is locked"；
  - foreign_keys=ON：SQLite 默认关闭外键，不开则 farming_* 的级联删除全是空转；
  - busy_timeout=8000：并发写入时最多等 8 秒。

路径仍以仓库根为基准（T02 的约定）：模块日后搬进子目录，库的位置不得跟着漂移。
环境变量仍是唯一配置入口：YUEXIANG_DB 让测试指向一份可弃的库副本，
避免 e2e 写坏真实数据。项目已改为自托管单机部署，不再有 serverless 分支。
"""

import os
import sqlite3

import repo_paths

# 以仓库根为基准，模块搬进子目录后数据库位置不变
DB_DIR = os.path.join(repo_paths.REPO_ROOT, 'data')
# YUEXIANG_DB 仅供测试覆盖：指向一份可弃的库副本，避免 E2E 写坏真实数据。
# 不设该变量时行为完全不变（仍用 data/yuexiang.db）。
DB_PATH = os.environ.get('YUEXIANG_DB') or os.path.join(DB_DIR, 'yuexiang.db')


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=8000")  # 并发写入时最多等 8s，避免瞬时 "database is locked"
    return conn
