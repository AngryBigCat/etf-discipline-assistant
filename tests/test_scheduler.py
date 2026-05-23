from __future__ import annotations

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import load_settings
from src.db.repository import save_account_snapshot, save_holding_snapshots, upsert_strategy_signals
from src.db.schema import init_schema
from src.scheduler.defaults import DEFAULT_SCHEDULER_JOBS
from src.scheduler.models import RUN_STATUS_FAILED, RUN_STATUS_SKIPPED, RUN_STATUS_SUCCESS
from src.scheduler.repository import (
    ensure_default_scheduler_jobs,
    get_scheduler_job,
    list_scheduler_jobs,
    list_scheduler_run_logs,
    update_scheduler_job_enabled,
)
from src.scheduler.runner import run_scheduler_job
from src.scheduler.service import build_cron_trigger, parse_cron_expr
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


def test_ensure_default_scheduler_jobs_is_idempotent(memory_conn):
    ensure_default_scheduler_jobs(memory_conn)
    ensure_default_scheduler_jobs(memory_conn)
    jobs = list_scheduler_jobs(memory_conn)
    assert len(jobs) == len(DEFAULT_SCHEDULER_JOBS)
    keys = {job["job_key"] for job in jobs}
    assert keys == {"daily_after_close", "weekly_review"}


def test_list_scheduler_jobs_reads_defaults(memory_conn):
    ensure_default_scheduler_jobs(memory_conn)
    jobs = list_scheduler_jobs(memory_conn)
    daily = next(job for job in jobs if job["job_key"] == "daily_after_close")
    assert daily["name"] == "每日收盘后流程"
    assert daily["cron_expr"] == "30 16 * * mon-fri"
    assert daily["job_type"] == "daily_pipeline"


def test_disabled_job_returns_skipped(memory_conn, settings):
    ensure_default_scheduler_jobs(memory_conn)
    update_scheduler_job_enabled(memory_conn, "daily_after_close", False)

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            result = run_scheduler_job("daily_after_close")

    assert result.success is True
    assert "跳过" in result.message
    logs = list_scheduler_run_logs(memory_conn, limit=10)
    assert logs[0]["status"] == RUN_STATUS_SKIPPED


def test_parse_cron_expr_supports_weekday_names():
    fields = parse_cron_expr("30 16 * * mon-fri")
    assert fields == {
        "minute": "30",
        "hour": "16",
        "day": "*",
        "month": "*",
        "day_of_week": "mon-fri",
    }


def test_build_cron_trigger_parses_weekday_names():
    job = {
        "job_key": "daily_after_close",
        "cron_expr": "30 16 * * mon-fri",
        "timezone": "Asia/Shanghai",
    }
    trigger = build_cron_trigger(job)
    assert isinstance(trigger, CronTrigger)
    next_run = trigger.get_next_fire_time(None, datetime(2026, 5, 23, 10, 0, tzinfo=trigger.timezone))
    assert next_run is not None


@patch("src.scheduler.runner.run_daily_pipeline")
def test_run_scheduler_job_success_writes_success_log(mock_pipeline, memory_conn, settings):
    ensure_default_scheduler_jobs(memory_conn)
    mock_pipeline.return_value = WorkflowResult(success=True, message="每日流程完成", detail="ok")

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            result = run_scheduler_job("daily_after_close")

    assert result.success is True
    logs = list_scheduler_run_logs(memory_conn, limit=5)
    assert logs[0]["status"] == RUN_STATUS_SUCCESS
    assert logs[0]["message"] == "每日流程完成"


@patch("src.scheduler.runner.run_daily_pipeline")
def test_run_scheduler_job_failure_writes_failed_log(mock_pipeline, memory_conn, settings):
    ensure_default_scheduler_jobs(memory_conn)
    mock_pipeline.return_value = WorkflowResult(success=False, message="失败", detail="step error")

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            result = run_scheduler_job("daily_after_close")

    assert result.success is False
    logs = list_scheduler_run_logs(memory_conn, limit=5)
    assert logs[0]["status"] == RUN_STATUS_FAILED


@patch("src.scheduler.runner._run_pipeline", side_effect=RuntimeError("boom"))
def test_run_scheduler_job_exception_does_not_crash(_mock_pipeline, memory_conn, settings):
    ensure_default_scheduler_jobs(memory_conn)

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            result = run_scheduler_job("daily_after_close")

    assert result.success is False
    logs = list_scheduler_run_logs(memory_conn, limit=5)
    assert logs[0]["status"] == RUN_STATUS_FAILED
    assert "异常" in logs[0]["message"]


@patch("src.scheduler.runner.run_daily_pipeline")
def test_run_scheduler_job_does_not_write_trade_log(
    mock_pipeline,
    memory_conn,
    settings,
):
    ensure_default_scheduler_jobs(memory_conn)
    mock_pipeline.return_value = WorkflowResult(success=True, message="ok")

    trade_before = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

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
                "final_score": 70,
                "action": "small_buy",
                "suggested_amount": 1000,
                "reason": "test",
                "confidence_level": "high",
                "review_status": "pending",
            }
        ],
    )
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": "2026-05-23",
            "cash_value": 10000,
            "etf_market_value": 50000,
            "total_account_value": 60000,
        },
    )
    save_holding_snapshots(
        memory_conn,
        "2026-05-23",
        [
            {
                "symbol": "A500",
                "quantity": 100,
                "market_value": 50000,
                "cost": 45000,
            }
        ],
    )
    signal_status_before = memory_conn.execute(
        "SELECT review_status FROM strategy_signal LIMIT 1"
    ).fetchone()[0]
    snapshot_before = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_before = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            run_scheduler_job("daily_after_close")

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_before
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == snapshot_before
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_before
    signal_status_after = memory_conn.execute(
        "SELECT review_status FROM strategy_signal LIMIT 1"
    ).fetchone()[0]
    assert signal_status_after == signal_status_before == "pending"


def test_list_scheduler_run_logs_returns_recent_entries(memory_conn):
    from src.scheduler.repository import save_scheduler_run_log

    ensure_default_scheduler_jobs(memory_conn)
    save_scheduler_run_log(
        memory_conn,
        {
            "job_key": "daily_after_close",
            "scheduled_time": "2026-05-23T16:30:00",
            "started_at": "2026-05-23T16:30:01",
            "finished_at": "2026-05-23T16:31:00",
            "status": RUN_STATUS_SUCCESS,
            "message": "ok",
            "detail": None,
        },
    )

    logs = list_scheduler_run_logs(memory_conn, limit=100)
    assert len(logs) == 1
    assert logs[0]["job_name"] == "每日收盘后流程"


@patch("src.scheduler.runner.run_weekly_pipeline")
def test_scheduler_job_does_not_auto_trade(mock_pipeline, memory_conn, settings):
    ensure_default_scheduler_jobs(memory_conn)
    mock_pipeline.return_value = WorkflowResult(success=True, message="weekly ok")

    with patch("src.scheduler.runner.db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = memory_conn
        mock_session.return_value.__exit__.return_value = None
        with patch("src.scheduler.runner.load_settings", return_value=settings):
            result = run_scheduler_job("weekly_review")

    assert result.success is True
    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == 0
    mock_pipeline.assert_called_once()
