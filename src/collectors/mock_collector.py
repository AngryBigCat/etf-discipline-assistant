from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from src.collectors.base import PriceCollector

MOCK_BASE_PRICES: dict[str, float] = {
    "A500": 1.05,
    "KC50": 0.88,
    "HS300": 3.95,
    "DIVIDEND": 3.10,
    "SP500": 1.65,
    "NASDAQ100": 1.42,
}


class MockCollector(PriceCollector):
    @property
    def source_name(self) -> str:
        return "mock"

    def fetch_history(
        self,
        symbol: str,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        dates = pd.bdate_range(start=start_date, end=end_date)
        if len(dates) == 0:
            return pd.DataFrame(
                columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"]
            )

        seed = int(hashlib.md5(f"{symbol}:{fund_code}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)

        base = MOCK_BASE_PRICES.get(symbol, 1.0)
        n = len(dates)
        daily_returns = rng.normal(0.0002, 0.012, size=n)
        closes = base * np.cumprod(1 + daily_returns)

        rows: list[dict] = []
        for i, dt in enumerate(dates):
            close = float(closes[i])
            open_price = close * float(rng.uniform(0.995, 1.005))
            high = max(open_price, close) * float(rng.uniform(1.0, 1.012))
            low = min(open_price, close) * float(rng.uniform(0.988, 1.0))
            volume = float(rng.integers(100_000, 2_000_000))
            amount = volume * close * 100
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": dt.strftime("%Y-%m-%d"),
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": volume,
                    "amount": round(amount, 2),
                }
            )
        return pd.DataFrame(rows)
