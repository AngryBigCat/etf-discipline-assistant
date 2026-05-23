from __future__ import annotations

import copy
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import (
    clear_settings_cache,
    get_config_path,
    get_llm_settings,
    get_project_root,
    load_settings,
)


class ConfigValidationError(ValueError):
    """Raised when editable config fails validation before save."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def get_backup_dir() -> Path:
    return get_project_root() / "backups" / "config"


def backup_config_file(*, config_path: Path | None = None) -> str:
    source = config_path or get_config_path()
    if not source.exists():
        raise FileNotFoundError(f"配置文件不存在: {source}")

    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"config_{timestamp}.yaml"
    shutil.copy2(source, backup_path)
    return str(backup_path)


def load_editable_config(*, config_path: Path | None = None) -> dict[str, Any]:
    if config_path is None:
        return copy.deepcopy(load_settings())

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return copy.deepcopy(data) if data else {}


def _cash_buffer_ratio(portfolio: dict[str, Any]) -> float | None:
    if "cash_buffer_ratio" in portfolio:
        return float(portfolio["cash_buffer_ratio"])
    if "min_cash_position" in portfolio:
        return float(portfolio["min_cash_position"])
    return None


def _normalize_ratio(value: float) -> float:
    if value > 1:
        return value / 100.0
    return value


def sum_etf_target_weights(assets: list[dict[str, Any]]) -> float:
    total = 0.0
    for asset in assets:
        if asset.get("symbol") == "CASH":
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


def validate_editable_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    portfolio = config.get("portfolio") or {}

    total_plan_amount = portfolio.get("total_plan_amount")
    if total_plan_amount is None or float(total_plan_amount) <= 0:
        errors.append("计划总投入必须大于 0")

    if "default_buy_amount" in portfolio:
        default_buy_amount = float(portfolio["default_buy_amount"])
        if default_buy_amount < 0:
            errors.append("默认买入金额不能小于 0")
        elif total_plan_amount is not None and default_buy_amount > float(total_plan_amount):
            errors.append("默认买入金额不能大于计划总投入")

    cash_buffer = _cash_buffer_ratio(portfolio)
    if cash_buffer is not None:
        ratio = _normalize_ratio(float(cash_buffer))
        if ratio < 0 or ratio > 1:
            errors.append("现金缓冲比例必须在 0% 到 100% 之间")

    assets = config.get("assets") or []
    if not isinstance(assets, list):
        errors.append("ETF 标的池配置格式无效")
        return errors

    etf_weight_sum = sum_etf_target_weights(assets)
    for index, asset in enumerate(assets, start=1):
        symbol = str(asset.get("symbol") or "").strip()
        if not symbol:
            errors.append(f"第 {index} 个标的的代码不能为空")
            continue

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

    if etf_weight_sum > 1.0 + 1e-9:
        errors.append(
            f"所有 ETF 目标仓位合计 ({etf_weight_sum * 100:.1f}%) 不能超过 100%"
        )

    return errors


def save_editable_config(
    config: dict[str, Any],
    *,
    config_path: Path | None = None,
) -> str:
    errors = validate_editable_config(config)
    if errors:
        raise ConfigValidationError(errors)

    target_path = config_path or get_config_path()
    backup_path = backup_config_file(config_path=target_path)

    temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            yaml.dump(
                config,
                handle,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        temp_path.replace(target_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise

    if config_path is None:
        clear_settings_cache()
    return backup_path


def format_ai_settings_display() -> dict[str, str]:
    llm = get_llm_settings()
    return {
        "provider": llm.get("provider") or "mock",
        "model": llm.get("model") or "未设置",
        "api_key_status": "已配置" if llm.get("api_key") else "未配置",
        "daily_review_enabled": "已启用",
        "weekly_review_enabled": "已启用",
    }
