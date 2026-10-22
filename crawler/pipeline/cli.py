"""Command-line entry point for crawler batch conversion."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .converter import run_batch


def _parser():
    parser = argparse.ArgumentParser(
        description="Convert crawler std candidates into auditable business rows."
    )
    parser.add_argument("--crawler-db", required=True, type=Path)
    parser.add_argument(
        "--business-db",
        type=Path,
        help="business database path; defaults to YUEXIANG_DB for real writes",
    )
    parser.add_argument(
        "--domain",
        required=True,
        choices=("jobs", "agri", "dialects", "ich"),
    )
    parser.add_argument("--batch-key", required=True)
    parser.add_argument(
        "--converter-version",
        default="crawler-converter-v1",
    )
    parser.add_argument(
        "--target-database",
        default="yuexiang",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write to the business database; omitted means dry-run",
    )
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--std-entity-id", action="append", type=int, default=[])
    parser.add_argument("--source-registry", type=Path)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    batch = {
        "batch_key": args.batch_key,
        "converter_version": args.converter_version,
        "target_database": args.target_database,
        "dry_run": not args.write,
        "source_ids": args.source_id,
        "std_entity_ids": args.std_entity_id,
    }
    result = run_batch(
        args.domain,
        batch,
        crawler_database_path=args.crawler_db,
        business_database_path=args.business_db,
        source_registry_path=args.source_registry,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
