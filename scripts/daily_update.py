from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.workflows.daily_workflow import run_market_update


def main() -> None:
    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())

    with db_session(db_path) as conn:
        result = run_market_update(conn, settings)

    if result.success:
        logger.info(result.message)
        if result.detail:
            logger.info(result.detail)
    else:
        logger.warning(result.message)
        if result.detail:
            logger.warning(result.detail)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
