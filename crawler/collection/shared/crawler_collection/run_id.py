"""Run identity helpers shared by all site spiders."""

from __future__ import annotations

from uuid import uuid4


def new_run_id(source_id):
    return f"{source_id}-{uuid4().hex}"
