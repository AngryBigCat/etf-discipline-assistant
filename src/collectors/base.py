from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceCollector(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch_history(
        self,
        symbol: str,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        raise NotImplementedError
