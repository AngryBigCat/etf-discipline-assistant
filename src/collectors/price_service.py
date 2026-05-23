from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.collectors.akshare_collector import AkshareCollector
from src.collectors.base import PriceCollector
from src.collectors.mock_collector import MockCollector
from src.config.settings import get_price_data_source


@dataclass
class FetchResult:
    df: pd.DataFrame
    source: str
    used_fallback: bool


class CompositeCollector:
    def __init__(
        self,
        primary: PriceCollector | None = None,
        fallback: PriceCollector | None = None,
        mode: str | None = None,
    ) -> None:
        self.mode = (mode or get_price_data_source()).lower()
        self.primary = primary or AkshareCollector()
        self.fallback = fallback or MockCollector()

    def fetch_history(
        self,
        symbol: str,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> FetchResult:
        if self.mode == "mock":
            df = self.fallback.fetch_history(symbol, fund_code, start_date, end_date)
            return FetchResult(df=df, source=self.fallback.source_name, used_fallback=True)

        if self.mode == "akshare":
            df = self.primary.fetch_history(symbol, fund_code, start_date, end_date)
            return FetchResult(df=df, source=self.primary.source_name, used_fallback=False)

        try:
            df = self.primary.fetch_history(symbol, fund_code, start_date, end_date)
            return FetchResult(df=df, source=self.primary.source_name, used_fallback=False)
        except Exception as exc:
            logger.warning(
                "Primary collector failed for {} ({}): {}. Falling back to mock.",
                symbol,
                fund_code,
                exc,
            )
            df = self.fallback.fetch_history(symbol, fund_code, start_date, end_date)
            return FetchResult(df=df, source=self.fallback.source_name, used_fallback=True)
