# Plane 项目知识沉淀

> 最后更新：2026-03-17
>
> 本文档汇总了 Plane CE 二开过程中积累的全部经验，包括本地开发踩坑、GitLab Bridge 开发经验、
> Fork 分支策略、AI 自动化开发方案、以及项目定位思考。供后续接手者参考。

---

## 1. 项目定位

### 核心结论

替代盗版 Jira v8.13.5 的唯一核心理由是 **完全自主可控**。图表能力（6 种视图）、AI 集成（MCP 55+ 工具）是锦上添花，不是决策理由。

### 正确的叙事逻辑（决策者视角）

1. **为什么必须离开盗版 Jira**（痛点驱动）
   - 法律风险：Atlassian 加大盗版追诉，赔偿是真金白银
   - 无法升级：卡在 v8.13.5，安全漏洞无法修补
   - 审计合规：ISO 27001 / 上市审计中盗版软件是硬伤
   - 人才断层：无官方支持，出问题只能内部摸索

2. **为什么选 Plane**（最安全的替代）
   - 开源自托管，合规零风险
   - 源码可控，不依赖任何供应商
   - 基础 PM 能力已覆盖日常需求
   - 缺的能力可以自己二开补齐

3. **额外收益**（锦上添花）
   - 图表能力丰富（Gantt、Burndown、Velocity、Calendar、Analytics、Board）
   - AI 集成潜力（MCP 55+ 工具，全链路 AI 开发工作流）

> **教训**：做材料不要用技术人思维列功能对比，要用"风险→方案→收益"的决策者叙事。

### Plane 版本体系

| 版本名     | 部署方式       | 授权           | 功能层级                           |
| ---------- | -------------- | -------------- | ---------------------------------- |
| CE         | 自托管         | AGPL v3.0 开源 | = Cloud Free                       |
| Commercial | 自托管         | 商业闭源       | = Cloud 全功能                     |
| Airgapped  | 自托管（离线） | 商业闭源       | 企业级                             |
| Cloud      | 官方托管       | SaaS           | Free / Pro / Business / Enterprise |

**我们用的是 CE = Cloud Free 功能等价。** Custom Properties 是 Pro 付费专属，CE 源码中无实现（仅有 filter_backend.py 占位注释）。

### CE 需要二开的能力

| 能力                          | 现状   | 说明                                          |
| ----------------------------- | ------ | --------------------------------------------- |
| Issue Types（Work Item 类型） | 需二开 | CE 只有单一 Work Item，无 Story/Bug/Epic 区分 |
| Custom Fields（自定义字段）   | 需二开 | CE 无 CustomField Model，Pro 专属功能         |
| Workflow（状态流转规则）      | 需二开 | CE 只有状态组，无状态转换约束                 |

---

## 2. Fork 分支策略

### 仓库关系

```
makeplane/plane (upstream)
    └── darkingtail/plane (fork, GitHub 用户名 darkingtail)
```

### 分支说明

| 分支          | 用途            | 操作                                                                                    |
| ------------- | --------------- | --------------------------------------------------------------------------------------- |
| `preview`     | 跟踪上游        | `git fetch upstream && git merge --ff-only upstream/preview && git push origin preview` |
| `feature/dev` | Wisedu 二开主干 | 所有定制在此分支                                                                        |

### 合并上游新功能

```bash
# 在 feature/dev 上
git merge preview
# 冲突对照 docs/plane-forge/tracking/overview.md 人工判断
```

### 目录结构

| 目录                | 用途                                              |
| ------------------- | ------------------------------------------------- |
| `docs/plane-forge/` | CE 增强，通用（tracking、sync、plans、reference） |
| `docs/wisedu/`      | 公司专属文档（jira 对比、迁移方案、本文档）       |
| `services/`         | 独立微服务（gitlab-bridge 等）                    |
| `.claude/skills/`   | Claude Code 自动化技能                            |

---

## 3. 本地开发踩坑

> 详细指南见 `docs/plane-forge/reference/local-dev-guide.md`

### .env 三个必改项

`setup.sh` 生成的 `apps/api/.env` 有 3 处需手动修正：

```diff
# 1. CORS：添加 127.0.0.1（Vite 默认绑定 127.0.0.1，不加会跨域）
- CORS_ALLOWED_ORIGINS="http://localhost:3000,..."
+ CORS_ALLOWED_ORIGINS="http://localhost:3000,...,http://127.0.0.1:3000,..."

# 2. MinIO：容器内 localhost 指向自身，改用 Docker 内部地址
- AWS_S3_ENDPOINT_URL="http://localhost:9000"
+ AWS_S3_ENDPOINT_URL="http://plane-minio:9000"

# 3. 启用 MinIO
- USE_MINIO=0
+ USE_MINIO=1
```

### 其他关键踩坑

| 问题                               | 原因                                                | 解决                                                                                       |
| ---------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| CORS_ALLOWED_ORIGINS 不能为空      | 空值导致 CSRF_TRUSTED_ORIGINS 也为空，POST 全部 403 | 必须显式列出所有前端地址                                                                   |
| local.py 需移除 CsrfViewMiddleware | SameSite=None 在 HTTP 下无效，Chrome 忽略回退 Lax   | `MIDDLEWARE = [m for m in MIDDLEWARE if m != "django.middleware.csrf.CsrfViewMiddleware"]` |
| 修改 .env 后 restart 无效          | `docker compose restart` 不重新加载 env_file        | 必须 `docker compose up -d api --force-recreate`                                           |
| API 重启后短暂不可用               | Django 启动需跑 migration 检查等，约 10-15 秒       | 等待约 15 秒再刷新                                                                         |
| 邮件测试不工作                     | 默认 EMAIL_BACKEND 可能不是 SMTP                    | 已修复：显式使用 `django.core.mail.backends.smtp.EmailBackend`                             |
| 附件上传 csv/json/xml 失败         | 文本文件无 magic bytes，MIME 检测返回空             | 已修复：前端回退 browser MIME，后端从文件名推断                                            |
| MinIO presigned URL 本地不可访问   | 无 Nginx 代理时，presigned URL 用容器内地址         | 已修复：支持 `MINIO_PRESIGNED_BASE_URL` 环境变量                                           |

### 服务访问地址

| 服务           | 地址                                            |
| -------------- | ----------------------------------------------- |
| Web 主应用     | http://127.0.0.1:3000/                          |
| Admin 管理面板 | http://127.0.0.1:3001/god-mode/                 |
| Space 公共空间 | http://127.0.0.1:3002/spaces/                   |
| Live 实时协作  | http://127.0.0.1:3100                           |
| Django API     | http://localhost:8000                           |
| MinIO 控制台   | http://localhost:9090 (access-key / secret-key) |

---

## 4. GitLab Bridge 开发经验

### 基本信息

| 项                  | 值                        |
| ------------------- | ------------------------- |
| 服务路径            | `services/gitlab-bridge/` |
| Docker service name | `gitlab-bridge`           |
| 端口                | 8080                      |
| 技术栈              | Python / FastAPI          |

### .env 关键配置

```env
PLANE_BASE_URL=http://api:8000     # compose service name 是 api 不是 plane-api
REDIS_URL=redis://plane-redis:6379
```

### Plane Webhook 配置

| 项                    | 值                                                                             |
| --------------------- | ------------------------------------------------------------------------------ |
| URL                   | `http://gitlab-bridge:8080/api/v1/webhooks/plane/issue`（注意 `/api/v1` 前缀） |
| Payload 中的 action   | `updated`（不是 `update`）                                                     |
| State 变更字段        | `state_id`（不是 `state`）                                                     |
| old_value / new_value | 状态 UUID                                                                      |

### API 注意事项

- Plane GET `/issues/<id>/` 不返回 `label_detail` 和 `project_detail`，`plane_service.get_issue()` 已做补全
- DB 配置有 `pgdata` volume 持久化，重置后需重跑 `services/gitlab-bridge/docs/plane-setup.sh`

### 已验证的工作流

- ✅ 分支创建（Issue 状态变更 → GitLab 自动创建分支）
- ✅ Integrating（feature → dev 合并请求）
- 手动触发分支创建：`POST http://localhost:8080/api/v1/debug/create-branch`

---

## 5. Plane + AI 自动化开发方案

### 架构

```
Plane (项目管理)  ──MCP──▶  opencode / Claude Code (AI 编码)  ──▶  本地代码仓库
     │                           │
     │  Issue/状态/评论           │  读取任务 → 编码 → 测试 → 提交
     │  通过 MCP 双向同步         │
     ▼                           ▼
Plane MCP Server            Git (commit/push)
(uvx plane-mcp-server stdio)
```

### Plane MCP Server

- 安装：`uvx plane-mcp-server stdio`（自动下载，无需 pip install）
- 55+ 工具，覆盖 Projects、Work Items、Cycles、Modules、Initiatives、Intake、Properties、Users
- 配置参数获取：
  - `PLANE_API_KEY`：Plane → Settings → API Tokens
  - `PLANE_WORKSPACE_SLUG`：URL 中的 slug
  - `PLANE_BASE_URL`：本地 `http://localhost:8000`

### opencode 配置

```json
{
  "mcp": {
    "plane": {
      "type": "local",
      "command": ["uvx", "plane-mcp-server", "stdio"],
      "environment": {
        "PLANE_API_KEY": "<your-api-key>",
        "PLANE_WORKSPACE_SLUG": "<your-workspace-slug>",
        "PLANE_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

> **注意**：opencode 用 `"mcp"` 不是 `"mcpServers"`，`"environment"` 不是 `"env"`，`"command"` 是单数组。

### 典型工作流

1. PM 在 Plane 创建 Issue（描述需求、验收标准）
2. AI Agent 通过 MCP 获取待办 Issue
3. AI 读取 Issue 详情 → 编码实现 → 测试 → 提交
4. AI 通过 MCP 更新 Issue 状态 + 添加评论

---

## 6. 已完成的代码修改清单

### 后端 (apps/api)

| 文件                                       | 修改                            | 目的                      |
| ------------------------------------------ | ------------------------------- | ------------------------- |
| `plane/settings/common.py`                 | 新增 csv/json/xml MIME 类型     | 支持更多附件格式          |
| `plane/settings/storage.py`                | 支持 `MINIO_PRESIGNED_BASE_URL` | 本地开发无 Nginx 时可访问 |
| `plane/app/views/issue/attachment.py`      | MIME 类型回退推断               | 文本文件上传不再失败      |
| `plane/license/api/views/configuration.py` | 显式 SMTP backend               | 邮件测试可靠              |
| `plane/app/serializers/issue_type.py`      | 新增                            | Issue Type 序列化器脚手架 |
| `plane/app/urls/issue_type.py`             | 新增                            | Issue Type URL 路由       |
| `plane/app/views/issue_type/`              | 新增                            | Issue Type 视图脚手架     |

### 前端 (apps/web)

| 文件                                              | 修改                       | 目的                       |
| ------------------------------------------------- | -------------------------- | -------------------------- |
| `vite.config.ts` (admin/space/web)                | host → 0.0.0.0             | Docker 内可外部访问        |
| `packages/services/src/file/helper.ts`            | MIME 类型回退 browser type | 文本文件上传修复           |
| `apps/web/.../gitlab/page.tsx`                    | 新增                       | GitLab 集成设置页面        |
| `apps/web/.../gitlab/header.tsx`                  | 新增                       | GitLab 设置页头            |
| `apps/web/core/services/gitlab-bridge.service.ts` | 新增                       | GitLab Bridge 前端 Service |

### 独立服务

| 目录                      | 说明                               |
| ------------------------- | ---------------------------------- |
| `services/gitlab-bridge/` | GitLab 双向集成桥接服务（FastAPI） |
