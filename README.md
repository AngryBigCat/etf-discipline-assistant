# ETF投资纪律助手

## 项目定位

面向个人投资者的 ETF **投资纪律管理工具**：行情与指标、持仓与仓位、策略信号、交易日志、报告与 AI 复盘、回测、任务与定时流程。

**不是**自动交易机器人或荐股系统；系统只提供纪律建议，最终交易由用户人工确认。

- 路线图与阶段计划：[`ROADMAP.md`](ROADMAP.md)
- AI 开发约束：[`AGENTS.md`](AGENTS.md)

## 核心原则

- 不自动下单，不接券商实盘
- 不做高频交易、个股荐股、收益承诺
- 不把 AI 作为买卖决策主体
- 回测与提醒仅作纪律辅助，不构成投资建议

当前已实现阶段 1–12 与 13.1（邮件通知），功能摘要见 [路线图 · 里程碑状态](ROADMAP.md#里程碑状态)。

## 当前页面

- 数据看板 · 持仓录入 · 仓位管理 · 策略信号 · 交易日志
- 报告复盘 · AI复盘 · 回测分析 · 任务中心
- 定时任务 · 通知中心 · 系统设置

## 运行方式

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts/init_db.py
python scripts/seed_data.py
python scripts/sync_assets_from_seed.py
python scripts/daily_update.py
python scripts/generate_signals.py
python scripts/generate_daily_report.py
python scripts/generate_weekly_report.py
python scripts/generate_ai_daily_review.py
python scripts/generate_ai_weekly_review.py
python scripts/generate_tasks.py
python scripts/run_scheduled_job.py --job daily_after_close
python scripts/run_scheduled_job.py --job weekly_review
python scripts/scheduler_worker.py
python scripts/backfill_prices.py --symbol A500 --start 2021-01-01 --end 2026-05-23
python scripts/run_backtest.py
python scripts/run_portfolio_backtest.py --start 2021-01-01 --end 2026-05-23 --cash 100000 --amount 3000 --frequency monthly

pytest
streamlit run app.py
```

任务中心 CLI 示例：

```bash
python scripts/generate_tasks.py
python scripts/generate_tasks.py --date 2026-05-23
```

回测 CLI 示例：

```bash
python scripts/backfill_prices.py --symbol A500 --start 2021-01-01 --end 2026-05-23
python scripts/backfill_prices.py --all --start 2021-01-01 --end 2026-05-23
python scripts/run_backtest.py --symbol A500 --strategy baseline_dca --start 2021-01-01 --end 2026-05-23 --cash 100000 --amount 3000 --frequency monthly
python scripts/run_portfolio_backtest.py --start 2021-01-01 --end 2026-05-23 --cash 100000 --amount 3000 --frequency monthly --strategy portfolio_dca --assets A500:0.5,DIVIDEND:0.2,KC50:0.1
```

若补全失败并提示系统代理（如 `127.0.0.1:7890`），请确认 Clash/V2Ray 等代理软件已启动；国内网络也可尝试关闭 Windows「使用代理服务器」后重试。

Linux 服务器部署（Streamlit + 独立 Scheduler 进程）见 [`docs/deployment-linux.md`](docs/deployment-linux.md)。
Docker Compose 部署（`etf-web` + `etf-scheduler` + 一次性 `etf-init`）见 [`docs/deployment-docker.md`](docs/deployment-docker.md)。

## 配置说明

配置文件统一放在 `config/` 目录：

- **`config/app.yaml`**：系统主配置（计划总投入、现金缓冲、策略阈值、仓位参数等；可在 Streamlit「系统设置」页编辑并保存，保存前会自动备份）
- **`config/assets.seed.yaml`**：默认标的池种子（仅用于初始化导入，不是日常编辑源）
- **`etf_universe`（数据库）**：运行时标的池主数据源

`config/app.yaml` 主要包含：计划总投入、现金缓冲比例、基准货币、策略分数阈值与均线参数、单次买入比例等纪律参数。

说明：

- **`etf_universe` 是标的池主数据源**；默认标的见 `config/assets.seed.yaml`，通过 `scripts/sync_assets_from_seed.py` 导入
- 系统设置页的标的池增删改直接写入数据库，**不会写回** `config/assets.seed.yaml` 或 `config/app.yaml`
- API Key 仅通过 `.env` 配置；系统设置页只显示「已配置 / 未配置」，**不会展示 API Key 明文**
- 可通过 `CONFIG_PATH` 环境变量覆盖主配置文件路径（相对路径基于项目根目录解析）

可选环境变量在 `.env`（可复制 `.env.example` 后修改，**不要提交 `.env` 到 Git**）：

- `DATABASE_PATH`
- `CONFIG_PATH`（默认 `config/app.yaml`）
- `PRICE_DATA_SOURCE=auto|akshare|mock`（默认 `auto`：东方财富 → 新浪，失败报错；`mock` 仅用于离线测试）
- `LLM_PROVIDER=mock|openai_compatible`
- `LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL` / `LLM_TIMEOUT`（默认 60 秒）
- `EMAIL_ENABLED` / `EMAIL_SMTP_*` / `EMAIL_FROM` / `EMAIL_TO` — 邮件通知（SMTP 密码仅放 `.env`）
- `NOTIFY_ON_*` — 各类通知开关（定时任务失败、高优先级任务、仓位风险等）

标的 `enabled` / `enabled_for_signal` 语义见 [路线图 · 已实现能力要点](ROADMAP.md#已实现能力要点)。

## 对接 DeepSeek 官方 API 测试

AI 复盘默认使用 `mock` 模式，**不需要 API Key**，离线可跑 pytest 与 Streamlit。

若要接入 DeepSeek 官方 API 做真实复盘测试：

1. 复制 `.env.example` 为 `.env`（`.gitignore` 已忽略 `.env`，请勿提交密钥）
2. 在 `.env` 中设置：

```bash
LLM_PROVIDER=openai_compatible
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY=your_deepseek_api_key
LLM_MODEL=deepseek-v4-flash
LLM_TIMEOUT=60
```

3. 先生成日报/周报，再运行 AI 复盘 CLI 或在 Streamlit「AI复盘」页点击生成

说明：

- 推荐先用 `deepseek-v4-flash` 做联调，成本与延迟较低
- 若 API 调用失败，系统会 fallback 到 mock，不影响页面与测试
- AI 复盘**仅用于纪律总结与行为复盘**，不构成投资建议，**不会自动交易**，也不会修改持仓、信号或交易日志
