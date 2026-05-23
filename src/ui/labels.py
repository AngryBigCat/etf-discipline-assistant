from __future__ import annotations

import pandas as pd

FIELD_LABELS = {
    "symbol": "标的代码",
    "name": "标的名称",
    "fund_code": "基金代码",
    "exchange": "交易所",
    "role": "资产角色",
    "enabled_for_signal": "是否参与策略信号",
    "trade_date": "交易日期",
    "close": "收盘价",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "volume": "成交量",
    "amount": "成交额",
    "ma20": "20日均线",
    "ma60": "60日均线",
    "ma120": "120日均线",
    "ma250": "250日均线",
    "drawdown_used": "当前回撤",
    "drawdown_window": "回撤窗口",
    "volatility_20d": "20日波动率",
    "return_5d": "近5日涨跌幅",
    "return_10d": "近10日涨跌幅",
    "return_20d": "近20日涨跌幅",
    "confidence_level": "数据置信度",
    "market_value": "持仓市值",
    "cost": "持仓成本",
    "profit_loss": "盈亏金额",
    "profit_loss_rate": "盈亏比例",
    "weight": "当前仓位",
    "target_weight": "目标仓位",
    "max_weight": "最大仓位",
    "max_allowed_value": "最大允许市值",
    "deviation": "仓位偏离",
    "status": "仓位状态",
    "quantity": "持仓数量",
    "latest_price": "最新价",
    "signal_date": "信号日期",
    "final_score": "纪律分数",
    "trend_score": "趋势分",
    "drawdown_score": "回撤分",
    "anti_chase_score": "反追高分",
    "position_score": "仓位分",
    "special_score": "特殊规则分",
    "action": "操作建议",
    "suggested_amount": "建议金额",
    "review_status": "审核状态",
    "reason": "原因说明",
    "signal_id": "关联信号",
    "deviation_amount": "偏离金额",
    "execution_status": "执行状态",
    "emotion": "情绪状态",
    "price": "交易价格",
    "note": "备注",
    "is_rule_based": "是否符合规则",
    "report_date": "报告日期",
    "week_start": "周开始",
    "week_end": "周结束",
    "summary": "概况",
    "risk_warning": "风险提示",
    "discipline_summary": "纪律统计",
    "behavior_findings": "行为发现",
    "risk_summary": "风险摘要",
    "action_suggestion": "操作建议",
    "total_position": "ETF 总仓位",
    "cash_position": "现金仓位",
    "preview": "摘要预览",
    "review_type": "复盘类型",
    "target_date": "复盘日期",
    "output_text": "原始输出",
    "status": "状态",
    "provider": "模型来源",
    "model": "模型",
    "run_name": "回测名称",
    "strategy_name": "策略名称",
    "initial_cash": "初始资金",
    "fixed_amount": "每期金额",
    "frequency": "定投频率",
    "final_value": "期末资产",
    "total_invested": "累计投入",
    "position_value": "持仓市值",
    "total_return": "总收益率",
    "annualized_return": "年化收益率",
    "max_drawdown": "最大回撤",
    "trade_count": "交易次数",
    "final_quantity": "期末数量",
    "average_cost": "平均成本",
    "quantity": "买入数量",
    "price": "成交价格",
    "amount": "买入金额",
    "reason": "原因说明",
    "total_value": "总资产",
    "drawdown": "回撤",
    "cash_value": "剩余现金",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "requested_start_date": "请求开始日期",
    "requested_end_date": "请求结束日期",
    "actual_start_date": "实际开始日期",
    "actual_end_date": "实际结束日期",
    "trading_days": "交易日数量",
}

ROLE_LABELS = {
    "core": "核心仓",
    "satellite": "卫星仓",
    "core_reference": "核心参考",
    "defensive": "防守仓",
    "overseas": "海外配置",
    "cash": "现金",
}

STATUS_LABELS = {
    "underweight": "低于目标仓位",
    "normal": "正常",
    "overweight": "高于目标",
    "exceed_max": "超过上限",
    "watch_only": "只观察",
}

CONFIDENCE_LABELS = {
    "normal": "正常",
    "low": "数据不足",
}

BOOLEAN_LABELS = {
    True: "是",
    False: "否",
    1: "是",
    0: "否",
}

ACTION_LABELS = {
    "strong_buy": "可正常买入",
    "small_buy": "可小额买入",
    "fixed_invest": "仅按定投计划",
    "hold": "观察，不主动买入",
    "stop_buy": "暂停买入",
}

REVIEW_STATUS_LABELS = {
    "generated": "系统生成",
    "reviewed": "已查看",
    "ignored": "已忽略",
    "executed": "已执行",
}

TRADE_ACTION_LABELS = {
    "buy": "买入",
    "sell": "卖出",
    "hold": "观察",
    "ignore": "忽略",
    "adjust": "调整",
}

EMOTION_LABELS = {
    "calm": "冷静",
    "planned": "计划内",
    "chasing": "追涨",
    "panic": "恐慌",
    "dip_buying": "补跌",
    "temporary": "临时决策",
    "other": "其他",
}

EXECUTION_STATUS_LABELS = {
    "recorded": "已记录",
    "matched_signal": "按信号执行",
    "deviated": "偏离信号",
    "manual": "手动记录",
    "ignored": "忽略信号",
}

REVIEW_TYPE_LABELS = {
    "daily": "日复盘",
    "weekly": "周复盘",
}

REVIEW_STATUS_LABELS_AI = {
    "success": "成功",
    "blocked": "已屏蔽",
    "failed": "失败",
}

BACKTEST_STRATEGY_LABELS = {
    "baseline_dca": "普通定投",
    "ma_filter_dca": "均线过滤定投",
    "drawdown_boost": "回撤加仓定投",
}

BACKTEST_FREQUENCY_LABELS = {
    "weekly": "每周",
    "monthly": "每月",
}

BACKTEST_ACTION_LABELS = {
    "buy": "买入",
}


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={col: FIELD_LABELS.get(col, col) for col in df.columns})


def localize_role(value: object) -> object:
    return ROLE_LABELS.get(value, value)


def localize_status(value: object) -> object:
    return STATUS_LABELS.get(value, value)


def localize_confidence(value: object) -> object:
    return CONFIDENCE_LABELS.get(value, value)


def localize_bool(value: object) -> object:
    return BOOLEAN_LABELS.get(value, value)


def localize_action(value: object, settings: dict | None = None) -> object:
    if settings:
        from src.strategy.rule_engine import get_action_label

        if isinstance(value, str):
            return get_action_label(value, settings)
    return ACTION_LABELS.get(value, value)


def localize_review_status(value: object) -> object:
    return REVIEW_STATUS_LABELS.get(value, value)


def localize_trade_action(value: object) -> object:
    return TRADE_ACTION_LABELS.get(value, value)


def localize_emotion(value: object) -> object:
    return EMOTION_LABELS.get(value, value)


def localize_execution_status(value: object) -> object:
    return EXECUTION_STATUS_LABELS.get(value, value)


def localize_review_type(value: object) -> object:
    return REVIEW_TYPE_LABELS.get(value, value)


def localize_ai_status(value: object) -> object:
    return REVIEW_STATUS_LABELS_AI.get(value, value)


def localize_backtest_strategy(value: object) -> object:
    return BACKTEST_STRATEGY_LABELS.get(value, value)


def localize_backtest_frequency(value: object) -> object:
    return BACKTEST_FREQUENCY_LABELS.get(value, value)


def localize_backtest_action(value: object) -> object:
    return BACKTEST_ACTION_LABELS.get(value, value)
