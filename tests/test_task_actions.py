from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from src.config.settings import load_settings
from src.db.repository import (
    list_task_action_logs,
    list_task_action_logs_by_task,
    upsert_etf_universe,
    upsert_strategy_signals,
)
from src.db.schema import init_schema
from src.tasks.actions import EXECUTABLE_TASK_TYPES, execute_task_action, is_executable_task
from src.tasks.rules import (
    TASK_CHECK_PORTFOLIO_RISK,
    TASK_GENERATE_DAILY_REPORT,
    TASK_GENERATE_STRATEGY_SIGNAL,
    TASK_INPUT_HOLDING_SNAPSHOT,
    TASK_RECORD_TRADE_LOG,
    TASK_REVIEW_STRATEGY_SIGNAL,
    TASK_UPDATE_MARKET_DATA,
)
from src.tasks.service import execute_task, refresh_tasks_for_date
from src.workflows.daily_workflow import WorkflowResult


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _find_task(tasks: list[dict], task_type: str) -> dict | None:
    return next((task for task in tasks if task["task_type"] == task_type), None)


def test_executable_task_whitelist():
    assert is_executable_task(TASK_UPDATE_MARKET_DATA)
    assert is_executable_task(TASK_GENERATE_STRATEGY_SIGNAL)
    assert is_executable_task(TASK_GENERATE_DAILY_REPORT)
    assert not is_executable_task(TASK_REVIEW_STRATEGY_SIGNAL)
    assert not is_executable_task(TASK_INPUT_HOLDING_SNAPSHOT)
    assert not is_executable_task(TASK_RECORD_TRADE_LOG)
    assert not is_executable_task(TASK_CHECK_PORTFOLIO_RISK)
    assert len(EXECUTABLE_TASK_TYPES) == 6


def test_execute_task_action_rejects_non_executable(memory_conn, settings):
    result = execute_task_action(
        memory_conn,
        settings,
        {
            "task_type": TASK_REVIEW_STRATEGY_SIGNAL,
            "task_date": "2026-05-23",
            "source_key": "",
        },
    )
    assert result.success is False
    assert result.should_mark_done is False


@patch("src.tasks.actions.run_market_update")
def test_execute_task_success_writes_log_and_marks_done(mock_run, memory_conn, settings):
    mock_run.return_value = WorkflowResult(success=True, message="行情更新完成")
    upsert_etf_universe(memory_conn, settings["assets"])
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    target = _find_task(tasks, TASK_UPDATE_MARKET_DATA)
    assert target is not None

    trade_log_count = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    holding_count = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_count = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]

    result = execute_task(memory_conn, settings, int(target["id"]))
    assert result.success is True

    task_row = memory_conn.execute("SELECT status FROM task_item WHERE id = ?", (target["id"],)).fetchone()
    assert task_row["status"] == "done"

    logs = list_task_action_logs_by_task(memory_conn, int(target["id"]))
    assert len(logs) == 1
    assert logs[0]["success"] == 1

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_log_count
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == holding_count
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_count


@patch("src.tasks.actions.run_market_update")
def test_execute_task_failure_keeps_pending(mock_run, memory_conn, settings):
    mock_run.return_value = WorkflowResult(success=False, message="行情更新失败", detail="network")
    upsert_etf_universe(memory_conn, settings["assets"])
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    target = _find_task(tasks, TASK_UPDATE_MARKET_DATA)
    assert target is not None

    result = execute_task(memory_conn, settings, int(target["id"]))
    assert result.success is False

    task_row = memory_conn.execute("SELECT status FROM task_item WHERE id = ?", (target["id"],)).fetchone()
    assert task_row["status"] == "pending"

    logs = list_task_action_logs(memory_conn, limit=10)
    assert len(logs) == 1
    assert logs[0]["success"] == 0


@patch("src.tasks.actions.run_generate_signals")
def test_execute_task_does_not_auto_review_signals(mock_run, memory_conn, settings):
    mock_run.return_value = WorkflowResult(success=True, message="策略信号已生成")
    upsert_etf_universe(memory_conn, settings["assets"])
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "trend_score": 10,
                "drawdown_score": 10,
                "volatility_score": 0,
                "position_score": 10,
                "anti_chase_score": 10,
                "special_score": 0,
                "final_score": 80,
                "action": "strong_buy",
                "suggested_amount": 3000,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )
    memory_conn.execute(
        """
        INSERT INTO task_item (
            task_date, category, task_type, title, description, priority, status,
            source_type, source_key
        ) VALUES (
            '2026-05-23', 'daily', ?, '生成策略信号', 'test', 'normal', 'pending',
            'strategy_signal', 'latest'
        )
        """,
        (TASK_GENERATE_STRATEGY_SIGNAL,),
    )
    task_id = int(memory_conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    execute_task(memory_conn, settings, task_id)

    review_status = memory_conn.execute(
        "SELECT review_status FROM strategy_signal WHERE symbol = 'A500'"
    ).fetchone()[0]
    assert review_status == "generated"


@patch("src.tasks.actions.run_market_update")
def test_execute_task_refreshes_tasks(mock_run, memory_conn, settings):
    mock_run.return_value = WorkflowResult(success=True, message="行情更新完成")
    upsert_etf_universe(memory_conn, settings["assets"])
    tasks = refresh_tasks_for_date(memory_conn, settings, "2026-05-23")
    target = _find_task(tasks, TASK_UPDATE_MARKET_DATA)
    assert target is not None

    execute_task(memory_conn, settings, int(target["id"]))

    refreshed = memory_conn.execute(
        "SELECT COUNT(*) FROM task_item WHERE task_date = ?",
        ("2026-05-23",),
    ).fetchone()[0]
    assert refreshed >= 1
