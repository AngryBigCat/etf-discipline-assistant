from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.settings import load_settings
from src.db.repository import (
    mark_task_done,
    mark_task_skipped,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_daily_report,
    upsert_etf_universe,
    upsert_strategy_signals,
)
from src.db.schema import init_schema
from src.tasks.generators import generate_all_tasks, generate_daily_tasks, generate_weekly_tasks
from src.tasks.rules import ALL_TASK_TYPES, TASK_GENERATE_AI_DAILY_REVIEW, TASK_INPUT_HOLDING_SNAPSHOT
from src.tasks.rules import TASK_RECORD_TRADE_LOG, TASK_REVIEW_STRATEGY_SIGNAL, TASK_UNREVIEWED_SIGNAL
from src.tasks.rules import TASK_STALE_MARKET_DATA, TASK_UPDATE_MARKET_DATA
from src.tasks.rules import TASK_GENERATE_WEEKLY_REPORT, TASK_EXCEED_MAX_POSITION
from src.strategy.rule_engine import ACTION_STRONG_BUY
from src.tasks.service import refresh_tasks_for_date
from src.ui.labels import (
    TASK_TYPE_LABELS,
    localize_task_category,
    localize_task_priority,
    localize_task_source_type,
    localize_task_status,
    localize_task_type,
)


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _seed_universe(memory_conn, settings):
    upsert_etf_universe(memory_conn, settings["assets"])


def _seed_prices(memory_conn, symbol: str, trade_date: str, close: float = 10.0):
    upsert_daily_prices(
        memory_conn,
        pd.DataFrame(
            {
                "symbol": [symbol],
                "trade_date": [trade_date],
                "open": [close],
                "high": [close],
                "low": [close],
                "close": [close],
                "volume": [1000.0],
                "amount": [close * 1000],
            }
        ),
    )


def _seed_snapshot(
    memory_conn,
    snapshot_date: str,
    *,
    etf_market_value: float = 20000,
    cash_value: float = 80000,
):
    total_account_value = etf_market_value + cash_value
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": snapshot_date,
            "cash_value": cash_value,
            "etf_market_value": etf_market_value,
            "total_account_value": total_account_value,
            "total_position": etf_market_value / total_account_value,
            "cash_position": cash_value / total_account_value,
        },
    )
    save_holding_snapshots(
        memory_conn,
        snapshot_date,
        [
            {
                "symbol": "A500",
                "quantity": 1000,
                "market_value": etf_market_value,
                "cost": etf_market_value * 0.9,
                "profit_loss": etf_market_value * 0.1,
                "profit_loss_rate": 0.11,
                "weight": etf_market_value / total_account_value,
            }
        ],
    )


def test_stale_market_data_only_generates_update_market_data_task(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    tasks = generate_all_tasks(memory_conn, settings, "2026-05-23")
    task_types = {task.task_type for task in tasks}
    assert TASK_UPDATE_MARKET_DATA in task_types
    assert TASK_STALE_MARKET_DATA not in task_types


def test_generate_input_holding_snapshot_when_missing(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    tasks = generate_daily_tasks(memory_conn, settings, "2026-05-23")
    task_types = {task.task_type for task in tasks}
    assert TASK_INPUT_HOLDING_SNAPSHOT in task_types


def test_generate_high_priority_task_when_exceed_max(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23", etf_market_value=70000, cash_value=30000)
    tasks = generate_all_tasks(memory_conn, settings, "2026-05-23")
    exceed_tasks = [task for task in tasks if task.task_type == TASK_EXCEED_MAX_POSITION]
    assert exceed_tasks
    assert exceed_tasks[0].priority == "high"


def test_generate_review_signal_task_when_unreviewed(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23")
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "final_score": 80,
                "trend_score": 20,
                "drawdown_score": 20,
                "volatility_score": 0,
                "anti_chase_score": 20,
                "position_score": 20,
                "special_score": 0,
                "action": ACTION_STRONG_BUY,
                "suggested_amount": 3000,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            },
            {
                "signal_date": "2026-05-23",
                "symbol": "DIVIDEND",
                "final_score": 70,
                "trend_score": 20,
                "drawdown_score": 20,
                "volatility_score": 0,
                "anti_chase_score": 10,
                "position_score": 20,
                "special_score": 0,
                "action": "hold",
                "suggested_amount": 0,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            },
        ],
    )
    tasks = generate_all_tasks(memory_conn, settings, "2026-05-23")
    review_tasks = [task for task in tasks if task.task_type == TASK_REVIEW_STRATEGY_SIGNAL]
    assert len(review_tasks) == 1
    assert "A500、DIVIDEND" in review_tasks[0].description
    assert "2 条待审核策略信号" in review_tasks[0].description
    assert not any(task.task_type == TASK_UNREVIEWED_SIGNAL for task in tasks)


def test_generate_record_trade_log_for_actionable_signal(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23")
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "final_score": 80,
                "trend_score": 20,
                "drawdown_score": 20,
                "volatility_score": 0,
                "anti_chase_score": 20,
                "position_score": 20,
                "special_score": 0,
                "action": ACTION_STRONG_BUY,
                "suggested_amount": 3000,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )
    tasks = generate_daily_tasks(memory_conn, settings, "2026-05-23")
    assert any(task.task_type == TASK_RECORD_TRADE_LOG for task in tasks)


def test_record_trade_log_not_generated_for_non_actionable_signal(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23")
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "final_score": 40,
                "trend_score": 10,
                "drawdown_score": 10,
                "volatility_score": 0,
                "anti_chase_score": 10,
                "position_score": 10,
                "special_score": 0,
                "action": "hold",
                "suggested_amount": 0,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )
    tasks = generate_daily_tasks(memory_conn, settings, "2026-05-23")
    assert not any(task.task_type == TASK_RECORD_TRADE_LOG for task in tasks)


def test_generate_ai_daily_review_when_report_exists(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23")
    upsert_daily_report(
        memory_conn,
        {
            "report_date": "2026-05-23",
            "total_position": 0.2,
            "cash_position": 0.8,
            "summary": "summary",
            "risk_warning": "risk",
            "action_suggestion": "action",
        },
    )
    tasks = generate_daily_tasks(memory_conn, settings, "2026-05-23")
    assert any(task.task_type == TASK_GENERATE_AI_DAILY_REVIEW for task in tasks)


def test_generate_weekly_report_task_on_friday(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    _seed_prices(memory_conn, "A500", "2026-05-23")
    _seed_snapshot(memory_conn, "2026-05-23")
    tasks = generate_weekly_tasks(memory_conn, settings, "2026-05-23")
    assert any(task.task_type == TASK_GENERATE_WEEKLY_REPORT for task in tasks)


def test_refresh_does_not_reset_done_task(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    target = next(task for task in tasks if task["task_type"] == TASK_INPUT_HOLDING_SNAPSHOT)
    mark_task_done(memory_conn, int(target["id"]))
    refreshed = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    done_task = next(item for item in refreshed if item["id"] == target["id"])
    assert done_task["status"] == "done"
    assert done_task["completed_at"] is not None


def test_refresh_does_not_duplicate_same_task(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    count = memory_conn.execute(
        """
        SELECT COUNT(*)
        FROM task_item
        WHERE task_date = ? AND task_type = ?
        """,
        ("2026-05-23", TASK_INPUT_HOLDING_SNAPSHOT),
    ).fetchone()[0]
    assert count == 1


def test_mark_task_done_sets_completed_at(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    task_id = int(tasks[0]["id"])
    mark_task_done(memory_conn, task_id, note="done")
    row = memory_conn.execute("SELECT status, completed_at, note FROM task_item WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "done"
    assert row["completed_at"] is not None
    assert row["note"] == "done"


def test_mark_task_skipped_sets_skipped_at(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    task_id = int(tasks[0]["id"])
    mark_task_skipped(memory_conn, task_id, note="skip")
    row = memory_conn.execute("SELECT status, skipped_at, note FROM task_item WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "skipped"
    assert row["skipped_at"] is not None
    assert row["note"] == "skip"


def test_task_generation_does_not_touch_real_tables(memory_conn, settings):
    _seed_universe(memory_conn, settings)
    trade_log_count = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    holding_count = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_count = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]
    signal_count = memory_conn.execute("SELECT COUNT(*) FROM strategy_signal").fetchone()[0]

    refresh_tasks_for_date(memory_conn, settings, "2026-05-23")

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_log_count
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == holding_count
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_count
    assert memory_conn.execute("SELECT COUNT(*) FROM strategy_signal").fetchone()[0] == signal_count


def test_task_labels_cover_all_task_types():
    assert set(TASK_TYPE_LABELS.keys()) == ALL_TASK_TYPES


def test_task_labels_do_not_expose_raw_values():
    for task_type in ALL_TASK_TYPES:
        assert localize_task_type(task_type) != task_type
    for value in ("daily", "weekly", "risk", "review", "data"):
        assert localize_task_category(value) != value
    for value in ("high", "normal", "low"):
        assert localize_task_priority(value) != value
    for value in ("pending", "done", "skipped"):
        assert localize_task_status(value) != value
    for value in ("daily_price", "strategy_signal", "trade_log"):
        localized = localize_task_source_type(value)
        assert localized not in {value, None, ""}
