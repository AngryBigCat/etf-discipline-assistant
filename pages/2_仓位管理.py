from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import load_settings
from src.db.connection import get_connection
from src.db.repository import get_portfolio_overview
from src.portfolio.rebalance import STATUS_EXCEED_MAX, STATUS_OVERWEIGHT, STATUS_WATCH_ONLY
from src.utils.number_utils import format_number, format_pct

STATUS_LABELS = {
    "underweight": "低于目标",
    "normal": "正常",
    "overweight": "超过目标",
    "exceed_max": "超过上限",
    "watch_only": "只观察",
}


st.set_page_config(page_title="仓位管理", layout="wide")
st.title("仓位管理")
st.caption("基于最新快照展示账户总览与各 ETF 仓位状态")

settings = load_settings()

with get_connection() as conn:
    overview = get_portfolio_overview(conn, settings)

account = overview["account"]
total_plan_amount = overview["total_plan_amount"]

if not account.get("valid"):
    st.warning("请先录入现金或 ETF 持仓（前往「持仓录入」页面保存快照）。")
    st.stop()

st.subheader("账户总览")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("账户总资产", f"{account['current_account_value']:,.2f}")
c2.metric("ETF 总市值", f"{account['etf_market_value']:,.2f}")
c3.metric("现金余额", f"{account['cash_value']:,.2f}")
c4.metric("总 ETF 仓位", format_pct(account["total_position"]))
c5.metric("现金仓位", format_pct(account["cash_position"]))
c6.metric("计划总投入", f"{total_plan_amount:,.0f}")
st.caption("计划总投入 (total_plan_amount) 不等于账户总资产，仅作计划参考。")

if overview.get("snapshot_date"):
    st.info(f"快照日期：{overview['snapshot_date']}")

alerts = overview.get("alerts") or []
if alerts:
    st.subheader("仓位提醒")
    for alert in alerts:
        st.warning(alert)

positions = overview.get("positions") or []
if not positions:
    st.info("当前快照无 ETF 持仓记录。")
    st.stop()

st.subheader("ETF 仓位明细")
rows = []
for pos in positions:
    rows.append(
        {
            "symbol": pos["symbol"],
            "name": pos["name"],
            "market_value": pos["market_value"],
            "cost": pos["cost"],
            "profit_loss": pos["profit_loss"],
            "profit_loss_rate": format_pct(pos["profit_loss_rate"]) if pos["profit_loss_rate"] is not None else "—",
            "weight": format_pct(pos["weight"]),
            "target_weight": format_pct(pos["target_weight"]),
            "max_weight": format_pct(pos["max_weight"]),
            "max_allowed_value": format_number(pos["max_allowed_value"], 2),
            "deviation": format_pct(pos["deviation"]),
            "status": STATUS_LABELS.get(pos["status"], pos["status"]),
            "enabled_for_signal": pos["enabled_for_signal"],
        }
    )

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

exceed_rows = [p for p in positions if p["status"] == STATUS_EXCEED_MAX]
over_rows = [p for p in positions if p["status"] == STATUS_OVERWEIGHT]
watch_rows = [p for p in positions if p["status"] == STATUS_WATCH_ONLY]

if exceed_rows:
    st.error("超过 max_weight 上限：" + "、".join(r["symbol"] for r in exceed_rows))
if over_rows:
    st.warning("高于目标仓位：" + "、".join(r["symbol"] for r in over_rows))
if watch_rows:
    st.info("只观察标的：" + "、".join(r["symbol"] for r in watch_rows))
