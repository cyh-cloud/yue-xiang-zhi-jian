from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.collection.shared.crawler_collection.pipelines import (
    collection_settings,
)


globals().update(
    collection_settings(
        bot_name="ihchina",
        package_name="ihchina",
        database_path=str(ROOT / "crawler.db"),
        download_root=str(ROOT / "downloads"),
        registry_path=str(ROOT / "docs" / "sources.json"),
    )
)
