from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.utils.date_utils import today_str
from src.workflows.daily_workflow import run_generate_ai_weekly_review


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI weekly discipline review")
    parser.add_argument("--start", dest="week_start", default=None, help="Week start YYYY-MM-DD")
    parser.add_argument("--end", dest="week_end", default=None, help="Week end YYYY-MM-DD")
    args = parser.parse_args()

    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())
    week_end = args.week_end or today_str()
    week_start = args.week_start or (
        datetime.strptime(week_end, "%Y-%m-%d") - timedelta(days=6)
    ).strftime("%Y-%m-%d")

    with db_session(db_path) as conn:
        result = run_generate_ai_weekly_review(conn, settings, week_start, week_end)

    if result.success:
        logger.info(result.message)
    else:
        logger.warning(result.message)
        if result.detail:
            logger.warning(result.detail)


if __name__ == "__main__":
    main()
