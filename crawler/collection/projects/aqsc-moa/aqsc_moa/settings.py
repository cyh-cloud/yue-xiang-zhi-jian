from pathlib import Path
import sys

CRAWLER_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = CRAWLER_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawler.collection.shared.crawler_collection.pipelines import (
    collection_settings,
)


globals().update(
    collection_settings(
        bot_name="aqsc-moa",
        package_name="aqsc_moa",
        database_path=str(CRAWLER_ROOT / "data" / "crawler.db"),
        download_root=str(CRAWLER_ROOT / "download"),
        registry_path=str(CRAWLER_ROOT / "docs" / "sources.json"),
        candidate_writer="aqsc_moa.candidate.write_candidate",
    )
)
