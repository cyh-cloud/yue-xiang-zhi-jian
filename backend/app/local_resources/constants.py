DIALECTS = {"yue": "粤语", "hak": "客家话", "nan": "潮汕话"}
DIALECT_LABELS = DIALECTS

POLICY_CATEGORIES = (
    "subsidy",
    "ecommerce",
    "heritage",
    "training",
    "certification",
    "general",
    "entrepreneurship",
)
POLICY_LABELS = {
    "subsidy": "补贴",
    "ecommerce": "电商",
    "heritage": "非遗",
    "training": "培训",
    "certification": "认证",
    "general": "综合",
    "entrepreneurship": "创业支持",
}

NEWS_CATEGORIES = ("news", "disaster_warning", "policy_update")
NEWS_LABELS = {
    "news": "新闻",
    "disaster_warning": "灾害预警",
    "policy_update": "政策更新",
}

RECOMMENDATION_TAGS = {
    "荔枝": ("subsidy", "training", "general"),
    "龙眼": ("subsidy", "training", "general"),
    "水稻": ("subsidy", "training", "general"),
    "水产": ("subsidy", "training", "general"),
    "电商直播": ("ecommerce", "entrepreneurship"),
    "短视频": ("ecommerce", "entrepreneurship"),
    "客服沟通": ("ecommerce", "entrepreneurship"),
    "电商运营": ("ecommerce", "entrepreneurship"),
    "客服专员": ("ecommerce", "entrepreneurship"),
    "手工艺": ("heritage",),
    "手工艺人": ("heritage",),
    "农业技术员": ("certification", "entrepreneurship"),
}
