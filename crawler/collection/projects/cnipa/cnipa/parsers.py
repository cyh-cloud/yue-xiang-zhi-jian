"""Fixture-only parsers for cnipa file evidence."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path


def fixture_files(root):
    records = []
    for path in sorted(Path(root).glob("*.pdf")):
        body = path.read_bytes()
        records.append(
            {
                "file_name": path.name,
                "mime_type": mimetypes.guess_type(path.name)[0]
                or "application/pdf",
                "byte_size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "locator": f"{path.name}#page=1",
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
        "locator": f"{path.name}#page=1",
        "fetch_url": "https://example.test/file.pdf?X-Amz-Signature=secret",
        "run_id": "fixture",
        "mode": "fixture",
        "rights_status": "attribution-required",
    }
