from __future__ import annotations

from datetime import date

import streamlit as st

from src.config.editor import (
    ConfigValidationError,
    compute_implicit_cash_target_weight,
    format_ai_settings_display,
    load_editable_config,
    save_editable_config,
    sum_etf_target_weights,
    validate_editable_config,
    validate_new_asset,
)
from src.config.sync import sync_assets_to_etf_universe
from src.db.connection import db_session
from src.ui.labels import FIELD_LABELS, ROLE_LABELS, localize_role


def _ensure_draft_config() -> dict:
    if "settings_draft_config" not in st.session_state:
        st.session_state["settings_draft_config"] = load_editable_config()
    return st.session_state["settings_draft_config"]


def _reset_draft_config() -> None:
    st.session_state["settings_draft_config"] = load_editable_config()


def _render_investment_plan(config: dict) -> None:
    st.subheader("投资计划设置")
    portfolio = config.setdefault("portfolio", {})
    app_cfg = config.setdefault("app", {})

    col1, col2 = st.columns(2)
    with col1:
        portfolio["total_plan_amount"] = st.number_input(
            FIELD_LABELS["total_plan_amount"],
            min_value=0.0,
            value=float(portfolio.get("total_plan_amount") or 0),
            step=1000.0,
            format="%.0f",
            help="用于计算建议金额与仓位提醒的总计划投入。",
        )
        if "default_buy_amount" in portfolio:
            portfolio["default_buy_amount"] = st.number_input(
                FIELD_LABELS["default_buy_amount"],
                min_value=0.0,
                value=float(portfolio.get("default_buy_amount") or 0),
                step=100.0,
                format="%.0f",
            )

    with col2:
        cash_key = "cash_buffer_ratio" if "cash_buffer_ratio" in portfolio else "min_cash_position"
        cash_ratio = float(portfolio.get(cash_key) or portfolio.get("min_cash_position") or 0)
        cash_pct = cash_ratio * 100 if cash_ratio <= 1 else cash_ratio
        cash_pct = st.number_input(
            "现金缓冲比例 (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(cash_pct),
            step=1.0,
            help="保留现金比例，用于分批补仓提醒。",
        )
        portfolio[cash_key] = cash_pct / 100.0

        currency_options = ["CNY", "USD", "HKD"]
        current_currency = str(app_cfg.get("base_currency") or "CNY")
        if current_currency not in currency_options:
            currency_options.append(current_currency)
        app_cfg["base_currency"] = st.selectbox(
            "基准货币",
            options=currency_options,
            index=currency_options.index(current_currency),
        )


def _asset_status_label(asset: dict) -> str:
    return "启用" if asset.get("enabled", True) else "停用"


def _render_add_asset_form(config: dict) -> None:
    st.markdown("#### 新增标的")
    assets = config.setdefault("assets", [])
    role_options = list(ROLE_LABELS.keys())
    default_role = "satellite" if "satellite" in role_options else role_options[0]

    with st.form("add_asset_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_symbol = st.text_input(FIELD_LABELS["symbol"], key="new_asset_symbol")
            new_name = st.text_input(FIELD_LABELS["name"], key="new_asset_name")
            new_fund_code = st.text_input(FIELD_LABELS["fund_code"], key="new_asset_fund_code")
            new_exchange = st.text_input(FIELD_LABELS["exchange"], key="new_asset_exchange")
        with col2:
            new_role = st.selectbox(
                FIELD_LABELS["role"],
                options=role_options,
                index=role_options.index(default_role),
                format_func=lambda value: str(localize_role(value)),
                key="new_asset_role",
            )
            new_enabled = st.checkbox(FIELD_LABELS["enabled"], value=True, key="new_asset_enabled")
            new_enabled_for_signal = st.checkbox(
                FIELD_LABELS["enabled_for_signal"],
                value=False,
                key="new_asset_enabled_for_signal",
            )
            new_target_pct = st.number_input(
                FIELD_LABELS["target_weight"] + " (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key="new_asset_target_weight",
            )
            new_max_pct = st.number_input(
                FIELD_LABELS["max_weight"] + " (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key="new_asset_max_weight",
            )

        submitted = st.form_submit_button("添加到配置草稿", use_container_width=True)

    if not submitted:
        return

    draft_asset = {
        "symbol": str(new_symbol or "").strip().upper(),
        "name": str(new_name or "").strip(),
        "fund_code": str(new_fund_code or "").strip(),
        "exchange": str(new_exchange or "").strip().upper(),
        "role": new_role,
        "enabled": new_enabled,
        "enabled_for_signal": new_enabled_for_signal,
        "target_weight": float(new_target_pct) / 100.0,
        "max_weight": float(new_max_pct) / 100.0,
    }

    errors = validate_new_asset(draft_asset, assets)
    if errors:
        st.error("无法添加到配置草稿：")
        for error in errors:
            st.write(f"- {error}")
        return

    if not draft_asset["fund_code"]:
        st.warning("未填写基金代码，无法自动拉取行情，需要后续补全。")

    assets.append(draft_asset)
    st.session_state["settings_draft_config"] = config
    st.success(f"已将 {draft_asset['symbol']} 添加到配置草稿，请点击「保存配置」写入 config.yaml。")


def _render_asset_pool(config: dict) -> None:
    st.subheader("ETF 标的池设置")
    st.caption(
        "可新增标的或停用已有标的。停用只会使其从新任务、信号和默认选择中隐藏，"
        "不会删除历史行情、回测、交易或持仓记录。"
    )

    _render_add_asset_form(config)

    assets = config.setdefault("assets", [])
    role_options = list(ROLE_LABELS.keys())

    for index, asset in enumerate(assets):
        symbol = str(asset.get("symbol") or f"asset_{index}")
        status_label = _asset_status_label(asset)
        title = f"{symbol} · {asset.get('name') or '未命名'} · {status_label}"
        is_enabled = bool(asset.get("enabled", True))
        with st.expander(
            title,
            expanded=False,
            key=f"asset_expander_{symbol}_{int(is_enabled)}",
        ):
            st.markdown(
                f"**{FIELD_LABELS['symbol']}**：{symbol}  "
                f"**{FIELD_LABELS['fund_code']}**：{asset.get('fund_code') or '—'}  "
                f"**{FIELD_LABELS['exchange']}**：{asset.get('exchange') or '—'}"
            )

            asset["enabled"] = st.checkbox(
                FIELD_LABELS["enabled"],
                value=bool(asset.get("enabled", True)),
                key=f"asset_enabled_{symbol}",
                help="停用标的只会隐藏未来使用，不会删除历史数据。",
            )

            asset["name"] = st.text_input(
                FIELD_LABELS["name"],
                value=str(asset.get("name") or ""),
                key=f"asset_name_{symbol}",
            )

            current_role = str(asset.get("role") or role_options[0])
            role_choices = role_options.copy()
            if current_role not in role_choices:
                role_choices = [current_role, *role_choices]
            asset["role"] = st.selectbox(
                FIELD_LABELS["role"],
                options=role_choices,
                index=role_choices.index(current_role),
                format_func=lambda value: str(localize_role(value)),
                key=f"asset_role_{symbol}",
            )

            asset["enabled_for_signal"] = st.checkbox(
                FIELD_LABELS["enabled_for_signal"],
                value=bool(asset.get("enabled_for_signal", True)),
                key=f"asset_signal_{symbol}",
            )

            col1, col2 = st.columns(2)
            with col1:
                target_pct = float(asset.get("target_weight") or 0) * 100
                asset["target_weight"] = st.number_input(
                    FIELD_LABELS["target_weight"] + " (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=target_pct,
                    step=1.0,
                    key=f"asset_target_{symbol}",
                ) / 100.0
            with col2:
                max_pct = float(asset.get("max_weight") or asset.get("target_weight") or 0) * 100
                asset["max_weight"] = st.number_input(
                    FIELD_LABELS["max_weight"] + " (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=max_pct,
                    step=1.0,
                    key=f"asset_max_{symbol}",
                ) / 100.0


def _render_position_rules(config: dict) -> None:
    st.subheader("仓位规则设置")
    st.warning(
        "目标仓位和最大仓位只用于提醒和规则判断，不会自动调仓，也不会自动修改真实持仓。"
    )

    assets = config.get("assets") or []
    etf_total = sum_etf_target_weights(assets)
    cash_target = compute_implicit_cash_target_weight(assets)

    st.metric("ETF 目标仓位合计", f"{etf_total * 100:.1f}%")
    if cash_target is not None:
        st.info(f"现金目标权重：{cash_target * 100:.1f}%")
    st.caption("可在上方 ETF 标的池中调整各标的的目标仓位与最大仓位。")


def _render_strategy_params(config: dict) -> None:
    st.subheader("策略信号参数设置")
    strategy = config.get("strategy") or {}
    actions = config.setdefault("actions", {})

    st.markdown("#### 可编辑阈值")
    col1, col2, col3 = st.columns(3)
    action_defs = [
        ("strong_buy", "强买入阈值"),
        ("small_buy", "可买入阈值"),
        ("hold", "暂停买入阈值"),
    ]
    for column, (action_key, label) in zip([col1, col2, col3], action_defs, strict=True):
        with column:
            action_cfg = actions.setdefault(action_key, {})
            action_cfg["min_score"] = st.number_input(
                label,
                min_value=0,
                max_value=100,
                value=int(action_cfg.get("min_score") or 0),
                step=1,
                key=f"action_{action_key}",
            )

    st.markdown("#### 均线参数")
    trend = strategy.setdefault("trend", {})
    ma_cols = st.columns(4)
    ma_fields = [
        ("ma_short", "短期均线"),
        ("ma_mid", "中期均线"),
        ("ma_long", "长期均线"),
        ("ma_year", "年线"),
    ]
    for column, (field, label) in zip(ma_cols, ma_fields, strict=True):
        with column:
            trend[field] = st.number_input(
                label,
                min_value=1,
                max_value=500,
                value=int(trend.get(field) or 1),
                step=1,
                key=f"ma_{field}",
            )

    st.markdown("#### 回撤窗口（只读）")
    drawdown = strategy.get("drawdown") or {}
    if drawdown:
        drawdown_rows = [
            {"参数": "小额买入回撤阈值", "数值": drawdown.get("small_buy_threshold")},
            {"参数": "正常买入回撤阈值", "数值": drawdown.get("normal_buy_threshold")},
            {"参数": "大额买入回撤阈值", "数值": drawdown.get("large_buy_threshold")},
            {"参数": "极端回撤阈值", "数值": drawdown.get("extreme_threshold")},
        ]
        st.table(drawdown_rows)
    else:
        st.info("当前配置未定义回撤窗口参数。")

    st.markdown("#### 其他策略参数（只读）")
    anti_chase = strategy.get("anti_chase") or {}
    score_cfg = strategy.get("score") or {}
    readonly_rows = [
        {"参数": "5日涨幅预警", "数值": anti_chase.get("five_day_gain_warning")},
        {"参数": "10日涨幅预警", "数值": anti_chase.get("ten_day_gain_warning")},
        {"参数": "基础分数", "数值": score_cfg.get("base_score")},
        {"参数": "最低分数", "数值": score_cfg.get("min_score")},
        {"参数": "最高分数", "数值": score_cfg.get("max_score")},
    ]
    st.table(readonly_rows)


def _render_ai_settings() -> None:
    st.subheader("AI 复盘设置")
    display = format_ai_settings_display()

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("AI 提供商", value=display["provider"], disabled=True)
        st.text_input("模型", value=display["model"], disabled=True)
    with col2:
        st.text_input("API Key 状态", value=display["api_key_status"], disabled=True)
        st.text_input("日复盘", value=display["daily_review_enabled"], disabled=True)
        st.text_input("周复盘", value=display["weekly_review_enabled"], disabled=True)

    st.info(
        "API Key 请通过 `.env` 文件配置（如 `LLM_API_KEY`）。"
        "本页面不会展示或保存 API Key 明文，也不会写入数据库。"
    )


def main() -> None:
    st.title("系统设置")
    st.caption(
        "系统设置用于维护投资纪律参数，不构成投资建议；"
        "修改配置不会自动交易，也不会自动修改持仓。"
    )

    config = _ensure_draft_config()

    _render_investment_plan(config)
    st.divider()
    _render_asset_pool(config)
    st.divider()
    _render_position_rules(config)
    st.divider()
    _render_strategy_params(config)
    st.divider()
    _render_ai_settings()
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("校验配置", use_container_width=True):
            errors = validate_editable_config(config)
            if errors:
                st.error("配置校验未通过：")
                for error in errors:
                    st.write(f"- {error}")
            else:
                st.success("配置校验通过，可以保存。")

    with col2:
        if st.button("保存配置", type="primary", use_container_width=True):
            errors = validate_editable_config(config)
            if errors:
                st.error("配置校验未通过，未保存：")
                for error in errors:
                    st.write(f"- {error}")
            else:
                try:
                    symbols_before_save = {
                        str(asset.get("symbol") or "").strip().upper()
                        for asset in load_editable_config().get("assets", [])
                    }
                    backup_path = save_editable_config(config)
                    with db_session() as conn:
                        sync_result = sync_assets_to_etf_universe(conn, config)

                    st.success("配置已保存。")
                    st.info(f"备份文件：{backup_path}")
                    st.success(f"已同步 {sync_result['synced_count']} 个标的到标的池。")

                    end_date = date.today().isoformat()
                    for symbol in sync_result.get("new_symbols_with_fund_code", []):
                        st.warning(
                            f"新标的 {symbol} 已加入配置，但尚未补全历史行情。请运行：\n"
                            f"python scripts/backfill_prices.py --symbol {symbol} "
                            f"--start 2021-01-01 --end {end_date}"
                        )
                    new_without_fund = [
                        symbol
                        for symbol in sync_result.get("new_symbols", [])
                        if symbol not in sync_result.get("new_symbols_with_fund_code", [])
                        and symbol not in symbols_before_save
                    ]
                    if new_without_fund:
                        st.info(
                            "部分新标的未填写基金代码，无法自动拉取行情；"
                            "补全 fund_code 后请再保存并运行 backfill_prices.py。"
                        )

                    st.warning("请刷新页面或重新运行相关任务，使新配置生效。")
                    _reset_draft_config()
                except ConfigValidationError as exc:
                    st.error("配置校验未通过，未保存：")
                    for error in exc.errors:
                        st.write(f"- {error}")

    with col3:
        if st.button("重新加载配置", use_container_width=True):
            _reset_draft_config()
            st.rerun()


if __name__ == "__main__":
    main()
else:
    main()
