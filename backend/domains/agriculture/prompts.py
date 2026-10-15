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

# 农业知识库
AGRICULTURE_KNOWLEDGE = {
    "lychee": {
        "name": "荔枝",
        "seasons": {
            "spring": {
                "tasks": ["促花肥施用", "病虫害预防", "修剪整形"],
                "tips": "春季是荔枝开花关键期，注意防治霜疫霉病"
            },
            "summer": {
                "tasks": ["果实采收", "采后修剪", "恢复肥施用"],
                "tips": "及时采收成熟果实，采后及时补充营养"
            },
            "autumn": {
                "tasks": ["秋梢管理", "病虫害防治", "水分管理"],
                "tips": "培养健壮秋梢，为来年结果打基础"
            },
            "winter": {
                "tasks": ["冬季清园", "树干涂白", "深翻改土"],
                "tips": "做好防寒措施，减少越冬病虫源"
            }
        },
        "diseases": [
            {"name": "霜疫霉病", "symptoms": "果实表面出现褐色病斑", "treatment": "喷施甲霜灵·锰锌"},
            {"name": "炭疽病", "symptoms": "叶片出现圆形病斑", "treatment": "喷施咪鲜胺"},
            {"name": "蒂蛀虫", "symptoms": "果实被蛀食", "treatment": "喷施高效氯氰菊酯"}
        ]
    },
    "longan": {
        "name": "龙眼",
        "seasons": {
            "spring": {"tasks": ["促花肥", "疏花"], "tips": "控制花量，提高坐果率"},
            "summer": {"tasks": ["壮果肥", "水分管理"], "tips": "保持土壤湿润"},
            "autumn": {"tasks": ["采收", "采后管理"], "tips": "适时采收"},
            "winter": {"tasks": ["冬季修剪", "清园"], "tips": "做好防寒"}
        }
    },
    "aquatic": {
        "name": "水产养殖",
        "basics": [
            "水质管理是关键",
            "合理投喂饲料",
            "定期消毒防病",
            "保持溶氧充足"
        ]
    }
}

# ---- 用药数值：模型可以给，但必须能说出出处；服务端再强制补一条免责声明 ----
#
# 背景（缺陷 A2）：本站「常见病虫害速查」严守「来源没给就写未提供、不作推算」，
# 而 AI 问答/诊断的自由文本里会出现「1500倍液」「间隔7天」这类看起来专业的数字 ——
# 这些数字由模型生成、无任何可核来源，与本站「不展示不存在的量化保证」的红线冲突。
# 口径选定为「保留数字但标注来源」，因此分两层落地：
#   ① 提示词要求模型给出处、拿不准就不给数字（见上方 _agri_system_prompt 与 _CHEM_DOSE_RULE）；
#   ② 服务端检测正文里出现用药数值时，强制在答案末尾补一条免责声明。
#      —— 不依赖模型自觉：模型漏了，服务端补上。这是「强制」二字的落点。


# 作物 id → 中文名的内置兜底表。
# 历史缺陷：专家身份此前只从 AGRICULTURE_KNOWLEDGE 取名，而该字典仅覆盖
# 荔枝/龙眼/水产养殖 3 个作物，导致选水稻/茶叶/蔬菜提问时 system_prompt
# 静默退化为「专注于广东特色农产品领域」，专家身份实际失效。
_AGRI_PRODUCT_NAME_FALLBACK = {
    'lychee': '荔枝',
    'longan': '龙眼',
    # v3 新增（A3）：柑橘、香蕉此前只存在于诊断库与速查，问答取不到名字会退化为
    # 「广东特色农产品」，专家身份实际失效。此处补齐，与 farming_data.FARMING_PRODUCTS 一致。
    'citrus': '柑橘',
    'banana': '香蕉',
    'aquatic': '水产养殖',
    'rice': '水稻',
    'tea': '茶叶',
    'vegetable': '蔬菜',
}


# 问答接口接受的作物集合（缺陷 A5）。
# 直接取内置名表：这张表是问答路径上「能不能给模型一个真实作物名」的最后一道底线 ——
# 取不到名字就会退化成「广东特色农产品」，生成的 system_prompt 丢掉作物针对性。
# 此前 /api/agriculture/ask 对任意 product 都返回 200 并静默退化，属「能力虚化」。
#
# ⚠️ 这张表必须与下面几处保持同一套 8 个作物（本项目历史上就吃过「三套口径」的亏）：
#   · farming_data.FARMING_PRODUCTS（农时日历，DB 播种）  · index.html 的顶部 .product-card
#   · script.js 的 getProductName()                        · pest_data.PEST_CROP_ORDER（诊断/速查）
_AGRI_SUPPORTED_PRODUCTS = frozenset(_AGRI_PRODUCT_NAME_FALLBACK)
_agri_name_cache = {}
_agri_name_cache_lock = threading.Lock()


def _agriculture_product_name(product):
    """取作物的中文名，用于拼装 AI 专家身份与提示文案。

    取值顺序：farming_products 目录（可随种子数据扩充）→ AGRICULTURE_KNOWLEDGE
    → 内置兜底表。三级回退确保任何已知作物都能拿到准确名称。
    """
    if not product:
        return '广东特色农产品'

    cached = _agri_name_cache.get(product)
    if cached:
        return cached

    name = ''
    try:
        row = farming.get_farming_product(product)
        if row and row.get('name'):
            name = str(row['name']).strip()
    except Exception as e:
        logger.debug('读取农产品名称失败(%s)，改用内置表: %s', product, e)

    if not name:
        name = str((AGRICULTURE_KNOWLEDGE.get(product) or {}).get('name') or '').strip()
    if not name:
        name = _AGRI_PRODUCT_NAME_FALLBACK.get(product, '')

    if name:
        with _agri_name_cache_lock:
            _agri_name_cache[product] = name
    return name or '广东特色农产品'


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
    """公开出口：问答接口接受的作物集合（未知 product 明确拒绝，不静默退化）。"""
    return _AGRI_SUPPORTED_PRODUCTS


__all__ = [
    'AGRICULTURE_KNOWLEDGE', 'CHEM_DOSE_NOTICE', 'CHEM_DOSE_NOTICE_BLOCK',
    'agriculture_product_name', 'agri_system_prompt', 'supported_products',
]
