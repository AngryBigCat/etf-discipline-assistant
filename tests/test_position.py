from __future__ import annotations

import sqlite3

import pytest

from src.db.schema import init_schema
from src.portfolio.holdings import HoldingInput, resolve_market_value, save_snapshot
from src.portfolio.position import calc_account_totals, calc_max_allowed_value
from src.portfolio.rebalance import (
    STATUS_EXCEED_MAX,
    STATUS_UNDERWEIGHT,
    STATUS_WATCH_ONLY,
    classify_position,
)


def test_calc_account_totals():
    totals = calc_account_totals(cash_value=30000, etf_market_value=70000)
    assert totals["current_account_value"] == 100000
    assert totals["total_position"] == pytest.approx(0.7)
    assert totals["cash_position"] == pytest.approx(0.3)
    assert totals["valid"] is True


def test_calc_account_totals_zero_does_not_crash():
    totals = calc_account_totals(cash_value=0, etf_market_value=0)
    assert totals["valid"] is False
    assert totals["current_account_value"] == 0


def test_resolve_market_value_from_price():
    value = resolve_market_value(quantity=1000, latest_price=1.02, manual_market_value=None)
    assert value == 1020.0


def test_resolve_market_value_manual_fallback():
    value = resolve_market_value(quantity=1000, latest_price=None, manual_market_value=9500)
    assert value == 9500.0


def test_max_allowed_value_uses_stricter_cap():
    plan_cap = calc_max_allowed_value(total_plan_amount=100000, current_account_value=150000, max_weight=0.2)
    assert plan_cap == 20000

    account_cap = calc_max_allowed_value(total_plan_amount=100000, current_account_value=80000, max_weight=0.2)
    assert account_cap == 16000


def test_classify_exceed_max():
    status = classify_position(
        weight=0.25,
        target_weight=0.15,
        market_value=25000,
        max_allowed_value=20000,
        enabled_for_signal=True,
    )
    assert status == STATUS_EXCEED_MAX


def test_classify_watch_only():
    status = classify_position(
        weight=0.08,
        target_weight=0.10,
        market_value=8000,
        max_allowed_value=20000,
        enabled_for_signal=False,
    )
    assert status == STATUS_WATCH_ONLY


def test_classify_underweight():
    status = classify_position(
        weight=0.05,
        target_weight=0.10,
        market_value=5000,
        max_allowed_value=20000,
        enabled_for_signal=True,
    )
    assert status == STATUS_UNDERWEIGHT


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_save_snapshot_persists_account_and_holdings(memory_conn):
    result = save_snapshot(
        memory_conn,
        snapshot_date="2026-05-23",
        cash_value=40000,
        inputs=[
            HoldingInput(symbol="A500", quantity=10000, cost=9000),
            HoldingInput(symbol="CASH", quantity=0, cost=0),
        ],
        price_map={"A500": 1.0},
    )
    memory_conn.commit()

    assert result["account"]["current_account_value"] == 50000
    account = memory_conn.execute("SELECT * FROM account_snapshot").fetchone()
    assert account["cash_value"] == 40000
    holdings = memory_conn.execute("SELECT * FROM holding_snapshot").fetchall()
    assert len(holdings) == 1
    assert holdings[0]["symbol"] == "A500"
    assert "CASH" not in [h["symbol"] for h in holdings]
