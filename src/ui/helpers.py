from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.connection import get_connection
from src.db.repository import get_latest_daily_prices, get_latest_indicators, list_etf_universe

EMPTY_UNIVERSE_HINT = (
    "标的池为空，请先运行初始化脚本：\n"
    "python scripts/seed_data.py\n"
    "或 python scripts/sync_assets_from_seed.py"
)


def is_etf_universe_empty(conn) -> bool:
    return len(list_etf_universe(conn, enabled_only=False)) == 0


def render_empty_universe_hint(*, stop: bool = True) -> bool:
    with get_connection() as conn:
        empty = is_etf_universe_empty(conn)
    if empty:
        st.warning(EMPTY_UNIVERSE_HINT)
        if stop:
            st.stop()
    return empty


def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with get_connection() as conn:
        universe = list_etf_universe(conn, enabled_only=True)
        prices = get_latest_daily_prices(conn, enabled_only=True)
        indicators = get_latest_indicators(conn, enabled_only=True)
    universe_df = pd.DataFrame([dict(row) for row in universe]) if universe else pd.DataFrame()
    return universe_df, prices, indicators
