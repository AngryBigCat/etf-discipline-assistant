from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.config.settings import load_settings
from src.db.repository import save_account_snapshot, save_holding_snapshots, upsert_strategy_signals, upsert_task_item
from src.db.schema import init_schema
from src.notifications.config import format_email_settings_display, get_email_settings, mask_recipients
from src.notifications.email_client import send_email
from src.notifications.models import (
    EVENT_HIGH_PRIORITY_TASKS,
    EVENT_TEST_EMAIL,
    LEVEL_INFO,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
)
from src.notifications.repository import list_notification_logs
from src.notifications.service import send_notification, send_scheduler_job_notifications
from src.scheduler.repository import ensure_default_scheduler_jobs
from src.workflows.daily_workflow import WorkflowResult
from src.workflows.pipelines import run_daily_pipeline


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def test_email_disabled_returns_skipped(memory_conn, monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    result = send_notification(
        memory_conn,
        event_type=EVENT_TEST_EMAIL,
        level=LEVEL_INFO,
        title="测试",
        body="测试正文",
    )
    assert result.status == STATUS_SKIPPED
    logs = list_notification_logs(memory_conn, limit=10)
    assert logs[0]["status"] == STATUS_SKIPPED


def test_smtp_password_not_written_to_notification_log(memory_conn, monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_SMTP_PASSWORD", "secret-pass")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    with patch("src.notifications.service.send_email") as mock_send:
        mock_send.return_value = MagicMock(success=True, message="ok", error=None)
        send_notification(
            memory_conn,
            event_type=EVENT_TEST_EMAIL,
            level=LEVEL_INFO,
            title="测试",
            body="正文",
        )

    log_text = str(list_notification_logs(memory_conn, limit=10))
    assert "secret-pass" not in log_text


def test_email_to_parsing(monkeypatch):
    monkeypatch.setenv("EMAIL_TO", "a@example.com, b@example.com")
    settings = get_email_settings()
    assert settings["email_to"] == ["a@example.com", "b@example.com"]
    assert mask_recipients(settings["email_to"]) == "a***@example.com, b***@example.com"


def test_send_email_missing_config_returns_failure():
    result = send_email(
        "测试",
        "正文",
        [],
        {
            "smtp_host": "",
            "email_from": "",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_password": "",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
            "timeout": 30,
        },
    )
    assert result.success is False
    assert result.error


@patch("src.notifications.service.send_email")
def test_send_notification_success_writes_log(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")
    mock_send.return_value = MagicMock(success=True, message="邮件发送成功", error=None)

    result = send_notification(
        memory_conn,
        event_type=EVENT_TEST_EMAIL,
        level=LEVEL_INFO,
        title="测试",
        body="正文",
        dedupe_key="test:1",
    )

    assert result.status == STATUS_SUCCESS
    logs = list_notification_logs(memory_conn, limit=5)
    assert logs[0]["status"] == STATUS_SUCCESS


@patch("src.notifications.service.send_email")
def test_send_notification_failure_writes_failed_log(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")
    mock_send.return_value = MagicMock(
        success=False,
        message="邮件发送失败",
        error="smtp error",
    )

    result = send_notification(
        memory_conn,
        event_type=EVENT_TEST_EMAIL,
        level=LEVEL_INFO,
        title="测试",
        body="正文",
    )

    assert result.status == STATUS_FAILED
    logs = list_notification_logs(memory_conn, limit=5)
    assert logs[0]["status"] == STATUS_FAILED


@patch("src.notifications.service.send_email")
def test_dedupe_key_prevents_duplicate_send(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")
    mock_send.return_value = MagicMock(success=True, message="ok", error=None)

    first = send_notification(
        memory_conn,
        event_type=EVENT_TEST_EMAIL,
        level=LEVEL_INFO,
        title="测试",
        body="正文",
        dedupe_key="dedupe:test",
    )
    second = send_notification(
        memory_conn,
        event_type=EVENT_TEST_EMAIL,
        level=LEVEL_INFO,
        title="测试",
        body="正文",
        dedupe_key="dedupe:test",
    )

    assert first.status == STATUS_SUCCESS
    assert second.status == STATUS_SKIPPED
    assert mock_send.call_count == 1


@patch("src.notifications.service.send_notification")
def test_scheduler_failure_triggers_notification(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("NOTIFY_ON_SCHEDULER_FAILURE", "true")
    ensure_default_scheduler_jobs(memory_conn)
    job = {"job_key": "daily_after_close", "name": "每日收盘后流程"}
    mock_send.return_value = MagicMock(success=True, status=STATUS_SUCCESS, message="ok", error=None)

    send_scheduler_job_notifications(
        memory_conn,
        job,
        WorkflowResult(success=False, message="失败"),
        scheduled_time="2026-05-23T16:30:00",
        job_success=False,
    )

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["event_type"] == "scheduler_failure"


@patch("src.notifications.service.send_notification")
def test_scheduler_success_default_does_not_notify(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("NOTIFY_ON_SCHEDULER_SUCCESS", "false")
    ensure_default_scheduler_jobs(memory_conn)
    job = {"job_key": "daily_after_close", "name": "每日收盘后流程"}

    send_scheduler_job_notifications(
        memory_conn,
        job,
        WorkflowResult(success=True, message="ok"),
        scheduled_time="2026-05-23T16:30:00",
        job_success=True,
    )

    mock_send.assert_not_called()


@patch("src.notifications.service.send_notification")
def test_high_priority_tasks_notification(mock_send, memory_conn, monkeypatch):
    monkeypatch.setenv("NOTIFY_ON_HIGH_PRIORITY_TASKS", "true")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    upsert_task_item(
        memory_conn,
        {
            "task_date": "2026-05-23",
            "category": "daily",
            "task_type": "review_strategy_signal",
            "title": "审核策略信号",
            "priority": "high",
            "status": "pending",
            "source_type": "strategy_signal",
            "source_key": "test",
        },
    )
    mock_send.return_value = MagicMock(success=True, status=STATUS_SUCCESS, message="ok", error=None)

    from src.notifications.service import send_daily_pipeline_notifications

    send_daily_pipeline_notifications(
        memory_conn,
        "2026-05-23",
        WorkflowResult(success=True, message="done"),
    )

    assert any(
        call.kwargs.get("event_type") == EVENT_HIGH_PRIORITY_TASKS
        for call in mock_send.call_args_list
    )


@patch("src.notifications.service.send_daily_pipeline_notifications")
@patch("src.workflows.pipelines.run_generate_ai_daily_review")
@patch("src.workflows.pipelines.run_generate_daily_report")
@patch("src.workflows.pipelines._run_refresh_tasks")
@patch("src.workflows.pipelines.run_generate_signals")
@patch("src.workflows.pipelines.run_market_update")
def test_notification_failure_does_not_fail_daily_pipeline(
    mock_market,
    mock_signals,
    mock_refresh,
    mock_report,
    mock_ai,
    mock_notify,
    memory_conn,
    settings,
):
    mock_market.return_value = WorkflowResult(success=True, message="ok")
    mock_signals.return_value = WorkflowResult(success=True, message="ok")
    mock_refresh.return_value = WorkflowResult(success=True, message="ok")
    mock_report.return_value = WorkflowResult(success=True, message="ok")
    mock_ai.return_value = WorkflowResult(success=True, message="ok")
    mock_notify.side_effect = RuntimeError("notify failed")

    result = run_daily_pipeline(memory_conn, settings, run_date="2026-05-23")

    assert result.success is True


@patch("src.notifications.service.send_daily_pipeline_notifications", return_value=[])
@patch("src.workflows.pipelines.run_generate_ai_daily_review")
@patch("src.workflows.pipelines.run_generate_daily_report")
@patch("src.workflows.pipelines._run_refresh_tasks")
@patch("src.workflows.pipelines.run_generate_signals")
@patch("src.workflows.pipelines.run_market_update")
def test_notification_does_not_write_trade_log(
    mock_market,
    mock_signals,
    mock_refresh,
    mock_report,
    mock_ai,
    memory_conn,
    settings,
):
    mock_market.return_value = WorkflowResult(success=True, message="ok")
    mock_signals.return_value = WorkflowResult(success=True, message="ok")
    mock_refresh.return_value = WorkflowResult(success=True, message="ok")
    mock_report.return_value = WorkflowResult(success=True, message="ok")
    mock_ai.return_value = WorkflowResult(success=True, message="ok")

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
        [{"symbol": "A500", "quantity": 100, "market_value": 50000, "cost": 45000}],
    )

    trade_before = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    snapshot_before = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_before = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]
    review_before = memory_conn.execute(
        "SELECT review_status FROM strategy_signal LIMIT 1"
    ).fetchone()[0]

    run_daily_pipeline(memory_conn, settings, run_date="2026-05-23")

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_before
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == snapshot_before
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_before
    assert (
        memory_conn.execute("SELECT review_status FROM strategy_signal LIMIT 1").fetchone()[0]
        == review_before
    )


def test_email_settings_display_hides_password(monkeypatch):
    monkeypatch.setenv("EMAIL_SMTP_PASSWORD", "super-secret")
    display = format_email_settings_display()
    assert display["smtp_password"] == "已配置"
    assert "super-secret" not in str(display)


def test_email_settings_repr_hides_password(monkeypatch):
    monkeypatch.setenv("EMAIL_SMTP_PASSWORD", "super-secret")
    settings = get_email_settings()
    assert "super-secret" not in repr(settings)
