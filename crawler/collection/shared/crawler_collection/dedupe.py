"""Natural keys used by stage and candidate upserts."""

from __future__ import annotations


def stage_natural_key(item, *, raw_fetch_id):
    return (str(raw_fetch_id), str(item.source_item_id))


def candidate_natural_key(item):
    return (str(item.source_id), str(item.source_item_id))
