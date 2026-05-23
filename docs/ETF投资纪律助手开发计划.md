# ETF投资纪律助手开发计划文档

## 1. 项目定位

本项目名称：**ETF投资纪律助手**

本项目不是自动交易机器人，也不是 AI 荐股系统，而是一个面向个人投资者的 **ETF 投资纪律管理系统**。

核心目标是帮助投资者在投资 ETF 时做到：

1. 不追高；
2. 不满仓；
3. 不情绪化补仓；
4. 按规则定投；
5. 按仓位纪律管理科创50等高波动品种；
6. 每日自动生成操作建议；
7. 每周自动复盘交易行为；
8. 最终由用户人工确认是否交易。

本项目第一版重点服务于以下投资场景：

```text
总计划资金：100000 元
投资风格：平衡型
主要标的：
- 中证A500ETF：核心仓
- 科创50ETF：卫星仓
- 沪深300ETF：参考核心仓
- 红利ETF：防守仓
- 标普500ETF / 纳斯达克100ETF：海外配置观察（第一版 enabled_for_signal = false）
- 现金 / 货币基金：备用资金（手动录入余额）
```

## 1.1 当前实现进度（截至 2026-05-23）

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段一：项目初始化 | 已完成 | init_db / seed_data / schema / config |
| 阶段二：行情数据 | 已完成 | AKShare + mock 兜底，daily_update |
| 阶段三：指标 + 数据看板 | 已完成 | indicator_service，pages/dashboard.py |
| 阶段四：持仓与仓位 | 已完成 | 持仓录入、仓位管理、signal_status / risk_status 分离 |
| 阶段五：策略规则 | 已完成 | score_engine / rule_engine / signal_generator，策略信号页 |
| 阶段六及以后 | 未开始 | 交易日志、日报/周报、AI 等 |

**当前 Streamlit 页面**（`app.py` + `st.navigation`）：

```text
1. 数据看板   — pages/dashboard.py
2. 持仓录入   — pages/holdings_entry.py
3. 仓位管理   — pages/position_mgmt.py
4. 策略信号   — pages/strategy_signals.py
```

**当前 CLI 脚本**：

```text
python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
python scripts/generate_signals.py   # 阶段五新增
pytest
streamlit run app.py
```

---

# 2. 核心原则

## 2.1 系统不做的事情

本系统第一版明确不做：

```text
1. 不自动下单
2. 不接入券商交易接口
3. 不做高频交易
4. 不预测明天涨跌
5. 不做个股荐股
6. 不用机器学习直接预测价格
7. 不鼓励用户满仓
8. 不把 AI 作为买卖决策主体
```

## 2.2 系统要做的事情

本系统第一版要做：

```text
1. 获取 ETF 每日行情
2. 维护 ETF 投资标的池
3. 手动录入持仓和交易记录
4. 自动计算均线、回撤、波动率、仓位
5. 自动生成买入、暂停、观察等纪律信号
6. 自动判断是否违反仓位纪律
7. 生成每日操作建议
8. 提供 Streamlit 可视化看板
9. 支持交易日志记录
10. 支持每周复盘
11. 后续可接入大模型生成自然语言复盘
```

---

# 3. 技术选型

第一版采用轻量技术栈，优先快速落地。

```text
语言：Python 3.11+
数据处理：pandas、numpy
行情数据：AKShare，后续可选 Tushare
数据库：SQLite
前端展示：Streamlit
配置文件：YAML
定时任务：APScheduler
图表：Plotly
环境变量：python-dotenv
日志：loguru
测试：pytest
```

第一版不使用：

```text
FastAPI
Celery
Redis
PostgreSQL
Docker
券商交易接口
复杂权限系统
```

后续稳定后再升级。

---

# 4. 项目目录结构

请 Cursor 按以下结构创建项目：

```text
etf-discipline-assistant/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config.yaml
│
├── app.py
│
├── pages/
│   ├── dashboard.py           # 数据看板
│   ├── holdings_entry.py      # 持仓录入
│   ├── position_mgmt.py       # 仓位管理
│   └── strategy_signals.py    # 策略信号（阶段五）
│
├── data/
│   ├── etf_assistant.db
│   └── sample_prices/
│
├── docs/
│   └── ETF投资纪律助手开发计划.md
│
├── scripts/
│   ├── init_db.py
│   ├── seed_data.py
│   ├── daily_update.py
│   ├── generate_signals.py    # 阶段五
│   └── weekly_review.py       # 待实现
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── schema.py          # etf_universe / daily_price / account_snapshot / ...
│   │   └── repository.py
│   │
│   ├── ui/                    # 阶段四 UI 中文化
│   │   ├── helpers.py
│   │   └── labels.py
│   │
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── akshare_collector.py
│   │   ├── mock_collector.py
│   │   ├── price_service.py
│   │   └── base.py
│   │
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── moving_average.py
│   │   ├── drawdown.py
│   │   ├── volatility.py
│   │   └── indicator_service.py
│   │
│   ├── portfolio/
│   │   ├── __init__.py
│   │   ├── holdings.py
│   │   ├── position.py
│   │   └── rebalance.py
│   │
│   ├── strategy/              # 阶段五
│   │   ├── __init__.py
│   │   ├── score_engine.py
│   │   ├── rule_engine.py
│   │   └── signal_generator.py
│   │
│   ├── reports/               # 待实现
│   │   ├── __init__.py
│   │   ├── daily_report.py
│   │   └── weekly_review.py
│   │
│   ├── ai/                    # 待实现
│   │   ├── __init__.py
│   │   ├── prompt_builder.py
│   │   └── llm_client.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py
│       └── number_utils.py
│
└── tests/
    ├── test_indicators.py
    ├── test_collectors.py
    ├── test_enabled_filter.py
    ├── test_position.py
    ├── test_ui_labels.py
    ├── test_score_engine.py
    ├── test_signal_generator.py
    └── test_suggested_amount.py
```

---

# 5. 关键口径约定（v1 冻结）

正式实现前，以下口径为第一版冻结规则，配置、数据库、策略引擎、页面均需一致遵守。

## 5.1 ETF 标的标识

系统必须区分 **业务 symbol** 与 **真实基金代码**：

| 字段 | 用途 | 示例 |
| --- | --- | --- |
| `symbol` | 系统内部逻辑标识 | `A500`、`KC50`、`HS300` |
| `fund_code` | AKShare 拉取 ETF 行情 | `512050`、`588000`、`510300` |
| `exchange` | 交易所 | `SH`、`SZ` |
| `index_code` | 预留，后续用指数数据补长期历史 | `000510`、`000688` |

规则：

```text
1. 所有业务逻辑（持仓、信号、日志）统一使用 symbol。
2. collectors 层根据 fund_code + exchange 调用 AKShare。
3. index_code 第一版可不拉数，仅入库预留。
4. 同一 symbol 对应一只默认 ETF，不在第一版做多 ETF 切换。
```

## 5.2 现金与仓位口径（手动录入）

第一版 **不推导现金**，全部采用手动录入：

```text
1. 用户手动录入 cash_value（现金/货币基金余额）。
2. 用户手动录入各 ETF 的 quantity、cost、market_value。
3. 系统计算：
   current_account_value = sum(ETF market_value) + cash_value
4. 禁止使用 total_plan_amount - ETF市值 推算现金。
```

`holding_snapshot` 保存各 ETF 持仓；新增 `account_snapshot` 保存账户级现金与总资产（见 §7.3、§7.4）。

## 5.3 total_plan_amount 与 current_account_value

```text
total_plan_amount：
  - 代表计划总投入金额（如 100000 元）
  - 用于建议买入金额基准、单次买入比例、科创50单次上限
  - 不等于当前账户总资产

current_account_value：
  - = ETF 市场总市值 + cash_value
  - 用于计算各标的仓位权重、总仓位、现金仓位
  - 风控判断需同时参考 current_account_value 与 total_plan_amount
```

仓位权重公式：

```python
asset_weight = asset_market_value / current_account_value
total_position = sum(etf_market_value) / current_account_value
cash_position = cash_value / current_account_value
```

## 5.4 volatility_score（第一版固定为 0）

```text
1. indicator_daily 仍计算并展示 volatility_20d。
2. 第一版 volatility_score 固定为 0，不参与 final_score。
3. 待后续回测验证后，再决定是否纳入打分。
```

## 5.5 历史数据不足处理（不得报错）

指标或规则计算时，历史长度不足 **不得抛异常中断流程**：

```text
1. MA250 数据不足：跳过 MA250 相关趋势打分，reason 中注明「MA250 数据不足」。
2. 250 日回撤不足：降级使用 120 日回撤参与回撤分。
3. 120 日回撤仍不足：使用已有历史窗口的最大回撤，并设置 confidence_level = low。
4. 可在 indicator_daily / strategy_signal 中记录 confidence_level（normal / low）。
5. daily_update 与 Streamlit 页面应正常展示已有指标，缺失项显示为「—」或 N/A。
```

## 5.6 跨境 ETF（第一版仅观察）

```text
1. SP500、NASDAQ100 等跨境标的默认 enabled_for_signal = false。
2. 可拉取并展示行情、指标，但不生成主动买入金额（suggested_amount = 0）。
3. action 最高为 hold / 观察，不参与 strong_buy / small_buy。
4. 后续版本再接入汇率、溢价率、海外指数同步逻辑。
```

## 5.7 策略信号 review_status

每条 `strategy_signal` 增加 `review_status`，用于用户确认与复盘：

| 状态 | 含义 |
| --- | --- |
| `generated` | 系统生成，用户未查看 |
| `reviewed` | 用户已查看 |
| `executed` | 用户已按建议执行 |
| `ignored` | 用户主动忽略 |

`trade_log` 增加 `signal_id` 字段，关联交易当日的策略信号，便于周复盘统计「建议 vs 实际操作」。

## 5.8 第一版实现范围（分阶段交付）

项目按阶段交付，**阶段 1-5 已完成**，阶段 6 及以后待启动：

```text
阶段 1-3（已完成）：
  - init_db / seed_data / daily_update
  - mock_collector + akshare_collector（失败兜底）
  - indicator_service（MA/回撤/波动率/收益率/降级）
  - Streamlit 数据看板（pages/dashboard.py）

阶段 4（已完成）：
  - 持仓录入（pages/holdings_entry.py）
  - 仓位管理（pages/position_mgmt.py）
  - signal_status（是否参与信号）与 risk_status（风控状态）分离
  - UI 中文化（src/ui/labels.py）

阶段 5（已完成）：
  - score_engine / rule_engine / signal_generator
  - strategy_signal 持久化 + scripts/generate_signals.py
  - 策略信号页（pages/strategy_signals.py）
  - review_status：generated / reviewed / ignored

待启动：
  - 阶段六：交易日志、完整看板整合
  - 阶段七～九：日报/周报、AI 复盘
```

---

# 6. 配置文件设计

创建 `config.yaml`。

```yaml
app:
  name: "ETF投资纪律助手"
  base_currency: "CNY"
  timezone: "Asia/Shanghai"

portfolio:
  total_plan_amount: 100000
  max_total_position: 0.80
  normal_position: 0.50
  min_cash_position: 0.20

risk_profile:
  name: "平衡型"
  description: "以宽基ETF为核心，控制科创类高波动仓位，保留现金用于分批补仓。"

assets:
  - symbol: "A500"
    name: "中证A500ETF"
    fund_code: "512050"
    exchange: "SH"
    index_code: "000510"
    role: "core"
    market: "CN"
    target_weight: 0.50
    max_weight: 0.65
    single_buy_ratio: 0.03
    risk_level: 3
    enabled: true
    enabled_for_signal: true

  - symbol: "KC50"
    name: "科创50ETF"
    fund_code: "588000"
    exchange: "SH"
    index_code: "000688"
    role: "satellite"
    market: "CN"
    target_weight: 0.15
    max_weight: 0.20
    single_buy_ratio: 0.02
    risk_level: 5
    enabled: true
    enabled_for_signal: true

  - symbol: "HS300"
    name: "沪深300ETF"
    fund_code: "510300"
    exchange: "SH"
    index_code: "000300"
    role: "core_reference"
    market: "CN"
    target_weight: 0.15
    max_weight: 0.25
    single_buy_ratio: 0.03
    risk_level: 3
    enabled: true
    enabled_for_signal: true

  - symbol: "DIVIDEND"
    name: "红利ETF"
    fund_code: "510880"
    exchange: "SH"
    index_code: "000015"
    role: "defensive"
    market: "CN"
    target_weight: 0.10
    max_weight: 0.20
    single_buy_ratio: 0.02
    risk_level: 2
    enabled: true
    enabled_for_signal: true

  - symbol: "SP500"
    name: "标普500ETF"
    fund_code: "513500"
    exchange: "SH"
    index_code: ""
    role: "overseas"
    market: "US"
    target_weight: 0.10
    max_weight: 0.20
    single_buy_ratio: 0.02
    risk_level: 3
    enabled: true
    enabled_for_signal: false

  - symbol: "NASDAQ100"
    name: "纳斯达克100ETF"
    fund_code: "513100"
    exchange: "SH"
    index_code: ""
    role: "overseas"
    market: "US"
    target_weight: 0.05
    max_weight: 0.10
    single_buy_ratio: 0.02
    risk_level: 3
    enabled: true
    enabled_for_signal: false

  - symbol: "CASH"
    name: "现金/货币基金"
    fund_code: ""
    exchange: ""
    index_code: ""
    role: "cash"
    market: "CASH"
    target_weight: 0.20
    min_weight: 0.20
    risk_level: 0
    enabled: true
    enabled_for_signal: false

strategy:
  trend:
    ma_short: 20
    ma_mid: 60
    ma_long: 120
    ma_year: 250

  drawdown:
    small_buy_threshold: -0.03
    normal_buy_threshold: -0.05
    large_buy_threshold: -0.10
    extreme_threshold: -0.15

  anti_chase:
    five_day_gain_warning: 0.05
    ten_day_gain_warning: 0.08

  score:
    base_score: 50
    min_score: 0
    max_score: 100

actions:
  strong_buy:
    min_score: 80
    label: "可正常买入"
  small_buy:
    min_score: 65
    label: "可小额买入"
  fixed_invest:
    min_score: 50
    label: "只按定投计划"
  hold:
    min_score: 35
    label: "观察，不主动买入"
  stop_buy:
    min_score: 0
    label: "暂停买入"
```

---

# 7. 数据库设计

使用 SQLite。

## 7.1 ETF 标的表

```sql
CREATE TABLE IF NOT EXISTS etf_universe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    fund_code TEXT,
    exchange TEXT,
    index_code TEXT,
    role TEXT,
    market TEXT,
    risk_level INTEGER DEFAULT 3,
    target_weight REAL DEFAULT 0,
    max_weight REAL DEFAULT 0,
    min_weight REAL DEFAULT 0,
    single_buy_ratio REAL DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    enabled_for_signal INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

说明：

```text
- symbol：业务标识，供持仓/信号/日志引用
- fund_code + exchange：供 akshare_collector 拉行情
- index_code：预留，后续指数补历史
- enabled_for_signal：false 时只展示，不生成主动买入建议
```

## 7.2 每日行情表

```sql
CREATE TABLE IF NOT EXISTS daily_price (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    nav REAL,
    premium_rate REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date)
);
```

## 7.3 账户快照表

```sql
CREATE TABLE IF NOT EXISTS account_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    cash_value REAL NOT NULL DEFAULT 0,
    etf_market_value REAL NOT NULL DEFAULT 0,
    total_account_value REAL NOT NULL DEFAULT 0,
    total_position REAL DEFAULT 0,
    cash_position REAL DEFAULT 0,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

说明：

```text
- cash_value：用户手动录入的现金/货币基金余额
- etf_market_value：当日各 ETF 市值之和（由 holding_snapshot 汇总）
- total_account_value = etf_market_value + cash_value
- 仓位权重均基于 total_account_value 计算，不使用 total_plan_amount 反推
```

## 7.4 持仓快照表

```sql
CREATE TABLE IF NOT EXISTS holding_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL DEFAULT 0,
    market_value REAL NOT NULL,
    cost REAL DEFAULT 0,
    profit_loss REAL DEFAULT 0,
    profit_loss_rate REAL DEFAULT 0,
    weight REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, symbol)
);
```

说明：用户手动录入 quantity、cost、market_value；系统根据 account_snapshot.total_account_value 计算 weight。

## 7.5 交易记录表

```sql
CREATE TABLE IF NOT EXISTS trade_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_id INTEGER,
    action TEXT NOT NULL,
    amount REAL NOT NULL,
    price REAL,
    quantity REAL,
    reason TEXT,
    emotion TEXT,
    is_rule_based INTEGER DEFAULT 1,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES strategy_signal(id)
);
```

说明：`signal_id` 关联当日策略信号，便于复盘「系统建议 vs 用户实际操作」。

## 7.6 指标表

```sql
CREATE TABLE IF NOT EXISTS indicator_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    ma20 REAL,
    ma60 REAL,
    ma120 REAL,
    ma250 REAL,
    drawdown_60d REAL,
    drawdown_120d REAL,
    drawdown_250d REAL,
    drawdown_used REAL,
    drawdown_window INTEGER,
    volatility_20d REAL,
    return_5d REAL,
    return_10d REAL,
    return_20d REAL,
    confidence_level TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date)
);
```

说明：

```text
- drawdown_used / drawdown_window：记录实际参与计算的回撤值与窗口（250/120/可用最大窗口）
- confidence_level：normal / low（历史不足时标记 low）
- volatility_20d：仅展示，第一版不参与打分
```

## 7.7 策略信号表

```sql
CREATE TABLE IF NOT EXISTS strategy_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trend_score REAL DEFAULT 0,
    drawdown_score REAL DEFAULT 0,
    volatility_score REAL DEFAULT 0,
    position_score REAL DEFAULT 0,
    anti_chase_score REAL DEFAULT 0,
    final_score REAL DEFAULT 0,
    action TEXT,
    suggested_amount REAL DEFAULT 0,
    reason TEXT,
    confidence_level TEXT DEFAULT 'normal',
    review_status TEXT DEFAULT 'generated',
    reviewed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(signal_date, symbol)
);
```

说明：

```text
- volatility_score：第一版固定写入 0
- review_status：generated / reviewed / executed / ignored
- enabled_for_signal = false 的标的：suggested_amount = 0，action 不超过 hold
```

## 7.8 每日报告表

```sql
CREATE TABLE IF NOT EXISTS daily_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    total_position REAL,
    cash_position REAL,
    summary TEXT,
    risk_warning TEXT,
    action_suggestion TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

# 8. 核心业务逻辑

## 8.1 指标计算

系统需要计算：

```text
1. MA20
2. MA60
3. MA120
4. MA250
5. 近60日回撤
6. 近120日回撤
7. 近250日回撤
8. 近20日波动率（仅展示，不参与打分）
9. 近5日收益率
10. 近10日收益率
11. 近20日收益率
12. drawdown_used / drawdown_window / confidence_level
```

### 回撤计算

```python
drawdown = close / rolling_max - 1
```

### 回撤降级规则（历史不足时不报错）

```python
def resolve_drawdown_for_scoring(indicator):
    if indicator["drawdown_250d"] is not None:
        return indicator["drawdown_250d"], 250, "normal"
    if indicator["drawdown_120d"] is not None:
        return indicator["drawdown_120d"], 120, "low"
    return indicator["drawdown_max_available"], indicator["drawdown_window"], "low"
```

### 波动率计算

```python
daily_return = close.pct_change()
volatility_20d = daily_return.rolling(20).std()
# 第一版仅展示，volatility_score 固定为 0
```

### 历史数据不足处理

```text
1. 可用历史 < 250 日：ma250 = None，趋势打分跳过 MA250 项。
2. 可用历史 < 120 日：drawdown_120d = None，继续降级。
3. 可用历史 < 60 日：仍计算已有窗口指标，confidence_level = low。
4. 任何指标缺失不得导致 daily_update 或页面崩溃。
```

---

# 9. 策略打分模型

最终分数：

```text
final_score =
    base_score
    + trend_score
    + drawdown_score
    + volatility_score      # 第一版固定为 0
    + position_score
    + anti_chase_score
```

基础分：

```text
base_score = 50
volatility_score = 0        # 第一版冻结，不参与计算
```

---

## 9.1 趋势分

```text
收盘价 > MA60：+10
收盘价 > MA120：+8
收盘价 < MA60：-8
收盘价 < MA120：-8

MA250 相关（仅当 ma250 不为 None 时计分）：
收盘价 > MA250：+8
收盘价 < MA250：-8
MA250 数据不足：跳过，reason 注明「MA250 数据不足」
```

解释：

```text
站上中长期均线，说明趋势较稳，可以正常定投。
跌破中长期均线，说明趋势偏弱，降低买入强度。
历史不足的标的（如 A500）不因 MA250 缺失而报错。
```

---

## 9.2 回撤分

使用 `drawdown_used`（按 §8.1 降级规则选取）：

```text
drawdown_used <= -3%：+5
drawdown_used <= -5%：+10
drawdown_used <= -10%：+15
drawdown_used <= -15%：+20
confidence_level = low 时，reason 中注明「回撤基于短窗口，置信度低」
```

但要注意：

```text
回撤越大，不代表越应该重仓。
回撤分只是提示“价格进入可观察区域”，还必须结合趋势和仓位。
```

---

## 9.3 反追高分

```text
近5日涨幅 >= 5%：-10
近10日涨幅 >= 8%：-15
近20日涨幅 >= 12%：-20
```

解释：

```text
短期涨幅过大时，禁止追高。
尤其是科创50这类高波动ETF，必须严格控制。
```

---

## 9.4 仓位分

仓位权重基于 **current_account_value**（非 total_plan_amount）：

```python
current_account_value = sum(etf_market_value) + cash_value
asset_weight = asset_market_value / current_account_value
total_position = sum(etf_market_value) / current_account_value
cash_position = cash_value / current_account_value
```

打分规则：

```text
当前标的仓位 > 最大仓位：-40
当前标的仓位 > 目标仓位：-15
当前标的仓位 < 目标仓位 * 0.7：+10
总仓位 > 70%：-15
总仓位 > 80%：-30
现金仓位 < 20%：-25
```

解释：

```text
仓位分优先级最高。
即使技术信号很好，只要仓位超了，也不能继续买。
风控需同时参考 current_account_value（实际仓位）与 total_plan_amount（计划投入与建议金额）。
```

---

## 9.5 科创50特殊规则

科创50属于高波动卫星仓，额外限制：

```text
1. 最大仓位不超过20%
2. 单次买入不超过总计划资金的2%
3. 当前仓位超过18%时，只允许观察
4. 近5日涨幅超过5%时禁止追买
5. 价格低于MA120时，只允许小额买入，不允许大额补仓
```

示例：

```text
总资金计划 100000 元
科创50单次买入上限 = 100000 * 0.02 = 2000 元
科创50最大总仓位（参考 total_plan_amount）= 100000 * 0.20 = 20000 元
当前科创50仓位（参考 current_account_value）用于判断是否接近 18% 上限
```

---

## 9.6 跨境 ETF 与 enabled_for_signal

```text
enabled_for_signal = false 的标的（如 SP500、NASDAQ100）：
1. 可计算指标并展示
2. 不生成主动买入金额（suggested_amount = 0）
3. action 最高为 hold，label 为「观察」
4. review_status 仍正常流转，便于用户标记已查看/已忽略
```

---

# 10. 操作信号映射

根据 final_score 生成动作。

```text
final_score >= 80：
    action = strong_buy
    label = 可正常买入

65 <= final_score < 80：
    action = small_buy
    label = 可小额买入

50 <= final_score < 65：
    action = fixed_invest
    label = 只按定投计划

35 <= final_score < 50：
    action = hold
    label = 观察，不主动买入

final_score < 35：
    action = stop_buy
    label = 暂停买入
```

---

# 11. 建议买入金额计算

建议金额基于 **total_plan_amount** 计算基准，但受 **current_account_value** 下的实际仓位与现金约束：

```text
total_plan_amount      → 建议买入金额基准、single_buy_ratio、科创50单次上限
current_account_value  → 仓位权重、最大仓位容量、现金保留比例
cash_value             → 用户手动录入，禁止由 total_plan_amount 反推
```

输入字段：

```text
total_plan_amount（计划总投入）
single_buy_ratio（单次买入比例）
current_account_value（ETF市值 + 现金）
asset_weight / total_position / cash_position
目标仓位 / 最大仓位
信号强度 action
enabled_for_signal
```

基础公式：

```python
base_buy_amount = total_plan_amount * single_buy_ratio
```

例如：

```text
中证A500 single_buy_ratio = 0.03
总计划资金 = 100000
基础买入金额 = 3000 元
```

根据 action 调整：

```text
strong_buy：base_buy_amount * 1.0
small_buy：base_buy_amount * 0.5
fixed_invest：base_buy_amount * 0.3
hold：0
stop_buy：0
enabled_for_signal = false：0（跨境观察标的）
```

限制条件：

```text
1. 买入后该 ETF 市值不得超过 total_plan_amount * max_weight（或 current 下 max_weight，取更严者）
2. 买入后 cash_position 不得低于 min_cash_position（基于 current_account_value）
3. 科创50单次买入不得超过 total_plan_amount * 0.02
4. total_position > 70% 时，买入金额减半
5. total_position > 80% 时，禁止买入
6. enabled_for_signal = false 时，suggested_amount 恒为 0
```

---

# 12. 每日运行流程

每日收盘后运行。

```text
15:10 获取行情数据
15:15 保存行情数据
15:20 计算指标
15:25 读取 account_snapshot / holding_snapshot（用户手动录入）
15:30 基于 current_account_value 计算仓位
15:35 生成策略信号
15:40 生成日报
15:45 展示在 Streamlit
```

第一版可以手动运行：

```bash
python scripts/daily_update.py
streamlit run app.py
```

后续再加定时任务。

---

# 13. Streamlit 页面设计

## 13.0 当前已实现页面（阶段 1-5）

使用 `app.py` + `st.navigation` 显式注册页面（ASCII 文件名，避免中文路径导航问题）：

| 页面 | 文件 | 阶段 | 功能 |
|------|------|------|------|
| 数据看板 | pages/dashboard.py | 3 | 标的池、最新行情、基础指标（中文表头） |
| 持仓录入 | pages/holdings_entry.py | 4 | 手动录入现金余额与 ETF 持仓，保存快照 |
| 仓位管理 | pages/position_mgmt.py | 4 | 账户总览、仓位明细、分级风险提示 |
| 策略信号 | pages/strategy_signals.py | 5 | 生成纪律信号、操作建议、建议金额、审核状态 |

**UI 中文化**：用户可见文案统一经 `src/ui/labels.py` 翻译；数据库字段名与代码内部变量名保持英文。

**仓位管理风控展示**（阶段四补充）：
- `signal_status`：参与信号 / 只观察（enabled_for_signal）
- `risk_status`：正常 / 低于目标仓位 / 高于目标 / 超过上限（所有持仓均检查，含 watch_only）
- 风险提示仅在「仓位提醒」区域展示一次，按 severity 分级（error / warning / info）

## 13.0.1 阶段 1-3 最简首页（历史说明）

第一版 Streamlit 曾仅实现最简首页，用于验证数据管道。现已扩展为上述四页，原最简首页能力并入「数据看板」。

## 13.0.2 待实现页面（阶段六及以后）

```text
1. 交易日志
2. 周复盘
3. 系统配置查看
4. review_status = executed（需交易日志模块完成后）
```

## 13.1 首页：今日操作建议

页面内容：

```text
1. 今日总览
2. 当前总仓位
3. 当前现金仓位
4. 是否适合买入
5. 今日最推荐操作
6. 今日风险提醒
```

展示示例：

```text
今日结论：谨慎小额定投

当前总仓位：35%
现金仓位：65%
科创50仓位：18%

今日建议：
- 中证A500：可小额买入 1500 元
- 科创50：暂停加仓
- 沪深300：观察
- 红利ETF：可观察
- 现金：继续保留
```

---

## 13.2 ETF看板页

字段：

```text
标的名称
当前价格
MA20
MA60
MA120
MA250
近250日回撤
近20日波动率
近5日涨幅
当前仓位
目标仓位
最大仓位
纪律分数
操作建议
建议金额
```

表格示例：

| 标的     |   当前价 |  MA60 | MA120 |    回撤 |  仓位 | 分数 | 动作   | 建议金额 |
| ------ | ----: | ----: | ----: | ----: | --: | -: | ---- | ---: |
| 中证A500 | 1.020 | 1.010 | 0.990 | -3.5% | 28% | 72 | 小额买入 | 1500 |
| 科创50   | 0.880 | 0.910 | 0.950 | -6.2% | 18% | 41 | 观察   |    0 |
| 沪深300  | 3.950 | 3.900 | 3.970 | -4.1% | 10% | 63 | 定投   |  900 |

---

## 13.3 仓位页

展示（基于手动录入的 account_snapshot / holding_snapshot）：

```text
1. 当前账户总资产 current_account_value
2. 用户录入的 cash_value
3. 各 ETF 市值（手动录入或 quantity * 最新价）
4. 当前仓位 vs 目标仓位（权重分母 = current_account_value）
5. 计划总投入 total_plan_amount（单独展示，不与总资产混淆）
6. 是否超配
7. 是否需要再平衡
```

表格：

| 资产     | 目标仓位 | 当前仓位 | 最大仓位 |   偏离 | 系统动作 |
| ------ | ---: | ---: | ---: | ---: | ---- |
| 中证A500 |  50% |  42% |  65% |  -8% | 优先补  |
| 科创50   |  15% |  18% |  20% |  +3% | 暂停加仓 |
| 红利ETF  |  10% |   5% |  20% |  -5% | 可补   |
| 现金     |  20% |  35% |    - | +15% | 可用   |

---

## 13.4 交易日志页

功能：

```text
1. 新增交易记录
2. 查看历史交易
3. 关联当日 strategy_signal（signal_id）
4. 标记是否符合规则
5. 记录交易情绪
6. 记录交易理由
7. 更新关联信号的 review_status（executed / ignored）
```

字段：

```text
交易日期
标的
买入/卖出
金额
价格
数量
交易理由
情绪状态
是否符合规则
备注
```

情绪状态可选：

```text
冷静
恐慌
贪婪
追涨
补跌
计划内定投
临时决策
```

---

## 13.5 周复盘页

统计：

```text
本周交易次数
符合规则次数
不符合规则次数
追涨次数
恐慌补仓次数
总买入金额
总卖出金额
当前总仓位变化
科创50仓位变化
```

输出示例：

```text
本周复盘：

1. 本周共交易3笔，其中2笔符合规则，1笔不符合规则。
2. 不符合规则的交易为科创50追涨买入。
3. 当前科创50仓位达到18%，接近20%上限。
4. 下周建议暂停科创50加仓，优先观察中证A500。
5. 当前现金仓位仍有65%，不用急于打满。
```

---

# 14. AI 模块设计

第一版 AI 可以先不接 API，只预留接口。

后续接入大模型时，AI 不直接决策，只负责解释。

## 14.1 AI 输入结构

```json
{
  "date": "2026-05-23",
  "portfolio": {
    "total_plan_amount": 100000,
    "current_account_value": 95000,
    "cash_value": 61750,
    "total_position": 0.35,
    "cash_position": 0.65
  },
  "signals": [
    {
      "symbol": "A500",
      "name": "中证A500ETF",
      "fund_code": "512050",
      "enabled_for_signal": true,
      "weight": 0.28,
      "target_weight": 0.50,
      "max_weight": 0.65,
      "drawdown_used": -0.035,
      "confidence_level": "normal",
      "return_5d": 0.012,
      "above_ma60": true,
      "above_ma120": true,
      "score": 72,
      "action": "small_buy",
      "suggested_amount": 1500,
      "review_status": "generated"
    },
    {
      "symbol": "KC50",
      "name": "科创50ETF",
      "enabled_for_signal": true,
      "weight": 0.18,
      "target_weight": 0.15,
      "max_weight": 0.20,
      "drawdown_used": -0.062,
      "confidence_level": "normal",
      "return_5d": 0.054,
      "above_ma60": false,
      "above_ma120": false,
      "score": 41,
      "action": "hold",
      "suggested_amount": 0,
      "review_status": "generated"
    },
    {
      "symbol": "SP500",
      "name": "标普500ETF",
      "enabled_for_signal": false,
      "action": "hold",
      "suggested_amount": 0,
      "review_status": "generated"
    }
  ]
}
```

## 14.2 AI 输出要求

```text
请根据结构化数据生成中文投资纪律复盘。
要求：
1. 不预测明天涨跌；
2. 不直接推荐满仓；
3. 强调仓位纪律；
4. 说明为什么可以买、为什么不能买；
5. 对科创50这类高波动ETF要更谨慎；
6. 输出结构包括：今日结论、可执行动作、风险提醒、下次观察点。
```

---

# 15. 核心代码逻辑示例

## 15.1 规则引擎伪代码

```python
def generate_signal(asset, indicator, position, portfolio, config):
    score = config["strategy"]["score"]["base_score"]
    volatility_score = 0  # 第一版固定为 0
    reasons = []
    confidence_level = indicator.get("confidence_level", "normal")

    close = indicator["close"]

    # 跨境观察标的：只展示，不生成买入建议
    if not asset.get("enabled_for_signal", True):
        return {
            "score": score,
            "volatility_score": 0,
            "action": "hold",
            "suggested_amount": 0,
            "confidence_level": confidence_level,
            "review_status": "generated",
            "reasons": ["跨境观察标的，第一版不生成主动买入建议"],
        }

    # 趋势分
    if close > indicator["ma60"]:
        score += 10
        reasons.append("价格站上MA60，短期趋势较好")
    else:
        score -= 8
        reasons.append("价格低于MA60，短期趋势偏弱")

    if close > indicator["ma120"]:
        score += 8
        reasons.append("价格站上MA120，中期趋势较好")
    else:
        score -= 8
        reasons.append("价格低于MA120，中期趋势偏弱")

    if indicator.get("ma250") is not None:
        if close > indicator["ma250"]:
            score += 8
            reasons.append("价格站上MA250，长期趋势较好")
        else:
            score -= 8
            reasons.append("价格低于MA250，长期趋势偏弱")
    else:
        reasons.append("MA250 数据不足，跳过 MA250 趋势打分")

    # 回撤分（按降级规则）
    drawdown, window, dd_confidence = resolve_drawdown_for_scoring(indicator)
    confidence_level = "low" if dd_confidence == "low" else confidence_level

    if drawdown <= -0.15:
        score += 20
        reasons.append(f"近{window}日回撤超过15%，进入深度回撤区域")
    elif drawdown <= -0.10:
        score += 15
        reasons.append(f"近{window}日回撤超过10%，具备分批观察价值")
    elif drawdown <= -0.05:
        score += 10
        reasons.append(f"近{window}日回撤超过5%，触发补仓观察")
    elif drawdown <= -0.03:
        score += 5
        reasons.append(f"近{window}日回撤超过3%，可小额观察")

    if dd_confidence == "low":
        reasons.append("回撤基于短窗口，confidence_level=low")

    # 反追高
    if indicator["return_5d"] >= 0.05:
        score -= 10
        reasons.append("近5日涨幅超过5%，存在追涨风险")

    if indicator["return_10d"] >= 0.08:
        score -= 15
        reasons.append("近10日涨幅超过8%，短期偏热")

    if indicator["return_20d"] >= 0.12:
        score -= 20
        reasons.append("近20日涨幅超过12%，短期过热")

    # 仓位控制（基于 current_account_value）
    if position["weight"] > asset["max_weight"]:
        score -= 40
        reasons.append("当前仓位超过最大仓位，禁止继续加仓")
    elif position["weight"] > asset["target_weight"]:
        score -= 15
        reasons.append("当前仓位高于目标仓位，降低买入优先级")
    elif position["weight"] < asset["target_weight"] * 0.7:
        score += 10
        reasons.append("当前仓位低于目标仓位，可作为补仓候选")

    if portfolio["total_position"] > 0.80:
        score -= 30
        reasons.append("总仓位超过80%，禁止继续加仓")
    elif portfolio["total_position"] > 0.70:
        score -= 15
        reasons.append("总仓位超过70%，降低买入强度")

    if portfolio["cash_position"] < 0.20:
        score -= 25
        reasons.append("现金仓位低于20%，需要保留备用资金")

    # 科创50特殊限制
    if asset["symbol"] == "KC50":
        if position["weight"] >= 0.18:
            score -= 20
            reasons.append("科创50仓位接近20%上限，暂停主动加仓")

        if indicator["return_5d"] >= 0.05:
            score -= 15
            reasons.append("科创50短期涨幅较大，禁止追买")

        if close < indicator["ma120"]:
            score -= 10
            reasons.append("科创50低于MA120，只允许观察或小额定投")

    score = max(0, min(100, score))

    if score >= 80:
        action = "strong_buy"
    elif score >= 65:
        action = "small_buy"
    elif score >= 50:
        action = "fixed_invest"
    elif score >= 35:
        action = "hold"
    else:
        action = "stop_buy"

    suggested_amount = calculate_suggested_amount(
        asset, action, position, portfolio, config
    )

    return {
        "score": score,
        "volatility_score": volatility_score,
        "action": action,
        "suggested_amount": suggested_amount,
        "confidence_level": confidence_level,
        "review_status": "generated",
        "reasons": reasons,
    }
```

---

## 15.2 建议金额伪代码

```python
def calculate_suggested_amount(asset, action, position, portfolio, config):
    total_plan_amount = config["portfolio"]["total_plan_amount"]
    current_account_value = portfolio["current_account_value"]
    cash_value = portfolio["cash_value"]

    if not asset.get("enabled_for_signal", True):
        return 0

    if action in ["hold", "stop_buy"]:
        return 0

    base_amount = total_plan_amount * asset["single_buy_ratio"]

    if action == "strong_buy":
        amount = base_amount
    elif action == "small_buy":
        amount = base_amount * 0.5
    elif action == "fixed_invest":
        amount = base_amount * 0.3
    else:
        amount = 0

    if portfolio["total_position"] > 0.70:
        amount *= 0.5

    if portfolio["total_position"] > 0.80:
        amount = 0

    # 买入后不超过 max_weight（基于 current_account_value）
    max_asset_value = current_account_value * asset["max_weight"]
    current_asset_value = position["market_value"]
    remaining_asset_capacity = max_asset_value - current_asset_value
    amount = min(amount, remaining_asset_capacity)

    # 保留 min_cash_position（基于 current_account_value，使用手动录入 cash_value）
    min_cash = current_account_value * config["portfolio"]["min_cash_position"]
    available_cash_after_reserve = cash_value - min_cash
    amount = min(amount, available_cash_after_reserve)

    if asset["symbol"] == "KC50":
        kc50_single_limit = total_plan_amount * 0.02
        amount = min(amount, kc50_single_limit)

    return max(0, round(amount, 2))
```

---

# 16. 开发阶段规划

> **当前进度：阶段一至阶段五已完成（2026-05-23）。** 下一步为阶段六（交易日志 + 看板整合）。

## 阶段一：项目初始化 ✅ 已完成

目标：项目能启动，数据库能初始化。

任务：

```text
1. 创建项目目录
2. 创建 requirements.txt
3. 创建 config.yaml（含 symbol / fund_code / exchange / index_code / enabled_for_signal）
4. 创建 SQLite 数据库连接模块
5. 创建数据库 schema（含 account_snapshot、review_status、signal_id）
6. 编写 init_db.py
7. 编写 seed_data.py（从 config 同步 etf_universe，含 fund_code 映射）
8. 能成功初始化 ETF 标的池
```

验收标准：

```text
运行 python scripts/init_db.py 后，data/etf_assistant.db 被创建。
运行 python scripts/seed_data.py 后，etf_universe 表有默认 ETF 数据，
且每条记录包含 symbol、fund_code、exchange、enabled_for_signal。
```

---

## 阶段二：行情数据模块 ✅ 已完成

目标：能获取并保存 ETF 历史行情。

任务：

```text
1. 编写 mock_collector.py，生成模拟行情数据
2. 编写 akshare_collector.py，按 fund_code 调用 AKShare（fund_etf_hist_em）
3. 数据字段统一为 open/high/low/close/volume/amount
4. daily_price 表按 symbol 存储（collector 内部做 fund_code → symbol 映射）
5. 对数据缺失、接口失败做异常处理
6. 如果 AKShare 获取失败，使用 mock 数据兜底
7. 跨境 ETF 同样拉行情，但 enabled_for_signal 不影响采集
```

验收标准：

```text
运行 python scripts/daily_update.py 后，daily_price 表有行情数据。
即使 AKShare 接口失败，系统也不能崩溃。
```

---

## 阶段三：指标计算 + 数据看板 ✅ 已完成

目标：能计算指标，并通过最简页面展示数据管道结果。

任务：

```text
1. 实现 indicator_service.py（MA/回撤/波动率/阶段涨跌幅）
2. 实现 MA20/MA60/MA120/MA250
3. 实现 60/120/250 日回撤及 drawdown_used 降级逻辑
4. 实现 20 日波动率（仅展示）
5. 实现 5/10/20 日收益率
6. 历史不足时不报错，写入 confidence_level
7. volatility_score 不参与打分（本阶段仅指标，策略后续再做）
8. 保存到 indicator_daily 表
9. 实现 Streamlit 数据看板（§13.0）：标的列表、最新行情、基础指标
```

验收标准：

```text
运行 daily_update.py 后，indicator_daily 表有每个 ETF 的指标数据。
运行 streamlit run app.py 后，数据看板可展示标的、行情、指标。
历史不足的标的显示 confidence_level=low，系统不崩溃。
以下命令均可成功运行：

python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
streamlit run app.py
```

---

## 阶段四：持仓与仓位模块 ✅ 已完成

目标：能手动录入持仓与现金，并基于 current_account_value 计算仓位。

任务：

```text
1. 实现 account_snapshot 手动录入（cash_value）
2. 实现 holding_snapshot 手动录入（quantity、cost、market_value）
3. 计算 current_account_value = sum(etf_market_value) + cash_value
4. 计算每个 ETF 当前仓位（分母 = current_account_value）
5. 计算总仓位、现金仓位
6. 计算目标仓位偏离
7. 禁止用 total_plan_amount - ETF市值 反推现金
8. signal_status / risk_status 分离（watch_only 仍做风控检查）
9. UI 中文化（src/ui/labels.py）
```

验收标准：

```text
用户可在 Streamlit 页面手动录入 cash_value 与 ETF 持仓。
系统能基于 current_account_value 计算总仓位、现金仓位、单 ETF 仓位。
total_plan_amount 与 current_account_value 分开展示，不混用。
watch_only 标的超限时仍显示风控提醒。
页面表头与提示文案中文化。
```

---

## 阶段五：策略规则模块 ✅ 已完成

目标：能生成纪律分数和操作信号。

任务：

```text
1. 实现 score_engine.py
2. 实现 rule_engine.py
3. 根据趋势、回撤、反追高、仓位生成分数
4. volatility_score 固定为 0
5. MA250 / 回撤降级与 confidence_level
6. enabled_for_signal = false 的标的不生成主动买入金额
7. 根据分数映射操作信号
8. 计算建议买入金额（total_plan_amount 基准 + current_account_value 约束）
9. 科创50使用特殊限制
10. 写入 review_status = generated
11. 保存到 strategy_signal 表
12. scripts/generate_signals.py CLI
13. pages/strategy_signals.py（生成信号、中文表格、今日摘要、审核状态编辑）
```

**打分模型摘要**：

```text
final_score = base_score(50) + trend + drawdown + anti_chase + position + special + volatility(0)

硬性 stop_buy：
  - 单 ETF 超过最大允许市值（max_allowed_value）
  - 总 ETF 仓位 > 80%
  - 科创50 仓位 >= 20%

建议金额：
  - 基准 total_plan_amount * single_buy_ratio
  - 受 action、总仓位、可用现金、最大允许市值、科创50 单次上限约束
  - 四舍五入到 100 元整数
```

验收标准：

```text
enabled_for_signal=true 的 ETF 生成：
  - final_score / action / suggested_amount / reason / confidence_level
  - review_status = generated
enabled_for_signal=false（SP500/NASDAQ100）不写入 strategy_signal，仅在页面「只观察标的」展示
超仓 ETF action=stop_buy，suggested_amount=0
pytest：test_score_engine / test_signal_generator / test_suggested_amount
```

---

## 阶段六：Streamlit 完整看板 ⏳ 待开始

目标：在现有四页基础上，扩展交易日志与看板整合。

页面：

```text
1. 今日建议（可与策略信号页整合或独立）
2. ETF看板（数据看板已部分覆盖）
3. 仓位管理（已实现）
4. 交易日志（待实现）
5. 周复盘（待实现）
6. 系统配置查看
7. review_status = executed（需交易日志完成后）
```

验收标准：

```text
运行 streamlit run app.py 后，页面可正常打开。
用户能查看今日建议、ETF指标、仓位状态、交易记录。
```

---

## 阶段七：交易日志模块 ⏳ 待开始

目标：记录交易行为，支持后续复盘。

任务：

```text
1. 实现新增交易记录
2. 实现交易记录查询
3. 支持 signal_id 关联 strategy_signal
4. 支持情绪字段
5. 支持是否符合规则字段
6. 支持按周统计交易纪律
7. 交易完成后可更新 signal.review_status
```

验收标准：

```text
用户能手动添加交易记录。
系统能统计本周不符合规则的交易数量。
```

---

## 阶段八：日报与周报模块 ⏳ 待开始

目标：生成自然语言报告。

第一版先用模板生成，不接 AI。

日报结构：

```text
今日结论
当前总仓位
现金仓位
各 ETF 操作建议
风险提醒
下次观察点
```

周报结构：

```text
本周交易次数
符合规则比例
仓位变化
主要风险
下周建议
```

验收标准：

```text
daily_report 表能保存日报。
周复盘页面能展示本周总结。
```

---

## 阶段九：AI 预留接口

目标：预留大模型生成自然语言复盘能力。

任务：

```text
1. 编写 prompt_builder.py
2. 将结构化信号转为 prompt
3. 编写 llm_client.py
4. 从 .env 读取 API KEY
5. 没有 API KEY 时使用模板报告
6. AI 输出不能直接修改策略信号
```

验收标准：

```text
有 API KEY 时可生成 AI 复盘。
无 API KEY 时系统仍然正常运行。
```

---

# 17. requirements.txt

```txt
pandas
numpy
streamlit
plotly
pyyaml
python-dotenv
loguru
apscheduler
pytest
akshare
```

后续可选：

```txt
openai
tushare
```

---

# 18. README.md 要求

README 需要包含：

```text
1. 项目介绍
2. 本项目不是自动交易系统
3. 功能列表
4. 安装方法
5. 初始化数据库
6. 运行方式
7. 配置说明
8. 策略规则说明
9. 关键口径说明（symbol/fund_code、手动录入现金、review_status）
10. 风险提示
```

运行命令：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
streamlit run app.py
```

---

# 19. Cursor 执行总提示词

## 19.1 阶段 1-3 提示词（历史归档）

下面这段用于阶段 1-3 初始开发（**已完成**）：

```text
请根据 docs/ETF投资纪律助手开发计划.md 开发 Python 项目。
…（阶段 1-3 要求，见历史版本）…
阶段 1-3 验收通过后，再请求继续阶段四（持仓）及以后。
```

## 19.2 当前阶段提示词（阶段六及以后）

继续开发时请遵守 v1 冻结口径，并基于已有模块扩展：

```text
请根据 docs/ETF投资纪律助手开发计划.md 继续开发。

当前已完成：阶段 1-5（数据管道、持仓、仓位、策略信号、UI 中文化）。
请勿修改数据库字段名、持仓录入与仓位管理核心逻辑。

冻结口径（必须遵守）：
1. symbol / fund_code / exchange / index_code 分离。
2. 现金与 ETF 持仓手动录入；current_account_value = ETF市值 + cash_value。
3. total_plan_amount 仅用于建议买入金额基准；仓位权重基于 current_account_value。
4. volatility_score 固定为 0；volatility_20d 只展示。
5. enabled_for_signal=false 不生成 strategy_signal；watch_only 仍做风控检查。
6. 单 ETF 超限口径：market_value > max_allowed_value（与仓位管理一致）。
7. strategy_signal 含 review_status；trade_log 含 signal_id（阶段七实现）。
8. 用户可见文案中文化，内部字段名不变。

阶段六起优先实现：
1. 交易日志 CRUD 与 Streamlit 页面
2. signal_id 关联 strategy_signal
3. review_status = executed 流转
4. 日报/周复盘模板（阶段八）
5. 为核心逻辑补充 pytest

验收命令：

python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
python scripts/generate_signals.py
pytest
streamlit run app.py
```

---

# 20. 第一版验收标准

## 阶段 1-3 验收 ✅ 已通过

```text
1. init_db / seed_data / daily_update 命令可运行
2. etf_universe 含 symbol、fund_code、exchange、enabled_for_signal
3. daily_price 有 mock 或真实行情
4. indicator_daily 有 MA/回撤/收益率；历史不足时 confidence_level=low，不崩溃
5. volatility_20d 有值但尚未参与策略打分
6. Streamlit 数据看板可展示标的、行情、指标
7. AKShare 失败时 mock 兜底，系统不崩溃
```

## 阶段 4-5 验收 ✅ 已通过

```text
1. 持仓录入与仓位管理页面正常
2. 仓位基于 current_account_value；total_plan_amount 单独展示
3. signal_status / risk_status 分离；watch_only 超限仍有风控提示
4. 策略信号页可生成纪律分数、操作建议、建议金额、原因说明
5. enabled_for_signal=false 不写入 strategy_signal
6. 超仓 / 总仓位>80% / 科创50>=20% 时 stop_buy
7. UI 中文化；pytest 38+ 用例通过
8. scripts/generate_signals.py 可 CLI 生成信号
```

## 完整第一版验收（阶段六至八完成后）⏳ 进行中

```text
1. 能启动 Streamlit 完整看板
2. 能手动录入 cash_value 与 ETF 持仓
3. 仓位基于 current_account_value 计算，total_plan_amount 单独展示
4. 能生成纪律分数与操作建议（volatility_score=0）
5. 跨境观察标的不生成主动买入金额
6. strategy_signal 含 review_status；trade_log 可关联 signal_id
7. 科创50接近上限、总仓位过高、短期涨幅过大时有纪律提示
8. 能记录交易日志并生成简单日报/周复盘
```

---

# 21. 最小可用版本目标

MVP 不追求复杂，只追求每天能回答三个问题：

```text
1. 今天能不能买？
2. 应该买哪个？
3. 买多少不会破坏仓位纪律？
```

**阶段五完成后**，上述问题已由「策略信号」页与 `scripts/generate_signals.py` 回答：纪律分数 → 操作建议 → 建议金额，并附中文原因说明。

示例输出：

```text
今日结论：谨慎小额定投。

中证A500：
- 当前仓位低于目标仓位
- 趋势尚可
- 可小额买入 1500 元

科创50：
- 当前仓位 18%，接近20%上限
- 近5日涨幅偏高
- 暂停加仓

当前总仓位：
- 总仓位 35%
- 现金仓位 65%
- 仍有补仓空间，但不建议急于打满
```

---

# 22. 后续升级方向

第一版稳定后，再考虑：

```text
1. 接入真实 Tushare 数据
2. 使用 index_code 补全 ETF 上市前的长期历史
3. 加入 volatility_score 打分（需回测验证）
4. 跨境 ETF 启用 enabled_for_signal，接入汇率、溢价率、海外指数同步
5. 加入基金估值分位
6. 加入指数 PE/PB 分位
7. 加入组合回测
8. 加入定投日历
9. 接入企业微信/Bark/Telegram 推送
10. 接入大模型 API 生成复盘
11. 加入 Notion/飞书同步
12. 增加多策略回测对比
```

---

# 23. 风险提示

本系统只用于辅助投资纪律管理，不构成投资建议。

系统输出的“可买入”“暂停买入”“小额定投”等信号，都是基于预设规则生成，不代表未来一定上涨。

最终交易必须由用户自行判断。

投资中最重要的是：

```text
控制仓位
长期纪律
分批执行
避免满仓
避免追涨杀跌
保留现金
定期复盘
```

---

# 24. 开发优先级总结

按照重要程度排序（**2026-05-23 更新**）：

```text
P0（阶段 1-5，已完成 ✅）：
- 数据库初始化（含 fund_code / review_status / account_snapshot）
- ETF 标的池（symbol ↔ fund_code 映射）
- 行情数据（AKShare + mock）
- 指标计算（含历史不足降级）
- Streamlit 四页：数据看板 / 持仓录入 / 仓位管理 / 策略信号
- 手动录入现金/持仓 + 仓位风控（signal_status / risk_status）
- 策略打分与 discipline 信号（volatility_score=0、review_status）
- UI 中文化（src/ui/labels.py）
- pytest 覆盖指标、仓位、策略、建议金额

P1（阶段 6-8，当前重点 ⏳）：
- 交易日志（signal_id 关联）
- review_status = executed 流转
- 日报 / 周复盘模板
- 看板页面整合

P2：
- AI 复盘
- APScheduler 定时任务
- 手机提醒

P3：
- 多数据源 / index_code 补历史
- 跨境 ETF 完整逻辑 / volatility_score 回测
- Notion 同步 / 云端部署
```

---

这份文档已纳入 v1 冻结口径。**阶段一至阶段五已完成**；下一步为阶段六（交易日志）及日报/周报，避免在未验收的数据管道上叠加不可维护功能。
