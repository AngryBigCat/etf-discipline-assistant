from __future__ import annotations

import pytest

from src.trading.discipline_checker import (
    EXECUTION_DEVIATED,
    EXECUTION_IGNORED,
    EXECUTION_MANUAL,
    EXECUTION_MATCHED,
    TRADE_ACTION_BUY,
    TRADE_ACTION_HOLD,
    TRADE_ACTION_IGNORE,
    check_discipline,
)


def test_buy_within_120_percent_is_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_BUY,
        amount=3000,
        signal={"action": "strong_buy", "suggested_amount": 3000},
        signal_id=1,
    )
    assert result.is_rule_based is True
    assert result.execution_status == EXECUTION_MATCHED


def test_buy_over_120_percent_not_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_BUY,
        amount=4000,
        signal={"action": "strong_buy", "suggested_amount": 3000},
        signal_id=1,
    )
    assert result.is_rule_based is False
    assert result.execution_status == EXECUTION_DEVIATED


def test_buy_on_hold_signal_not_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_BUY,
        amount=1000,
        signal={"action": "hold", "suggested_amount": 0},
        signal_id=1,
    )
    assert result.is_rule_based is False
    assert result.execution_status == EXECUTION_DEVIATED


def test_buy_on_stop_buy_signal_not_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_BUY,
        amount=500,
        signal={"action": "stop_buy", "suggested_amount": 0},
        signal_id=1,
    )
    assert result.is_rule_based is False
    assert result.execution_status == EXECUTION_DEVIATED


def test_ignore_signal_is_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_IGNORE,
        amount=0,
        signal={"action": "strong_buy", "suggested_amount": 3000},
        signal_id=1,
    )
    assert result.is_rule_based is True
    assert result.execution_status == EXECUTION_IGNORED


def test_hold_trade_is_rule_based():
    result = check_discipline(
        trade_action=TRADE_ACTION_HOLD,
        amount=0,
        signal={"action": "hold", "suggested_amount": 0},
        signal_id=1,
    )
    assert result.is_rule_based is True
    assert result.execution_status == EXECUTION_MATCHED


def test_manual_trade_without_signal():
    result = check_discipline(
        trade_action=TRADE_ACTION_BUY,
        amount=1000,
        signal_id=None,
        user_is_rule_based=False,
    )
    assert result.is_rule_based is False
    assert result.execution_status == EXECUTION_MANUAL
