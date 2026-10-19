import re
from urllib.parse import urlparse

from .. import source_registry


SOURCE_ID = "dialect-org"
BASE_URL = "https://dialect.org.cn"

PROVINCES = (
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
)


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def _audio_status(audio_node, audio_box):
    if audio_node is None:
        return "missing", None
    source = (audio_node.get("src") or "").strip()
    parsed = urlparse(source)
    host = (parsed.hostname or "").lower()
    if (
        not source
        or any(char.isspace() for char in source)
        or parsed.scheme not in {"http", "https"}
        or host == "xn--oss%20bucket-8m3n10a.oss-cn-hangzhou.aliyuncs.com"
        or "你的oss" in source.lower()
    ):
        return "invalid", None
    if audio_box is not None and "暂无音频录音" in audio_box.get_text(" ", strip=True):
        return "missing", None
    return "unknown", source


def _normalize_region(region_raw):
    raw = (region_raw or "").strip()
    if raw.startswith("广西"):
        return _region_result("广西", raw[len("广西"):].removeprefix("壮族自治区"))
    if raw.startswith("新疆"):
        return _region_result("新疆", raw[len("新疆"):].removeprefix("维吾尔自治区"))
    if raw.startswith("宁夏"):
        return _region_result("宁夏", raw[len("宁夏"):].removeprefix("回族自治区"))
    for province in sorted(PROVINCES, key=len, reverse=True):
        if raw.startswith(province):
            city = raw[len(province):].lstrip("省市")
            return _region_result(province, city)
    return {"province": None, "city": None, "status": "unresolved"}


def _region_result(province, city):
    city = city or None
    return {
        "province": province,
        "city": city,
        "status": "resolved" if city else "partial",
    }


def _dialect_name(definition):
    if not definition:
        return None
    match = re.match(r"^([^：:]{1,12})[：:]", definition.strip())
    return match.group(1).strip() if match else None


def parse_detail(source_item_id, detail_html, rights=None):
    from bs4 import BeautifulSoup

    rights = rights or source_registry.rights_fields(
        source_registry.load_registry()[SOURCE_ID]
    )
    rights_risk = {
        "status": rights["rights_status"],
        "notice": "页面未发现开放许可；仅保留短释义和来源链接，不复制音频或大段正文。",
    }
    soup = BeautifulSoup(detail_html, "html.parser")
    source_url = f"{BASE_URL}/dialect/{source_item_id}"
    region_raw = _text(soup.select_one(".detail-header .card-tag"))
    lemma = _text(soup.select_one(".detail-word"))
    phonetic = _text(soup.select_one(".detail-phonetic"))
    definition = _text(
        soup.select_one(".detail-header ~ .card p")
        or soup.select_one("main > .card p")
    )
    audio_box = soup.select_one(".audio-box")
    audio_status, audio_url = _audio_status(
        soup.select_one(".audio-box audio[src]"), audio_box
    )
    if not lemma:
        raise ValueError(f"dialect-org {source_item_id}: missing lemma")
    region = _normalize_region(region_raw)
    common = {
        "source_id": SOURCE_ID,
        "source_item_id": str(source_item_id),
        "source_url": source_url,
        "long_term_url": source_url,
        "detail_url": source_url,
        "detail_url_status": "direct",
        "publish_status": "draft",
        **rights,
        "confidence": "medium",
    }
    point = {
        **common,
        "region_raw": region_raw,
        "province": region["province"],
        "city": region["city"],
        "county": None,
        "dialect_name": None,
        "point_note": None,
        "extra": {
            "region_raw": region_raw,
            "region_normalization": {
                "status": region["status"],
                "province": region["province"],
                "city": region["city"],
                "requires_review": region["status"] != "resolved",
            },
            "dialect_name_suggestion": _dialect_name(definition),
            "rights_risk": rights_risk,
        },
    }
    lexeme = {
        **common,
        "point_source_item_id": str(source_item_id),
        "lemma": lemma,
        "phonetic": phonetic,
        "definition": definition,
        "example": None,
        "audio_url": audio_url,
        "audio_status": audio_status,
        "extra": {
            "audio": {
                "status": audio_status,
                "src_present": audio_box is not None,
                "playable": audio_status == "available",
            },
            "rights_risk": rights_risk,
        },
    }
    return {"point": point, "lexeme": lexeme}
