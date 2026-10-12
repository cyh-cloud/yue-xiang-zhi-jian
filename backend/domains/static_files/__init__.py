# -*- coding: utf-8 -*-
"""静态资源域：首页与静态文件兜底。

蓝图在 routes 里定义，本文件只做门面转发。白名单常量经此转出，是为了让
test_paths.py 的「uploads 在放行目录里」断言继续从 app / domains.static_files
读到同一份 frozenset，而不是各自复制一份事实源。
"""

from core.app_factory import BASE_DIR
from domains.static_files.routes import (
    _ALLOWED_STATIC_DIRS,
    _ALLOWED_STATIC_EXTS,
    _FORBIDDEN_STATIC_DIRS,
    _FORBIDDEN_STATIC_EXTS,
    static_bp,
)

__all__ = ['static_bp', 'BASE_DIR',
           '_ALLOWED_STATIC_DIRS', '_ALLOWED_STATIC_EXTS',
           '_FORBIDDEN_STATIC_DIRS', '_FORBIDDEN_STATIC_EXTS']
