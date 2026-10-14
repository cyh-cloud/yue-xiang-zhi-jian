# -*- coding: utf-8 -*-
"""政府域路由：政策管理与数据大屏。

从 app.py 迁出（后端按领域拆分 T17），URL、请求响应结构、状态码、错误码保持不变。

三条口径必须保持：

1. 分类归一化：政府端表单的「综合」value 是英文 general，入库前统一归一化成中文分类，
   否则学员端显示英文标签、分类筛选也筛不到（database.normalize_policy_category）。
2. 摘要 / 发布日期 / 资料来源全部落库：缺任一项，学员端政策卡片就是残缺的。
   资料来源单独走 source_text 参数（表单原文 → JSON），不直接写 source 列。
3. 下架是真的下架：is_published=0 后学员端 /api/resources/policies 不再返回该条，
   本域的测试用这条链路锁住它。

角色把关走能力表（core.permissions.require_capability）：本域只有 policy.manage
一个能力，列表、发布、改、删、大屏全挂在它上面。
"""

from datetime import datetime

from flask import Blueprint, jsonify, request

from core.permissions import require_capability
from core.session import get_session_user

import database

government_bp = Blueprint('government', __name__)


@government_bp.route('/api/government/policies', methods=['GET'])
@require_capability('policy.manage')
def gov_get_policies():
    user = get_session_user()
    policies = database.get_all_government_policies()
    return jsonify({"success": True, "policies": policies})


@government_bp.route('/api/government/policies', methods=['POST'])
@require_capability('policy.manage')
def gov_create_policy():
    user = get_session_user()
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify({"success": False, "message": "标题和内容不能为空"}), 400
    policy_id = database.create_policy(
        title, content,
        # 「综合」在政府端表单里的 value 是英文 general，入库前统一归一化成中文分类，
        # 否则学员端会显示成英文标签、且任何分类筛选都筛不到（详见 database.normalize_policy_category）
        database.normalize_policy_category(data.get('category')),
        user['username'],
        # 摘要 / 发布日期 / 资料来源全部落库（缺了学员端卡片就是残缺的，见 create_policy 注释）
        summary=(data.get('summary') or '').strip(),
        date=(data.get('date') or '').strip() or datetime.now().strftime('%Y-%m-%d'),
        source_text=data.get('source') or '')
    return jsonify({"success": True, "id": policy_id, "message": "政策发布成功"})


@government_bp.route('/api/government/policies/<int:policy_id>', methods=['PUT'])
@require_capability('policy.manage')
def gov_update_policy(policy_id):
    user = get_session_user()
    data = request.get_json() or {}
    fields = {k: v for k, v in data.items()
              if k in ('title', 'content', 'category', 'is_published', 'summary', 'date')}
    if 'category' in fields:
        fields['category'] = database.normalize_policy_category(fields['category'])
    # 资料来源单独走 source_text（表单原文 → JSON），不直接写 source 列
    if 'source' in data:
        fields['source_text'] = data.get('source') or ''
    database.update_policy(policy_id, **fields)
    return jsonify({"success": True, "message": "更新成功"})


@government_bp.route('/api/government/policies/<int:policy_id>', methods=['DELETE'])
@require_capability('policy.manage')
def gov_delete_policy(policy_id):
    database.delete_policy(policy_id)
    return jsonify({"success": True, "message": "已删除"})


# ---- 数据大屏 ----

@government_bp.route('/api/government/dashboard', methods=['GET'])
@require_capability('policy.manage')
def gov_dashboard():
    return jsonify({"success": True, "overview": database.get_government_overview()})
