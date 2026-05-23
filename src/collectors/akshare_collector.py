from __future__ import annotations

import pandas as pd
from loguru import logger

from src.collectors.base import PriceCollector


class AkshareCollector(PriceCollector):
    @property
    def source_name(self) -> str:
        return "akshare"

    def fetch_history(
        self,
        symbol: str,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("akshare is not installed") from exc

        logger.info("Fetching {} ({}) from AKShare", symbol, fund_code)
        raw = ak.fund_etf_hist_em(
            symbol=fund_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="",
        )
        if raw is None or raw.empty:
            raise RuntimeError(f"AKShare returned empty data for {fund_code}")

        column_map = {
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = raw.rename(columns=column_map)
        required = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise RuntimeError(f"AKShare missing columns: {missing}")

        df = df[required].copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        df["symbol"] = symbol
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close", "trade_date"])
        if df.empty:
            raise RuntimeError(f"AKShare returned no valid rows for {fund_code}")
        return df
