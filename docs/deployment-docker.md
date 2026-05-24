# Docker 部署说明

本文说明如何用同一个镜像启动三个 Compose 服务：

- `etf-init`：一次性初始化数据库，并从 `config/assets.seed.yaml` 导入默认标的池
- `etf-web`：Streamlit Web 服务
- `etf-scheduler`：独立 APScheduler Worker

系统只用于投资纪律辅助，不构成投资建议；Docker 部署不会自动交易，不会接入券商接口，也不会在 Streamlit 进程内启动 scheduler。

## 前置条件

- Linux 服务器已安装 Docker 与 Docker Compose
- 项目目录包含 `config/app.yaml` 与 `config/assets.seed.yaml`
- 已准备 `.env`，用于运行时注入 LLM、EMAIL、SMTP 等敏感配置

首次部署可复制示例配置：

```bash
cp .env.example .env
```

请只在 `.env` 中填写 API Key、SMTP 密码等敏感信息。`.env` 已被 `.dockerignore` 排除，不会写入镜像。

## 目录与持久化

Compose 默认挂载以下目录：

| 宿主机目录 | 容器目录 | 用途 |
| --- | --- | --- |
| `./config` | `/app/config` | 主配置与标的池种子文件 |
| `./data` | `/app/data` | SQLite 数据库 |
| `./backups` | `/app/backups` | 配置备份 |
| `./logs` | `/app/logs` | 运行日志预留目录 |

默认路径：

- `DATABASE_PATH=data/etf_assistant.db`
- `CONFIG_PATH=config/app.yaml`

如需覆盖路径，请在 `.env` 中设置。相对路径会按容器内项目根目录 `/app` 解析。

## 构建镜像

推荐直接使用一键部署脚本：

```bash
bash scripts/deploy_docker.sh
```

脚本会依次完成：准备 `.env` 与持久化目录、构建镜像、运行 `etf-init`、启动 `etf-web` 和 `etf-scheduler`、检查 Web 健康状态。

若服务器已经有镜像，可跳过构建：

```bash
bash scripts/deploy_docker.sh --skip-build
```

若确认数据库与标的池已经初始化，可跳过初始化：

```bash
bash scripts/deploy_docker.sh --skip-init
```

也可以手动执行以下步骤。

## 手动构建镜像

```bash
docker compose build
```

## 初始化数据库与标的池

```bash
docker compose run --rm etf-init
```

`etf-init` 只执行：

```bash
python scripts/init_db.py
python scripts/sync_assets_from_seed.py
```

不会删除历史数据；标的池同步默认不会覆盖用户已停用的标的。

## 启动长期服务

```bash
docker compose up -d etf-web etf-scheduler
```

访问：

```text
http://服务器IP:8501
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f etf-web
docker compose logs -f etf-scheduler
```

## 单独操作

重启 Web：

```bash
docker compose restart etf-web
```

重启 Scheduler：

```bash
docker compose restart etf-scheduler
```

手动执行定时任务：

```bash
docker compose run --rm etf-scheduler python scripts/run_scheduled_job.py --job daily_after_close
docker compose run --rm etf-scheduler python scripts/run_scheduled_job.py --job weekly_review
```

停止服务：

```bash
docker compose down
```

`docker compose down` 不会删除 `./data`、`./config`、`./backups`、`./logs` 目录中的宿主机数据。

## 安全边界

- `.env` 只在容器运行时注入，不写入镜像。
- SMTP 密码、LLM API Key 不应提交到 Git，也不应写入 Dockerfile 或 Compose 明文字段。
- `docker compose config` 可能展开 `.env` 中的运行时变量，排障输出不要对外粘贴。
- `etf-web` 只运行 Streamlit。
- `etf-scheduler` 只运行独立 APScheduler Worker。
- 定时任务只执行安全 pipeline，不会自动下单、不会自动修改真实持仓、不会自动审核策略信号。
- `etf-init` 只做 schema 初始化和默认标的池导入，不做交易动作。
