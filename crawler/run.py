import argparse
from pathlib import Path

from .pipeline import RUN_MODES, RunConfig, run_source


def main():
    parser = argparse.ArgumentParser(description="Run one crawler source.")
    parser.add_argument("source_id")
    parser.add_argument("--mode", choices=RUN_MODES, default="fixture")
    parser.add_argument("--database", default="crawler/data/crawler.db")
    parser.add_argument("--download-root", default="crawler/download")
    parser.add_argument("--fixture-root", default="crawler/tests/fixtures")
    parser.add_argument("--page-limit", type=int, default=100)
    parser.add_argument("--xlsx-root", default="crawler/download/www.aqsc.agri.cn")
    parser.add_argument("--pdf-root", default="crawler/download/ggfw.cnipa.gov.cn")
    parser.add_argument("--source-root", default=None)
    args = parser.parse_args()
    config = RunConfig(
        database_path=Path(args.database),
        download_root=Path(args.download_root),
        fixture_root=Path(args.fixture_root),
        page_limit=args.page_limit,
        xlsx_root=Path(args.xlsx_root),
        pdf_root=Path(args.pdf_root),
        source_root=Path(args.source_root) if args.source_root else None,
    )
    result = run_source(args.source_id, args.mode, config)
    print(result)


if __name__ == "__main__":
    main()
