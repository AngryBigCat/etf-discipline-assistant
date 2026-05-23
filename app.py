from __future__ import annotations

import streamlit as st

from src.config.settings import load_settings

settings = load_settings()
app_name = settings.get("app", {}).get("name", "ETF投资纪律助手")

st.set_page_config(
    page_title=app_name,
    layout="wide",
    initial_sidebar_state="expanded",
)

page = st.navigation(
    [
        st.Page("pages/dashboard.py", title="数据看板", default=True),
        st.Page("pages/holdings_entry.py", title="持仓录入"),
        st.Page("pages/position_mgmt.py", title="仓位管理"),
        st.Page("pages/strategy_signals.py", title="策略信号"),
        st.Page("pages/trade_log.py", title="交易日志"),
        st.Page("pages/reports.py", title="报告复盘"),
        st.Page("pages/ai_review.py", title="AI复盘"),
        st.Page("pages/backtest.py", title="回测分析"),
        st.Page("pages/tasks.py", title="任务中心"),
    ]
)
page.run()
