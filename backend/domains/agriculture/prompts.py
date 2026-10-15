# -*- coding: utf-8 -*-
"""农业培训域的农技问答提示词组。

为什么整组下沉到这里而不是放共享层：它的两个调用方都在问答路径上（问答与追问建议）。
留在共享层意味着每个领域都能改农技口径，而农技口径是农业培训域自己的规则。

用药口径的判定函数与免责声明文案都在共享层 shared.agri_dosage：除本域的问答路径外，
病虫害诊断域与本土资源域也要用，放任何一个领域都会逼出领域间 import。这里按需转发
给本域的问答路径，不复制第二份。
"""

import logging
import threading


from shared.agri_dosage import CHEM_DOSE_NOTICE, CHEM_DOSE_NOTICE_BLOCK
from db_domains import farming

logger = logging.getLogger(__name__)

# 作物名解析不到时的文案。刻意不给具体作物名：那会把「这个作物在平台上不存在」
# 这件事藏起来，生成的 system_prompt 装作认识这个作物。上游的 _parse_agri_request
# 已经用 supported_products() 把未知作物挡在 400，走到这里只剩空 product 一种情形。
UNKNOWN_PRODUCT_FALLBACK = u'广东特色农产品'

# 作物中文名的进程内缓存。读的是 farming_products 表，一次会话里不会变，
# 但每条问答都要拼 system_prompt，不值得每条都打一次库。
_agri_name_cache = {}
_agri_name_cache_lock = threading.Lock()


def _supported_product_names():
    """从 farming_products 目录表读「作物 id -> 中文名」。

    这是全站唯一的作物名真相源（REFACTOR-PLAN 4.2 删掉了代码里四份副本：
    AGRICULTURE_KNOWLEDGE、_AGRI_PRODUCT_NAME_FALLBACK、前端 PRODUCT_NAMES 之外的
    农时目录）。运营在后台改作物名，问答的专家身份跟着变，不需要发版。
    读表失败时返回空字典：宁可退化成泛泛称呼，也不拿一份会过期的硬编码表顶上。
    """
    try:
        return {p['id']: (p.get('name') or '').strip()
                for p in farming.get_farming_products() if p.get('name')}
    except Exception as e:
        logger.debug('读取作物目录失败: %s', e)
        return {}


def _agriculture_product_name(product):
    """取作物的中文名，用于拼装 AI 专家身份与提示文案。

    取值顺序只有一级：farming_products 目录表。取不到就明说「广东特色农产品」，
    不再退回内置兜底表 —— 那正是本次要删的第五份作物名副本。
    """
    if not product:
        return UNKNOWN_PRODUCT_FALLBACK

    cached = _agri_name_cache.get(product)
    if cached is not None:
        return cached

    name = _supported_product_names().get(product, '')
    if name:
        with _agri_name_cache_lock:
            _agri_name_cache[product] = name
    return name or UNKNOWN_PRODUCT_FALLBACK

# ---- 用药数值：模型可以给，但必须能说出出处；服务端再强制补一条免责声明 ----
#
# 背景（缺陷 A2）：本站「常见病虫害速查」严守「来源没给就写未提供、不作推算」，
# 而 AI 问答/诊断的自由文本里会出现「1500倍液」「间隔7天」这类看起来专业的数字 ——
# 这些数字由模型生成、无任何可核来源，与本站「不展示不存在的量化保证」的红线冲突。
# 口径选定为「保留数字但标注来源」，因此分两层落地：
#   ① 提示词要求模型给出处、拿不准就不给数字（见上方 _agri_system_prompt 与 _CHEM_DOSE_RULE）；
#   ② 服务端检测正文里出现用药数值时，强制在答案末尾补一条免责声明。
#      —— 不依赖模型自觉：模型漏了，服务端补上。这是「强制」二字的落点。


def _agri_system_prompt(product):
    product_name = _agriculture_product_name(product)
    return (
        f"你是粤乡智匠平台的专业农业技术专家，专注于{product_name}领域。"
        f"回答要求：1)简洁实用，分点列出；2)结合广东本地气候和种植条件；"
        f"3)涉及农药、兽药时：可以给出药剂名称与防治思路；"
        f"若给出具体用量、稀释倍数或安全间隔期，必须同时写明该数值的出处"
        f"（例如某产品的标签、当地农业农村部门的技术指导、某个具体标准），"
        f"并且只能引用你确实掌握出处的数值；"
        f"凡拿不准出处的，一律不给数字，只给药剂名称与施用方法，并提示用户以所购产品标签为准；"
        f"严禁凭印象编造用量、倍数、间隔期，也不要给出自己说不出出处的具体数值；"
        f"4)适当用通俗易懂的语言。回答控制在300字以内。"
    )


def agriculture_product_name(product):
    """公开出口：取作物的中文名（供追问建议等问答路径上的调用方拼专家身份）。"""
    return _agriculture_product_name(product)


def agri_system_prompt(product):
    """公开出口：农技问答的系统提示词。"""
    return _agri_system_prompt(product)


def supported_products():
    """公开出口：问答接口接受的作物集合（未知 product 明确拒绝，不静默退化）。

    集合直接来自 farming_products 目录表：平台上有哪些作物由运营定，问答能问哪些
    作物就跟着定。此前这里是一份写死的 8 个 id，与目录表、前端卡片、病虫害作物层
    四处口径要手工对齐（本项目历史上就吃过「三套口径」的亏）。
    """
    return frozenset(_supported_product_names())


__all__ = [
    'CHEM_DOSE_NOTICE', 'CHEM_DOSE_NOTICE_BLOCK', 'UNKNOWN_PRODUCT_FALLBACK',
    'agriculture_product_name', 'agri_system_prompt', 'supported_products',
]
