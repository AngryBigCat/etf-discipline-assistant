from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config.settings import get_watch_only_assets, load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import get_latest_price_map, get_latest_strategy_signals, get_portfolio_overview
from src.strategy.rule_engine import calc_available_cash
from src.strategy.signal_generator import SnapshotRequiredError, generate_and_save_signals
from src.trading.trade_log import create_buy_from_signal, create_ignore_from_signal, mark_signal_reviewed
from src.ui.labels import (
    EMOTION_LABELS,
    localize_action,
    localize_confidence,
    localize_review_status,
    rename_columns,
)
from src.utils.date_utils import today_str
from src.utils.number_utils import format_number, format_pct

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

    st.markdown(f"- **可考虑买入**：{('、'.join(buy_symbols) if buy_symbols else '无')}")
    st.markdown(f"- **暂停买入**：{('、'.join(stop_symbols) if stop_symbols else '无')}")
    st.markdown(f"- **观察标的**：{('、'.join(observe_symbols) if observe_symbols else '无')}")
    st.markdown(f"- **只观察标的**：{('、'.join(watch_symbols) if watch_symbols else '无')}")


def _render_signal_actions(signal: dict, price_map: dict[str, float]) -> None:
    signal_id = signal.get("id")
    if signal_id is None:
        return

    symbol = signal["symbol"]
    name = signal.get("name") or symbol
    suggested = float(signal.get("suggested_amount") or 0)
    latest_price = price_map.get(symbol)
    default_price = float(latest_price) if latest_price else 0.0
    default_quantity = suggested / default_price if default_price > 0 else 0.0

    with st.expander(f"{symbol} · {name} · {localize_review_status(signal.get('review_status'))}"):
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("标记已查看", key=f"reviewed_{signal_id}"):
                with db_session() as conn:
                    mark_signal_reviewed(conn, int(signal_id))
                st.success("已标记为已查看")
                st.rerun()
        with btn2:
            if st.button("标记忽略", key=f"ignore_{signal_id}"):
                with db_session() as conn:
                    create_ignore_from_signal(conn, signal)
                st.success("已标记为忽略，并写入交易日志")
                st.rerun()

        with st.form(f"buy_form_{signal_id}"):
            st.markdown("**记录买入**")
            c1, c2, c3 = st.columns(3)
            with c1:
                trade_date = st.date_input(
                    "交易日期",
                    value=date.today(),
                    key=f"trade_date_{signal_id}",
                )
                amount = st.number_input(
                    "交易金额",
                    min_value=0.0,
                    value=suggested,
                    step=100.0,
                    format="%.2f",
                    key=f"amount_{signal_id}",
                )
            with c2:
                price = st.number_input(
                    "交易价格",
                    min_value=0.0,
                    value=default_price,
                    step=0.0001,
                    format="%.4f",
                    key=f"price_{signal_id}",
                )
                quantity = st.number_input(
                    "交易数量",
                    min_value=0.0,
                    value=default_quantity,
                    step=100.0,
                    format="%.4f",
                    key=f"quantity_{signal_id}",
                )
            with c3:
                emotion = st.selectbox(
                    "情绪状态",
                    options=list(EMOTION_LABELS.keys()),
                    index=list(EMOTION_LABELS.keys()).index("planned"),
                    format_func=lambda v: EMOTION_LABELS[v],
                    key=f"emotion_{signal_id}",
                )
                note = st.text_input("备注", key=f"note_{signal_id}")
            reason = st.text_area("交易理由", key=f"reason_{signal_id}")

            if st.form_submit_button("保存买入记录", type="primary"):
                try:
                    with db_session() as conn:
                        create_buy_from_signal(
                            conn,
                            signal,
                            trade_date=trade_date.strftime("%Y-%m-%d"),
                            amount=amount,
                            price=price if price > 0 else None,
                            quantity=quantity if quantity > 0 else None,
                            reason=reason,
                            emotion=emotion,
                            note=note,
                        )
                    st.success("买入记录已保存，信号状态已更新为已执行")
                    st.rerun()
                except Exception as exc:
                    st.error(f"保存失败：{exc}")


def render() -> None:
    st.title("策略信号")
    st.caption("基于最新行情、持仓与 ETF 配置生成纪律信号")

    settings = load_settings()
    watch_only_assets = get_watch_only_assets(settings)

    with get_connection() as conn:
        overview = get_portfolio_overview(conn, settings)
        price_map = get_latest_price_map(conn)

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

    st.subheader("信号操作")
    for signal in signals:
        _render_signal_actions(signal, price_map)


render()
