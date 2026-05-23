from __future__ import annotations

import pytest

from src.strategy.rule_engine import calc_suggested_amount, round_to_100


@pytest.fixture
def settings():
    return {
        "portfolio": {
            "total_plan_amount": 100000,
            "min_cash_position": 0.20,
        }
    }


def test_suggested_amount_zero_for_stop_buy(settings):
    amount = calc_suggested_amount(
        action="stop_buy",
        asset={"symbol": "A500", "single_buy_ratio": 0.03, "max_weight": 0.65},
        position={"market_value": 10000, "weight": 0.1},
        portfolio={
            "current_account_value": 100000,
            "cash_value": 50000,
            "total_position": 0.5,
        },
        settings=settings,
    )
    assert amount == 0


def test_suggested_amount_not_exceed_available_cash(settings):
    amount = calc_suggested_amount(
        action="strong_buy",
        asset={"symbol": "A500", "single_buy_ratio": 0.03, "max_weight": 0.65},
        position={"market_value": 10000, "weight": 0.1},
        portfolio={
            "current_account_value": 100000,
            "cash_value": 25000,
            "total_position": 0.75,
        },
        settings=settings,
    )
    available_cash = 25000 - 100000 * 0.20
    assert amount <= available_cash


def test_suggested_amount_not_exceed_max_capacity(settings):
    amount = calc_suggested_amount(
        action="strong_buy",
        asset={"symbol": "A500", "single_buy_ratio": 0.03, "max_weight": 0.65},
        position={"market_value": 64000, "weight": 0.64},
        portfolio={
            "current_account_value": 100000,
            "cash_value": 50000,
            "total_position": 0.5,
        },
        settings=settings,
    )
    remaining = 65000 - 64000
    assert amount <= remaining


def test_suggested_amount_rounds_to_100(settings):
    amount = calc_suggested_amount(
        action="small_buy",
        asset={"symbol": "A500", "single_buy_ratio": 0.03, "max_weight": 0.65},
        position={"market_value": 10000, "weight": 0.1},
        portfolio={
            "current_account_value": 100000,
            "cash_value": 50000,
            "total_position": 0.5,
        },
        settings=settings,
    )
    assert amount % 100 == 0
    assert round_to_100(1550) == 1600
    assert round_to_100(1549) == 1500


def test_kc50_single_limit(settings):
    amount = calc_suggested_amount(
        action="strong_buy",
        asset={"symbol": "KC50", "single_buy_ratio": 0.05, "max_weight": 0.20},
        position={"market_value": 0, "weight": 0},
        portfolio={
            "current_account_value": 100000,
            "cash_value": 100000,
            "total_position": 0.0,
        },
        settings=settings,
    )
    assert amount <= 2000
