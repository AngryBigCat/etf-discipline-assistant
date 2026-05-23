from __future__ import annotations

from typing import Any

from src.assets.queries import list_watch_only_assets
from src.db.repository import (
    get_latest_strategy_signal_date,
    get_latest_strategy_signals,
    get_portfolio_overview,
    get_trade_logs,
    upsert_daily_report,
)
from src.reports.report_formatter import (
    compose_section,
    format_action_lines,
    format_amount,
    format_percent,
    format_symbol_list,
)
from src.ui.labels import localize_action
from src.utils.date_utils import today_str

ACCOUNT_MISSING_MESSAGE = "暂无账户快照，请先在持仓录入页面录入持仓后再生成日报。"
SIGNAL_MISSING_MESSAGE = "暂无策略信号，请先运行 generate_signals.py 或在策略信号页面生成信号。"

BUY_ACTIONS = {"strong_buy", "small_buy"}
OBSERVE_ACTIONS = {"hold", "fixed_invest"}
TOTAL_ETF_POSITION_WARNING = 0.80
LOW_CASH_POSITION_WARNING = 0.10


def bucket_signals(signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buyable: list[dict[str, Any]] = []
    observe: list[dict[str, Any]] = []
    stop_buy: list[dict[str, Any]] = []
    for signal in signals:
        action = str(signal.get("action") or "")
        if action in BUY_ACTIONS:
            buyable.append(signal)
        elif action == "stop_buy":
            stop_buy.append(signal)
        elif action in OBSERVE_ACTIONS:
            observe.append(signal)
    return {
        "buyable": buyable,
        "observe": observe,
        "stop_buy": stop_buy,
    }


def summarize_day_trades(trade_rows: list[Any]) -> dict[str, Any]:
    total_count = len(trade_rows)
    buy_count = sum(1 for row in trade_rows if row["action"] == "buy")
    sell_count = sum(1 for row in trade_rows if row["action"] == "sell")
    total_buy_amount = sum(float(row["amount"] or 0) for row in trade_rows if row["action"] == "buy")
    total_sell_amount = sum(float(row["amount"] or 0) for row in trade_rows if row["action"] == "sell")
    rule_based_count = sum(1 for row in trade_rows if row["is_rule_based"])
    not_rule_based_count = total_count - rule_based_count
    chasing_count = sum(1 for row in trade_rows if row["emotion"] == "chasing")
    panic_count = sum(1 for row in trade_rows if row["emotion"] == "panic")
    temporary_count = sum(1 for row in trade_rows if row["emotion"] == "temporary")
    return {
        "total_count": total_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "total_buy_amount": total_buy_amount,
        "total_sell_amount": total_sell_amount,
        "rule_based_count": rule_based_count,
        "not_rule_based_count": not_rule_based_count,
        "chasing_count": chasing_count,
        "panic_count": panic_count,
        "temporary_count": temporary_count,
    }


def collect_daily_context(
    conn,
    settings: dict[str, Any],
    report_date: str,
) -> dict[str, Any]:
    overview = get_portfolio_overview(conn, settings)
    account_valid = bool(overview.get("account", {}).get("valid"))
    signals = [dict(row) for row in get_latest_strategy_signals(conn)]
    signal_date = get_latest_strategy_signal_date(conn)
    watch_only = list_watch_only_assets(conn)
    trade_rows = get_trade_logs(conn, start_date=report_date, end_date=report_date)
    day_trade_stats = summarize_day_trades(trade_rows)

    return {
        "report_date": report_date,
        "account_missing": not account_valid,
        "signals_missing": not signals,
        "signal_date": signal_date,
        "overview": overview,
        "signals": signals,
        "signals_bucketed": bucket_signals(signals),
        "watch_only": watch_only,
        "day_trade_stats": day_trade_stats,
        "settings": settings,
    }


def generate_daily_report_text(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("account_missing"):
        return {
            "summary": ACCOUNT_MISSING_MESSAGE,
            "risk_warning": "",
            "action_suggestion": "",
            "total_position": None,
            "cash_position": None,
        }

    overview = context["overview"]
    account = overview["account"]
    bucketed = context["signals_bucketed"]
    stats = context["day_trade_stats"]
    settings = context["settings"]
    watch_only = context["watch_only"]
    report_date = context["report_date"]

    total_position = float(account.get("total_position") or 0)
    cash_position = float(account.get("cash_position") or 0)
    current_account_value = float(account.get("current_account_value") or 0)

    buy_symbols = [s["symbol"] for s in bucketed["buyable"]]
    stop_symbols = [s["symbol"] for s in bucketed["stop_buy"]]
    observe_symbols = [s["symbol"] for s in bucketed["observe"]]
    watch_symbols = [asset["symbol"] for asset in watch_only]
    suggested_total = sum(float(s.get("suggested_amount") or 0) for s in bucketed["buyable"])

    summary_lines = [
        f"- 报告日期：{report_date}",
        f"- 账户总资产：{format_amount(current_account_value)} 元",
        f"- ETF 总仓位：{format_percent(total_position)}",
        f"- 现金仓位：{format_percent(cash_position)}",
        f"- 可考虑买入：{format_symbol_list(buy_symbols)}",
        f"- 建议买入金额合计：{format_amount(suggested_total, 0)} 元",
        f"- 观察标的：{format_symbol_list(observe_symbols)}",
        f"- 暂停买入：{format_symbol_list(stop_symbols)}",
        f"- 只观察标的：{format_symbol_list(watch_symbols)}",
        f"- 当日交易次数：{stats['total_count']} 次",
        f"- 当日买入金额：{format_amount(stats['total_buy_amount'])} 元",
        f"- 符合规则交易：{stats['rule_based_count']} 次",
        f"- 不符合规则交易：{stats['not_rule_based_count']} 次",
    ]
    if context.get("signals_missing"):
        summary_lines.append(f"- 策略信号：{SIGNAL_MISSING_MESSAGE}")

    risk_lines: list[str] = []
    for alert in overview.get("alerts", []):
        risk_lines.append(f"- {alert['message']}")

    if stats["not_rule_based_count"] > 0:
        risk_lines.append(
            f"- 今日存在不符合规则的交易 {stats['not_rule_based_count']} 笔，请复盘交易纪律"
        )
    if total_position > TOTAL_ETF_POSITION_WARNING:
        risk_lines.append(
            f"- 总 ETF 仓位 {format_percent(total_position)} 偏高，建议保持现金缓冲"
        )
    if cash_position < LOW_CASH_POSITION_WARNING:
        risk_lines.append(
            f"- 现金仓位 {format_percent(cash_position)} 偏低，注意保留备用资金"
        )
    for signal in bucketed["stop_buy"]:
        name = signal.get("name") or signal["symbol"]
        risk_lines.append(
            f"- {signal['symbol']} · {name}：{localize_action(signal.get('action'), settings)}"
        )

    action_lines: list[str] = []
    if bucketed["buyable"]:
        action_lines.extend(format_action_lines(bucketed["buyable"], settings))
    else:
        action_lines.append("- 今日暂无可考虑买入标的")
    if bucketed["stop_buy"]:
        action_lines.append(
            f"- 暂停买入标的：{format_symbol_list([s['symbol'] for s in bucketed['stop_buy']])}"
        )
    if bucketed["observe"]:
        action_lines.append(
            f"- 下个交易日观察重点：{format_symbol_list([s['symbol'] for s in bucketed['observe']])}"
        )
    if watch_symbols:
        action_lines.append(f"- 只观察标的：{format_symbol_list(watch_symbols)}")
    action_lines.append("- 最终交易需用户人工确认，系统不构成投资建议")

    return {
        "summary": compose_section("今日账户概况", summary_lines[:4])
        + "\n\n"
        + compose_section("今日策略信号", summary_lines[4:10])
        + "\n\n"
        + compose_section("今日交易纪律", summary_lines[10:]),
        "risk_warning": compose_section("风险提示", risk_lines),
        "action_suggestion": compose_section("操作建议", action_lines),
        "total_position": total_position,
        "cash_position": cash_position,
    }


def save_daily_report(conn, report_date: str, report: dict[str, Any]) -> None:
    upsert_daily_report(
        conn,
        {
            "report_date": report_date,
            "total_position": report.get("total_position"),
            "cash_position": report.get("cash_position"),
            "summary": report.get("summary") or "",
            "risk_warning": report.get("risk_warning") or "",
            "action_suggestion": report.get("action_suggestion") or "",
        },
    )


def build_and_save_daily_report(
    conn,
    settings: dict[str, Any],
    report_date: str | None = None,
) -> tuple[dict[str, Any], bool, str]:
    target_date = report_date or today_str()
    context = collect_daily_context(conn, settings, target_date)
    report = generate_daily_report_text(context)

    if context.get("account_missing"):
        return report, False, ACCOUNT_MISSING_MESSAGE

    save_daily_report(conn, target_date, report)
    return report, True, f"日报已生成：{target_date}"
