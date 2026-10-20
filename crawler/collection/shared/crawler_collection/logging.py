"""Structured run logging without cookies, credentials, or resume bodies."""

from __future__ import annotations

import json
from pathlib import Path


def append_run_report(path, report):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
    return target
