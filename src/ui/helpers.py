from __future__ import annotations

import pandas as pd

from src.db.connection import get_connection
from src.db.repository import get_latest_daily_prices, get_latest_indicators, list_etf_universe


def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with get_connection() as conn:
        universe = list_etf_universe(conn, enabled_only=True)
        prices = get_latest_daily_prices(conn)
        indicators = get_latest_indicators(conn)
    universe_df = pd.DataFrame([dict(row) for row in universe]) if universe else pd.DataFrame()
    return universe_df, prices, indicators
