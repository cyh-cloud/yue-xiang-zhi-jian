import json
from pathlib import Path

from .. import source_registry


SOURCE_ID = "cass-linguistics"


def discover(fixture_root, registry_path=None):
    """Load the public CASS fixture without following external or login-only links."""
    path = Path(fixture_root) / "discover.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_id") != SOURCE_ID:
        raise ValueError(f"expected source_id {SOURCE_ID}")
    articles = []
    source = source_registry.load_registry(registry_path)[SOURCE_ID]
    default_rights = source_registry.rights_fields(source)
    for raw in data.get("items") or []:
        if raw.get("body_access") != "public":
            continue
        source_url = raw.get("source_url")
        long_term_url = raw.get("long_term_url") or source_url
        if not source_url or not long_term_url:
            continue
        articles.append(
            {
                "source_item_id": str(raw["source_item_id"]),
                "title": raw["title"],
                "summary": raw.get("summary"),
                "published_at": raw.get("published_at"),
                "body_text": raw.get("body_text"),
                "media": raw.get("media"),
                "source_url": source_url,
                "long_term_url": long_term_url,
                "body_access": "public",
                "rights_status": (
                    raw.get("rights_status")
                    or default_rights["rights_status"]
                ),
                "attribution_required": default_rights[
                    "attribution_required"
                ],
                "attribution_text": (
                    raw.get("media") or default_rights["attribution_text"]
                ),
                "rights_evidence_url": default_rights[
                    "rights_evidence_url"
                ],
            }
        )
    return articles


def deferred_subresources(fixture_root):
    path = Path(fixture_root) / "discover.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        subresource
        for subresource in data.get("subresources") or []
        if subresource.get("access") == "login-required"
    ]
