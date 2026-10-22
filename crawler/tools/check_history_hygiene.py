"""Scan reachable Git history for crawler evidence and credential leaks."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "crawler" / "docs" / "operations" / "history-hygiene-baseline.json"

try:
    from crawler.tools.public_hygiene import scan_fixture_bytes
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT))
    from crawler.tools.public_hygiene import scan_fixture_bytes

CONTENT_MARKERS = {
    "set-cookie": re.compile(rb"set-cookie\s*:", re.IGNORECASE),
    "authorization": re.compile(rb"authorization\s*:", re.IGNORECASE),
    "bearer-token": re.compile(rb"\bbearer\s+[a-z0-9._-]{8,}", re.IGNORECASE),
    "signature": re.compile(
        rb"[?&](?:x-amz-signature|signature|sig)=", re.IGNORECASE
    ),
    "api-key": re.compile(
        rb"\bapi[_-]?key\s*[:=]|\baccess_token\s*[:=]|\bsk-[a-z0-9]{20,}",
        re.IGNORECASE,
    ),
    "private-key": re.compile(
        rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE
    ),
}

HIGH_CONFIDENCE_MARKERS = {
    "set-cookie": re.compile(rb"set-cookie\s*:\s*[^\s<]", re.IGNORECASE),
    "authorization": re.compile(
        rb"authorization\s*:\s*(?:bearer|basic|token)\s+[a-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    "bearer-token": CONTENT_MARKERS["bearer-token"],
    "signature": re.compile(
        rb"[?&](?:x-amz-signature|signature|sig)="
        rb"[a-z0-9%._~+/=-]{12,}",
        re.IGNORECASE,
    ),
    "api-key": re.compile(
        rb"\b(?:api[_-]?key|access_token)\s*[:=]\s*"
        rb"[a-z0-9._~+/=-]{16,}|\bsk-[a-z0-9]{20,}",
        re.IGNORECASE,
    ),
    "private-key": CONTENT_MARKERS["private-key"],
}

TEXT_SUFFIXES = {
    "",
    ".csv",
    ".headers",
    ".htm",
    ".html",
    ".json",
    ".log",
    ".md",
    ".txt",
    ".xml",
}


def _git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _object_paths():
    result = _git("rev-list", "--objects", "--all")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    paths = defaultdict(set)
    for raw_line in result.stdout.splitlines():
        parts = raw_line.decode("utf-8", errors="replace").split(" ", 1)
        object_id = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        paths[object_id].add(path)
    return paths


def _is_text(path):
    return Path(path or "").suffix.lower() in TEXT_SUFFIXES


def _valid_chinese_id(value):
    if not re.fullmatch(r"\d{17}[\dXx]", value):
        return False
    try:
        date(
            int(value[6:10]),
            int(value[10:12]),
            int(value[12:14]),
        )
    except ValueError:
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    total = sum(int(digit) * weight for digit, weight in zip(value[:17], weights))
    return checks[total % 11].upper() == value[-1].upper()


def _personal_markers(body):
    text = body.decode("utf-8", errors="ignore")
    categories = []
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
        categories.append("personal-phone")
    if re.search(
        r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    ):
        categories.append("personal-email")
    if any(
        _valid_chinese_id(match.group(0))
        for match in re.finditer(r"(?<!\d)\d{17}[\dXx](?!\d)", text)
    ):
        categories.append("personal-id")
    return categories


def _is_evidence_path(path):
    normalized = (path or "").replace("\\", "/")
    return (
        normalized.startswith("crawler/download/")
        or normalized.startswith("crawler/tests/fixtures/evidence/")
        or normalized.endswith(".headers")
    )


def _is_private_path(path):
    normalized = (path or "").replace("\\", "/").lower()
    parts = set(normalized.split("/"))
    if parts & {
        "private",
        "session",
        "sessions",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "secret",
        "secrets",
    }:
        return True
    return normalized.endswith(
        (".session", ".cookie", ".credentials", ".secrets")
    )


def _blob_objects(paths_by_object):
    object_ids = list(paths_by_object)
    request = ("\n".join(object_ids) + "\n").encode("ascii")
    result = _git_with_input(
        "cat-file", "--batch-check", input_bytes=request
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    blobs = {}
    for raw_line in result.stdout.splitlines():
        parts = raw_line.decode("ascii", errors="replace").split()
        if len(parts) >= 3 and parts[1] == "blob":
            blobs[parts[0]] = int(parts[2])
    return blobs


def _blob_contents(blob_ids):
    if not blob_ids:
        return {}
    request = ("\n".join(blob_ids) + "\n").encode("ascii")
    result = _git_with_input("cat-file", "--batch", input_bytes=request)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    data = result.stdout
    position = 0
    contents = {}
    for expected_id in blob_ids:
        newline = data.index(b"\n", position)
        header = data[position:newline].decode("ascii", errors="replace").split()
        position = newline + 1
        if len(header) < 3 or header[1] != "blob":
            continue
        size = int(header[2])
        contents[expected_id] = data[position : position + size]
        position += size + 1
    return contents


def _git_with_input(*args, input_bytes):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def scan_history():
    findings = set()
    paths_by_object = _object_paths()
    blobs = _blob_objects(paths_by_object)
    contents = _blob_contents(list(blobs))
    for object_id, body in contents.items():
        paths = paths_by_object[object_id]
        for path in paths:
            normalized = path.replace("\\", "/")
            if normalized.startswith("crawler/download/") or normalized.endswith(
                ".headers"
            ):
                findings.add((object_id, normalized, "raw-evidence-path"))
            if _is_private_path(normalized):
                findings.add((object_id, normalized, "private-session-path"))
        evidence_paths = {
            path for path in paths if _is_evidence_path(path)
        }
        for path in evidence_paths:
            for category in scan_fixture_bytes(path, body):
                findings.add((object_id, path.replace("\\", "/"), category))
            if _is_text(path):
                for category, pattern in CONTENT_MARKERS.items():
                    if pattern.search(body):
                        findings.add(
                            (object_id, path.replace("\\", "/"), category)
                        )
        text_paths = {path for path in paths if _is_text(path)}
        non_evidence_text = {
            path for path in text_paths if path not in evidence_paths
        }
        if non_evidence_text:
            for category, pattern in HIGH_CONFIDENCE_MARKERS.items():
                if pattern.search(body):
                    findings.add((object_id, min(non_evidence_text), category))
        broad_scan = any(_is_private_path(path) for path in paths)
        if text_paths and broad_scan:
            for category in _personal_markers(body):
                findings.add((object_id, min(text_paths), category))
    return sorted(findings)


def _load_baseline():
    if not BASELINE.exists():
        return set()
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {
        (item["object"], item["path"], item["category"])
        for item in payload.get("findings", [])
    }


def _write_baseline(findings):
    payload = {
        "note": (
            "The clean public branch has no historical findings. The baseline "
            "is intentionally empty; values are never stored."
        ),
        "findings": [
            {"object": object_id, "path": path, "category": category}
            for object_id, path, category in findings
        ],
    }
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    findings = scan_history()
    if args.write_baseline:
        _write_baseline(findings)
        print(f"history hygiene baseline written: {len(findings)} finding(s)")
        return 0
    known = _load_baseline()
    new_findings = [item for item in findings if item not in known]
    if new_findings:
        for object_id, path, category in new_findings:
            print(
                f"{category}: {object_id[:12]} {path or '<no-path>'}",
                file=sys.stderr,
            )
        print(
            f"history hygiene failed: {len(new_findings)} new finding(s)",
            file=sys.stderr,
        )
        return 1
    print(
        "history hygiene passed: "
        f"{len(findings)} documented finding(s), no new leaks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
