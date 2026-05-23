from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.collectors.price_service import CompositeCollector
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.db.repository import (
    get_daily_prices,
    list_priceable_etfs,
    upsert_daily_prices,
    upsert_indicator_rows,
)
from src.indicators.indicator_service import compute_indicators_for_symbol


def main() -> None:
    db_path = ensure_database_dir(get_database_path())
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    collector = CompositeCollector()

    with db_session(db_path) as conn:
        etfs = list_priceable_etfs(conn)
        if not etfs:
            raise RuntimeError("No priceable ETFs found. Run seed_data.py first.")

        sources: dict[str, str] = {}
        for etf in etfs:
            symbol = etf["symbol"]
            fund_code = etf["fund_code"]
            result = collector.fetch_history(symbol, fund_code, start_date, end_date)
            upsert_daily_prices(conn, result.df)
            sources[symbol] = result.source
            logger.info(
                "Updated prices for {} via {} (fallback={})",
                symbol,
                result.source,
                result.used_fallback,
            )

            price_df = get_daily_prices(conn, symbol)
            indicator_rows = compute_indicators_for_symbol(symbol, price_df)
            if indicator_rows:
                upsert_indicator_rows(conn, indicator_rows)
                latest = indicator_rows[-1]
                logger.info(
                    "Updated indicators for {} on {} (confidence={})",
                    symbol,
                    latest["trade_date"],
                    latest["confidence_level"],
                )

    logger.info("Daily update completed. Sources: {}", sources)


if __name__ == "__main__":
    main()
