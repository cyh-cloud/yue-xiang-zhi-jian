"""Deterministic helpers for project-level fixture replay tests."""

from __future__ import annotations

from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def source_fixture_dir(source_id):
    evidence_dir = FIXTURE_ROOT / "evidence" / source_id
    if evidence_dir.is_dir():
        return evidence_dir
    return FIXTURE_ROOT / source_id
