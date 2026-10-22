"""Stable process exit codes for collection run reports."""

from __future__ import annotations


SUCCESS = 0
FAILED = 1
PARTIAL = 2


def exit_code_for_status(status):
    """Map a run report status to its CLI contract."""
    status = str(status or "").strip()
    if status == "succeeded":
        return SUCCESS
    if status == "partial":
        return PARTIAL
    return FAILED
