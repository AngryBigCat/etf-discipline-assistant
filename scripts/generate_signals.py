from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.db.repository import get_latest_strategy_signals
from src.strategy.rule_engine import get_action_label
from src.workflows.daily_workflow import run_generate_signals


def main() -> None:
    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())

    with db_session(db_path) as conn:
        result = run_generate_signals(conn, settings)
        if not result.success:
            raise SystemExit(result.message)
        signal_rows = get_latest_strategy_signals(conn)

    logger.info(result.message)
    for row in signal_rows:
        logger.info(
            "{} | score={:.1f} | {} | amount={:.0f} | {}",
            row["symbol"],
            row["final_score"],
            get_action_label(row["action"], settings),
            row["suggested_amount"],
            row["reason"],
        )


if __name__ == "__main__":
    main()
