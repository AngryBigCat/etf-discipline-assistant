from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.db.repository import (
    get_account_snapshot,
    get_ai_review_by_daily_date,
    get_ai_review_by_week,
    get_daily_report_by_date,
    get_holding_snapshots,
    get_latest_daily_prices,
    get_latest_indicators,
    get_latest_strategy_signal_date,
    get_latest_strategy_signals,
    get_portfolio_overview,
    get_trade_logs,
    get_weekly_report,
)
from src.portfolio.rebalance import RISK_STATUS_EXCEED_MAX, RISK_STATUS_OVERWEIGHT, SIGNAL_STATUS_WATCH_ONLY
from src.tasks.models import TaskItem
from src.tasks.rules import (
    TASK_CATEGORY_DAILY,
    TASK_CATEGORY_DATA,
    TASK_CATEGORY_REVIEW,
    TASK_CATEGORY_RISK,
    TASK_CATEGORY_WEEKLY,
    TASK_CHECK_INDICATORS,
    TASK_CHECK_PORTFOLIO_DEVIATION,
    TASK_CHECK_PORTFOLIO_RISK,
    TASK_EXCEED_MAX_POSITION,
    TASK_GENERATE_AI_DAILY_REVIEW,
    TASK_GENERATE_AI_WEEKLY_REVIEW,
    TASK_GENERATE_DAILY_REPORT,
    TASK_GENERATE_STRATEGY_SIGNAL,
    TASK_GENERATE_WEEKLY_REPORT,
    TASK_INPUT_HOLDING_SNAPSHOT,
    TASK_MISSING_HOLDING_SNAPSHOT,
    TASK_NON_RULE_BASED_TRADE,
    TASK_OVERWEIGHT_POSITION,
    TASK_PRIORITY_HIGH,
    TASK_PRIORITY_LOW,
    TASK_PRIORITY_NORMAL,
    TASK_RECORD_TRADE_LOG,
    TASK_REVIEW_STRATEGY_SIGNAL,
    TASK_REVIEW_WEEKLY_DISCIPLINE,
    TASK_STALE_MARKET_DATA,
    TASK_UNREVIEWED_SIGNAL,
    TASK_UPDATE_MARKET_DATA,
    TASK_WATCH_ONLY_OVERWEIGHT,
)


def _rolling_week(task_date: str) -> tuple[str, str]:
    end_dt = datetime.strptime(task_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=6)
    return start_dt.strftime("%Y-%m-%d"), task_date


def _is_weekly_task_day(task_date: str) -> bool:
    return datetime.strptime(task_date, "%Y-%m-%d").weekday() in {4, 5, 6}


def _latest_market_date(conn, *, enabled_only: bool = True) -> str | None:
    prices_df = get_latest_daily_prices(conn, enabled_only=enabled_only)
    if prices_df.empty:
        return None
    return str(prices_df["trade_date"].max())


def _latest_indicator_date(conn, *, enabled_only: bool = True) -> str | None:
    indicators_df = get_latest_indicators(conn, enabled_only=enabled_only)
    if indicators_df.empty:
        return None
    return str(indicators_df["trade_date"].max())


def _has_snapshot_for_date(conn, task_date: str) -> bool:
    account = get_account_snapshot(conn, task_date)
    if account is None:
        return False
    holdings = get_holding_snapshots(conn, task_date)
    return len(holdings) > 0


def generate_daily_tasks(conn, settings: dict[str, Any], task_date: str) -> list[TaskItem]:
    tasks: list[TaskItem] = []
    latest_price_date = _latest_market_date(conn)
    latest_indicator_date = _latest_indicator_date(conn)

    if latest_price_date is None or latest_price_date < task_date:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DATA,
                task_type=TASK_UPDATE_MARKET_DATA,
                title="更新行情数据",
                description=(
                    f"当前最新行情日期为 {latest_price_date or '无'}，"
                    f"早于任务日期 {task_date}。请运行 daily_update 或补全行情。"
                ),
                priority=TASK_PRIORITY_NORMAL,
                source_type="daily_price",
                source_key="",
                due_date=task_date,
            )
        )

    if (
        latest_price_date is not None
        and latest_indicator_date is not None
        and latest_indicator_date < latest_price_date
    ):
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DATA,
                task_type=TASK_CHECK_INDICATORS,
                title="计算技术指标",
                description=(
                    f"指标最新日期 {latest_indicator_date} 早于行情最新日期 {latest_price_date}，"
                    "请更新指标数据。"
                ),
                priority=TASK_PRIORITY_NORMAL,
                source_type="daily_price",
                source_key="indicators",
                due_date=task_date,
            )
        )

    if not _has_snapshot_for_date(conn, task_date):
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DAILY,
                task_type=TASK_INPUT_HOLDING_SNAPSHOT,
                title="录入持仓快照",
                description=f"{task_date} 尚未录入账户或持仓快照，请在「持仓录入」页面补充。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="account_snapshot",
                source_key=task_date,
                due_date=task_date,
            )
        )

    overview = get_portfolio_overview(conn, settings)
    alerts = overview.get("alerts") or []
    if alerts:
        has_exceed_max = any(
            position.get("risk_status") == RISK_STATUS_EXCEED_MAX
            for position in overview.get("positions") or []
        )
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DAILY,
                task_type=TASK_CHECK_PORTFOLIO_RISK,
                title="检查仓位风险",
                description="；".join(alert["message"] for alert in alerts[:5]),
                priority=TASK_PRIORITY_HIGH if has_exceed_max else TASK_PRIORITY_NORMAL,
                source_type="portfolio",
                source_key="overview",
                due_date=task_date,
            )
        )

    latest_signal_date = get_latest_strategy_signal_date(conn)
    if latest_price_date and (latest_signal_date is None or latest_signal_date < latest_price_date):
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DAILY,
                task_type=TASK_GENERATE_STRATEGY_SIGNAL,
                title="生成策略信号",
                description=(
                    f"最新信号日期为 {latest_signal_date or '无'}，"
                    f"行情已更新至 {latest_price_date}，请生成今日策略信号。"
                ),
                priority=TASK_PRIORITY_NORMAL,
                source_type="strategy_signal",
                source_key="latest",
                due_date=task_date,
            )
        )

    unreviewed_signals = [
        dict(row)
        for row in get_latest_strategy_signals(conn)
        if row["review_status"] == "generated"
    ]
    if unreviewed_signals:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_REVIEW,
                task_type=TASK_REVIEW_STRATEGY_SIGNAL,
                title="审核策略信号",
                description=f"当前有 {len(unreviewed_signals)} 条待审核策略信号，请在「策略信号」页面确认。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="strategy_signal",
                source_key="generated",
                due_date=task_date,
            )
        )

    actionable_signals = [
        signal
        for signal in unreviewed_signals
        if signal.get("action") in {"buy", "hold", "adjust"}
    ]
    trade_rows = get_trade_logs(conn, start_date=task_date, end_date=task_date)
    if actionable_signals and not trade_rows:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DAILY,
                task_type=TASK_RECORD_TRADE_LOG,
                title="如有实际交易请记录交易日志",
                description="今日有可关注的策略信号。若您已实际交易，请在「交易日志」页面记录；未交易可忽略本提醒。",
                priority=TASK_PRIORITY_LOW,
                source_type="trade_log",
                source_key=task_date,
                due_date=task_date,
            )
        )

    if get_daily_report_by_date(conn, task_date) is None:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_DAILY,
                task_type=TASK_GENERATE_DAILY_REPORT,
                title="生成今日日报",
                description=f"{task_date} 的日报尚未生成，可在「报告复盘」页面生成。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="daily_report",
                source_key=task_date,
                due_date=task_date,
            )
        )
    elif get_ai_review_by_daily_date(conn, task_date) is None:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_REVIEW,
                task_type=TASK_GENERATE_AI_DAILY_REVIEW,
                title="生成 AI 日复盘",
                description=f"{task_date} 已有日报但尚未生成 AI 日复盘，可在「AI复盘」页面生成。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="ai_review",
                source_key=task_date,
                due_date=task_date,
            )
        )

    return tasks


def generate_weekly_tasks(conn, settings: dict[str, Any], task_date: str) -> list[TaskItem]:
    if not _is_weekly_task_day(task_date):
        return []

    tasks: list[TaskItem] = []
    week_start, week_end = _rolling_week(task_date)

    if get_weekly_report(conn, week_start, week_end) is None:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_WEEKLY,
                task_type=TASK_GENERATE_WEEKLY_REPORT,
                title="生成本周周报",
                description=f"本周（{week_start} ~ {week_end}）周报尚未生成，可在「报告复盘」页面生成。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="weekly_report",
                source_key=f"{week_start}_{week_end}",
                due_date=week_end,
            )
        )
    elif get_ai_review_by_week(conn, week_start, week_end) is None:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_WEEKLY,
                task_type=TASK_GENERATE_AI_WEEKLY_REVIEW,
                title="生成 AI 周复盘",
                description=f"本周（{week_start} ~ {week_end}）已有周报但尚未生成 AI 周复盘。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="ai_review",
                source_key=f"{week_start}_{week_end}",
                due_date=week_end,
            )
        )

    trade_rows = get_trade_logs(conn, start_date=week_start, end_date=week_end)
    non_rule_based = [row for row in trade_rows if not row["is_rule_based"]]
    if non_rule_based:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_WEEKLY,
                task_type=TASK_REVIEW_WEEKLY_DISCIPLINE,
                title="复盘本周交易纪律",
                description=f"本周有 {len(non_rule_based)} 笔不符合规则的交易，请回顾原因并改进执行纪律。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="trade_log",
                source_key=f"{week_start}_{week_end}",
                due_date=week_end,
            )
        )

    overview = get_portfolio_overview(conn, settings)
    deviated_positions = [
        position
        for position in overview.get("positions") or []
        if abs(float(position.get("deviation") or 0)) >= 0.03
    ]
    if deviated_positions and overview.get("account", {}).get("valid"):
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_WEEKLY,
                task_type=TASK_CHECK_PORTFOLIO_DEVIATION,
                title="检查组合权重偏离",
                description=(
                    "以下标的当前权重与目标权重偏离较大："
                    + "、".join(position["symbol"] for position in deviated_positions[:5])
                ),
                priority=TASK_PRIORITY_NORMAL,
                source_type="portfolio",
                source_key="deviation",
                due_date=week_end,
            )
        )

    return tasks


def generate_risk_tasks(conn, settings: dict[str, Any], task_date: str) -> list[TaskItem]:
    tasks: list[TaskItem] = []
    latest_price_date = _latest_market_date(conn)

    if latest_price_date is None or latest_price_date < task_date:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_RISK,
                task_type=TASK_STALE_MARKET_DATA,
                title="行情数据可能过期",
                description=(
                    f"最新行情日期为 {latest_price_date or '无'}，"
                    "可能影响策略信号与仓位判断，请尽快更新。"
                ),
                priority=TASK_PRIORITY_NORMAL,
                source_type="daily_price",
                source_key="stale",
                due_date=task_date,
            )
        )

    if not _has_snapshot_for_date(conn, task_date):
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_RISK,
                task_type=TASK_MISSING_HOLDING_SNAPSHOT,
                title="持仓快照缺失",
                description=f"{task_date} 缺少账户或持仓快照，仓位风险判断可能不准确。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="holding_snapshot",
                source_key=task_date,
                due_date=task_date,
            )
        )

    overview = get_portfolio_overview(conn, settings)
    for position in overview.get("positions") or []:
        symbol = position["symbol"]
        risk_status = position.get("risk_status")
        signal_status = position.get("signal_status")

        if risk_status == RISK_STATUS_EXCEED_MAX:
            tasks.append(
                TaskItem(
                    task_date=task_date,
                    category=TASK_CATEGORY_RISK,
                    task_type=TASK_EXCEED_MAX_POSITION,
                    title=f"{symbol} 仓位超过上限",
                    description=(
                        f"{position.get('name') or symbol} 当前仓位 "
                        f"{position.get('weight', 0) * 100:.1f}%，已超过最大允许仓位。"
                    ),
                    priority=TASK_PRIORITY_HIGH,
                    source_type="portfolio",
                    source_key=symbol,
                    due_date=task_date,
                )
            )
        elif risk_status == RISK_STATUS_OVERWEIGHT:
            if signal_status == SIGNAL_STATUS_WATCH_ONLY:
                tasks.append(
                    TaskItem(
                        task_date=task_date,
                        category=TASK_CATEGORY_RISK,
                        task_type=TASK_WATCH_ONLY_OVERWEIGHT,
                        title=f"{symbol}（只观察）仓位偏高",
                        description=(
                            f"{position.get('name') or symbol} 为只观察标的，"
                            f"当前仓位 {position.get('weight', 0) * 100:.1f}% 高于目标，请关注风险。"
                        ),
                        priority=TASK_PRIORITY_HIGH,
                        source_type="portfolio",
                        source_key=symbol,
                        due_date=task_date,
                    )
                )
            else:
                tasks.append(
                    TaskItem(
                        task_date=task_date,
                        category=TASK_CATEGORY_RISK,
                        task_type=TASK_OVERWEIGHT_POSITION,
                        title=f"{symbol} 仓位偏高",
                        description=(
                            f"{position.get('name') or symbol} 当前仓位 "
                            f"{position.get('weight', 0) * 100:.1f}%，高于目标仓位。"
                        ),
                        priority=TASK_PRIORITY_NORMAL,
                        source_type="portfolio",
                        source_key=symbol,
                        due_date=task_date,
                    )
                )

    unreviewed_signals = [
        dict(row)
        for row in get_latest_strategy_signals(conn)
        if row["review_status"] == "generated"
    ]
    for signal in unreviewed_signals:
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_RISK,
                task_type=TASK_UNREVIEWED_SIGNAL,
                title=f"待审核信号：{signal['symbol']}",
                description=f"{signal['symbol']} 的策略信号尚未审核，请在「策略信号」页面处理。",
                priority=TASK_PRIORITY_NORMAL,
                source_type="strategy_signal",
                source_key=str(signal["id"]),
                due_date=task_date,
            )
        )

    week_start, week_end = _rolling_week(task_date)
    trade_rows = get_trade_logs(conn, start_date=week_start, end_date=week_end)
    for trade in trade_rows:
        if trade["is_rule_based"]:
            continue
        tasks.append(
            TaskItem(
                task_date=task_date,
                category=TASK_CATEGORY_RISK,
                task_type=TASK_NON_RULE_BASED_TRADE,
                title="存在不符合规则的交易",
                description=(
                    f"{trade['trade_date']} {trade['symbol']} 有一笔不符合规则的交易，"
                    "请回顾执行过程并改进纪律。"
                ),
                priority=TASK_PRIORITY_HIGH,
                source_type="trade_log",
                source_key=str(trade["id"]),
                due_date=task_date,
            )
        )

    return tasks


def generate_all_tasks(conn, settings: dict[str, Any], task_date: str) -> list[TaskItem]:
    tasks: list[TaskItem] = []
    tasks.extend(generate_daily_tasks(conn, settings, task_date))
    tasks.extend(generate_weekly_tasks(conn, settings, task_date))
    tasks.extend(generate_risk_tasks(conn, settings, task_date))

    deduped: dict[tuple[str, str | None, str], TaskItem] = {}
    for task in tasks:
        deduped[task.unique_key] = task
    return list(deduped.values())
