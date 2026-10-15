# -*- coding: utf-8 -*-
"""病虫害域路由装配：病虫害诊断与常见病虫害速查。

从 app.py 迁出（后端按领域拆分 T11），URL、请求响应结构、状态码、错误码保持不变：
`POST /api/agriculture/diagnose` 与 `GET /api/agriculture/pest-knowledge`。

本文件只做路由装配，两条链路的实现在同域的另外两个模块里：
diagnosis.py（请求校验、提示词、AI 解析、知识库匹配、来源角标）与
knowledge.py（速查条目整形与筛选）。这样拆是因为诊断一条链路就有 200 多行，
加上速查会顶破 spec 的「单个领域路由文件不超过 600 行」。

注：原 /api/agriculture/diag-crops 已删除。
它是全项目无调用者的死接口（诊断面板的作物按钮由 index.html 静态渲染），
保留只会让「支持哪些作物」有两个互相不同步的出口。
"""

from flask import Blueprint

from domains.pest.diagnosis import parse_diag_request, run_diagnosis
from domains.pest.knowledge import read_pest_knowledge

pest_bp = Blueprint('pest', __name__)


@pest_bp.route('/api/agriculture/diagnose', methods=['POST'])
def diagnose_pest():
    """AI 病虫害诊断 —— 支持文字描述与照片（多模态）。

    路径约定：
      · 带照片 → 必须走视觉模型。知识库匹配根本不读图片，带图时降级返回 KB 结论
        会让用户误以为「看图诊断成功」，因此 AI 不可用时直接报错，不降级。
      · 纯文字 → 优先 AI；AI 不可用时降级知识库，来源如实标注。
    """
    payload, err = parse_diag_request()
    if err:
        return err
    return run_diagnosis(payload)


@pest_bp.route('/api/agriculture/pest-knowledge', methods=['GET'])
def get_pest_knowledge():
    """常见病虫害速查 —— 只读。

    筛选与分页都在服务端做：crop / kind / q 之外新增 limit / offset
    （默认每页 50 条），响应带 total 与筛选后的 crops[].count。
    见 knowledge.py 的模块说明（ADR 0002 记录的唯一一处接口变化）。
    """
    return read_pest_knowledge()


__all__ = ['pest_bp']
