# -*- coding: utf-8 -*-
"""运营域路由装配：蓝图对象与三块共用的请求解析、错误映射。

URL、请求响应结构、状态码、错误码在本票是**新增**的（此前没有运营后台），
所以这里的形状按仓库既有约定定，而不是复刻某个旧接口：

- 鉴权走 core.permissions.require_capability('<域>.manage')，未登录与能力不足
  都是 403 + 「权限不足」，与 admin / government / enterprise 三域逐字一致；
- 业务失败统一 {success: false, message: ...}，状态码 400 / 404 两档，
  与 government 域的 create_policy / update_policy 同形状；
- 数据层抛的 ValueError 一律映射成 400，消息直接用异常文本 ——
  校验规则只有一处（数据层），文案也就只有一处，路由不再复述一遍。

CAPABILITIES_USED 声明本域读 farming 与 pest 两个能力域，
让 tools/check_architecture.py 有据可判（ADR 0002 修订了「领域之间不得
互相 import」为「不得访问不具有该角色权限的数据」）。装饰器
require_capability 由 farming.py 与 pest.py 各自 import 使用。
"""

import logging

from flask import Blueprint, jsonify, request

from core.session import get_session_user

# 本域读这两个能力域的数据，写在这一处供机械检查判权。
CAPABILITIES_USED = ('farming.manage', 'pest.manage')

logger = logging.getLogger(__name__)

operator_bp = Blueprint('operator', __name__)


def json_body():
    """取 JSON 请求体。非对象（数组 / 字符串 / 缺 body）一律给空字典。

    与 admin 域的 data.get('x') 用法兼容：空字典让后面的取值自然落空，
    由字段校验给出 400，不会在这里 500。
    """
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def current_username():
    """当前登录用户名，供「标记已复核」写 verified_by 用。"""
    user = get_session_user() or {}
    return (user.get('username') or '').strip()


def ok(**payload):
    body = {'success': True}
    body.update(payload)
    return jsonify(body), 200


def fail(message, status=400):
    return jsonify({'success': False, 'message': message}), status


def run_write(action, *args, **kwargs):
    """执行一次数据层写操作，把 ValueError 映射成 400。

    为什么不逐条 try：校验规则集中在数据层，路由只需要一种失败形状。
    其它异常不接，让它按 500 出去 —— 那是真 bug，不该被包装成「参数不合法」。
    """
    try:
        return ok(result=action(*args, **kwargs))
    except ValueError as exc:
        return fail(str(exc), 400)


def register_routes():
    """把各内容块的路由挂到蓝图。由包门面（__init__.py）在全部模块导入后调用。

    不在本模块导入时自动调用的理由：那样会成环 —— farming.py 要用本模块的
    json_body / run_write，而本模块又要 import farming 去注册它的路由。
    改成由门面在最后显式调用，导入顺序即注册顺序，环也消失。
    """
    from domains.operator.farming import register_farming_routes
    from domains.operator.pest import register_pest_routes
    register_farming_routes(operator_bp)
    register_pest_routes(operator_bp)


__all__ = ['operator_bp', 'CAPABILITIES_USED', 'json_body', 'current_username',
           'ok', 'fail', 'run_write', 'register_routes']
