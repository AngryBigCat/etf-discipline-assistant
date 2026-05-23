from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from src.ai_review.llm_client import MockLLMClient, get_llm_client
from src.ai_review.review_service import generate_daily_ai_review, generate_weekly_ai_review
from src.ai_review.safety import validate_ai_review_output
from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.db.repository import (
    get_ai_review_by_daily_date,
    get_ai_review_by_week,
    list_ai_reviews,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_report,
    upsert_etf_universe,
    upsert_strategy_signals,
    upsert_weekly_report,
)
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _seed(memory_conn, settings):
    upsert_etf_universe(memory_conn, load_assets_seed())
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": "2026-05-23",
            "cash_value": 50000,
            "etf_market_value": 50000,
            "total_account_value": 100000,
            "total_position": 0.5,
            "cash_position": 0.5,
        },
    )
    save_holding_snapshots(memory_conn, "2026-05-23", [])
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "trend_score": 10,
                "drawdown_score": 5,
                "volatility_score": 0,
                "position_score": 0,
                "anti_chase_score": 0,
                "special_score": 0,
                "final_score": 80,
                "action": "strong_buy",
                "suggested_amount": 3000,
                "reason": "测试信号",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )
    upsert_daily_report(
        memory_conn,
        {
            "report_date": "2026-05-23",
            "total_position": 0.5,
            "cash_position": 0.5,
            "summary": "测试日报",
            "risk_warning": "测试风险",
            "action_suggestion": "测试建议",
        },
    )
    upsert_weekly_report(
        memory_conn,
        {
            "week_start": "2026-05-17",
            "week_end": "2026-05-23",
            "summary": "测试周报",
            "discipline_summary": "测试纪律",
            "risk_summary": "测试风险",
            "action_suggestion": "测试建议",
        },
    )


class DangerWordClient(MockLLMClient):
    def __init__(self, word: str) -> None:
        self.word = word

    def complete(self, system: str, user: str) -> dict[str, Any]:
        return {
            "text": f'{{"discipline_summary":"{self.word}","behavior_findings":[],"risk_summary":[],"action_suggestion":[],"final_note":"测试"}}',
            "model": "mock-danger",
            "provider": "mock",
            "status": "success",
            "error_message": "",
        }


def test_mock_client_stable_output():
    client = MockLLMClient()
    user = "- 当日交易次数：2\n- 不符合规则交易：1\n- 追涨次数：0"
    first = client.complete("system", user)["text"]
    second = client.complete("system", user)["text"]
    assert first == second


def test_generate_daily_ai_review_persists(memory_conn, settings):
    _seed(memory_conn, settings)
    review, saved, message = generate_daily_ai_review(
        memory_conn,
        settings,
        "2026-05-23",
        client=MockLLMClient(),
    )
    assert saved is True
    assert "AI 日复盘已生成" in message
    stored = get_ai_review_by_daily_date(memory_conn, "2026-05-23")
    assert stored is not None
    assert review is not None
    assert stored["discipline_summary"] == review["discipline_summary"]
    assert stored["behavior_findings"]
    assert "不构成投资建议" in stored["output_text"]
    for phrase in ("建议买入", "建议补仓", "建议减仓", "可考虑买入", "可考虑补仓"):
        assert phrase not in stored["output_text"]


def test_generate_weekly_ai_review_persists(memory_conn, settings):
    _seed(memory_conn, settings)
    review, saved, _ = generate_weekly_ai_review(
        memory_conn,
        settings,
        "2026-05-17",
        "2026-05-23",
        client=MockLLMClient(),
    )
    assert saved is True
    stored = get_ai_review_by_week(memory_conn, "2026-05-17", "2026-05-23")
    assert stored is not None
    assert review is not None


def test_append_disclaimer_when_missing():
    cleaned, status, _ = validate_ai_review_output("这是一段没有风险提示的复盘。")
    assert status == "success"
    assert "不构成投资建议" in cleaned


@pytest.mark.parametrize(
    "text",
    [
        "下个交易日注意控制仓位，不要满仓。",
        "当前波动较大，避免满仓操作。",
        "不要建议满仓，保持现金缓冲。",
    ],
)
def test_full_position_risk_warnings_not_blocked(text):
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


@pytest.mark.parametrize("word", ["保证收益", "必涨", "必买", "建议满仓", "可以满仓", "必须满仓", "直接满仓"])
def test_dangerous_words_blocked(memory_conn, settings, word):
    _seed(memory_conn, settings)
    review, saved, _ = generate_daily_ai_review(
        memory_conn,
        settings,
        "2026-05-23",
        client=DangerWordClient(word),
    )
    assert saved is True
    assert review is not None
    assert review["status"] == "blocked"
    assert word not in review["output_text"]
    assert review["error_message"]


def test_get_llm_client_fallback_without_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE", "")
    client = get_llm_client(
        {
            "provider": "openai_compatible",
            "api_key": "",
            "api_base": "",
            "model": "",
            "timeout": 30,
        }
    )
    assert isinstance(client, MockLLMClient)


def test_daily_ai_review_upsert_overwrites(memory_conn, settings):
    _seed(memory_conn, settings)
    generate_daily_ai_review(memory_conn, settings, "2026-05-23", client=MockLLMClient())
    generate_daily_ai_review(memory_conn, settings, "2026-05-23", client=MockLLMClient())
    rows = list_ai_reviews(memory_conn, review_type="daily")
    assert len(rows) == 1


def test_weekly_ai_review_upsert_overwrites(memory_conn, settings):
    _seed(memory_conn, settings)
    generate_weekly_ai_review(
        memory_conn,
        settings,
        "2026-05-17",
        "2026-05-23",
        client=MockLLMClient(),
    )
    generate_weekly_ai_review(
        memory_conn,
        settings,
        "2026-05-17",
        "2026-05-23",
        client=MockLLMClient(),
    )
    rows = list_ai_reviews(memory_conn, review_type="weekly")
    assert len(rows) == 1


def test_generate_daily_without_report(memory_conn, settings):
    upsert_etf_universe(memory_conn, load_assets_seed())
    review, saved, message = generate_daily_ai_review(
        memory_conn,
        settings,
        "2026-05-23",
        client=MockLLMClient(),
    )
    assert saved is False
    assert review is None
    assert "暂无日报" in message
