from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.backtest.models import BacktestConfig
from src.backtest.service import run_and_save_backtest
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.utils.date_utils import today_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ETF backtest simulation")
    parser.add_argument("--symbol", default="A500")
    parser.add_argument("--strategy", default="baseline_dca")
    parser.add_argument("--start", dest="start_date", default="2021-01-01")
    parser.add_argument("--end", dest="end_date", default=None)
    parser.add_argument("--cash", dest="initial_cash", type=float, default=100000.0)
    parser.add_argument("--amount", dest="fixed_amount", type=float, default=3000.0)
    parser.add_argument("--frequency", default="monthly", choices=["weekly", "monthly"])
    args = parser.parse_args()

    config = BacktestConfig(
        symbol=args.symbol,
        strategy_name=args.strategy,
        start_date=args.start_date,
        end_date=args.end_date or today_str(),
        initial_cash=args.initial_cash,
        fixed_amount=args.fixed_amount,
        frequency=args.frequency,
    )

    db_path = ensure_database_dir(get_database_path())
    with db_session(db_path) as conn:
        run_id, result, message = run_and_save_backtest(conn, config)

    if run_id is None:
        logger.warning(message)
        return

    logger.info(message)
    logger.info("run_id={}", run_id)
    logger.info("final_value={:.2f}", result.final_value)
    logger.info("total_return={:.2%}", result.total_return)
    logger.info("max_drawdown={:.2%}", result.max_drawdown)
    logger.info("trade_count={}", result.trade_count)


if __name__ == "__main__":
    main()
