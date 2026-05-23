from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.backtest.models import BacktestConfig
from src.backtest.portfolio import PortfolioAssetConfig, PortfolioBacktestConfig
from src.backtest.service import (
    load_backtest_detail,
    run_and_save_backtest,
    run_and_save_portfolio_backtest,
    run_backtest_comparison,
)
from src.config.settings import get_enabled_portfolio_assets, load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import list_backtest_run_summaries
from src.ui.labels import (
    localize_backtest_action,
    localize_backtest_frequency,
    localize_backtest_strategy,
    localize_backtest_symbol,
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

MODE_OPTIONS = {
    "single": "单策略回测",
    "compare": "多策略对比",
    "portfolio": "组合回测",
}

PORTFOLIO_SYMBOL_OPTIONS = ["A500", "DIVIDEND", "KC50", "HS300", "SP500", "NASDAQ100"]

PORTFOLIO_DEFAULT_WEIGHTS = {
    "A500": 50.0,
    "DIVIDEND": 20.0,
    "KC50": 10.0,
}

PORTFOLIO_STRATEGY_OPTIONS = {
    "portfolio_dca": "组合定投",
    "portfolio_rebalance": "组合定投 + 再平衡",
}


def _format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:.2f}%"


def _format_money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.2f}"


def _render_date_warning(requested_start: str, actual_start: str) -> None:
    if (
        actual_start not in ("—", "")
        and requested_start not in ("—", "")
        and actual_start > requested_start
    ):
        st.warning(
            f"当前数据库行情数据晚于你选择的开始日期，本次回测实际从 {actual_start} 开始。"
            "年化收益按实际数据区间计算。"
        )


def _render_result_summary(run: dict, result: dict, equity_curve: list[dict] | None = None) -> None:
    requested_start = run.get("start_date") or "—"
    requested_end = run.get("end_date") or "—"
    actual_start = result.get("actual_start_date") or "—"
    actual_end = result.get("actual_end_date") or "—"
    if (actual_start == "—" or actual_end == "—") and equity_curve:
        actual_start = equity_curve[0].get("trade_date") or actual_start
        actual_end = equity_curve[-1].get("trade_date") or actual_end
    trading_days = result.get("trading_days")
    if trading_days is None and equity_curve:
        trading_days = len(equity_curve)

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
        average_cost = "—" if run.get("symbol") == "PORTFOLIO" else _format_money(result.get("average_cost"))
        st.metric("平均成本", average_cost)
        st.metric("资金利用率", _format_pct(result.get("cash_utilization")))

    st.caption(
        f"标的：{localize_backtest_symbol(run.get('symbol'))} · "
        f"策略：{localize_backtest_strategy(run.get('strategy_name'))} · "
        f"频率：{localize_backtest_frequency(run.get('frequency'))}"
    )
    st.caption(f"请求区间：{requested_start} ~ {requested_end}")
    st.caption(f"实际数据区间：{actual_start} ~ {actual_end} · 交易日数量：{trading_days or '—'}")
    _render_date_warning(requested_start, actual_start)


def _render_charts(equity_curve: list[dict], *, key_prefix: str) -> None:
    if not equity_curve:
        st.info("暂无净值曲线数据")
        return
    df = pd.DataFrame(equity_curve)
    fig_total = go.Figure()
    fig_total.add_trace(
        go.Scatter(x=df["trade_date"], y=df["total_value"], mode="lines", name="总资产")
    )
    fig_total.update_layout(title="总资产曲线", xaxis_title="日期", yaxis_title="总资产")
    st.plotly_chart(fig_total, use_container_width=True, key=f"{key_prefix}_total_value")

    fig_drawdown = go.Figure()
    fig_drawdown.add_trace(
        go.Scatter(x=df["trade_date"], y=df["drawdown"], mode="lines", name="回撤")
    )
    fig_drawdown.update_layout(title="回撤曲线", xaxis_title="日期", yaxis_title="回撤")
    st.plotly_chart(fig_drawdown, use_container_width=True, key=f"{key_prefix}_drawdown")


def _render_positions(positions: list[dict]) -> None:
    if not positions:
        return
    st.markdown("#### 组合持仓明细")
    position_df = pd.DataFrame(
        [
            {
                "symbol": localize_backtest_symbol(row["symbol"]),
                "quantity": row["quantity"],
                "average_cost": row["average_cost"],
                "last_price": row["last_price"],
                "market_value": row["market_value"],
                "weight": row["weight"],
                "target_weight": row["target_weight"],
                "deviation": row["deviation"],
            }
            for row in positions
        ]
    )
    display_df = position_df.copy()
    for col in ("weight", "target_weight", "deviation"):
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(_format_pct)
    for col in ("average_cost", "last_price", "market_value"):
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(_format_money)
    column_map = {
        "symbol": "标的代码",
        "quantity": "持仓数量",
        "average_cost": "平均成本",
        "last_price": "最新价格",
        "market_value": "持仓市值",
        "weight": "当前权重",
        "target_weight": "目标权重",
        "deviation": "权重偏离",
    }
    st.dataframe(display_df.rename(columns=column_map), use_container_width=True, hide_index=True)


def _render_trades(trades: list[dict]) -> None:
    st.markdown("#### 模拟交易记录")
    if not trades:
        st.info("本次回测无模拟交易")
        return
    trade_df = pd.DataFrame(
        [
            {
                "trade_date": row["trade_date"],
                "symbol": localize_backtest_symbol(row["symbol"]),
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


def _render_detail(detail: dict, *, key_prefix: str) -> None:
    run = detail.get("run") or {}
    result = detail.get("result") or {}
    if not run or not result:
        st.warning("未找到回测详情")
        return
    _render_result_summary(run, result, detail.get("equity_curve") or [])
    _render_charts(detail.get("equity_curve") or [], key_prefix=key_prefix)
    _render_positions(detail.get("positions") or [])
    _render_trades(detail.get("trades") or [])


def _build_comparison_row(item: dict, detail: dict | None = None) -> dict:
    run = (detail or {}).get("run") or {}
    result_obj = item.get("result")
    result = (detail or {}).get("result") or {}
    if not result and result_obj is not None:
        result = {
            "final_value": result_obj.final_value,
            "total_invested": result_obj.total_invested,
            "cash_value": result_obj.cash_value,
            "position_value": result_obj.position_value,
            "total_return": result_obj.total_return,
            "annualized_return": result_obj.annualized_return,
            "max_drawdown": result_obj.max_drawdown,
            "trade_count": result_obj.trade_count,
            "average_cost": result_obj.average_cost,
            "actual_start_date": result_obj.actual_start_date,
            "actual_end_date": result_obj.actual_end_date,
            "trading_days": result_obj.trading_days,
            "cash_utilization": result_obj.cash_utilization,
        }
        run = {
            "start_date": result_obj.requested_start_date,
            "end_date": result_obj.requested_end_date,
        }
    return {
        "strategy_name": localize_backtest_strategy(item["strategy_name"]),
        "requested_range": f"{run.get('start_date', '—')} ~ {run.get('end_date', '—')}",
        "actual_range": f"{result.get('actual_start_date') or '—'} ~ {result.get('actual_end_date') or '—'}",
        "trading_days": result.get("trading_days") or "—",
        "final_value": result.get("final_value"),
        "total_invested": result.get("total_invested"),
        "cash_value": result.get("cash_value"),
        "position_value": result.get("position_value"),
        "total_return": result.get("total_return"),
        "annualized_return": result.get("annualized_return"),
        "max_drawdown": result.get("max_drawdown"),
        "trade_count": result.get("trade_count"),
        "average_cost": result.get("average_cost"),
        "cash_utilization": result.get("cash_utilization"),
        "status": item.get("message") or "—",
    }


def _render_comparison_results(comparison_items: list[dict]) -> None:
    st.subheader("策略对比结果")

    table_rows = []
    for item in comparison_items:
        detail = None
        if item.get("run_id"):
            with get_connection() as conn:
                detail = load_backtest_detail(conn, int(item["run_id"]))
        table_rows.append(_build_comparison_row(item, detail))

    display_df = pd.DataFrame(table_rows)
    for col in ("total_return", "annualized_return", "max_drawdown", "cash_utilization"):
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(_format_pct)
    for col in ("final_value", "total_invested", "cash_value", "position_value", "average_cost"):
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(_format_money)

    column_map = {
        "strategy_name": "策略名称",
        "requested_range": "请求区间",
        "actual_range": "实际数据区间",
        "trading_days": "交易日数量",
        "final_value": "期末资产",
        "total_invested": "累计投入",
        "cash_value": "剩余现金",
        "position_value": "持仓市值",
        "total_return": "总收益率",
        "annualized_return": "年化收益率",
        "max_drawdown": "最大回撤",
        "trade_count": "交易次数",
        "average_cost": "平均成本",
        "cash_utilization": "资金利用率",
        "status": "状态",
    }
    st.dataframe(display_df.rename(columns=column_map), use_container_width=True, hide_index=True)

    fig_total = go.Figure()
    fig_drawdown = go.Figure()
    for item in comparison_items:
        if not item.get("run_id"):
            continue
        with get_connection() as conn:
            detail = load_backtest_detail(conn, int(item["run_id"]))
        curve = detail.get("equity_curve") or []
        if not curve:
            continue
        df = pd.DataFrame(curve)
        label = localize_backtest_strategy(item["strategy_name"])
        fig_total.add_trace(
            go.Scatter(x=df["trade_date"], y=df["total_value"], mode="lines", name=label)
        )
        fig_drawdown.add_trace(
            go.Scatter(x=df["trade_date"], y=df["drawdown"], mode="lines", name=label)
        )

    if fig_total.data:
        fig_total.update_layout(title="多策略总资产曲线", xaxis_title="日期", yaxis_title="总资产")
        st.plotly_chart(fig_total, use_container_width=True, key="comparison_total_value")
    if fig_drawdown.data:
        fig_drawdown.update_layout(title="多策略回撤曲线", xaxis_title="日期", yaxis_title="回撤")
        st.plotly_chart(fig_drawdown, use_container_width=True, key="comparison_drawdown")


def _render_history(rows: list) -> None:
    st.markdown("#### 历史回测记录")
    preview_df = pd.DataFrame(
        [
            {
                "symbol": localize_backtest_symbol(row["symbol"]),
                "strategy_name": localize_backtest_strategy(row["strategy_name"]),
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "actual_start_date": row["actual_start_date"] or "—",
                "actual_end_date": row["actual_end_date"] or "—",
                "trading_days": row["trading_days"] or "—",
                "final_value": row["final_value"],
                "total_return": row["total_return"],
                "annualized_return": row["annualized_return"],
                "max_drawdown": row["max_drawdown"],
                "trade_count": row["trade_count"],
                "cash_utilization": row["cash_utilization"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    )
    display_df = preview_df.copy()
    for col in ("total_return", "annualized_return", "max_drawdown", "cash_utilization"):
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(_format_pct)
    if "final_value" in display_df.columns:
        display_df["final_value"] = display_df["final_value"].apply(_format_money)
    st.dataframe(rename_columns(display_df), use_container_width=True, hide_index=True)

    for row in rows:
        label = (
            f"{localize_backtest_symbol(row['symbol'])} · {localize_backtest_strategy(row['strategy_name'])} · "
            f"{row['start_date']} ~ {row['end_date']} · "
            f"{_format_pct(row['total_return'])}"
        )
        with st.expander(label):
            with get_connection() as conn:
                detail = load_backtest_detail(conn, int(row["run_id"]))
            _render_detail(detail, key_prefix=f"history_{row['run_id']}")


def render() -> None:
    st.title("回测分析")
    st.info("回测仅用于历史规则验证，不代表未来收益，不构成投资建议。")

    settings = load_settings()
    assets = get_enabled_portfolio_assets(settings)
    symbols = [asset["symbol"] for asset in assets if asset.get("symbol") != "CASH"]
    if not symbols:
        symbols = ["A500"]

    mode = st.radio(
        "回测模式",
        options=list(MODE_OPTIONS.keys()),
        format_func=lambda key: MODE_OPTIONS[key],
        horizontal=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if mode != "portfolio":
            symbol = st.selectbox("标的代码", options=symbols, index=0)
        else:
            selected_symbols = st.multiselect(
                "组合标的",
                options=PORTFOLIO_SYMBOL_OPTIONS,
                default=["A500", "DIVIDEND", "KC50"],
            )
            portfolio_weights: dict[str, float] = {}
            if selected_symbols:
                st.caption("目标权重（%）")
                for portfolio_symbol in selected_symbols:
                    default_weight = PORTFOLIO_DEFAULT_WEIGHTS.get(portfolio_symbol, 0.0)
                    portfolio_weights[portfolio_symbol] = st.number_input(
                        portfolio_symbol,
                        min_value=0.0,
                        max_value=100.0,
                        value=default_weight,
                        step=1.0,
                        key=f"portfolio_weight_{portfolio_symbol}",
                    )
                total_weight_pct = sum(portfolio_weights.values())
                st.caption(f"ETF 权重合计：{total_weight_pct:.1f}%")
                if total_weight_pct > 100.0:
                    st.error("ETF 权重合计超过 100%，请调整后再运行")
                elif total_weight_pct < 100.0:
                    st.info(f"现金目标权重：{100.0 - total_weight_pct:.1f}%（仅用于风险展示，不参与每期定投分配）")
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

    if mode == "portfolio":
        portfolio_strategy = st.selectbox(
            "组合策略",
            options=list(PORTFOLIO_STRATEGY_OPTIONS.keys()),
            format_func=lambda key: PORTFOLIO_STRATEGY_OPTIONS[key],
        )
        rebalance_threshold_pct = st.number_input(
            "再平衡阈值（%）",
            min_value=1.0,
            max_value=20.0,
            value=5.0,
            step=0.5,
            help="仅「组合定投 + 再平衡」策略生效",
        )
        if st.button("运行组合回测", type="primary"):
            if len(selected_symbols) < 2:
                st.warning("请至少选择 2 个组合标的")
            elif sum(portfolio_weights.values()) > 100.0:
                st.error("ETF 权重合计超过 100%，请调整后再运行")
            else:
                assets = [
                    PortfolioAssetConfig(symbol=item, target_weight=portfolio_weights[item] / 100.0)
                    for item in selected_symbols
                    if portfolio_weights.get(item, 0) > 0
                ]
                if len(assets) < 2:
                    st.warning("请至少为 2 个标的设置大于 0 的目标权重")
                else:
                    config = PortfolioBacktestConfig(
                        assets=assets,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        initial_cash=float(initial_cash),
                        fixed_amount=float(fixed_amount),
                        frequency=frequency,
                        strategy_name=portfolio_strategy,
                        rebalance_threshold=float(rebalance_threshold_pct) / 100.0,
                    )
                    with db_session() as conn:
                        run_id, result, message = run_and_save_portfolio_backtest(conn, config)
                    if run_id is None:
                        st.warning(message)
                    else:
                        st.success(message)
                        st.session_state["latest_backtest_run_id"] = run_id
                        st.session_state.pop("latest_comparison_items", None)

        latest_run_id = st.session_state.get("latest_backtest_run_id")
        if latest_run_id:
            with get_connection() as conn:
                detail = load_backtest_detail(conn, int(latest_run_id))
            if detail and (detail.get("run") or {}).get("symbol") == "PORTFOLIO":
                st.subheader("本次组合回测结果")
                _render_detail(detail, key_prefix=f"latest_{latest_run_id}")
    elif mode == "single":
        strategy = st.selectbox(
            "策略类型",
            options=list(STRATEGY_OPTIONS.keys()),
            format_func=lambda key: STRATEGY_OPTIONS[key],
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
                st.session_state.pop("latest_comparison_items", None)

        latest_run_id = st.session_state.get("latest_backtest_run_id")
        if latest_run_id:
            with get_connection() as conn:
                detail = load_backtest_detail(conn, int(latest_run_id))
            if detail:
                st.subheader("本次回测结果")
                _render_detail(detail, key_prefix=f"latest_{latest_run_id}")
    else:
        selected_strategies = st.multiselect(
            "策略多选",
            options=list(STRATEGY_OPTIONS.keys()),
            default=["baseline_dca", "ma_filter_dca", "drawdown_boost"],
            format_func=lambda key: STRATEGY_OPTIONS[key],
        )
        if st.button("运行策略对比", type="primary"):
            if not selected_strategies:
                st.warning("请至少选择一个策略")
            else:
                base_config = BacktestConfig(
                    symbol=symbol,
                    strategy_name="baseline_dca",
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    initial_cash=float(initial_cash),
                    fixed_amount=float(fixed_amount),
                    frequency=frequency,
                )
                with db_session() as conn:
                    comparison_items = run_backtest_comparison(conn, base_config, selected_strategies)
                st.session_state["latest_comparison_items"] = comparison_items
                st.session_state.pop("latest_backtest_run_id", None)
                success_count = sum(1 for item in comparison_items if item["run_id"] is not None)
                st.success(f"策略对比完成：{success_count}/{len(comparison_items)} 个策略成功")

        comparison_items = st.session_state.get("latest_comparison_items")
        if comparison_items:
            _render_comparison_results(comparison_items)

    with get_connection() as conn:
        history_rows = list_backtest_run_summaries(conn, limit=20)
    if history_rows:
        _render_history(history_rows)
    else:
        st.info("暂无历史回测记录")


render()
