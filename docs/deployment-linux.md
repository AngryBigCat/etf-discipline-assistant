# Linux 部署说明

本文说明如何在 Linux 服务器上分别运行 Streamlit 前端与定时任务 Worker。

## 前置条件

- Python 3.10+
- 已创建虚拟环境并安装依赖：`pip install -r requirements.txt`
- 已初始化数据库与标的池：

```bash
python scripts/init_db.py
python scripts/seed_data.py
python scripts/sync_assets_from_seed.py
```

## 1. 启动 Streamlit

```bash
streamlit run app.py --server.port 8501
```

Streamlit 仅负责 Web 界面，**不要在 Streamlit 进程内启动 APScheduler**。

## 2. 启动 Scheduler Worker

```bash
python scripts/scheduler_worker.py
```

Worker 启动后会：

1. 初始化数据库 schema
2. 写入默认定时任务（`daily_after_close`、`weekly_review`）
3. 读取已启用任务并注册 APScheduler
4. 以前台 BlockingScheduler 持续运行

日志会输出每个任务的 cron 表达式与下一次运行时间。

## 3. 手动执行单个任务（测试）

```bash
python scripts/run_scheduled_job.py --job daily_after_close
python scripts/run_scheduled_job.py --job weekly_review
```

执行结果写入 `scheduler_run_log` 表，可在 Streamlit「定时任务」页查看。

## 4. systemd 托管 Scheduler

示例 unit 文件 `/etc/systemd/system/etf-assistant-scheduler.service`：

```ini
[Unit]
Description=ETF Assistant Scheduler
After=network.target

[Service]
WorkingDirectory=/opt/etf-discipline-assistant
ExecStart=/opt/etf-discipline-assistant/.venv/bin/python scripts/scheduler_worker.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable etf-assistant-scheduler
sudo systemctl start etf-assistant-scheduler
sudo systemctl status etf-assistant-scheduler
```

## 5. 重要说明

- **systemd 只负责进程保活**，任务调度由 Python APScheduler 在 Worker 进程内完成。
- 若服务器停机，错过的任务会按 `misfire_grace_time`（默认 3600 秒）处理。
- 定时任务只执行行情更新、信号生成、报告生成、任务刷新等**安全流程**。
- **不会自动交易**，不会自动修改真实持仓，不会自动审核策略信号。
- 配置文件默认位于 `config/app.yaml`，可通过 `CONFIG_PATH` 覆盖。

## 6. 默认任务

| job_key | 名称 | cron | 说明 |
|---------|------|------|------|
| `daily_after_close` | 每日收盘后流程 | `30 16 * * mon-fri` | 行情 → 信号 → 任务 → 日报 → AI 日复盘 |
| `weekly_review` | 每周复盘流程 | `30 17 * * fri` | 周报 → AI 周复盘 → 任务刷新 |

时区默认 `Asia/Shanghai`。
