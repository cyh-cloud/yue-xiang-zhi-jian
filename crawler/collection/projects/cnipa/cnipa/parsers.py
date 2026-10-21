"""Parsers for cnipa PDF product tables and fixture metadata."""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
from pathlib import Path

from pypdf import PdfReader


PDF_MIME_TYPE = "application/pdf"
_SEQUENCE = re.compile(r"^\s*(\d{1,3})(?:\s+(.*))?$")
_PAGE_NUMBER = re.compile(r"^-\s*\d+\s*-$")
_PROVINCES = (
    "北京市",
    "天津市",
    "上海市",
    "重庆市",
    "河北省",
    "山西省",
    "辽宁省",
    "吉林省",
    "黑龙江省",
    "江苏省",
    "浙江省",
    "安徽省",
    "福建省",
    "江西省",
    "山东省",
    "河南省",
    "湖北省",
    "湖南省",
    "广东省",
    "海南省",
    "四川省",
    "贵州省",
    "云南省",
    "陕西省",
    "甘肃省",
    "青海省",
    "台湾省",
    "内蒙古自治区",
    "广西壮族自治区",
    "西藏自治区",
    "宁夏回族自治区",
    "新疆维吾尔自治区",
    "香港特别行政区",
    "澳门特别行政区",
)


def _line(value):
    return " ".join(str(value or "").split())


def _compact(value):
    return "".join(str(value or "").split())


def _row_hash(payload):
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _province_in(text):
    best = None
    for province in _PROVINCES:
        index = text.find(province)
        if index < 0:
            continue
        if (
            best is None
            or index < best[0]
            or (index == best[0] and len(province) > len(best[1]))
        ):
            best = (index, province)
    return best


def _county_from_scope(origin_scope):
    if not origin_scope:
        return None
    match = re.search(
        r"([\u4e00-\u9fff]{1,12}(?:县|区|旗))",
        origin_scope,
    )
    return match.group(1) if match else None


def _block_fields(parts):
    values = [_line(part) for part in parts if _line(part)]
    for index, value in enumerate(values):
        compact = _compact(value)
        province_match = _province_in(compact)
        if province_match is None:
            continue
        position, province = province_match
        product_parts = values[:index]
        if position:
            product_parts.append(compact[:position])
        product_name = _compact("".join(product_parts))
        if not product_name:
            continue
        remainder = compact[position + len(province):]
        following = ([remainder] if remainder else []) + values[index + 1:]
        applicant = following[0] if following else None
        origin_scope = following[1] if len(following) > 1 else None
        return {
            "product_name": product_name,
            "province": province,
            "applicant": applicant,
            "origin_scope": origin_scope,
            "county": _county_from_scope(origin_scope),
        }

    product_name = values[0] if values else None
    return {
        "product_name": product_name,
        "province": values[1] if len(values) > 1 else None,
        "applicant": values[2] if len(values) > 2 else None,
        "origin_scope": values[3] if len(values) > 3 else None,
        "county": (
            _county_from_scope(values[3]) if len(values) > 3 else None
        ),
    }


def _key_part(value):
    return " ".join(str(value or "").split())


def _natural_key(fields):
    return "02:" + "|".join(
        (
            f"batch={_key_part(fields['batch'])}",
            f"product={_key_part(fields['product_name'])}",
            f"province={_key_part(fields['province'])}",
            f"county={_key_part(fields['county'])}",
            f"applicant={_key_part(fields['applicant'])}",
        )
    )


def parse_pdf_rows(body, *, file_name, metadata=None):
    """Parse product rows and page locators from a CNIPA PDF attachment."""

    metadata = dict(metadata or {})
    reader = PdfReader(io.BytesIO(bytes(body)), strict=False)
    records = []
    seen = set()
    expected_seq = 1
    for page_no, page in enumerate(reader.pages, start=1):
        current = None
        blocks = []
        for raw_line in (page.extract_text() or "").splitlines():
            line = _line(raw_line)
            if not line or _PAGE_NUMBER.fullmatch(line):
                continue
            match = _SEQUENCE.match(line)
            if match and int(match.group(1)) == expected_seq:
                if current is not None:
                    blocks.append(current)
                current = {
                    "seq": expected_seq,
                    "parts": [match.group(2)] if match.group(2) else [],
                }
                expected_seq += 1
            elif current is not None:
                current["parts"].append(line)
        if current is not None:
            blocks.append(current)

        for row_no, block in enumerate(blocks, start=1):
            fields = _block_fields(block["parts"])
            product_name = fields["product_name"]
            if not product_name:
                continue
            announcement_id = str(
                metadata.get("announcement_id")
                or Path(file_name).stem
            )
            seq = block["seq"]
            batch = (
                metadata.get("batch")
                or metadata.get("announcement_no")
                or announcement_id
            )
            locator = (
                f"pdf={file_name}; page={page_no}; "
                f"row={row_no}; seq={seq}"
            )
            extra = {
                "announcement_id": announcement_id,
                "announcement_no": metadata.get("announcement_no"),
                "batch": batch,
                "cert_type": metadata.get("cert_type") or "地理标志",
                "product_name": product_name,
                "product_name_raw": product_name,
                "normalized_name": product_name,
                "province": fields["province"],
                "county": fields["county"],
                "applicant": fields["applicant"],
                "origin_scope": fields["origin_scope"],
                "file_name": file_name,
                "page": page_no,
                "row_no": row_no,
                "seq": seq,
            }
            source_item_id = _natural_key(
                {
                    "batch": batch,
                    "product_name": product_name,
                    "province": fields["province"],
                    "county": fields["county"],
                    "applicant": fields["applicant"],
                }
            )
            if source_item_id in seen:
                continue
            seen.add(source_item_id)
            content_hash = _row_hash(extra)
            records.append(
                {
                    "source_item_id": source_item_id,
                    "title": product_name,
                    "source_url": metadata.get("source_url"),
                    "long_term_url": metadata.get("long_term_url"),
                    "detail_url": None,
                    "detail_url_status": "missing",
                    "locator": locator,
                    "published_at": metadata.get("published_at"),
                    "content_type": PDF_MIME_TYPE,
                    "content_hash": content_hash,
                    "parser_version": "cnipa-pdf-v2",
                    "candidate_status": "deferred",
                    "candidate_reason": metadata.get(
                        "candidate_reason"
                    )
                    or "file-source:fixture",
                    "extra": extra,
                }
            )
    return records


def fixture_files(root):
    records = []
    for path in sorted(Path(root).glob("*.pdf")):
        body = path.read_bytes()
        records.append(
            {
                "file_name": path.name,
                "mime_type": mimetypes.guess_type(path.name)[0]
                or PDF_MIME_TYPE,
                "byte_size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "locator": "page=1; seq=1",
            }
        )
    return records


def fixture_item(path):
    path = Path(path)
    source_url = "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541"
    return {
        "source_id": "cnipa",
        "source_item_id": path.stem,
        "title": path.stem,
        "source_url": source_url,
        "long_term_url": source_url,
        "detail_url": None,
        "detail_url_status": "missing",
        "locator": "page=1; seq=1",
        "run_id": "fixture",
        "mode": "fixture",
        "candidate_status": "deferred",
        "candidate_reason": "file-source:fixture",
    }
