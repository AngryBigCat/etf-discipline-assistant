from __future__ import annotations

import pandas as pd
from loguru import logger

from src.collectors.base import PriceCollector
from src.utils.network import (
    EASTMONEY_KLINE_URL,
    build_network_hint,
    is_connection_error,
    resilient_get_json,
)


def _eastmoney_market_id(fund_code: str) -> int:
    if fund_code.startswith(("5", "6")):
        return 1
    if fund_code.startswith(("0", "1", "2", "3")):
        return 0
    return 1


def _to_sina_symbol(fund_code: str) -> str:
    if fund_code.startswith(("5", "6")):
        return f"sh{fund_code}"
    return f"sz{fund_code}"


def _parse_eastmoney_klines(data_json: dict) -> pd.DataFrame:
    klines = data_json.get("data", {}).get("klines") or []
    if not klines:
        return pd.DataFrame()
    temp_df = pd.DataFrame([item.split(",") for item in klines])
    temp_df.columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    return temp_df


def _normalize_price_frame(
    raw: pd.DataFrame,
    symbol: str,
    column_map: dict[str, str],
    *,
    derive_amount: bool = False,
) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise RuntimeError(f"No price data returned for {symbol}")

    df = raw.rename(columns=column_map)
    required = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns: {missing}")

    df = df[required].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = symbol
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if derive_amount:
        df["amount"] = df["close"] * df["volume"]
    df = df.dropna(subset=["close", "trade_date"])
    if df.empty:
        raise RuntimeError(f"No valid rows for {symbol}")
    return df


class AkshareCollector(PriceCollector):
    def __init__(self) -> None:
        self.last_data_source = "eastmoney"

    @property
    def source_name(self) -> str:
        return "akshare"

    def _fetch_eastmoney_history(
        self,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101",
            "fqt": "0",
            "beg": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
        }
        primary_market_id = _eastmoney_market_id(fund_code)
        market_ids = [primary_market_id]
        fallback_market_id = 1 - primary_market_id
        if fallback_market_id not in market_ids:
            market_ids.append(fallback_market_id)

        last_exc: BaseException | None = None
        for market_id in market_ids:
            request_params = {**params, "secid": f"{market_id}.{fund_code}"}
            try:
                data_json = resilient_get_json(EASTMONEY_KLINE_URL, request_params)
                df = _parse_eastmoney_klines(data_json)
                if not df.empty:
                    return df
            except Exception as exc:
                last_exc = exc
                if is_connection_error(exc):
                    break
        if last_exc is not None:
            raise last_exc
        return pd.DataFrame()

    def _fetch_sina_history(
        self,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("akshare is not installed") from exc

        sina_symbol = _to_sina_symbol(fund_code)
        logger.warning(
            "East Money unavailable for {} ({}), falling back to Sina",
            fund_code,
            sina_symbol,
        )
        raw = ak.fund_etf_hist_sina(symbol=sina_symbol)
        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        if df.empty:
            return pd.DataFrame()

        df["amount"] = df["close"] * df["volume"]
        return df.rename(
            columns={
                "date": "trade_date",
            }
        )

    def fetch_history(
        self,
        symbol: str,
        fund_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        logger.info("Fetching {} ({}) from AKShare", symbol, fund_code)
        eastmoney_error: BaseException | None = None
        try:
            raw = self._fetch_eastmoney_history(fund_code, start_date, end_date)
            if raw is not None and not raw.empty:
                self.last_data_source = "eastmoney"
                return _normalize_price_frame(
                    raw,
                    symbol,
                    {
                        "日期": "trade_date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume",
                        "成交额": "amount",
                    },
                )
        except Exception as exc:
            eastmoney_error = exc
            if not is_connection_error(exc):
                raise RuntimeError(str(exc)) from exc

        try:
            sina_df = self._fetch_sina_history(fund_code, start_date, end_date)
        except Exception as sina_exc:
            if eastmoney_error is not None and is_connection_error(eastmoney_error):
                raise RuntimeError(
                    f"{eastmoney_error}。{build_network_hint(eastmoney_error)}"
                ) from sina_exc
            raise RuntimeError(str(sina_exc)) from sina_exc

        if sina_df is None or sina_df.empty:
            if eastmoney_error is not None and is_connection_error(eastmoney_error):
                raise RuntimeError(
                    f"{eastmoney_error}。{build_network_hint(eastmoney_error)}"
                ) from eastmoney_error
            raise RuntimeError(f"AKShare returned empty data for {fund_code}")

        self.last_data_source = "sina"
        return _normalize_price_frame(
            sina_df,
            symbol,
            {
                "trade_date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "amount",
            },
        )
