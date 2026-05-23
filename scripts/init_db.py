from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.db.schema import init_schema


def main() -> None:
    db_path = ensure_database_dir(get_database_path())
    with db_session(db_path) as conn:
        init_schema(conn)
    logger.info("Database initialized at {}", db_path)


if __name__ == "__main__":
    main()
