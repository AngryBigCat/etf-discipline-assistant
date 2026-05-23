from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.config.settings import load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import list_daily_reports, list_weekly_reports
from src.reports.daily_report import build_and_save_daily_report
from src.reports.weekly_report import build_and_save_weekly_report
from src.ui.labels import rename_columns


def _preview(text: str | None, max_len: int = 120) -> str:
    if not text:
        return "—"
    plain = text.replace("\n", " ").strip()
    if len(plain) <= max_len:
        return plain
    return plain[:max_len] + "…"


def render() -> None:
    st.title("报告复盘")
    st.caption("基于账户快照、策略信号与交易日志生成模板化日报/周报，用于复盘投资纪律")

    settings = load_settings()

    st.subheader("日报")
    daily_date = st.date_input("报告日期", value=date.today(), key="daily_report_date")
    if st.button("生成今日日报", type="primary", key="generate_daily"):
        with db_session() as conn:
            report, saved, message = build_and_save_daily_report(
                conn,
                settings,
                daily_date.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_daily_report"] = report
        else:
            st.warning(message)

    latest_daily = st.session_state.get("latest_daily_report")
    if latest_daily:
        st.markdown("#### 概况")
        st.markdown(latest_daily.get("summary") or "—")
        st.markdown("#### 风险提示")
        st.markdown(latest_daily.get("risk_warning") or "—")
        st.markdown("#### 操作建议")
        st.markdown(latest_daily.get("action_suggestion") or "—")

    with get_connection() as conn:
        daily_rows = list_daily_reports(conn, limit=30)
    if daily_rows:
        st.markdown("#### 历史日报")
        daily_df = pd.DataFrame(
            [
                {
                    "report_date": row["report_date"],
                    "summary": _preview(row["summary"]),
                    "risk_warning": _preview(row["risk_warning"]),
                    "action_suggestion": _preview(row["action_suggestion"]),
                }
                for row in daily_rows
            ]
        )
        st.dataframe(
            rename_columns(daily_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无历史日报")

    st.divider()

    st.subheader("周报")
    end_default = date.today()
    start_default = end_default - timedelta(days=6)
    c1, c2 = st.columns(2)
    with c1:
        week_start = st.date_input("周开始日期", value=start_default, key="week_start")
    with c2:
        week_end = st.date_input("周结束日期", value=end_default, key="week_end")

    if st.button("生成本周周报", type="primary", key="generate_weekly"):
        with db_session() as conn:
            report, saved, message = build_and_save_weekly_report(
                conn,
                settings,
                week_start.strftime("%Y-%m-%d"),
                week_end.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_weekly_report"] = report
        else:
            st.warning(message)

    latest_weekly = st.session_state.get("latest_weekly_report")
    if latest_weekly:
        st.markdown("#### 概况")
        st.markdown(latest_weekly.get("summary") or "—")
        st.markdown("#### 纪律统计")
        st.markdown(latest_weekly.get("discipline_summary") or "—")
        st.markdown("#### 风险摘要")
        st.markdown(latest_weekly.get("risk_summary") or "—")
        st.markdown("#### 操作建议")
        st.markdown(latest_weekly.get("action_suggestion") or "—")

    with get_connection() as conn:
        weekly_rows = list_weekly_reports(conn, limit=20)
    if weekly_rows:
        st.markdown("#### 历史周报")
        weekly_df = pd.DataFrame(
            [
                {
                    "week_start": row["week_start"],
                    "week_end": row["week_end"],
                    "summary": _preview(row["summary"]),
                    "discipline_summary": _preview(row["discipline_summary"]),
                    "risk_summary": _preview(row["risk_summary"]),
                    "action_suggestion": _preview(row["action_suggestion"]),
                }
                for row in weekly_rows
            ]
        )
        st.dataframe(
            rename_columns(weekly_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无历史周报")


render()
