# ETF投资纪律助手

个人 ETF 投资纪律管理系统（非自动交易、非荐股）。

当前版本：**阶段 6** — 在策略信号基础上，支持交易日志记录与投资纪律复盘统计。

详细规划见 [`docs/ETF投资纪律助手开发计划.md`](docs/ETF投资纪律助手开发计划.md)。

## 功能

### 阶段 1-3
- ETF 标的池（symbol / fund_code / exchange）
- AKShare 行情采集，失败时 mock 兜底
- 指标：MA20/60/120/250、回撤、20 日波动率、5/10/20 日收益率
- 历史不足时 `confidence_level=low`，不中断流程
- 数据看板：标的、行情、指标（中文表头）

### 阶段 4
- 持仓录入：手动录入现金余额与 ETF 持仓数量/成本
- 自动计算「最新价 × 数量」市值（无最新价时可手动填市值）
- 保存 `account_snapshot` + `holding_snapshot`（同日 upsert）
- 仓位管理：账户总览、目标偏离、最大仓位风控
- `signal_status`（是否参与信号）与 `risk_status`（风控状态）分离；只观察标的仍做超限检查
- UI 中文化（`src/ui/labels.py`）

### 阶段 5
- 策略打分：趋势 / 回撤 / 反追高 / 仓位 / 科创50 特殊规则（`volatility_score=0`）
- 操作建议：可正常买入 / 可小额买入 / 仅按定投计划 / 观察 / 暂停买入
- 建议买入金额：受计划总投入、可用现金、最大允许市值等约束，100 元取整
- 写入 `strategy_signal` 表，支持 `review_status`（系统生成 / 已查看 / 已忽略 / 已执行）
- `enabled_for_signal=false` 的标的（如 SP500、NASDAQ100）不生成买入建议，仅在页面展示为「只观察标的」

### 阶段 6
- 交易日志：手动录入交易，或从策略信号页「记录买入 / 标记忽略」写入
- `trade_log` 关联 `signal_id`，持久化 `suggested_amount`、`deviation_amount`、`execution_status`
- 纪律校验（`discipline_checker`）：买入金额不超过建议 120%、违反 `stop_buy` / `hold` 等规则自动标记
- `review_status` 支持 `executed`（按建议执行后由交易记录更新）
- 交易日志页：最近记录表格、可配置区间的纪律统计（符合规则比例、追涨/恐慌/临时决策次数等）
- 本阶段不自动更新持仓，不接入券商

### enabled 语义
- `enabled=false`：隐藏，不采集，不展示
- `enabled=true, enabled_for_signal=false`：可展示/录入，不参与策略信号，仍做风控检查
- `enabled=true, enabled_for_signal=true`：正常参与仓位计算与策略信号

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 初始化与运行

```bash
python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
python scripts/generate_signals.py   # 可选：CLI 生成今日纪律信号
streamlit run app.py
pytest
```

Streamlit 侧边栏页面（`streamlit run app.py` 后左侧导航）：

1. **数据看板** — 标的、行情、指标
2. **持仓录入** — 录入现金与 ETF 持仓，保存快照
3. **仓位管理** — 账户总览、仓位明细与风险提示
4. **策略信号** — 生成纪律信号、操作建议、建议金额与原因说明；记录买入 / 已查看 / 忽略
5. **交易日志** — 手动录入与历史记录、纪律统计

## 配置

- `config.yaml`：标的池、计划总投入、策略参数与操作建议阈值
- `.env`：可选 `DATABASE_PATH`、`PRICE_DATA_SOURCE=auto|akshare|mock`

## 风险提示

本系统输出仅供参考，不构成投资建议。最终交易需用户自行判断。
