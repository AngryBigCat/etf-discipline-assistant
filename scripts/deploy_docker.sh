#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE=(docker compose)
SERVICES=(etf-web etf-scheduler)
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8501/_stcore/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-2}"
SKIP_BUILD=0
SKIP_INIT=0

usage() {
  cat <<'EOF'
用法:
  bash scripts/deploy_docker.sh [选项]

选项:
  --skip-build    跳过镜像构建，要求本机已有 etf-discipline-assistant:latest
  --skip-init     跳过 etf-init 初始化
  -h, --help      显示帮助

环境变量:
  HEALTH_URL          Web 健康检查地址，默认 http://127.0.0.1:8501/_stcore/health
  HEALTH_RETRIES      健康检查重试次数，默认 30
  HEALTH_INTERVAL     健康检查间隔秒数，默认 2

说明:
  脚本只部署 Streamlit Web 与独立 Scheduler Worker，不会自动交易。
EOF
}

log() {
  printf '[deploy] %s\n' "$1"
}

die() {
  printf '[deploy][error] %s\n' "$1" >&2
  exit 1
}

for arg in "$@"; do
  case "$arg" in
    --skip-build)
      SKIP_BUILD=1
      ;;
    --skip-init)
      SKIP_INIT=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "未知参数: $arg"
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  die "未找到 docker，请先安装 Docker。"
fi

if ! docker compose version >/dev/null 2>&1; then
  die "未找到 docker compose，请先安装 Docker Compose。"
fi

if [ ! -f docker-compose.yml ]; then
  die "当前目录不是项目根目录，缺少 docker-compose.yml。"
fi

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    log "未发现 .env，已从 .env.example 创建。请按需编辑 LLM / EMAIL / SMTP 配置。"
  else
    die "缺少 .env，且未找到 .env.example。"
  fi
fi

mkdir -p data backups logs

if [ "$SKIP_BUILD" -eq 0 ]; then
  log "构建 Docker 镜像..."
  "${COMPOSE[@]}" build
else
  log "跳过镜像构建。"
fi

if [ "$SKIP_INIT" -eq 0 ]; then
  log "初始化数据库与默认标的池..."
  "${COMPOSE[@]}" run --rm etf-init
else
  log "跳过 etf-init 初始化。"
fi

log "启动长期服务: ${SERVICES[*]}..."
"${COMPOSE[@]}" up -d "${SERVICES[@]}"

log "等待 Web 健康检查: $HEALTH_URL"
for attempt in $(seq 1 "$HEALTH_RETRIES"); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    log "Web 健康检查通过。"
    "${COMPOSE[@]}" ps
    log "部署完成。访问地址: http://服务器IP:8501"
    exit 0
  fi
  sleep "$HEALTH_INTERVAL"
  log "等待 Web 启动中... ($attempt/$HEALTH_RETRIES)"
done

"${COMPOSE[@]}" ps
die "Web 健康检查未通过，请查看日志: docker compose logs -f etf-web etf-scheduler"
