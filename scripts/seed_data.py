from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.db.repository import upsert_etf_universe


def main() -> None:
    settings = load_settings()
    assets = settings.get("assets", [])
    db_path = ensure_database_dir(get_database_path())
    with db_session(db_path) as conn:
        count = upsert_etf_universe(conn, assets)
    logger.info("Seeded {} ETF universe records into {}", count, db_path)


if __name__ == "__main__":
    main()
