# -*- coding: utf-8 -*-
"""手工技艺域路由：技艺列表与详情。

从 app.py 迁出（后端按领域拆分 T07），URL、响应结构与状态码保持不变：
`GET /api/crafts/list` 与 `GET /api/crafts/<craft_id>`。未知 id 的既有契约是
200 + success=False，不是 404，搬迁时一并保留。

T08 起内容改读库（ADR 0002）：原先内联在本文件的 CRAFTS_KNOWLEDGE（四种技艺的
步骤与三层嵌套采购指南，约 300 行字面量）已灌进 crafts / craft_steps /
craft_purchase_categories / craft_purchase_items / craft_budgets 五张表，
由 db_domains.crafts 按原形状组装，本文件只剩两条路由。

仍留在读取侧的两处口径（都不是内容行，是**读侧的呈现规则**）：

- 列表项的难度分级 level：取 crafts.level。该列在库里是空串（T05 灌库时未迁该值），
  运营后台补上等级后这里立即生效；补之前列表角标整排消失，这是如实呈现，不兜底；
- 详情响应的 videos：库里没有视频表（旧前端视频教学区曾读它），
  因此**不再下发这个键**。前端 renderCraftVideo 对空数组的处理是收起整块，
  不会留空壳，属于「没有数据就不显示」而非坏档。
"""

from flask import Blueprint, jsonify

from db_domains import crafts as crafts_db

crafts_bp = Blueprint('crafts', __name__)


@crafts_bp.route('/api/crafts/list', methods=['GET'])
def get_crafts_list():
    crafts = [
        {"id": c["id"], "name": c["name"], "origin": c["origin"],
         "level": c.get("level") or ""}
        for c in crafts_db.get_crafts()
    ]
    return jsonify({"success": True, "crafts": crafts})


@crafts_bp.route('/api/crafts/<craft_id>', methods=['GET'])
def get_craft_detail(craft_id):
    craft = crafts_db.get_craft_detail(craft_id)
    if craft is not None:
        return jsonify({"success": True, "data": craft})
    return jsonify({"success": False, "message": "未找到该手工艺信息"})
