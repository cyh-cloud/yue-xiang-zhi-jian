#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电商实训的作物白名单与校验。

T13 从 `domains/ecommerce/prompts.py` 提到共享层。原因是 spec 把 `_ec_product_ok`
裁定给电商运营域、直播实训域显式引用，但「领域路由模块之间不得互相 import」
是一条机械检查的硬约束（T01），两者直接冲突。作物白名单是零领域状态的纯数据，
放共享层不违背「共享层不感知领域」（同层的 shared/options.py、shared/copywriting.py
也是这类纯函数），且能保证全站只有一份作物表。
"""

import os

# 电商实训的**唯一**作物表（中文名）。前端作物卡与下拉展示的都是中文名，
# 故用中文名做白名单。
EC_PRODUCTS = ('荔枝', '龙眼', '柑橘', '香蕉', '水产养殖', '水稻', '茶叶', '蔬菜')


# ---- 电商与直播两类实训共用的输入上限与限流额度 ----
# T13 从 domains/ecommerce/prompts.py 提到共享层，理由同作物白名单：
# 直播实训域也要用这些额度，领域之间不得 import，而它们是零领域状态的纯配置。
EC_RATE_SCRIPT_LIMIT = int(os.getenv('EC_RATE_SCRIPT_LIMIT', '30'))       # 带货话术生成
EC_RATE_FEEDBACK_LIMIT = int(os.getenv('EC_RATE_FEEDBACK_LIMIT', '30'))   # 话术评分
EC_RATE_COPY_LIMIT = int(os.getenv('EC_RATE_COPY_LIMIT', '30'))           # 商品文案
EC_RATE_CS_LIMIT = int(os.getenv('EC_RATE_CS_LIMIT', '120'))              # 客服对练（逐轮对话，放宽）
EC_RATE_CS_AUX_LIMIT = int(os.getenv('EC_RATE_CS_AUX_LIMIT', '40'))       # 客服辅助（开场白/提示）
EC_SCRIPT_MAX_LEN = 3000     # 送去评分 / 入库的话术最大字符数
EC_LIVE_TRANSCRIPT_MAX_LEN = 4000   # 朗读识别文本最大字符数
EC_COPY_MAX_LEN = 4000             # 文案实训「我的稿」最大字符数（详情页文案普遍较长）
EC_CS_TRANSCRIPT_MAX_TURNS = 30    # 客服对练最多保存的轮数
EC_CS_TURN_MAX_LEN = 500           # 客服对练单条消息最大字符数
EC_RATE_COMMENTS_LIMIT = int(os.getenv('EC_RATE_COMMENTS_LIMIT', '30'))  # 观众提问（AI 题库化）


def ec_product_ok(product):
    """校验电商实训的作物名（中文）。空值视为未选择，由调用方决定是否回退默认值。"""
    return str(product or '').strip() in EC_PRODUCTS


__all__ = ['EC_PRODUCTS', 'ec_product_ok'] + [
    name for name in list(globals()) if name.startswith('EC_') and name != 'EC_PRODUCTS'
]
