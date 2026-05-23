from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest

from src.config.settings import load_settings
from src.db.schema import init_schema
from src.workflows.daily_workflow import WorkflowResult
from src.workflows.pipelines import run_daily_pipeline, run_weekly_pipeline


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


@patch("src.workflows.pipelines.run_market_update")
@patch("src.workflows.pipelines.run_generate_signals")
@patch("src.workflows.pipelines._run_refresh_tasks")
@patch("src.workflows.pipelines.run_generate_daily_report")
@patch("src.workflows.pipelines.run_generate_ai_daily_review")
def test_daily_pipeline_runs_steps_in_order(
    mock_ai,
    mock_report,
    mock_refresh,
    mock_signals,
    mock_market,
    memory_conn,
    settings,
):
    call_order: list[str] = []

    def _track(name: str, result: WorkflowResult):
        def _inner(*args, **kwargs):
            call_order.append(name)
            return result

        return _inner

    mock_market.side_effect = _track("market_update", WorkflowResult(success=True, message="ok"))
    mock_signals.side_effect = _track("generate_signals", WorkflowResult(success=True, message="ok"))
    mock_report.side_effect = _track("daily_report", WorkflowResult(success=True, message="ok"))
    mock_ai.side_effect = _track("ai_daily_review", WorkflowResult(success=True, message="ok"))

    refresh_call_count = 0

    def refresh_side_effect(*args, **kwargs):
        nonlocal refresh_call_count
        refresh_call_count += 1
        step_name = "refresh_tasks" if refresh_call_count == 1 else "refresh_tasks_final"
        call_order.append(step_name)
        return WorkflowResult(success=True, message="ok")

    mock_refresh.side_effect = refresh_side_effect

    result = run_daily_pipeline(memory_conn, settings, run_date="2026-05-23")

    assert result.success is True
    assert call_order == [
        "market_update",
        "generate_signals",
        "refresh_tasks",
        "daily_report",
        "ai_daily_review",
        "refresh_tasks_final",
    ]
    steps = json.loads(result.detail or "[]")
    assert len(steps) == 6
    assert [step["step"] for step in steps] == call_order
    assert all(step["success"] for step in steps)


@patch("src.workflows.pipelines.run_market_update")
@patch("src.workflows.pipelines.run_generate_signals")
def test_daily_pipeline_stops_on_failure_without_rollback(
    mock_signals,
    mock_market,
    memory_conn,
    settings,
):
    mock_market.return_value = WorkflowResult(success=True, message="ok")
    mock_signals.return_value = WorkflowResult(success=False, message="信号失败", detail="no snapshot")

    result = run_daily_pipeline(memory_conn, settings, run_date="2026-05-23")

    assert result.success is False
    assert "generate_signals" in result.message
    steps = json.loads(result.detail or "[]")
    assert steps[0]["success"] is True
    assert steps[1]["success"] is False


@patch("src.workflows.pipelines.run_generate_weekly_report")
@patch("src.workflows.pipelines.run_generate_ai_weekly_review")
@patch("src.workflows.pipelines._run_refresh_tasks")
def test_weekly_pipeline_runs_steps_in_order(
    mock_refresh,
    mock_ai,
    mock_report,
    memory_conn,
    settings,
):
    call_order: list[str] = []

    def _track(name: str):
        def _inner(*args, **kwargs):
            call_order.append(name)
            return WorkflowResult(success=True, message="ok")

        return _inner

    mock_report.side_effect = _track("weekly_report")
    mock_ai.side_effect = _track("ai_weekly_review")
    mock_refresh.side_effect = _track("refresh_tasks")

    result = run_weekly_pipeline(memory_conn, settings, run_date="2026-05-23")

    assert result.success is True
    assert call_order == ["weekly_report", "ai_weekly_review", "refresh_tasks"]
