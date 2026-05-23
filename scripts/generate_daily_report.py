from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.reports.daily_report import build_and_save_daily_report
from src.utils.date_utils import today_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily discipline report")
    parser.add_argument("--date", dest="report_date", default=None, help="Report date YYYY-MM-DD")
    args = parser.parse_args()

    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())
    report_date = args.report_date or today_str()

    with db_session(db_path) as conn:
        report, saved, message = build_and_save_daily_report(conn, settings, report_date)

    if saved:
        logger.info(message)
        logger.info("Summary preview:\n{}", report.get("summary", "")[:200])
    else:
        logger.warning(message)


if __name__ == "__main__":
    main()
