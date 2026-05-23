from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.data.backfill import backfill_all_prices, backfill_symbol_prices
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.utils.date_utils import today_str
from src.utils.network import build_network_hint, get_system_proxies


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ETF historical prices via AKShare")
    parser.add_argument("--symbol", default=None, help="Symbol from config.yaml, e.g. A500")
    parser.add_argument("--all", action="store_true", help="Backfill all enabled symbols")
    parser.add_argument("--start", dest="start_date", default="2021-01-01")
    parser.add_argument("--end", dest="end_date", default=None)
    args = parser.parse_args()

    if not args.all and not args.symbol:
        parser.error("请指定 --symbol 或 --all")

    settings = load_settings()
    end_date = args.end_date or today_str()
    db_path = ensure_database_dir(get_database_path())

    with db_session(db_path) as conn:
        if args.all:
            results = backfill_all_prices(conn, settings, args.start_date, end_date)
        else:
            results = [
                backfill_symbol_prices(conn, settings, args.symbol, args.start_date, end_date)
            ]

    success_count = sum(1 for item in results if item.success)
    logger.info("Backfill finished: {}/{} succeeded", success_count, len(results))
    for item in results:
        if item.success:
            logger.info("{} [{} ~ {}]: {}", item.symbol, item.start_date, item.end_date, item.message)
        else:
            logger.warning("{} [{} ~ {}]: {}", item.symbol, item.start_date, item.end_date, item.message)

    if success_count == 0 and results:
        proxies = get_system_proxies()
        if proxies:
            logger.warning("全部补全失败。当前系统代理：{}", proxies.get("https") or proxies.get("http"))
        logger.warning("{}", build_network_hint())


if __name__ == "__main__":
    main()
