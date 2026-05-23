from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import get_project_root, load_settings
from src.db.connection import get_connection
from src.db.repository import get_latest_daily_prices, get_latest_indicators, list_etf_universe
from src.utils.number_utils import format_number, format_pct


def load_dashboard_data():
    with get_connection() as conn:
        universe = list_etf_universe(conn)
        prices = get_latest_daily_prices(conn)
        indicators = get_latest_indicators(conn)
    universe_df = pd.DataFrame([dict(row) for row in universe]) if universe else pd.DataFrame()
    return universe_df, prices, indicators


def main() -> None:
    settings = load_settings()
    app_name = settings.get("app", {}).get("name", "ETF投资纪律助手")

    st.set_page_config(page_title=app_name, layout="wide")
    st.title(app_name)
    st.caption("阶段 1-3 最简首页：标的列表、最新行情、基础指标")

    try:
        universe_df, prices_df, indicators_df = load_dashboard_data()
    except Exception as exc:
        st.error(f"无法读取数据库，请先运行 init_db.py / seed_data.py / daily_update.py。详情: {exc}")
        st.stop()

    if universe_df.empty:
        st.warning("etf_universe 为空，请先运行 seed_data.py")
        st.stop()

    st.subheader("ETF 标的池")
    display_cols = [
        "symbol",
        "name",
        "fund_code",
        "exchange",
        "role",
        "enabled_for_signal",
    ]
    existing = [c for c in display_cols if c in universe_df.columns]
    st.dataframe(universe_df[existing], use_container_width=True, hide_index=True)

    if prices_df.empty:
        st.warning("暂无行情数据，请运行 daily_update.py")
    else:
        st.subheader("最新行情")
        price_view = prices_df[
            ["symbol", "trade_date", "close", "open", "high", "low", "volume", "amount"]
        ].copy()
        st.dataframe(price_view, use_container_width=True, hide_index=True)

    if indicators_df.empty:
        st.warning("暂无指标数据，请运行 daily_update.py")
    else:
        st.subheader("最新指标")
        indicator_cols = [
            "symbol",
            "trade_date",
            "ma20",
            "ma60",
            "ma120",
            "ma250",
            "drawdown_used",
            "drawdown_window",
            "volatility_20d",
            "return_5d",
            "return_10d",
            "return_20d",
            "confidence_level",
        ]
        existing_ind = [c for c in indicator_cols if c in indicators_df.columns]
        view = indicators_df[existing_ind].copy()
        for col in ["drawdown_used", "volatility_20d", "return_5d", "return_10d", "return_20d"]:
            if col in view.columns:
                view[col] = view[col].apply(lambda x: format_pct(x) if col != "volatility_20d" else format_number(x, 4))
        st.dataframe(view, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        f"""
**运行提示**

```bash
python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
streamlit run app.py
```

项目根目录：`{get_project_root()}`
"""
    )


if __name__ == "__main__":
    main()
