# ETF投资纪律助手

个人 ETF 投资纪律管理系统（非自动交易、非荐股）。

当前版本：**阶段 4** — 在阶段 1-3 数据管道基础上，支持手动录入现金/持仓与仓位管理。

## 功能

### 阶段 1-3
- ETF 标的池（symbol / fund_code / exchange）
- AKShare 行情采集，失败时 mock 兜底
- 指标：MA20/60/120/250、回撤、20 日波动率、5/10/20 日收益率
- 历史不足时 `confidence_level=low`，不中断流程

### 阶段 4
- Streamlit 三页：数据看板 / 持仓录入 / 仓位管理
- 手动录入 `cash_value` 与 ETF `quantity/cost`
- 自动计算 `latest_price * quantity` 市值（无最新价时可手动填市值）
- 保存 `account_snapshot` + `holding_snapshot`（同日 upsert）
- 仓位总览、目标偏离、max_weight 状态（含 `watch_only` 观察标的）

### enabled 语义
- `enabled=false`：隐藏，不采集，不展示
- `enabled=true, enabled_for_signal=false`：可展示/录入，状态为 `watch_only`
- `enabled=true, enabled_for_signal=true`：正常仓位计算

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
streamlit run app.py
pytest
```

Streamlit 侧边栏页面：
1. **app** — 数据看板（标的、行情、指标）
2. **持仓录入** — 录入现金与 ETF 持仓，保存快照
3. **仓位管理** — 查看账户总览与仓位状态

## 配置

- `config.yaml`：标的池与策略参数
- `.env`：可选 `DATABASE_PATH`、`PRICE_DATA_SOURCE=auto|akshare|mock`

## 风险提示

本系统输出仅供参考，不构成投资建议。最终交易需用户自行判断。
