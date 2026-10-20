"""Site-specific dialect.org.cn list and detail parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


BASE_URL = "https://dialect.org.cn"
PROVINCES = (
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
    "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "香港", "澳门",
)


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def _source_item_id(url):
    match = re.search(r"/dialect/([^/?#]+)", urlparse(url).path)
    return match.group(1) if match else None


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
    if audio_box is not None and "暂无音频录音" in audio_box.get_text(
        " ", strip=True
    ):
        return "missing", None
    return "unknown", source


def _region_result(province, city):
    city = city or None
    return {
        "province": province,
        "city": city,
        "status": "resolved" if city else "partial",
    }


def _normalize_region(region_raw):
    raw = (region_raw or "").strip()
    if raw.startswith("广西"):
        return _region_result(
            "广西", raw[len("广西"):].removeprefix("壮族自治区")
        )
    if raw.startswith("新疆"):
        return _region_result(
            "新疆", raw[len("新疆"):].removeprefix("维吾尔自治区")
        )
    if raw.startswith("宁夏"):
        return _region_result(
            "宁夏", raw[len("宁夏"):].removeprefix("回族自治区")
        )
    for province in sorted(PROVINCES, key=len, reverse=True):
        if raw.startswith(province):
            city = raw[len(province):].lstrip("省市")
            return _region_result(province, city)
    return {"province": None, "city": None, "status": "unresolved"}


def _dialect_name(definition):
    if not definition:
        return None
    match = re.match(r"^([^：:]{1,12})[：:]", definition.strip())
    return match.group(1).strip() if match else None


def parse_dialect_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for link in soup.select('a[href*="/dialect/"]'):
        url = urljoin(BASE_URL, link.get("href"))
        source_item_id = _source_item_id(url)
        if not source_item_id or source_item_id in seen:
            continue
        seen.add(source_item_id)
        items.append(
            {
                "source_item_id": source_item_id,
                "title": link.get_text(" ", strip=True),
                "detail_url": url,
            }
        )
    return items


def parse_dialect_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    source_item_id = _source_item_id(response.url)
    region_raw = _text(soup.select_one(".detail-header .card-tag"))
    lemma = _text(soup.select_one(".detail-word"))
    if not lemma:
        raise ValueError(f"dialect-org {source_item_id}: missing lemma")
    phonetic = _text(soup.select_one(".detail-phonetic"))
    definition = _text(
        soup.select_one(".detail-header ~ .card p")
        or soup.select_one("main > .card p")
    )
    audio_box = soup.select_one(".audio-box")
    audio_status, audio_url = _audio_status(
        soup.select_one(".audio-box audio[src]"), audio_box
    )
    region = _normalize_region(region_raw)
    rights = {
        "rights_status": "attribution-required",
        "attribution_required": True,
        "attribution_text": "中国方言库",
        "rights_evidence_url": "https://dialect.org.cn/",
    }
    common = {
        "source_id": "dialect-org",
        "source_item_id": str(source_item_id),
        "source_url": response.url,
        "long_term_url": response.url,
        "detail_url": response.url,
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
            "rights_risk": {
                "status": rights["rights_status"],
                "notice": "页面未发现开放许可；仅保留短释义和来源链接，不复制音频或大段正文。",
            },
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
            "rights_risk": {
                "status": rights["rights_status"],
                "notice": "页面未发现开放许可；仅保留短释义和来源链接，不复制音频或大段正文。",
            },
        },
    }
    return {"point": point, "lexeme": lexeme}
