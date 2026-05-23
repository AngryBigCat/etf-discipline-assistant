# ETF投资纪律助手

## 项目定位

本项目是一个面向个人投资者的 ETF 投资纪律管理工具。

它不是自动交易机器人，也不是荐股系统，而是帮助用户完成：

- ETF 行情观察
- 指标计算
- 持仓录入
- 仓位管理
- 策略纪律信号
- 交易日志记录
- 交易纪律统计
- 后续复盘分析

核心目标是帮助用户减少追涨杀跌、满仓冲动、无计划补仓等行为。

详细规划见 [`docs/ETF投资纪律助手开发计划.md`](docs/ETF投资纪律助手开发计划.md)。

## 核心原则

- 不自动下单
- 不接券商实盘交易接口
- 不做高频交易
- 不预测明天涨跌
- 不做个股荐股
- 不把 AI 作为买卖决策主体
- 系统只提供纪律建议，最终交易由用户人工确认

## 当前已完成功能

### 阶段 1-3：数据底座

- ETF 标的池（symbol / fund_code / exchange）
- AKShare 行情采集
- mock 数据兜底
- SQLite 数据库
- MA20 / MA60 / MA120 / MA250
- 回撤、波动率、阶段涨跌幅
- 历史不足时 `confidence_level=low`，不中断流程
- Streamlit 数据看板

### 阶段 4：持仓与仓位管理

- 手动录入现金
- 手动录入 ETF 数量和成本
- 自动计算持仓市值
- 保存账户快照（`account_snapshot`）
- 保存持仓快照（`holding_snapshot`）
- 计算 ETF 总仓位
- 计算现金仓位
- 计算单 ETF 仓位
- 判断低于目标、超过目标、超过最大仓位
- 区分只观察标的和参与策略信号标的（`signal_status` 与 `risk_status` 分离）
- UI 中文化（`src/ui/labels.py`）

### 阶段 5：策略信号

- 策略打分
  - 趋势分
  - 回撤分
  - 反追高分
  - 仓位分
  - 科创50 特殊规则分（`volatility_score=0`）
- 操作建议：可正常买入 / 可小额买入 / 仅按定投计划 / 观察 / 暂停买入
- 建议金额计算（受计划总投入、可用现金、最大允许市值约束，100 元取整）
- 生成纪律信号并写入 `strategy_signal` 表
- 审核状态 `review_status`（系统生成 / 已查看 / 已忽略 / 已执行）
- 只观察标的（`enabled_for_signal=false`，如 SP500、NASDAQ100）不生成买入建议

### 阶段 6：交易日志

- 从策略信号记录买入
- 标记信号已查看
- 标记信号忽略
- 手动新增交易记录
- 记录交易金额、价格、数量
- 记录交易理由和情绪状态
- 判断是否符合系统纪律（`discipline_checker`，买入金额 ≤ 建议 120% 等阈值）
- 统计最近交易纪律（符合规则比例、追涨 / 恐慌 / 临时决策次数等）
- 本阶段不接入券商

**注意**：交易日志只记录用户实际交易行为，不会自动修改 `account_snapshot` 或 `holding_snapshot`；交易后仍需在「持仓录入」页面手动更新持仓快照。

### 阶段 7：日报与周报

- 模板化日报：账户概况、策略信号摘要、当日交易纪律、风险提示、操作建议
- 模板化周报：本周交易统计、纪律执行率、仓位风险、下周建议
- 数据来源：账户快照、策略信号、交易日志、仓位 alerts（只读聚合，不修改持仓）
- 写入 `daily_report` / `weekly_report` 表，支持同日/同周 upsert 覆盖
- CLI：`scripts/generate_daily_report.py`、`scripts/generate_weekly_report.py`
- Streamlit「报告复盘」页：生成/查看日报与周报、历史列表
- 无账户快照时友好提示；无交易日志时统计为 0，不崩溃
- 本阶段不接 AI，不自动交易，不自动修改持仓

### enabled 语义

- `enabled=false`：隐藏，不采集，不展示
- `enabled=true, enabled_for_signal=false`：可展示 / 录入，不参与策略信号，仍做风控检查
- `enabled=true, enabled_for_signal=true`：正常参与仓位计算与策略信号

## 当前页面

- 数据看板
- 持仓录入
- 仓位管理
- 策略信号
- 交易日志
- 报告复盘

## 运行方式

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
python scripts/generate_signals.py
python scripts/generate_daily_report.py
python scripts/generate_weekly_report.py

pytest
streamlit run app.py
```

## 配置说明

主要配置在 `config.yaml`：

- ETF 标的
- 真实基金代码
- 目标仓位
- 最大仓位
- 单次买入比例
- 是否启用
- 是否参与策略信号

可选环境变量在 `.env`：

- `DATABASE_PATH`
- `PRICE_DATA_SOURCE=auto|akshare|mock`

## 未来蓝图

### 阶段 8：AI 复盘

- 将结构化交易数据输入大模型
- 生成自然语言复盘
- 分析用户是否频繁追涨、恐慌、临时决策
- 给出下周纪律建议
- AI 只解释和复盘，不直接决定交易

### 阶段 9：回测模块

- 回测普通定投
- 回测跌幅补仓
- 回测均线过滤
- 回测组合再平衡
- 对比最大回撤和收益

### 阶段 10：提醒系统

- 企业微信 / Bark / Telegram / 邮件提醒
- 每日收盘后提醒
- 触发纪律信号提醒
- 仓位超限提醒

### 阶段 11：更高级的组合管理

- 定投日历
- 组合再平衡计划
- 跨境 ETF 溢价提醒
- QDII 汇率影响提示
- 多账户支持

## 风险提示

- 本系统输出仅用于投资纪律管理，不构成投资建议。
- 系统信号基于预设规则，不代表未来收益。
- 所有交易由用户自行判断和承担风险。
