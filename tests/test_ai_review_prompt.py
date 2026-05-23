from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.ai_review.context_builder import build_daily_review_context, build_weekly_review_context
from src.ai_review.prompt_builder import build_daily_review_prompt, build_weekly_review_prompt
from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.db.repository import (
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_report,
    upsert_etf_universe,
    upsert_strategy_signals,
    upsert_weekly_report,
)
from src.db.schema import init_schema
from src.trading.trade_log import TradeLogInput, create_manual_trade


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


def test_daily_prompt_contains_safety_constraints(memory_conn, settings):
    _seed(memory_conn, settings)
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
    context = build_daily_review_context(memory_conn, settings, "2026-05-23")
    prompt = build_daily_review_prompt(context)
    assert "你不能预测市场涨跌" in prompt["system"]
    assert "不构成投资建议" in prompt["system"]
    assert "你不能推荐个股" in prompt["system"]
    assert "你不能直接建议用户买入" in prompt["system"]
    assert "系统信号显示" in prompt["system"]


def test_weekly_prompt_contains_trade_stats(memory_conn, settings):
    _seed(memory_conn, settings)
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
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-22",
            symbol="A500",
            action="buy",
            amount=1000,
            user_is_rule_based=True,
        ),
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="KC50",
            action="buy",
            amount=2000,
            emotion="chasing",
            user_is_rule_based=False,
        ),
    )
    context = build_weekly_review_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    prompt = build_weekly_review_prompt(context)
    assert "纪律执行率" in prompt["user"]
    assert "不符合规则次数：1" in prompt["user"]
