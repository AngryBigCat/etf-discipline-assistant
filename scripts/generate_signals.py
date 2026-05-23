from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.strategy.rule_engine import get_action_label
from src.strategy.signal_generator import SnapshotRequiredError, generate_and_save_signals


def main() -> None:
    settings = load_settings()
    db_path = ensure_database_dir(get_database_path())

    with db_session(db_path) as conn:
        try:
            signals, context = generate_and_save_signals(conn, settings)
        except SnapshotRequiredError as exc:
            raise SystemExit(str(exc)) from exc

    logger.info("Generated {} strategy signals for {}", len(signals), context["signal_date"])
    for signal in signals:
        logger.info(
            "{} | score={:.1f} | {} | amount={:.0f} | {}",
            signal.symbol,
            signal.final_score,
            get_action_label(signal.action, settings),
            signal.suggested_amount,
            signal.reason,
        )


if __name__ == "__main__":
    main()
