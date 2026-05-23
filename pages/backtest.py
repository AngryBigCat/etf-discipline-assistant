from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.backtest.models import BacktestConfig
from src.backtest.service import load_backtest_detail, run_and_save_backtest
from src.config.settings import get_enabled_portfolio_assets, load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import list_backtest_runs
from src.ui.labels import (
    localize_backtest_action,
    localize_backtest_frequency,
    localize_backtest_strategy,
    rename_columns,
)

STRATEGY_OPTIONS = {
    "baseline_dca": "普通定投",
    "ma_filter_dca": "均线过滤定投",
    "drawdown_boost": "回撤加仓定投",
}

FREQUENCY_OPTIONS = {
    "monthly": "每月",
    "weekly": "每周",
}


def _format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}%"


def _format_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def _render_result_summary(run: dict, result: dict) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("期末资产", _format_money(result.get("final_value")))
        st.metric("累计投入", _format_money(result.get("total_invested")))
        st.metric("剩余现金", _format_money(result.get("cash_value")))
    with c2:
        st.metric("持仓市值", _format_money(result.get("position_value")))
        st.metric("总收益率", _format_pct(result.get("total_return")))
        st.metric("年化收益率", _format_pct(result.get("annualized_return")))
    with c3:
        st.metric("最大回撤", _format_pct(result.get("max_drawdown")))
        st.metric("交易次数", result.get("trade_count", 0))
        st.metric("平均成本", _format_money(result.get("average_cost")))

    st.caption(
        f"标的：{run.get('symbol')} · 策略：{localize_backtest_strategy(run.get('strategy_name'))} · "
        f"区间：{run.get('start_date')} ~ {run.get('end_date')} · "
        f"频率：{localize_backtest_frequency(run.get('frequency'))}"
    )


def _render_charts(equity_curve: list[dict]) -> None:
    if not equity_curve:
        st.info("暂无净值曲线数据")
        return
    df = pd.DataFrame(equity_curve)
    fig_total = go.Figure()
    fig_total.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["total_value"],
            mode="lines",
            name="总资产",
        )
    )
    fig_total.update_layout(title="总资产曲线", xaxis_title="日期", yaxis_title="总资产")
    st.plotly_chart(fig_total, use_container_width=True)

    fig_drawdown = go.Figure()
    fig_drawdown.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["drawdown"],
            mode="lines",
            name="回撤",
        )
    )
    fig_drawdown.update_layout(title="回撤曲线", xaxis_title="日期", yaxis_title="回撤")
    st.plotly_chart(fig_drawdown, use_container_width=True)


def _render_trades(trades: list[dict]) -> None:
    st.markdown("#### 模拟交易记录")
    if not trades:
        st.info("本次回测无模拟交易")
        return
    trade_df = pd.DataFrame(
        [
            {
                "trade_date": row["trade_date"],
                "symbol": row["symbol"],
                "action": localize_backtest_action(row["action"]),
                "price": row["price"],
                "amount": row["amount"],
                "quantity": row["quantity"],
                "reason": row.get("reason") or "—",
            }
            for row in trades
        ]
    )
    st.dataframe(rename_columns(trade_df), use_container_width=True, hide_index=True)


def _render_detail(detail: dict) -> None:
    run = detail.get("run") or {}
    result = detail.get("result") or {}
    if not run or not result:
        st.warning("未找到回测详情")
        return
    _render_result_summary(run, result)
    _render_charts(detail.get("equity_curve") or [])
    _render_trades(detail.get("trades") or [])


def _render_history(rows: list) -> None:
    st.markdown("#### 历史回测记录")
    preview_df = pd.DataFrame(
        [
            {
                "symbol": row["symbol"],
                "strategy_name": localize_backtest_strategy(row["strategy_name"]),
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "frequency": localize_backtest_frequency(row["frequency"]),
                "initial_cash": row["initial_cash"],
                "fixed_amount": row["fixed_amount"],
            }
            for row in rows
        ]
    )
    st.dataframe(rename_columns(preview_df), use_container_width=True, hide_index=True)

    for row in rows:
        label = (
            f"{row['symbol']} · {localize_backtest_strategy(row['strategy_name'])} · "
            f"{row['start_date']} ~ {row['end_date']}"
        )
        with st.expander(label):
            with get_connection() as conn:
                detail = load_backtest_detail(conn, int(row["id"]))
            _render_detail(detail)


def render() -> None:
    st.title("回测分析")
    st.info("回测仅用于历史规则验证，不代表未来收益，不构成投资建议。")

    settings = load_settings()
    assets = get_enabled_portfolio_assets(settings)
    symbols = [asset["symbol"] for asset in assets if asset.get("symbol") != "CASH"]
    if not symbols:
        symbols = ["A500"]

    c1, c2, c3 = st.columns(3)
    with c1:
        symbol = st.selectbox("标的代码", options=symbols, index=0)
        strategy = st.selectbox(
            "策略类型",
            options=list(STRATEGY_OPTIONS.keys()),
            format_func=lambda key: STRATEGY_OPTIONS[key],
        )
    with c2:
        start_date = st.date_input("开始日期", value=date(2021, 1, 1))
        end_date = st.date_input("结束日期", value=date.today())
    with c3:
        initial_cash = st.number_input("初始资金", min_value=1000.0, value=100000.0, step=1000.0)
        fixed_amount = st.number_input("每期定投金额", min_value=100.0, value=3000.0, step=100.0)
        frequency = st.selectbox(
            "定投频率",
            options=list(FREQUENCY_OPTIONS.keys()),
            format_func=lambda key: FREQUENCY_OPTIONS[key],
        )

    if st.button("运行回测", type="primary"):
        config = BacktestConfig(
            symbol=symbol,
            strategy_name=strategy,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            initial_cash=float(initial_cash),
            fixed_amount=float(fixed_amount),
            frequency=frequency,
        )
        with db_session() as conn:
            run_id, result, message = run_and_save_backtest(conn, config)
        if run_id is None:
            st.warning(message)
        else:
            st.success(message)
            st.session_state["latest_backtest_run_id"] = run_id

    latest_run_id = st.session_state.get("latest_backtest_run_id")
    if latest_run_id:
        with get_connection() as conn:
            detail = load_backtest_detail(conn, int(latest_run_id))
        if detail:
            st.subheader("本次回测结果")
            _render_detail(detail)

    with get_connection() as conn:
        history_rows = list_backtest_runs(conn, limit=20)
    if history_rows:
        _render_history(history_rows)
    else:
        st.info("暂无历史回测记录")


render()
