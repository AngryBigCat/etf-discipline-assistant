from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.sync import sync_assets_from_seed
from src.db.connection import db_session, ensure_database_dir, get_database_path


def main() -> None:
    db_path = ensure_database_dir(get_database_path())
    with db_session(db_path) as conn:
        stats = sync_assets_from_seed(conn, force=False)
    logger.info(
        "Seeded {} ETF universe records into {} (skipped {} disabled)",
        stats["imported"],
        db_path,
        stats["skipped"],
    )


if __name__ == "__main__":
    main()
