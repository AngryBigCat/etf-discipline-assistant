from __future__ import annotations

import sqlite3

import pytest

from src.ai_review.safety import rewrite_trading_advice_phrases, validate_ai_review_output
from src.db.repository import upsert_ai_review
from src.db.schema import _table_has_column, apply_schema_migrations


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("策略信号支持买入", "系统信号显示为可关注状态"),
        ("买入类标的", "可关注类标的"),
        ("可考虑买入", "系统信号显示可关注，最终需人工确认"),
        ("可考虑补仓", "可关注仓位偏离情况，等待系统信号并人工确认"),
        ("进行仓位调整", "检查仓位是否偏离既定规则，最终需人工确认"),
    ],
)
def test_rewrite_conservative_phrases(source, expected):
    text = rewrite_trading_advice_phrases(f"复盘：{source}。")
    assert source not in text
    assert expected in text


def test_rewrite_suggest_replenish():
    text = rewrite_trading_advice_phrases("复盘建议：建议补仓。")
    assert "建议补仓" not in text
    assert "等待系统信号并人工确认" in text


def test_rewrite_suggest_reduce():
    text = rewrite_trading_advice_phrases("当前建议减仓。")
    assert "建议减仓" not in text
    assert "超过规则仓位上限" in text


@pytest.mark.parametrize(
    "text",
    [
        "下个交易日注意控制仓位，不要满仓。",
        "当前波动较大，避免满仓操作。",
    ],
)
def test_avoid_full_position_not_blocked(text):
    cleaned, status, error_message = validate_ai_review_output(text)
    assert status == "success"
    assert error_message == ""
    assert "满仓" in cleaned
    assert "[已屏蔽]" not in cleaned


@pytest.mark.parametrize("phrase", ["建议满仓", "可以满仓", "必须满仓", "直接满仓"])
def test_full_position_recommendations_blocked(phrase):
    cleaned, status, error_message = validate_ai_review_output(f"复盘结论：{phrase}。")
    assert status == "blocked"
    assert phrase in error_message
    assert phrase not in cleaned
    assert "[已屏蔽]" in cleaned


def test_output_always_contains_disclaimer():
    cleaned, status, _ = validate_ai_review_output("这是一段没有风险提示的复盘。")
    assert status == "success"
    assert "不构成投资建议" in cleaned


def test_ai_review_behavior_findings_migration():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE ai_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_type TEXT NOT NULL,
            target_date TEXT NOT NULL DEFAULT '',
            week_start TEXT NOT NULL DEFAULT '',
            week_end TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL,
            source_digest TEXT,
            prompt_version TEXT NOT NULL DEFAULT 'v1',
            provider TEXT DEFAULT 'mock',
            model TEXT,
            input_snapshot TEXT,
            output_text TEXT,
            discipline_summary TEXT,
            risk_summary TEXT,
            action_suggestion TEXT,
            status TEXT DEFAULT 'success',
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(review_type, target_date, week_start, week_end, prompt_version)
        )
        """
    )
    assert not _table_has_column(conn, "ai_review", "behavior_findings")

    apply_schema_migrations(conn)
    assert _table_has_column(conn, "ai_review", "behavior_findings")

    upsert_ai_review(
        conn,
        {
            "review_type": "daily",
            "target_date": "2026-05-23",
            "week_start": "",
            "week_end": "",
            "source_type": "daily_report",
            "source_digest": "abc",
            "prompt_version": "v1",
            "provider": "mock",
            "model": "mock",
            "input_snapshot": "{}",
            "output_text": "test",
            "discipline_summary": "summary",
            "behavior_findings": "- finding",
            "risk_summary": "risk",
            "action_suggestion": "action",
            "status": "success",
            "error_message": "",
        },
    )
    row = conn.execute(
        "SELECT behavior_findings FROM ai_review WHERE target_date = '2026-05-23'"
    ).fetchone()
    assert row[0] == "- finding"
