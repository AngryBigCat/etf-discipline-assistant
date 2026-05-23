from __future__ import annotations

import pytest

from src.strategy.score_engine import (
    calc_anti_chase_score,
    calc_drawdown_score,
    calc_special_score,
    calc_trend_score,
    compute_score,
)


def test_trend_score_positive_when_above_mas():
    score, reasons = calc_trend_score(close=110, ma60=100, ma120=95, ma250=90)
    assert score == pytest.approx(26)
    assert any("60日均线" in reason for reason in reasons)


def test_trend_score_skips_missing_ma_without_error():
    score, reasons = calc_trend_score(close=110, ma60=100, ma120=None, ma250=None)
    assert score == pytest.approx(10)
    assert len(reasons) == 1


def test_drawdown_score_extreme():
    score, reasons = calc_drawdown_score(drawdown_used=-0.16, drawdown_window=120)
    assert score == 20
    assert any("15%" in reason for reason in reasons)


def test_anti_chase_penalizes_return_20d():
    score, reasons = calc_anti_chase_score(return_5d=0.01, return_10d=0.05, return_20d=0.13)
    assert score == -20
    assert any("20日" in reason for reason in reasons)


def test_kc50_position_18_penalized():
    score, reasons, force_stop = calc_special_score(
        symbol="KC50",
        weight=0.19,
        close=1.2,
        ma120=1.1,
        return_5d=0.0,
    )
    assert score == -20
    assert force_stop is False
    assert any("20%" in reason for reason in reasons)


def test_kc50_position_20_forces_stop_buy():
    score, reasons, force_stop = calc_special_score(
        symbol="KC50",
        weight=0.21,
        close=1.0,
        ma120=1.1,
        return_5d=0.0,
    )
    assert force_stop is True
    assert any("20%" in reason for reason in reasons)


def test_compute_score_clamps_between_0_and_100():
    indicator = {
        "ma60": 100,
        "ma120": 100,
        "ma250": 100,
        "drawdown_used": -0.20,
        "drawdown_window": 250,
        "return_5d": 0.0,
        "return_10d": 0.0,
        "return_20d": 0.0,
        "confidence_level": "normal",
    }
    asset = {"symbol": "A500", "target_weight": 0.5, "max_weight": 0.65}
    position = {"weight": 0.1, "market_value": 10000}
    portfolio = {"total_position": 0.5, "cash_position": 0.5}
    result = compute_score(
        close=120,
        indicator=indicator,
        asset=asset,
        position=position,
        portfolio=portfolio,
        max_allowed_value=65000,
    )
    assert 0 <= result.final_score <= 100
