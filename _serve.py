#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""以 run.py 相同的参数启动 Flask（0.0.0.0，debug=False，use_reloader=False）。

与 run.py 的唯一区别：不自动打开系统浏览器 —— 手动测试时系统浏览器会抢焦点，
内嵌浏览器里已经开着页面了。代理环境变量由 _start_server.ps1 负责清掉。
端口与 run.py 共用 resolve_port()：.env 的 PORT 优先，留空/非法回落默认 5000。
"""

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from run import resolve_port  # noqa: E402

import db_init  # noqa: E402
from app import app  # noqa: E402

if __name__ == '__main__':
    db_init.init_db()
    port, _source = resolve_port()
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
