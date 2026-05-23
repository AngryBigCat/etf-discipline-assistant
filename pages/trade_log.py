from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.config.settings import get_enabled_portfolio_assets, load_settings
from src.db.connection import db_session, get_connection
from src.trading.trade_log import (
    TradeLogInput,
    create_manual_trade,
    get_recent_trade_logs,
    get_trade_summary,
)
from src.ui.labels import (
    EMOTION_LABELS,
    TRADE_ACTION_LABELS,
    localize_bool,
    localize_emotion,
    localize_execution_status,
    localize_trade_action,
    rename_columns,
)
from src.utils.date_utils import today_str
from src.utils.number_utils import format_number


def render() -> None:
    st.title("交易日志")
    st.caption("记录实际交易行为，用于复盘投资纪律")

    settings = load_settings()
    with get_connection() as conn:
        assets = get_enabled_portfolio_assets(conn)
    asset_options = {asset["symbol"]: asset["name"] for asset in assets}

    st.subheader("手动新增交易")
    with st.form("manual_trade_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            trade_date = st.date_input("交易日期", value=date.today())
            symbol = st.selectbox(
                "标的代码",
                options=list(asset_options.keys()),
                format_func=lambda s: f"{s} · {asset_options[s]}",
            )
            action = st.selectbox(
                "操作方向",
                options=list(TRADE_ACTION_LABELS.keys()),
                format_func=lambda v: TRADE_ACTION_LABELS[v],
            )
        with c2:
            amount = st.number_input("交易金额", min_value=0.0, step=100.0, format="%.2f")
            price = st.number_input("交易价格", min_value=0.0, step=0.0001, format="%.4f")
            quantity = st.number_input("交易数量", min_value=0.0, step=100.0, format="%.4f")
        with c3:
            emotion = st.selectbox(
                "情绪状态",
                options=list(EMOTION_LABELS.keys()),
                index=list(EMOTION_LABELS.keys()).index("planned"),
                format_func=lambda v: EMOTION_LABELS[v],
            )
            user_is_rule_based = st.checkbox("是否符合规则", value=False)
            note = st.text_input("备注")
        reason = st.text_area("交易理由")

        if st.form_submit_button("保存交易记录", type="primary"):
            try:
                with db_session() as conn:
                    create_manual_trade(
                        conn,
                        TradeLogInput(
                            trade_date=trade_date.strftime("%Y-%m-%d"),
                            symbol=symbol,
                            action=action,
                            amount=amount,
                            price=price if price > 0 else None,
                            quantity=quantity if quantity > 0 else None,
                            reason=reason,
                            emotion=emotion,
                            note=note,
                            user_is_rule_based=user_is_rule_based,
                        ),
                    )
                st.success("交易记录已保存")
                st.rerun()
            except Exception as exc:
                st.error(f"保存失败：{exc}")

    st.subheader("最近交易记录")
    with get_connection() as conn:
        recent_rows = get_recent_trade_logs(conn, limit=50)

    if not recent_rows:
        st.info("暂无交易记录")
    else:
        display_columns = [
            "trade_date",
            "symbol",
            "name",
            "action",
            "amount",
            "price",
            "quantity",
            "suggested_amount",
            "deviation_amount",
            "is_rule_based",
            "execution_status",
            "reason",
            "emotion",
            "note",
        ]
        rows = []
        for row in recent_rows:
            item = dict(row)
            rows.append(
                {
                    "trade_date": item.get("trade_date"),
                    "symbol": item.get("symbol"),
                    "name": item.get("name") or item.get("symbol"),
                    "action": localize_trade_action(item.get("action")),
                    "amount": format_number(item.get("amount"), 2),
                    "price": format_number(item.get("price"), 4)
                    if item.get("price") is not None
                    else "—",
                    "quantity": format_number(item.get("quantity"), 4)
                    if item.get("quantity") is not None
                    else "—",
                    "suggested_amount": format_number(item.get("suggested_amount"), 0),
                    "deviation_amount": format_number(item.get("deviation_amount"), 2),
                    "is_rule_based": localize_bool(bool(item.get("is_rule_based"))),
                    "execution_status": localize_execution_status(item.get("execution_status")),
                    "reason": item.get("reason") or "",
                    "emotion": localize_emotion(item.get("emotion")),
                    "note": item.get("note") or "",
                }
            )
        st.dataframe(
            rename_columns(pd.DataFrame(rows)[display_columns]),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("交易纪律统计")
    end_default = date.today()
    start_default = end_default - timedelta(days=30)
    c1, c2 = st.columns(2)
    with c1:
        stat_start = st.date_input("统计开始日期", value=start_default, key="stat_start")
    with c2:
        stat_end = st.date_input("统计结束日期", value=end_default, key="stat_end")

    with get_connection() as conn:
        summary = get_trade_summary(
            conn,
            start_date=stat_start.strftime("%Y-%m-%d"),
            end_date=stat_end.strftime("%Y-%m-%d"),
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("总交易次数", summary["total_count"])
    m2.metric("买入次数", summary["buy_count"])
    m3.metric("卖出次数", summary["sell_count"])
    m4.metric("符合规则比例", f"{summary['compliance_rate'] * 100:.1f}%")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("符合规则次数", summary["rule_based_count"])
    m6.metric("不符合规则次数", summary["not_rule_based_count"])
    m7.metric("追涨次数", summary["chasing_count"])
    m8.metric("恐慌交易次数", summary["panic_count"])

    m9, m10, m11, m12 = st.columns(4)
    m9.metric("临时决策次数", summary["temporary_count"])
    m10.metric("总买入金额", f"{summary['total_buy_amount']:,.2f}")
    m11.metric("总卖出金额", f"{summary['total_sell_amount']:,.2f}")
    m12.metric("统计区间", f"{summary['start_date']} ~ {summary['end_date']}")


render()
