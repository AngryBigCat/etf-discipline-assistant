from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """你是 ETF 投资纪律复盘助手。
你只能基于用户提供的数据进行复盘。
你不能预测市场涨跌。
你不能推荐个股。
你不能要求用户买入或卖出某个标的。
你不能替用户做交易决定。
你只能分析交易纪律、仓位风险、执行偏差和行为模式。
如果数据不足，必须明确说明数据不足。
输出必须包含风险提示：本内容不构成投资建议。"""

JSON_OUTPUT_INSTRUCTION = """
请严格输出 JSON，不要包含 Markdown 代码块，字段如下：
{
  "discipline_summary": "一段中文纪律总结",
  "behavior_findings": ["行为发现1", "行为发现2"],
  "risk_summary": ["风险提醒1", "风险提醒2"],
  "action_suggestion": ["纪律建议1", "纪律建议2"],
  "final_note": "以上内容仅用于纪律复盘，不构成投资建议。"
}
"""


def _format_bucket(bucket: dict[str, list[dict[str, Any]]]) -> str:
    buyable = [s["symbol"] for s in bucket.get("buyable", [])]
    observe = [s["symbol"] for s in bucket.get("observe", [])]
    stop = [s["symbol"] for s in bucket.get("stop_buy", [])]
    return f"可考虑：{buyable or '无'}；观察：{observe or '无'}；暂停：{stop or '无'}"


def build_daily_review_prompt(context: dict[str, Any]) -> dict[str, str]:
    account = context.get("overview_account", {})
    stats = context.get("day_trade_stats", {})
    watch = [w["symbol"] for w in context.get("watch_only", [])]
    report = context.get("daily_report", {})

    user_lines = [
        f"复盘日期：{context.get('target_date')}",
        f"ETF 总仓位：{account.get('total_position', 0) * 100:.1f}%",
        f"现金仓位：{account.get('cash_position', 0) * 100:.1f}%",
        f"策略信号分组：{_format_bucket(context.get('signals_bucketed', {}))}",
        f"只观察标的：{watch or '无'}",
        f"当日交易次数：{stats.get('total_count', 0)}",
        f"当日买入次数：{stats.get('buy_count', 0)}",
        f"符合规则交易：{stats.get('rule_based_count', 0)}",
        f"不符合规则交易：{stats.get('not_rule_based_count', 0)}",
        f"追涨次数：{stats.get('chasing_count', 0)}",
        f"恐慌次数：{stats.get('panic_count', 0)}",
        f"临时决策次数：{stats.get('temporary_count', 0)}",
        f"仓位提醒：{context.get('alerts') or '无'}",
        f"日报概况摘要：{(report.get('summary') or '')[:500]}",
        f"日报风险提示摘要：{(report.get('risk_warning') or '')[:500]}",
    ]
    user_prompt = "\n".join(f"- {line}" for line in user_lines)
    user_prompt += JSON_OUTPUT_INSTRUCTION
    return {"system": SYSTEM_PROMPT, "user": user_prompt}


def build_weekly_review_prompt(context: dict[str, Any]) -> dict[str, str]:
    account = context.get("overview_account", {})
    stats = context.get("trade_summary", {})
    watch = [w["symbol"] for w in context.get("watch_only", [])]
    report = context.get("weekly_report", {})

    user_lines = [
        f"统计区间：{context.get('week_start')} ~ {context.get('week_end')}",
        f"本周交易次数：{stats.get('total_count', 0)}",
        f"买入次数：{stats.get('buy_count', 0)}",
        f"卖出次数：{stats.get('sell_count', 0)}",
        f"符合规则次数：{stats.get('rule_based_count', 0)}",
        f"不符合规则次数：{stats.get('not_rule_based_count', 0)}",
        f"纪律执行率：{stats.get('compliance_rate', 0) * 100:.1f}%",
        f"追涨次数：{stats.get('chasing_count', 0)}",
        f"恐慌次数：{stats.get('panic_count', 0)}",
        f"临时决策次数：{stats.get('temporary_count', 0)}",
        f"当前 ETF 总仓位：{account.get('total_position', 0) * 100:.1f}%",
        f"当前现金仓位：{account.get('cash_position', 0) * 100:.1f}%",
        f"策略信号分组：{_format_bucket(context.get('signals_bucketed', {}))}",
        f"只观察标的：{watch or '无'}",
        f"仓位提醒：{context.get('alerts') or '无'}",
        f"周报概况摘要：{(report.get('summary') or '')[:500]}",
        f"周报纪律统计摘要：{(report.get('discipline_summary') or '')[:500]}",
    ]
    user_prompt = "\n".join(f"- {line}" for line in user_lines)
    user_prompt += JSON_OUTPUT_INSTRUCTION
    return {"system": SYSTEM_PROMPT, "user": user_prompt}


def dumps_context_for_snapshot(context: dict[str, Any]) -> str:
    safe = {k: v for k, v in context.items() if k not in {"daily_report", "weekly_report"}}
    return json.dumps(safe, ensure_ascii=False, default=str)
