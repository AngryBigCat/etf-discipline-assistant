from __future__ import annotations

import streamlit as st

from src.ui.helpers import EMPTY_UNIVERSE_HINT, load_dashboard_data, render_empty_universe_hint
from src.ui.labels import localize_bool, localize_confidence, localize_role, rename_columns
from src.utils.number_utils import format_number, format_pct


def render() -> None:
    st.title("数据看板")
    st.caption("标的列表、最新行情、基础指标")

    render_empty_universe_hint()

    try:
        universe_df, prices_df, indicators_df = load_dashboard_data()
    except Exception as exc:
        st.error(f"无法读取数据库，请先运行 init_db.py / seed_data.py / daily_update.py。详情: {exc}")
        st.stop()

    if universe_df.empty:
        st.warning(EMPTY_UNIVERSE_HINT)
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
    universe_view = universe_df[existing].copy()
    if "role" in universe_view.columns:
        universe_view["role"] = universe_view["role"].apply(localize_role)
    if "enabled_for_signal" in universe_view.columns:
        universe_view["enabled_for_signal"] = universe_view["enabled_for_signal"].apply(localize_bool)
    st.dataframe(rename_columns(universe_view), use_container_width=True, hide_index=True)

    if prices_df.empty:
        st.warning("暂无行情数据，请运行 daily_update.py")
    else:
        st.subheader("最新行情")
        price_view = prices_df[
            ["symbol", "trade_date", "close", "open", "high", "low", "volume", "amount"]
        ].copy()
        st.dataframe(rename_columns(price_view), use_container_width=True, hide_index=True)

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
                view[col] = view[col].apply(
                    lambda x: format_pct(x) if col != "volatility_20d" else format_number(x, 4)
                )
        if "confidence_level" in view.columns:
            view["confidence_level"] = view["confidence_level"].apply(localize_confidence)
        st.dataframe(rename_columns(view), use_container_width=True, hide_index=True)


render()
