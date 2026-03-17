#!/usr/bin/env bash
# Plane 本地开发一键启动脚本
# 使用方式: 在仓库根目录执行 bash docs/plane-forge/plans/scripts/local-dev-start.sh
#
# 新机器零配置启动：自动检测环境、生成 .env、修正已知问题、构建镜像、启动服务
# 自动检测本机局域网 IP，局域网设备可直接访问
# 退出时自动还原所有 .env 为 localhost
#
# 为什么不能直接 pnpm dev？
# pnpm dev = turbo run dev，turbo 会同时启动 packages(tsdown --watch) 和 apps。
# tsdown --watch 启动时先清空 dist 再重建，apps 同时启动去解析包时 dist 已被清空。
# pnpm --filter 也不行，turbo 的 ^build 依赖仍会触发 packages 重建。
# 正确做法：先构建 packages，再用 pnpm -C 直接启动各 app（绕过 turbo）。

set -e

COMPOSE_FILE="docker-compose-local.yml"
# 自动获取本机局域网 IP，获取失败则用 localhost（仅本机访问）
DEV_HOST=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
DEV_HOST="${DEV_HOST:-localhost}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# 前端 .env: 可以安全地全局替换 localhost
FRONTEND_ENVS="apps/web/.env apps/admin/.env apps/space/.env"

# API .env 中需要替换的 key（排除 CORS，CORS 用追加方式）
API_URL_KEYS="WEB_URL ADMIN_BASE_URL SPACE_BASE_URL APP_BASE_URL LIVE_BASE_URL"

# ─── 前置检查 ────────────────────────────────────────────────────────────────

# 检查是否在仓库根目录
if [ ! -f "$COMPOSE_FILE" ]; then
  err "请在仓库根目录下运行此脚本"
  exit 1
fi

check_prerequisites() {
  local missing=()

  if ! command -v docker &>/dev/null; then
    missing+=("docker (https://docs.docker.com/get-docker/)")
  elif ! docker info &>/dev/null; then
    err "Docker 未启动，请先启动 Docker Desktop"
    exit 1
  fi

  if ! command -v node &>/dev/null; then
    missing+=("node (https://nodejs.org/)")
  fi

  if ! command -v pnpm &>/dev/null; then
    # 尝试通过 corepack 启用
    if command -v corepack &>/dev/null; then
      info "启用 pnpm (via corepack)..."
      corepack enable pnpm
    else
      missing+=("pnpm (npm install -g pnpm)")
    fi
  fi

  if [ ${#missing[@]} -gt 0 ]; then
    err "缺少以下工具，请先安装："
    for tool in "${missing[@]}"; do
      echo "  - $tool"
    done
    exit 1
  fi

  info "前置检查通过 (docker, node, pnpm)"
}

# ─── 初始化 .env ──────────────────────────────────────────────────────────────

init_env_files() {
  # 如果 apps/api/.env 已存在，跳过初始化
  if [ -f "apps/api/.env" ]; then
    info ".env 文件已存在，跳过初始化"
    return
  fi

  info "首次启动，初始化 .env 文件..."

  # 复制所有 .env.example → .env
  local services=("" "web" "api" "space" "admin" "live")
  for service in "${services[@]}"; do
    if [ "$service" = "" ]; then
      prefix="./"
    else
      prefix="./apps/$service/"
    fi
    if [ -f "${prefix}.env.example" ]; then
      cp "${prefix}.env.example" "${prefix}.env"
      info "  已创建 ${prefix}.env"
    fi
  done

  # 生成 Django SECRET_KEY
  SECRET_KEY=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c50)
  echo "SECRET_KEY=\"$SECRET_KEY\"" >> ./apps/api/.env
  info "  已生成 SECRET_KEY"

  # 修正 .env.example 的已知问题
  fix_env_defaults
}

fix_env_defaults() {
  local env_file="apps/api/.env"

  info "修正 .env 已知问题..."

  # 1. CORS: 添加 127.0.0.1 地址（Vite 默认绑定 127.0.0.1，不加会 CORS 报错）
  if ! grep "^CORS_ALLOWED_ORIGINS" "$env_file" | grep -q "127.0.0.1"; then
    sed -i '' 's|^CORS_ALLOWED_ORIGINS="\(.*\)"|CORS_ALLOWED_ORIGINS="\1,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002,http://127.0.0.1:3100"|' "$env_file"
    info "  CORS: 已添加 127.0.0.1 地址"
  fi

  # 2. MinIO: localhost → Docker 内部地址（容器内 localhost 不是宿主机）
  if grep -q '^AWS_S3_ENDPOINT_URL="http://localhost:9000"' "$env_file"; then
    sed -i '' 's|^AWS_S3_ENDPOINT_URL="http://localhost:9000"|AWS_S3_ENDPOINT_URL="http://plane-minio:9000"|' "$env_file"
    info "  MinIO: localhost → plane-minio"
  fi

  # 3. USE_MINIO: 0 → 1（本地开发需要启用）
  if grep -q '^USE_MINIO=0' "$env_file"; then
    sed -i '' 's|^USE_MINIO=0|USE_MINIO=1|' "$env_file"
    info "  USE_MINIO: 0 → 1"
  fi

  # 4. WEB_URL: 8000 → 3000（.env.example 默认写错了）
  if grep -q '^WEB_URL="http://localhost:8000"' "$env_file"; then
    sed -i '' 's|^WEB_URL="http://localhost:8000"|WEB_URL="http://localhost:3000"|' "$env_file"
    info "  WEB_URL: 8000 → 3000"
  fi
}

# ─── 安装 Node 依赖 ──────────────────────────────────────────────────────────

install_deps() {
  if [ ! -d "node_modules" ]; then
    info "安装 Node 依赖 (pnpm install)..."
    pnpm install
  else
    info "node_modules 已存在，跳过安装"
  fi
}

# ─── IP 替换 ──────────────────────────────────────────────────────────────────

apply_host() {
  local host="$1"
  if [ "$host" = "localhost" ]; then return; fi

  info "DEV_HOST=${host}，更新 .env..."

  # 前端 .env: 全局替换 localhost -> IP
  for env_file in $FRONTEND_ENVS; do
    if [ -f "$env_file" ]; then
      sed -i '' "s|localhost|${host}|g" "$env_file"
      info "  已更新 $env_file"
    fi
  done

  # API .env: 只替换 URL 相关的 key
  if [ -f apps/api/.env ]; then
    for key in $API_URL_KEYS; do
      sed -i '' "s|^${key}=\"http://localhost|${key}=\"http://${host}|" apps/api/.env
    done
    # CORS: 追加 IP 的 origins（如果 CORS 行里还没有的话）
    if ! grep "^CORS_ALLOWED_ORIGINS" apps/api/.env | grep -q "${host}"; then
      sed -i '' "s|^CORS_ALLOWED_ORIGINS=\"\(.*\)\"|CORS_ALLOWED_ORIGINS=\"\1,http://${host}:3000,http://${host}:3001,http://${host}:3002,http://${host}:3100\"|" apps/api/.env
    fi
    info "  已更新 apps/api/.env"
  fi
}

restore_host() {
  local host="$1"
  if [ "$host" = "localhost" ]; then return; fi

  info "还原 .env 为 localhost..."

  # 前端 .env: 全局还原 IP -> localhost
  for env_file in $FRONTEND_ENVS; do
    if [ -f "$env_file" ]; then
      sed -i '' "s|${host}|localhost|g" "$env_file"
    fi
  done

  # API .env: 只还原 URL 相关的 key
  if [ -f apps/api/.env ]; then
    for key in $API_URL_KEYS; do
      sed -i '' "s|^${key}=\"http://${host}|${key}=\"http://localhost|" apps/api/.env
    done
    # CORS: 移除追加的 IP origins
    sed -i '' "s|,http://${host}:3000,http://${host}:3001,http://${host}:3002,http://${host}:3100||" apps/api/.env
  fi
}

# ─── 清理 ─────────────────────────────────────────────────────────────────────

cleanup() {
  info "正在停止前端进程..."
  kill $WEB_PID $ADMIN_PID $SPACE_PID $LIVE_PID 2>/dev/null
  wait $WEB_PID $ADMIN_PID $SPACE_PID $LIVE_PID 2>/dev/null
  restore_host "$DEV_HOST"
  info "已退出"
}

# ─── 主流程 ───────────────────────────────────────────────────────────────────

# 0. 前置检查
check_prerequisites

# 1. 初始化 .env（首次运行时）
init_env_files

# 2. 安装 Node 依赖
install_deps

# 3. 替换 .env 中的 localhost 为实际 IP
apply_host "$DEV_HOST"

# 4. 清除 turbo 缓存并构建 packages
info "清除 turbo 缓存..."
find . -name ".turbo" -type d -maxdepth 3 -exec rm -rf {} + 2>/dev/null || true
info "构建 packages..."
pnpm turbo run build --filter='./packages/*'

# 5. 启动后端 Docker 服务（--build 确保首次构建镜像，后续有缓存不会重复构建）
info "启动后端 Docker 服务..."
docker compose -f "$COMPOSE_FILE" up -d --build

# 6. 等待 API 就绪
info "等待 API 就绪..."
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" logs api --tail 1 2>&1 | grep -q "Starting development server"; then
    info "API 已就绪"
    break
  fi
  if [ "$i" -eq 60 ]; then
    warn "等待超时（60s），API 可能尚未就绪"
    warn "请检查: docker compose -f $COMPOSE_FILE logs api --tail 10"
  fi
  sleep 1
done

# 7. 检查后端容器状态
check_docker_services() {
  info "检查后端服务状态..."
  local all_ok=true
  local services=("api" "worker" "beat-worker" "plane-db" "plane-redis" "plane-mq" "plane-minio")
  for svc in "${services[@]}"; do
    local status
    status=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Status}}' "$svc" 2>/dev/null)
    if echo "$status" | grep -qi "up"; then
      info "  ✓ $svc — 运行中"
    elif [ -z "$status" ]; then
      err "  ✗ $svc — 未启动"
      all_ok=false
    else
      err "  ✗ $svc — $status"
      all_ok=false
    fi
  done
  if [ "$all_ok" = false ]; then
    warn "部分后端服务异常，请检查: docker compose -f $COMPOSE_FILE ps"
  fi
}
check_docker_services

# 8. 启动前端（用 pnpm -C 直接运行，完全绕过 turbo）
info "启动前端服务..."
pnpm -C apps/admin dev &
ADMIN_PID=$!
pnpm -C apps/space dev &
SPACE_PID=$!
pnpm -C apps/live dev &
LIVE_PID=$!
pnpm -C apps/web dev &
WEB_PID=$!

trap cleanup EXIT INT TERM

# 9. 等待前端端口就绪并输出状态
check_frontend_services() {
  info "等待前端服务就绪..."
  local ports=("3000:web" "3001:admin" "3002:space" "3100:live")
  # 最多等 30 秒
  for attempt in $(seq 1 30); do
    local all_ready=true
    for entry in "${ports[@]}"; do
      local port="${entry%%:*}"
      if ! lsof -i ":$port" &>/dev/null; then
        all_ready=false
        break
      fi
    done
    if [ "$all_ready" = true ]; then
      break
    fi
    sleep 1
  done

  # 输出最终状态
  echo ""
  info "═══════════════════════════════════════════════"
  info "  Plane 本地开发环境启动状态"
  info "═══════════════════════════════════════════════"
  for entry in "${ports[@]}"; do
    local port="${entry%%:*}"
    local name="${entry#*:}"
    if lsof -i ":$port" &>/dev/null; then
      info "  ✓ $name — http://${DEV_HOST}:${port}"
    else
      err "  ✗ $name — 端口 $port 未就绪"
    fi
  done
  info "  ✓ api  — http://${DEV_HOST}:8000"
  info "═══════════════════════════════════════════════"

  if [ "$DEV_HOST" != "localhost" ]; then
    info "  局域网访问: http://${DEV_HOST}:3000"
  fi
  info "  按 Ctrl+C 停止所有前端服务"
  echo ""
}
check_frontend_services

# 保持脚本运行，等待前台进程退出
wait $WEB_PID
