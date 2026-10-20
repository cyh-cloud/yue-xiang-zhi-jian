"""Fixture-only parsers for aqsc-moa file evidence."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path


def fixture_files(root):
    records = []
    for path in sorted(Path(root).glob("*.xlsx")):
        body = path.read_bytes()
        records.append(
            {
                "file_name": path.name,
                "mime_type": mimetypes.guess_type(path.name)[0]
                or "application/octet-stream",
                "byte_size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "locator": f"{path.name}#Sheet1!A1",
            }
        )
    return records


def fixture_item(path):
    path = Path(path)
    source_url = (
        "http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm"
    )
    return {
        "source_id": "aqsc-moa",
        "source_item_id": path.stem,
        "title": path.stem,
        "source_url": source_url,
        "long_term_url": source_url,
        "detail_url": None,
        "detail_url_status": "missing",
        "locator": f"{path.name}#Sheet1!A1",
        "run_id": "fixture",
        "mode": "fixture",
        "rights_status": "attribution-required",
    }
