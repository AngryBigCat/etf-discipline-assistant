from __future__ import annotations

from datetime import date

import streamlit as st

from src.config.settings import get_enabled_portfolio_assets, load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import (
    get_account_snapshot,
    get_holding_snapshots,
    get_latest_price_map,
)
from src.portfolio.holdings import HoldingInput, resolve_market_value, save_snapshot
from src.utils.date_utils import today_str


def _load_existing(snapshot_date: str) -> tuple[float, dict[str, dict]]:
    with get_connection() as conn:
        account = get_account_snapshot(conn, snapshot_date)
        holdings = get_holding_snapshots(conn, snapshot_date)
    cash_value = float(account["cash_value"]) if account else 0.0
    holding_map = {row["symbol"]: dict(row) for row in holdings}
    return cash_value, holding_map


def render() -> None:
    st.title("持仓录入")
    st.caption("手动录入现金与 ETF 持仓，保存为当日快照")

    settings = load_settings()
    assets = get_enabled_portfolio_assets(settings)

    if not assets:
        st.warning("没有可录入的 ETF 标的（enabled=true）")
        st.stop()

    snapshot_date = st.date_input("快照日期", value=date.today()).strftime("%Y-%m-%d")
    existing_cash, existing_holdings = _load_existing(snapshot_date)

    with get_connection() as conn:
        price_map = get_latest_price_map(conn)

    if existing_cash > 0 or existing_holdings:
        st.info(f"已加载 {snapshot_date} 的已有快照，可修改后重新保存。")

    cash_value = st.number_input(
        "现金余额 (cash_value)",
        min_value=0.0,
        value=float(existing_cash),
        step=1000.0,
        format="%.2f",
    )

    st.subheader("ETF 持仓")
    inputs: list[HoldingInput] = []

    for asset in assets:
        symbol = asset["symbol"]
        name = asset["name"]
        latest_price = price_map.get(symbol)
        existing = existing_holdings.get(symbol, {})

        with st.expander(f"{symbol} · {name}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("最新价", f"{latest_price:.4f}" if latest_price else "—")
            with col2:
                quantity = st.number_input(
                    "数量 (quantity)",
                    min_value=0.0,
                    value=float(existing.get("quantity") or 0),
                    step=100.0,
                    key=f"qty_{symbol}",
                )
            with col3:
                cost = st.number_input(
                    "成本 (cost)",
                    min_value=0.0,
                    value=float(existing.get("cost") or 0),
                    step=1000.0,
                    key=f"cost_{symbol}",
                )

            manual_default = 0.0
            if latest_price is None and existing.get("market_value"):
                manual_default = float(existing["market_value"])

            manual_market_value = None
            if latest_price is None:
                manual_market_value = st.number_input(
                    "手动市值 (无最新价时使用)",
                    min_value=0.0,
                    value=manual_default,
                    step=1000.0,
                    key=f"manual_{symbol}",
                )
                if manual_market_value <= 0:
                    manual_market_value = None
            else:
                st.caption("市值将按 最新价 × 数量 自动计算")

            preview = resolve_market_value(quantity, latest_price, manual_market_value)
            st.write(f"预览市值：**{preview if preview is not None else '—'}**")

            if quantity > 0 or cost > 0 or preview:
                inputs.append(
                    HoldingInput(
                        symbol=symbol,
                        quantity=quantity,
                        cost=cost,
                        manual_market_value=manual_market_value,
                    )
                )

    if st.button("保存今日快照", type="primary"):
        try:
            with db_session() as conn:
                result = save_snapshot(conn, snapshot_date, cash_value, inputs, price_map)
            st.success(
                f"已保存 {result['snapshot_date']} 快照："
                f"账户总资产 {result['account']['current_account_value']:.2f}，"
                f"ETF {result['holdings_count']} 条"
            )
        except Exception as exc:
            st.error(f"保存失败：{exc}")

    st.caption(f"默认今天：{today_str()} · CASH 仅通过上方现金余额录入，不写入 holding_snapshot")


render()
