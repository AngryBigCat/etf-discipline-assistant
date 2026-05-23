from __future__ import annotations

from typing import Any

from src.assets.queries import list_watch_only_assets
from src.db.repository import (
    get_latest_indicators,
    get_latest_strategy_signals,
    get_portfolio_overview,
    upsert_weekly_report,
)
from src.reports.daily_report import (
    ACCOUNT_MISSING_MESSAGE,
    TOTAL_ETF_POSITION_WARNING,
    LOW_CASH_POSITION_WARNING,
    bucket_signals,
)
from src.reports.report_formatter import (
    compose_section,
    format_action_lines,
    format_amount,
    format_percent,
    format_symbol_list,
)
from src.trading.trade_log import get_trade_summary

HIGH_VOLATILITY_THRESHOLD = 0.03


def collect_weekly_context(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
) -> dict[str, Any]:
    overview = get_portfolio_overview(conn, settings)
    account_valid = bool(overview.get("account", {}).get("valid"))
    signals = [dict(row) for row in get_latest_strategy_signals(conn)]
    trade_summary = get_trade_summary(conn, start_date=week_start, end_date=week_end)
    watch_only = list_watch_only_assets(conn)
    indicators_df = get_latest_indicators(conn, enabled_only=True)
    high_volatility_symbols: list[str] = []
    if not indicators_df.empty:
        for _, row in indicators_df.iterrows():
            volatility = row.get("volatility_20d")
            if volatility is not None and float(volatility) >= HIGH_VOLATILITY_THRESHOLD:
                high_volatility_symbols.append(str(row["symbol"]))

    return {
        "week_start": week_start,
        "week_end": week_end,
        "account_missing": not account_valid,
        "overview": overview,
        "signals": signals,
        "signals_bucketed": bucket_signals(signals),
        "trade_summary": trade_summary,
        "watch_only": watch_only,
        "high_volatility_symbols": high_volatility_symbols,
        "settings": settings,
    }


def generate_weekly_report_text(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("account_missing"):
        return {
            "summary": ACCOUNT_MISSING_MESSAGE,
            "discipline_summary": "",
            "risk_summary": "",
            "action_suggestion": "",
        }

    overview = context["overview"]
    account = overview["account"]
    bucketed = context["signals_bucketed"]
    stats = context["trade_summary"]
    settings = context["settings"]
    watch_only = context["watch_only"]
    week_start = context["week_start"]
    week_end = context["week_end"]

    total_position = float(account.get("total_position") or 0)
    cash_position = float(account.get("cash_position") or 0)
    current_account_value = float(account.get("current_account_value") or 0)

    summary_lines = [
        f"- 统计区间：{week_start} ~ {week_end}",
        f"- 本周交易次数：{stats['total_count']} 次",
        f"- 买入次数：{stats['buy_count']} 次",
        f"- 卖出次数：{stats['sell_count']} 次",
        f"- 总买入金额：{format_amount(stats['total_buy_amount'])} 元",
        f"- 总卖出金额：{format_amount(stats['total_sell_amount'])} 元",
        f"- 当前账户总资产：{format_amount(current_account_value)} 元",
        f"- ETF 总仓位：{format_percent(total_position)}",
        f"- 现金仓位：{format_percent(cash_position)}",
    ]

    discipline_lines = [
        f"- 符合规则次数：{stats['rule_based_count']} 次",
        f"- 不符合规则次数：{stats['not_rule_based_count']} 次",
        f"- 纪律执行率：{format_percent(stats['compliance_rate'])}",
        f"- 追涨次数：{stats['chasing_count']} 次",
        f"- 恐慌次数：{stats['panic_count']} 次",
        f"- 临时决策次数：{stats['temporary_count']} 次",
    ]
    if stats["not_rule_based_count"] > 0:
        discipline_lines.append(
            f"- 本周存在 {stats['not_rule_based_count']} 笔不符合规则交易，建议复盘原因"
        )

    risk_lines: list[str] = []
    for alert in overview.get("alerts", []):
        risk_lines.append(f"- {alert['message']}")

    if total_position > TOTAL_ETF_POSITION_WARNING:
        risk_lines.append(
            f"- 总 ETF 仓位 {format_percent(total_position)} 偏高，注意控制总仓位"
        )
    if cash_position < LOW_CASH_POSITION_WARNING:
        risk_lines.append(
            f"- 现金仓位 {format_percent(cash_position)} 偏低，注意保留备用资金"
        )

    high_vol_symbols = context.get("high_volatility_symbols") or []
    if high_vol_symbols:
        risk_lines.append(f"- 高波动标的：{format_symbol_list(high_vol_symbols)}")

    watch_symbols = [asset["symbol"] for asset in watch_only]
    if watch_symbols:
        risk_lines.append(f"- 只观察标的：{format_symbol_list(watch_symbols)}，不参与策略信号但仍需关注风控")

    action_lines: list[str] = []
    if bucketed["buyable"]:
        action_lines.append("- 下周优先观察标的：")
        action_lines.extend(format_action_lines(bucketed["buyable"], settings))
    if bucketed["stop_buy"]:
        action_lines.append(
            f"- 下周暂停/谨慎标的：{format_symbol_list([s['symbol'] for s in bucketed['stop_buy']])}"
        )
    if bucketed["observe"]:
        action_lines.append(
            f"- 下周继续观察：{format_symbol_list([s['symbol'] for s in bucketed['observe']])}"
        )
    action_lines.append("- 仓位纪律提醒：优先补齐低于目标仓位的核心标的，避免追涨与临时决策")
    action_lines.append("- 最终交易需用户人工确认，系统不构成投资建议")

    return {
        "summary": compose_section("本周交易概况", summary_lines[:6])
        + "\n\n"
        + compose_section("当前仓位概况", summary_lines[6:]),
        "discipline_summary": compose_section("纪律统计", discipline_lines),
        "risk_summary": compose_section("风险摘要", risk_lines),
        "action_suggestion": compose_section("下周建议", action_lines),
    }


def save_weekly_report(
    conn,
    week_start: str,
    week_end: str,
    report: dict[str, Any],
) -> None:
    upsert_weekly_report(
        conn,
        {
            "week_start": week_start,
            "week_end": week_end,
            "summary": report.get("summary") or "",
            "discipline_summary": report.get("discipline_summary") or "",
            "risk_summary": report.get("risk_summary") or "",
            "action_suggestion": report.get("action_suggestion") or "",
        },
    )


def build_and_save_weekly_report(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
) -> tuple[dict[str, Any], bool, str]:
    context = collect_weekly_context(conn, settings, week_start, week_end)
    report = generate_weekly_report_text(context)

    if context.get("account_missing"):
        return report, False, ACCOUNT_MISSING_MESSAGE

    save_weekly_report(conn, week_start, week_end, report)
    return report, True, f"周报已生成：{week_start} ~ {week_end}"
