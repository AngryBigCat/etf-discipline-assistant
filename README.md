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
- AKShare 行情采集（东方财富优先，失败自动切新浪）
- `PRICE_DATA_SOURCE=mock` 时可用 mock 数据（仅开发/测试）
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

### 阶段 8：AI 复盘

- 基于日报/周报、交易日志、策略信号与仓位状态生成 AI 复盘解释
- 默认 `MockLLMClient`，无 API Key 也可离线使用
- 可选 `LLM_PROVIDER=openai_compatible` 接入 OpenAI 兼容 API，失败时 fallback mock
- 写入 `ai_review` 表，支持同日/同周 upsert 覆盖
- CLI：`scripts/generate_ai_daily_review.py`、`scripts/generate_ai_weekly_review.py`
- Streamlit「AI复盘」页：生成/查看日复盘与周复盘、历史列表
- 输出经 `safety.py` 校验，自动追加「不构成投资建议」，危险词会被屏蔽
- AI 仅用于纪律解释与行为复盘，**不决定买卖、不修改持仓/信号/交易日志**

### 阶段 9：回测模块

- 基于历史 `daily_price` 模拟不同定投纪律策略的表现（只读行情，不写真实持仓/交易日志）
- 三种策略：普通定投（`baseline_dca`）、均线过滤定投（`ma_filter_dca`）、回撤加仓定投（`drawdown_boost`）
- 支持 weekly / monthly 定投频率；成交价=当日 close，不含手续费/滑点
- 指标：期末资产、累计投入、总收益率、年化收益率、最大回撤、交易次数、平均成本、资金利用率
- 展示兼容空值：历史记录缺少 `cash_utilization` 等字段时显示「—」，不显示 `nan%`
- 写入 `backtest_run` / `backtest_result` / `backtest_trade` / `backtest_equity_curve`
- CLI：`scripts/run_backtest.py`
- Streamlit「回测分析」页：参数配置、收益摘要、总资产/回撤曲线、模拟交易记录、历史回测
- **回测仅用于历史规则验证，不代表未来收益，不构成投资建议**

### 阶段 9.1：历史行情补全与多策略对比

- 历史行情补全 CLI：`scripts/backfill_prices.py`（东方财富优先，失败自动切新浪；内置直连/代理重试）
- 支持单标的或全部启用标的补全，重复运行 upsert 不产生重复数据
- 回测加载行情时会自动清洗：`close <= 0`、空值、重复日期、新浪节假日错价（相对近 20 日 median 偏低 >12% 的低价点）
- 清洗过滤会在日志中提示「已过滤 X 条无效行情数据」；修改清洗逻辑后需**重新跑回测**，旧历史记录的曲线不会自动更新
- 多策略对比：同一标的/区间/资金参数下并行运行多个回测策略
- 新增指标：资金利用率（`total_invested / initial_cash`）
- 回测页支持「单策略回测 / 多策略对比」两种模式
- 对比结果展示表格 + 多策略总资产/回撤曲线
- 历史回测记录展示收益率、最大回撤、资金利用率等关键指标
- **补全与回测结果均不代表未来收益，不构成投资建议**

### 阶段 9.2：组合回测

- 多 ETF 组合历史回测：验证 A500、红利 ETF、科创50 等组合在历史中的收益、回撤、资金利用率、仓位偏离和再平衡效果
- 组合策略：`portfolio_dca`（组合定投）、`portfolio_rebalance`（组合定投 + 再平衡）
- 定投金额按 ETF 目标权重归一化分配；现金目标权重仅用于风险展示，不参与每期定投分配
- 多标的行情取共同可用区间（各标的有效数据起止日的交集），至少 2 个有效标的、至少 30 个交易日
- 写入 `backtest_run`（`symbol=PORTFOLIO`）/ `backtest_result` / `backtest_trade` / `backtest_equity_curve` / `backtest_position`
- CLI：`scripts/run_portfolio_backtest.py`
- Streamlit「回测分析」页：
  - 单策略回测 / 多策略对比 / 组合回测
  - 组合回测 `symbol=PORTFOLIO` 在 UI 显示为「组合」；组合摘要不展示无意义的「平均成本」
  - 组合再平衡阈值仅在「组合定投 + 再平衡」策略下显示
- **组合回测只用于历史规则验证，不代表未来收益，不构成投资建议；不得根据回测结果自动调整真实配置或自动交易**

### 阶段 10：任务中心

- 根据系统当前状态自动生成每日 / 每周 / 风险类流程任务（行情、持仓、信号、报告、AI 复盘、仓位风险等）
- 写入 `task_item` 表；支持标记完成 / 跳过，已完成任务刷新后不会被重置
- 任务生成去重：行情过期只生成「更新行情数据」；未审核信号只保留汇总「审核策略信号」任务
- CLI：`scripts/generate_tasks.py`
- Streamlit「任务中心」页：
  - 顶部概览：待处理 / 已完成 / 已跳过 / 高优先级
  - **今日任务**：待处理且非 risk，卡片式展示（描述 + 操作按钮一体）
  - **风险任务**：待处理 risk 任务，高优先级默认展开
  - **历史任务**：表格展示最近 100 条已完成 / 已跳过记录（不含待处理）
  - 状态与优先级使用 emoji badge（🟡 待处理、🟢 已完成、🔴 高 等）
- **任务中心只做流程提醒，不构成投资建议，不会自动交易，不做外部推送**

### 阶段 10.1：任务中心快捷执行

- 为安全任务提供「执行任务」按钮：行情更新、策略信号生成、日报/周报、AI 日复盘/周复盘
- 执行白名单见 `src/tasks/actions.py`；持仓录入、信号审核、交易记录、仓位风险类任务仅显示前往处理说明
- 执行过程写入 `task_action_log`；成功后自动标记任务完成并刷新列表
- 工作流函数位于 `src/workflows/daily_workflow.py`，CLI 脚本与任务中心共用
- **涉及持仓、交易、审核的任务仍需人工处理，任务中心不会自动交易或自动审核**

### 阶段 11：系统设置 / 配置中心

- 新增 Streamlit「系统设置」页，集中维护投资纪律参数
- 配置编辑 service（`src/config/editor.py`）：读取、校验、保存 `config/app.yaml`，保存前自动备份到 `backups/config/`
- 可编辑：计划总投入、现金缓冲比例、基准货币、ETF 名称/角色/是否参与策略信号/目标仓位/最大仓位、策略分数阈值与均线参数
- 只读展示：回撤窗口、反追高参数、AI 提供商/模型、API Key 配置状态（**不展示 API Key 明文**）
- **修改配置不会自动交易，不会自动修改持仓/交易日志/策略信号；不构成投资建议**

### 阶段 11.1：标的管理增强

- 系统设置页支持**新增标的**（写入配置草稿后需点击保存）与**停用标的**（`enabled=false`，不物理删除）
- 保存配置后自动同步 `etf_universe`；**不删除**旧标的、历史行情、交易或持仓记录
- 校验增强：symbol 唯一、停用标的不计入权重合计、参与策略信号需启用且填写基金代码
- 新增标的且填写 `fund_code` 后，页面提示运行 `backfill_prices.py` 补全历史行情（**不自动拉行情**）
- **新增标的不自动交易，不自动生成投资建议**

### 阶段 11.2：标的池数据库化

- **`etf_universe` 为标的池唯一主数据源**；系统设置页新增 / 编辑 / 停用标的直接读写数据库
- 标的池 `assets` **已迁移为** `config/assets.seed.yaml`（初始化种子文件）；系统主配置位于 `config/app.yaml`
- 初始化脚本：`scripts/seed_data.py`、`scripts/sync_assets_from_seed.py`（旧 `sync_assets_from_config.py` 仍兼容）
- 保存系统配置（`save_editable_config`）**不再写入或覆盖** 标的池配置，也不会同步覆盖 `etf_universe`
- 校验逻辑位于 `src/assets/validator.py`；仓库操作位于 `src/db/repository.py`
- 行情更新、策略信号、任务中心、回测选择、持仓录入等优先从 `etf_universe` 读取
- **停用标的不删除历史行情 / 交易 / 持仓 / 策略信号**

### 阶段 12：定时任务 / 自动流程编排

- 新增独立进程 `scripts/scheduler_worker.py`，使用 APScheduler 在 Linux 服务器中调度安全流程
- 默认任务：`daily_after_close`（工作日 16:30）、`weekly_review`（周五 17:30，Asia/Shanghai）
- 流程编排位于 `src/workflows/pipelines.py`，复用 `src/workflows/daily_workflow.py` 与任务刷新逻辑
- 任务配置与运行日志持久化到 `scheduler_job_config` / `scheduler_run_log`
- Streamlit「定时任务」页支持查看任务、启用/停用、立即执行、查看最近 100 条日志
- 手动测试：`python scripts/run_scheduled_job.py --job daily_after_close`
- Linux 部署说明见 [`docs/deployment-linux.md`](docs/deployment-linux.md)
- **定时任务不会自动交易，不会自动修改真实持仓，不会自动审核策略信号；不构成投资建议**

### 阶段 13.1：邮件通知提醒

- 新增 `src/notifications/`，基于 Python 标准库 `smtplib` / `EmailMessage` 发送邮件
- 邮件配置全部从 `.env` 读取，**不写入** `config/app.yaml` 或数据库
- 通知日志持久化到 `notification_log`；收件人脱敏保存，不保存 SMTP 密码
- 集成场景：定时任务失败/成功、高优先级任务、仓位风险、每日流程完成
- Streamlit「通知中心」页：查看配置状态、发送测试邮件、查看最近 100 条通知日志
- **邮件只做流程提醒，不构成投资建议，不会自动交易**

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
- AI复盘
- 回测分析
- 任务中心
- 定时任务
- 通知中心
- 系统设置

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

## 配置说明

配置文件统一放在 `config/` 目录：

- **`config/app.yaml`**：系统主配置（计划总投入、现金缓冲、策略阈值、仓位参数等；可在 Streamlit「系统设置」页编辑并保存，保存前会自动备份）
- **`config/assets.seed.yaml`**：默认标的池种子（仅用于初始化导入，不是日常编辑源）
- **`etf_universe`（数据库）**：运行时标的池主数据源

`config/app.yaml` 主要包含：

- 计划总投入、现金缓冲比例、基准货币
- 策略分数阈值与均线参数
- 单次买入比例等纪律参数

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
- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`
- `LLM_TIMEOUT`（默认 60 秒）
- `EMAIL_ENABLED` / `EMAIL_SMTP_*` / `EMAIL_FROM` / `EMAIL_TO` — 邮件通知（SMTP 密码仅放 `.env`）
- `NOTIFY_ON_*` — 各类通知开关（定时任务失败、高优先级任务、仓位风险等）

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

## 未来蓝图与目标

当前项目已经形成个人 ETF 投资纪律工具的完整闭环：

数据采集 → 指标计算 → 持仓录入 → 仓位管理 → 策略信号 → 交易日志 → 报告复盘 → AI 复盘 → 回测分析 → 任务中心 → 定时任务 → 系统设置。

后续目标不是把系统做成自动交易机器人，而是继续增强“纪律执行、流程自动化、风险提醒、长期复盘”的能力。

### 阶段 13：外部提醒与通知

目标：让系统在关键流程和风险事件出现时，主动提醒用户查看，而不是自动交易。

计划能力：

- 邮件提醒
- Telegram / Bark / 企业微信提醒
- 每日收盘后流程完成提醒
- 策略信号生成提醒
- 仓位超限提醒
- 数据更新失败提醒
- 定时任务失败提醒
- AI 复盘生成完成提醒

边界：

- 只提醒，不自动交易
- 不发送“必须买入 / 必须卖出”指令
- 不在提醒中承诺收益

### 阶段 14：定时任务增强与运维能力

目标：让 Linux 服务器部署更稳定，方便长期无人值守运行。

计划能力：

- 定时任务重试机制
- 定时任务失败原因分类
- 任务运行耗时统计
- 最近 N 次运行成功率
- 节假日 / 非交易日识别
- 手动补跑某一天流程
- systemd 部署模板完善
- 日志文件轮转
- 数据库备份任务

边界：

- systemd 只做进程保活
- APScheduler 仍作为 Python 内部调度器
- 不引入复杂分布式任务系统，除非未来确实需要

### 阶段 15：外部提醒与任务中心联动

目标：把任务中心从“站内待办”扩展为“站内 + 外部提醒”的工作流入口。

计划能力：

- 任务中心高优先级任务外部提醒
- 未完成任务每日汇总提醒
- 定时任务失败自动生成风险任务
- 仓位超限提醒自动进入任务中心
- 报告 / AI 复盘生成后提醒查看
- 提醒频率控制，避免骚扰

边界：

- 外部提醒不包含 API Key 明文
- 不把提醒写成投资建议
- 不根据提醒自动修改任务状态

### 阶段 16：高级组合管理

目标：让系统更接近真实长期投资组合管理。

计划能力：

- 定投日历
- 组合再平衡计划
- 目标仓位偏离趋势
- 再平衡模拟与实际执行对比
- 核心仓 / 防守仓 / 卫星仓分层统计
- QDII ETF 溢价提醒
- 汇率影响提示
- 黄金 / 债券 / 货币基金等低相关资产支持
- 不同组合方案对比

边界：

- 再平衡计划只做提醒和模拟
- 不自动卖出或买入
- 不根据回测结果自动调整真实配置

### 阶段 17：数据质量、备份与恢复

目标：提高长期使用的可靠性。

计划能力：

- 数据质量检查页
- 行情缺失检测
- 异常价格检测报告
- 数据库自动备份
- 配置备份查看与恢复
- 标的池变更审计
- 策略参数变更审计
- 回测结果版本管理
- 一键导出数据包

边界：

- 不自动删除历史数据
- 数据修复需要用户确认
- 配置恢复前必须备份当前配置

### 阶段 18：多账户与多组合

目标：支持用户管理多个账户、多个投资计划。

计划能力：

- 多账户记录
- 多组合配置
- 账户级持仓快照
- 组合级目标仓位
- 不同账户的纪律统计
- 家庭账户 / 养老金账户 / 普通投资账户分开管理
- 组合之间的资产重复度分析

边界：

- 不接券商实盘接口
- 不自动同步真实账户
- 账户数据由用户手动录入或导入

### 阶段 19：导入导出与开放数据接口

目标：降低长期维护成本，提高数据可迁移性。

计划能力：

- CSV / Excel 导入持仓
- CSV / Excel 导入交易记录
- 导出交易日志
- 导出策略信号
- 导出日报 / 周报 / AI 复盘
- 导出回测结果
- 本地 API 或命令行接口增强

边界：

- 导入数据必须校验
- 导入交易日志不自动修改持仓快照
- 导入持仓快照不自动生成交易记录

### 长期不做事项

本项目长期保持以下边界：

- 不做自动交易
- 不接券商实盘下单接口
- 不做高频交易
- 不做个股荐股
- 不承诺收益
- 不把 AI 作为买卖决策主体
- 不根据回测结果自动修改真实投资配置
- 不自动修改真实持仓、交易日志或策略审核状态