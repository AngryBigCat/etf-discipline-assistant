from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import get_watch_only_assets, load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import (
    get_latest_strategy_signals,
    get_portfolio_overview,
    update_strategy_signal_review_status,
)
from src.strategy.rule_engine import calc_available_cash
from src.strategy.signal_generator import SnapshotRequiredError, generate_and_save_signals
from src.ui.labels import (
    localize_action,
    localize_confidence,
    localize_review_status,
    rename_columns,
)
from src.utils.date_utils import today_str
from src.utils.number_utils import format_number, format_pct

REVIEW_OPTIONS = ["generated", "reviewed", "ignored"]
BUY_ACTIONS = {"strong_buy", "small_buy"}
OBSERVE_ACTIONS = {"hold", "fixed_invest"}


def _load_signal_rows() -> list[dict]:
    with get_connection() as conn:
        rows = get_latest_strategy_signals(conn)
    return [dict(row) for row in rows]


def _render_summary(signals: list[dict], watch_only_assets: list[dict]) -> None:
    st.subheader("今日摘要")
    buy_symbols = [row["symbol"] for row in signals if row.get("action") in BUY_ACTIONS]
    stop_symbols = [row["symbol"] for row in signals if row.get("action") == "stop_buy"]
    observe_symbols = [row["symbol"] for row in signals if row.get("action") in OBSERVE_ACTIONS]
    watch_symbols = [asset["symbol"] for asset in watch_only_assets]

    st.markdown(
        f"- **可考虑买入**：{('、'.join(buy_symbols) if buy_symbols else '无')}"
    )
    st.markdown(
        f"- **暂停买入**：{('、'.join(stop_symbols) if stop_symbols else '无')}"
    )
    st.markdown(
        f"- **观察标的**：{('、'.join(observe_symbols) if observe_symbols else '无')}"
    )
    st.markdown(
        f"- **只观察标的**：{('、'.join(watch_symbols) if watch_symbols else '无')}"
    )


def render() -> None:
    st.title("策略信号")
    st.caption("基于最新行情、持仓与 ETF 配置生成纪律信号")

    settings = load_settings()
    watch_only_assets = get_watch_only_assets(settings)

    with get_connection() as conn:
        overview = get_portfolio_overview(conn, settings)

    account = overview["account"]
    total_plan_amount = overview["total_plan_amount"]
    min_cash_position = float(settings.get("portfolio", {}).get("min_cash_position") or 0)

    if overview.get("snapshot_date"):
        st.info(f"最新快照日期：{overview['snapshot_date']}")

    if not account.get("valid"):
        st.warning("请先录入现金或 ETF 持仓（前往「持仓录入」页面保存快照）。")
    else:
        available_cash = calc_available_cash(
            float(account["cash_value"]),
            float(account["current_account_value"]),
            min_cash_position,
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("账户总资产", f"{account['current_account_value']:,.2f}")
        c2.metric("ETF 总仓位", format_pct(account["total_position"]))
        c3.metric("现金仓位", format_pct(account["cash_position"]))
        c4.metric("可用现金", f"{available_cash:,.2f}")
        c5.metric("计划总投入", f"{total_plan_amount:,.0f}")

    if st.button("生成今日纪律信号", type="primary", disabled=not account.get("valid")):
        try:
            with db_session() as conn:
                signals, context = generate_and_save_signals(conn, settings, today_str())
            st.success(f"已生成 {len(signals)} 条 {context['signal_date']} 纪律信号")
            st.rerun()
        except SnapshotRequiredError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"生成失败：{exc}")

    signals = _load_signal_rows()
    if not signals:
        st.info("暂无策略信号，请先点击「生成今日纪律信号」。")
        if watch_only_assets:
            _render_summary([], watch_only_assets)
        st.stop()

    display_columns = [
        "symbol",
        "name",
        "final_score",
        "trend_score",
        "drawdown_score",
        "anti_chase_score",
        "position_score",
        "special_score",
        "action",
        "suggested_amount",
        "confidence_level",
        "review_status",
        "reason",
    ]
    rows = []
    for signal in signals:
        rows.append(
            {
                "symbol": signal["symbol"],
                "name": signal.get("name") or signal["symbol"],
                "final_score": format_number(signal.get("final_score"), 1),
                "trend_score": format_number(signal.get("trend_score"), 1),
                "drawdown_score": format_number(signal.get("drawdown_score"), 1),
                "anti_chase_score": format_number(signal.get("anti_chase_score"), 1),
                "position_score": format_number(signal.get("position_score"), 1),
                "special_score": format_number(signal.get("special_score"), 1)
                if signal.get("special_score") is not None
                else "—",
                "action": localize_action(signal.get("action"), settings),
                "suggested_amount": format_number(signal.get("suggested_amount"), 0),
                "confidence_level": localize_confidence(signal.get("confidence_level")),
                "review_status": localize_review_status(signal.get("review_status")),
                "reason": signal.get("reason") or "",
            }
        )

    st.subheader("纪律信号明细")
    st.dataframe(
        rename_columns(pd.DataFrame(rows)[display_columns]),
        use_container_width=True,
        hide_index=True,
    )

    _render_summary(signals, watch_only_assets)

    st.subheader("审核状态")
    for signal in signals:
        signal_id = signal.get("id")
        if signal_id is None:
            continue
        current_status = signal.get("review_status") or "generated"
        cols = st.columns([2, 3])
        with cols[0]:
            st.write(f"{signal['symbol']} · {signal.get('name') or signal['symbol']}")
        with cols[1]:
            selected = st.selectbox(
                "审核状态",
                options=REVIEW_OPTIONS,
                index=REVIEW_OPTIONS.index(current_status)
                if current_status in REVIEW_OPTIONS
                else 0,
                format_func=localize_review_status,
                key=f"review_{signal_id}",
                label_visibility="collapsed",
            )
            if selected != current_status:
                with db_session() as conn:
                    update_strategy_signal_review_status(conn, int(signal_id), selected)
                st.rerun()


render()
