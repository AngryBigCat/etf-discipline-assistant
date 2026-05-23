from __future__ import annotations

from typing import Any

from src.ui.labels import localize_action
from src.utils.number_utils import format_number, format_pct


def format_amount(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.{digits}f}"


def format_percent(value: float | None, digits: int = 2) -> str:
    return format_pct(value, digits)


def format_symbol_list(symbols: list[str]) -> str:
    if not symbols:
        return "无"
    return "、".join(symbols)


def format_action_lines(signals: list[dict[str, Any]], settings: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for signal in signals:
        symbol = str(signal.get("symbol") or "")
        name = str(signal.get("name") or symbol)
        action = localize_action(signal.get("action"), settings)
        suggested = float(signal.get("suggested_amount") or 0)
        if suggested > 0:
            lines.append(f"- {symbol} · {name}：{action}，建议金额 {format_amount(suggested, 0)} 元")
        else:
            lines.append(f"- {symbol} · {name}：{action}")
    return lines


def compose_section(title: str, lines: list[str]) -> str:
    if not lines:
        return f"### {title}\n\n无"
    body = "\n".join(lines)
    return f"### {title}\n\n{body}"
