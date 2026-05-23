from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.ai_review.review_service import generate_daily_ai_review
from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.utils.date_utils import today_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI daily discipline review")
    parser.add_argument("--date", dest="target_date", default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())
    target_date = args.target_date or today_str()

    with db_session(db_path) as conn:
        review, saved, message = generate_daily_ai_review(conn, settings, target_date)

    if saved:
        logger.info(message)
        logger.info("Discipline summary preview: {}", (review or {}).get("discipline_summary", "")[:200])
    else:
        logger.warning(message)


if __name__ == "__main__":
    main()
