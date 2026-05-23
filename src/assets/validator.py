from __future__ import annotations

from typing import Any


def _asset_enabled(asset: dict[str, Any]) -> bool:
    enabled = asset.get("enabled", True)
    if isinstance(enabled, str):
        return enabled.lower() not in {"0", "false", "no"}
    return bool(enabled)


def _is_cash_asset(asset: dict[str, Any]) -> bool:
    return asset.get("symbol") == "CASH" or asset.get("role") == "cash"


def _counts_toward_etf_weight_sum(asset: dict[str, Any]) -> bool:
    if _is_cash_asset(asset):
        return False
    if not _asset_enabled(asset):
        return False
    return True


def sum_etf_target_weights(assets: list[dict[str, Any]]) -> float:
    total = 0.0
    for asset in assets:
        if not _counts_toward_etf_weight_sum(asset):
            continue
        target_weight = asset.get("target_weight")
        if target_weight is not None:
            total += float(target_weight)
    return total


def compute_implicit_cash_target_weight(assets: list[dict[str, Any]]) -> float | None:
    etf_total = sum_etf_target_weights(assets)
    if etf_total >= 1.0:
        return None
    return 1.0 - etf_total


def validate_asset(
    asset: dict[str, Any],
    existing_assets: list[dict[str, Any]] | None = None,
    *,
    exclude_symbol: str | None = None,
) -> list[str]:
    errors: list[str] = []
    symbol = str(asset.get("symbol") or "").strip().upper()
    if not symbol:
        errors.append("标的代码不能为空")
        return errors

    asset["symbol"] = symbol

    if existing_assets is not None:
        existing_symbols = {
            str(item.get("symbol") or "").strip().upper()
            for item in existing_assets
            if exclude_symbol is None
            or str(item.get("symbol") or "").strip().upper() != exclude_symbol.upper()
        }
        if symbol in existing_symbols:
            errors.append(f"标的代码 {symbol} 不能重复")

    enabled = _asset_enabled(asset)
    enabled_for_signal = bool(asset.get("enabled_for_signal", False))
    fund_code = str(asset.get("fund_code") or "").strip()

    if enabled_for_signal and not enabled:
        errors.append(f"{symbol} 参与策略信号时必须启用")
    if enabled_for_signal and not fund_code:
        errors.append(f"{symbol} 参与策略信号时必须填写基金代码")

    target_weight = asset.get("target_weight")
    max_weight = asset.get("max_weight")
    if target_weight is not None and float(target_weight) < 0:
        errors.append(f"{symbol} 的目标仓位不能小于 0")
    if (
        target_weight is not None
        and max_weight is not None
        and float(max_weight) < float(target_weight)
    ):
        errors.append(f"{symbol} 的最大仓位不能小于目标仓位")

    return errors


def validate_asset_pool(assets: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(assets, list):
        errors.append("ETF 标的池配置格式无效")
        return errors

    seen_symbols: set[str] = set()
    for index, asset in enumerate(assets, start=1):
        symbol = str(asset.get("symbol") or "").strip().upper()
        if not symbol:
            errors.append(f"第 {index} 个标的的代码不能为空")
            continue

        if symbol in seen_symbols:
            errors.append(f"标的代码 {symbol} 不能重复")
        seen_symbols.add(symbol)

        errors.extend(
            validate_asset(
                {**asset, "symbol": symbol},
                existing_assets=None,
            )
        )

    etf_weight_sum = sum_etf_target_weights(assets)
    if etf_weight_sum > 1.0 + 1e-9:
        errors.append(
            f"启用的 ETF 目标仓位合计 ({etf_weight_sum * 100:.1f}%) 不能超过 100%"
        )

    return errors
