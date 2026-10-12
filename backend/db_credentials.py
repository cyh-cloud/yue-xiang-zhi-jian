#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口令散列。认证播种与认证业务函数共用同一份实现。

单独成模块的理由：播种侧（db_seed_accounts 灌演示账号）与 database.py 的
authenticate_user / change_password / register_user 都要用它。让它留在 database.py，
播种模块就得反向 import 那个聚合模块；在两边各写一份又会出现第二份口令算法。
所以收敛到这里，再由 database.py 原样再导出，`database.hash_password()` 不变。
"""

import hashlib
import uuid

def hash_password(password, salt=None):
    """哈希密码"""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(stored, password):
    """验证密码"""
    salt, hashed = stored.split('$', 1)
    return hash_password(password, salt) == stored
