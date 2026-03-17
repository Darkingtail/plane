# Plane 本地开发启动指南

[TOC]

## 前置条件

- Docker & Docker Compose
- Node.js v22+
- pnpm v10+

## 一键启动

在仓库根目录执行：

```bash
bash docs/plane-forge/plans/scripts/local-dev-start.sh
```

## 手动启动

### 1. 构建 packages

首次拉取或 `packages/` 目录有变更时，需要先构建：

```bash
# 如果 turbo 缓存脏了（dist 为空），先清除缓存
find . -name ".turbo" -type d -maxdepth 3 -exec rm -rf {} + 2>/dev/null
pnpm turbo run build --filter='./packages/*'
```

> 如果遇到 `Failed to resolve entry for package "@plane/utils"` 等错误，就是这一步没做。

### 2. 启动后端（Docker）

```bash
docker compose -f docker-compose-local.yml up -d
```

等待 API 就绪（出现 `Starting development server` 即可）：

```bash
docker compose -f docker-compose-local.yml logs api --tail 5
```

### 3. 启动前端

```bash
# 不要用 pnpm dev（turbo 会同时跑 packages 的 tsdown --watch 清空 dist）
# 也不要用 pnpm --filter（turbo 的 ^build 依赖仍会触发 packages 重建）
# 正确做法：用 pnpm -C 直接启动各 app，完全绕过 turbo
pnpm -C apps/web dev
pnpm -C apps/admin dev    # 另一个终端
pnpm -C apps/space dev    # 另一个终端
pnpm -C apps/live dev     # 另一个终端
```

## 服务地址

| 服务           | 地址                                             |
| -------------- | ------------------------------------------------ |
| Web 主应用     | http://127.0.0.1:3000/                           |
| Admin 管理面板 | http://127.0.0.1:3001/god-mode/                  |
| Space 公共空间 | http://127.0.0.1:3002/spaces/                    |
| Live 实时协作  | http://127.0.0.1:3100/                           |
| Django API     | http://localhost:8000/                           |
| MinIO 控制台   | http://localhost:9090/ (access-key / secret-key) |

## 停止服务

```bash
# 前端: 在 pnpm dev 终端按 Ctrl+C

# 后端
docker compose -f docker-compose-local.yml down
```

## 常见问题

### `@plane/utils` 解析失败

turbo 缓存命中但 `dist/` 为空，先清缓存再重建：

```bash
find . -name ".turbo" -type d -maxdepth 3 -exec rm -rf {} + 2>/dev/null
pnpm turbo run build --filter='./packages/*'
```

### 修改 `.env` 后不生效

`restart` 不会重新加载 `env_file`，必须用 `--force-recreate`：

```bash
docker compose -f docker-compose-local.yml up -d api --force-recreate
```

### CORS / CSRF 报错

确认 `apps/api/.env` 中 `CORS_ALLOWED_ORIGINS` 同时包含 `localhost` 和 `127.0.0.1` 地址。
