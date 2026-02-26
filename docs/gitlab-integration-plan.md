# 第二阶段：Plane GitLab 仓库联动集成方案

## 目标

将 jira-scripts 项目（`/Users/wisedu/FEProjects/WisFE/jira-scripts`）中已实现的 Jira + GitLab 联动能力迁移到 Plane，实现 Issue 状态驱动的 Git 自动化工作流。

## 现状分析

### Plane 当前 GitLab 支持

- **仅支持 OAuth 登录**：`apps/api/plane/authentication/provider/oauth/gitlab.py`，scope 为 `read_user`
- **不支持仓库关联和 Issue 同步**
- **GitHub 集成代码残留**：历史版本有 GitHub 集成但已移除入口，代码仍在

### jira-scripts 已实现的能力

| 功能         | 触发方式                      | Git 操作                                      |
| ------------ | ----------------------------- | --------------------------------------------- |
| 自动创建分支 | 创建"创建分支"子任务          | 按模块映射在多个 GitLab 仓库创建 feature 分支 |
| 联调合并     | DEVELOPING → INTEGRATING      | feature → dev，触发 dev 环境构建              |
| 提测合并     | 状态 → TESTING                | feature → test，触发 test 环境构建            |
| 测试失败回退 | TESTING → DEVELOPING          | 通知开发者修复                                |
| 测试通过     | TESTING → TO_PUBLISH          | 记录审计日志                                  |
| 开始封版     | TODO → FREEZE_READY           | 收集待发布 Story                              |
| 执行封版     | FREEZE_READY → REGRESSING     | test → release，触发 release 构建             |
| 完成封版     | REGRESSING → READY_TO_PUBLISH | 删除 feature 分支，更新状态                   |
| 发布版本     | READY_TO_PUBLISH → DONE       | release → main，打 tag，生成 Changelog        |
| 冲突检测     | GitLab MR webhook             | 冲突解决后回写评论通知                        |

### 可复用 vs 需改造

| 层级                      | 可直接复用       | 需要改造                                 |
| ------------------------- | ---------------- | ---------------------------------------- |
| GitLab Service（~800 行） | 分支/MR/Tag 操作 | 无需改动                                 |
| 模块配置服务              | 映射逻辑         | modules.yml 格式适配                     |
| Webhook Handler           | 工作流编排逻辑   | 入口解析（Jira payload → Plane payload） |
| Issue 读写                | —                | Jira API → Plane API 全部替换            |
| 评论回写                  | —                | Jira comment → Plane comment             |
| 状态触发                  | —                | Jira status ID → Plane state UUID        |

## 方案设计

### 方案选择：独立 Bridge 服务

| 维度       | 独立 Bridge 服务        | Plane 内置改造          |
| ---------- | ----------------------- | ----------------------- |
| 改动范围   | 不改 Plane 源码         | 需改 Django + React     |
| 部署复杂度 | 多一个服务              | 无额外服务              |
| 升级兼容   | Plane 升级无影响        | 可能被覆盖              |
| 开发速度   | 快（复用 jira-scripts） | 慢（需理解 Plane 内部） |
| 维护性     | 独立维护                | 与 Plane 耦合           |

**选择独立 Bridge 服务**：Plane 是开源项目频繁更新，内置改动会在升级时产生冲突。通过 Webhook + API 松耦合最稳妥。

### 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                   Plane (前端 + API)                      │
│                                                           │
│  Issue 状态变更  ──Webhook──▶  出站 Webhook               │
│  Label 标记模块               (issue.updated 事件)        │
└───────────────────────────────────┬───────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────┐
│              plane-gitlab-bridge (FastAPI)                │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Plane       │  │ GitLab       │  │ Module Config   │  │
│  │ Webhook     │  │ Service      │  │ Service         │  │
│  │ Handler     │  │ (直接复用)    │  │ (modules.yml)   │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                │                    │           │
│  ┌──────▼────────────────▼────────────────────▼────────┐  │
│  │ Workflows                                           │  │
│  │  ├─ branch_creation  (创建 feature 分支)             │  │
│  │  ├─ integrating      (feature → dev 合并)            │  │
│  │  ├─ testing          (feature → test 合并)            │  │
│  │  ├─ release          (发版封版流程)                    │  │
│  │  └─ conflict_notify  (冲突检测回写)                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────┐                                          │
│  │ Plane       │  ← 新增：替代 jira_service               │
│  │ Service     │  (评论回写、状态查询)                      │
│  └─────────────┘                                          │
└───────────────────────────────────┬───────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │ GitLab API    │               │
                    ▼               ▼               ▼
              创建分支         创建/合并 MR       打 Tag
                    │               │               │
                    ▼               ▼               ▼
┌──────────────────────────────────────────────────────────┐
│                       GitLab                              │
│                                                           │
│  MR 状态变化 ──MR Webhook──▶ plane-gitlab-bridge          │
│                              (冲突检测 → Plane 评论通知)   │
└──────────────────────────────────────────────────────────┘
```

### 模块映射方案

jira-scripts 用 Jira Component 映射 GitLab 仓库，Plane 中用 **Label** 替代：

| Jira 概念    | Plane 概念                            | 说明             |
| ------------ | ------------------------------------- | ---------------- |
| Component    | **Label**（如 `repo:admin-campusos`） | 灵活，无周期限制 |
| Story        | Issue (Work Item)                     | 直接对应         |
| Sprint       | Cycle                                 | 直接对应         |
| Story Status | State（自定义 state group）           | 需创建对应状态   |

### 状态映射

需要在 Plane 项目中创建对应的自定义 State：

| 工作流阶段 | Plane State | State Group | 触发动作             |
| ---------- | ----------- | ----------- | -------------------- |
| 待开发     | Todo        | unstarted   | —                    |
| 开发中     | Developing  | started     | —                    |
| 联调中     | Integrating | started     | feature → dev        |
| 测试中     | Testing     | started     | feature → test       |
| 待发布     | To Publish  | started     | —                    |
| 已完成     | Done        | completed   | release → main + tag |

### 配置文件设计

`config/modules.yml`：

```yaml
workflow:
  branches:
    main: "main"
    release: "release"
    test: "test"
    dev: "dev"

plane:
  base_url_env: "PLANE_BASE_URL"
  api_key_env: "PLANE_API_KEY"
  workspace_slug_env: "PLANE_WORKSPACE_SLUG"
  # 状态名称 → 工作流阶段映射
  state_mapping:
    integrating: "Integrating" # 联调
    testing: "Testing" # 提测
    to_publish: "To Publish" # 待发布
    done: "Done" # 已完成

gitlab:
  url_env: "GITLAB_URL"
  token_env: "GITLAB_TOKEN"
  branch_name_template: "feature/{issue_id}_{date}_{desc}"
  timeout: 30
  max_retries: 3

modules:
  - label: "repo:admin-campusos"
    display_name: "底座 PC 端"
    gitlab:
      project_id: 45
    enabled: true

  - label: "repo:component-lib"
    display_name: "组件库 PC 端"
    gitlab:
      project_id: 46
    enabled: true

branch_creation:
  check_existence: true
  if_exists: "skip"
  add_plane_comment: true
```

### Bridge 服务接口

| 接口                             | 方法 | 说明                               |
| -------------------------------- | ---- | ---------------------------------- |
| `/webhooks/plane/issue`          | POST | 接收 Plane Issue 状态变更 Webhook  |
| `/webhooks/gitlab/merge-request` | POST | 接收 GitLab MR Webhook（冲突检测） |
| `/api/health`                    | GET  | 健康检查                           |
| `/api/modules`                   | GET  | 获取模块配置列表                   |
| `/api/branches/create`           | POST | 手动触发为指定 Issue 创建分支      |

### Plane API 替换对照

| 操作         | Jira API                      | Plane API                                                  |
| ------------ | ----------------------------- | ---------------------------------------------------------- |
| 获取 Issue   | `GET /rest/api/2/issue/{key}` | `GET /api/v1/workspaces/{slug}/projects/{id}/issues/{id}/` |
| 更新状态     | `POST .../transitions`        | `PATCH .../issues/{id}/` + `{"state": "uuid"}`             |
| 添加评论     | `POST .../comment`            | `POST .../issues/{id}/comments/`                           |
| 搜索 Issue   | JQL                           | `GET .../issues/?state={uuid}`                             |
| 获取 Label   | —                             | `GET .../labels/`                                          |
| 获取状态列表 | —                             | `GET .../states/`                                          |

## 项目结构

```
plane-gitlab-bridge/
├── app/
│   ├── api/v1/
│   │   ├── webhooks/
│   │   │   ├── plane_webhook.py          # Plane Webhook 入口
│   │   │   ├── gitlab_webhook.py         # GitLab MR Webhook
│   │   │   ├── operations/               # 复用 jira-scripts
│   │   │   │   ├── branch.py
│   │   │   │   ├── merge.py
│   │   │   │   └── comment.py
│   │   │   └── workflows/
│   │   │       ├── branch_creation.py    # 创建分支
│   │   │       ├── integrating.py        # 联调（feature → dev）
│   │   │       ├── testing.py            # 提测（feature → test）
│   │   │       ├── testing_failed.py     # 测试失败通知
│   │   │       └── release.py            # 发版（封版/发布）
│   │   └── system.py                     # 健康检查
│   ├── services/
│   │   ├── plane_service/                # 新增：替代 jira_service
│   │   │   ├── __init__.py
│   │   │   ├── issues.py                 # Issue 读取/更新
│   │   │   ├── comments.py               # 评论回写
│   │   │   ├── states.py                 # 状态列表（缓存 UUID）
│   │   │   └── labels.py                 # Label 查询
│   │   ├── gitlab_service/               # 直接复用 jira-scripts
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── branch_operations.py
│   │   │   ├── merge_request_operations.py
│   │   │   ├── tag_operations.py
│   │   │   └── project_operations.py
│   │   ├── module_config_service.py      # 适配 Label 映射
│   │   └── cache_service.py              # Redis 缓存
│   ├── core/
│   │   ├── config.py                     # Pydantic Settings
│   │   └── logging.py
│   └── models/
├── config/
│   ├── modules.yml
│   └── modules.example.yml
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

## 实现计划

### 第 1 步：搭建 Bridge 服务骨架（1 天）

- [ ] 创建 `plane-gitlab-bridge/` 项目
- [ ] FastAPI 框架搭建（复用 jira-scripts 项目结构）
- [ ] 复制 `gitlab_service/` 层（branch、MR、tag 操作，~800 行）
- [ ] 复制 `module_config_service.py`，适配新 modules.yml 格式
- [ ] 编写 `.env.example` + `config/modules.example.yml`
- [ ] Docker Compose 集成（与 Plane 同网络）
- [ ] 健康检查接口

### 第 2 步：实现 Plane Service 层（1 天）

- [ ] `plane_service/issues.py` — 获取/更新 Issue
- [ ] `plane_service/comments.py` — 添加评论（替代 Jira comment）
- [ ] `plane_service/states.py` — 获取状态列表，缓存 state name → UUID 映射
- [ ] `plane_service/labels.py` — 获取 Label 列表
- [ ] HTTP 客户端封装（token 认证、重试、超时）
- [ ] 单元测试

### 第 3 步：实现 Webhook Handler + 开发工作流（2 天）

- [ ] `POST /webhooks/plane/issue` 入口
- [ ] Webhook 签名验证（Plane webhook secret）
- [ ] 事件解析：`old_data.state` → `data.state` 状态变更检测
- [ ] Label 解析：从 Issue labels 中提取 `repo:xxx` 映射模块
- [ ] **分支创建工作流**：Issue 创建/手动触发 → 为每个模块创建 feature 分支 → Plane 评论
- [ ] **联调工作流**：状态 → Integrating → feature → dev 合并 → Plane 评论
- [ ] **提测工作流**：状态 → Testing → feature → test 合并 → Plane 评论
- [ ] **测试失败**：状态 → Developing → 通知评论
- [ ] `POST /webhooks/gitlab/merge-request`（GitLab MR webhook 冲突检测 → Plane 评论）

### 第 4 步：实现发版工作流（1 天）

- [ ] 封版流程：test → release 合并（所有模块）
- [ ] 发布流程：release → main 合并 + 打 tag
- [ ] 分支清理：删除已发布的 feature 分支
- [ ] Changelog 生成
- [ ] 状态批量更新

### 第 5 步：测试与文档（1 天）

- [ ] 单元测试（复用 jira-scripts 测试结构，替换 mock 对象）
- [ ] 集成测试：Plane Webhook → Bridge → GitLab
- [ ] 部署文档（Docker Compose 配置说明）
- [ ] Plane Webhook 配置指南
- [ ] modules.yml 配置示例

## 环境变量

```bash
# Plane
PLANE_API_KEY=plane-api-key
PLANE_WORKSPACE_SLUG=my-workspace
PLANE_BASE_URL=http://localhost:8000
PLANE_WEBHOOK_SECRET=webhook-secret

# GitLab
GITLAB_URL=http://172.16.7.53:9090
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# Redis
REDIS_URL=redis://localhost:6379

# Service
PORT=8080
LOG_LEVEL=INFO
```

## 预估工期

| 步骤     | 内容                                   | 工期      |
| -------- | -------------------------------------- | --------- |
| 1        | Bridge 服务骨架 + GitLab Service 复用  | 1 天      |
| 2        | Plane Service 层                       | 1 天      |
| 3        | Webhook Handler + 开发/联调/提测工作流 | 2 天      |
| 4        | 发版工作流                             | 1 天      |
| 5        | 测试与文档                             | 1 天      |
| **合计** |                                        | **~6 天** |

## 与第一阶段的关系

```
第一阶段（已完成）          第二阶段（本方案）
┌─────────────────┐     ┌─────────────────────┐
│ Plane 本地部署   │     │ plane-gitlab-bridge  │
│ + 自定义 LLM    │     │ (GitLab 联动服务)     │
│ + opencode MCP  │     │                      │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
         ▼                         ▼
  AI 辅助开发              Git 自动化工作流
  (MCP 获取任务)           (状态驱动分支/合并)
         │                         │
         └────────────┬────────────┘
                      ▼
            完整的自动化开发闭环
            Plane Issue → AI 开发 → 自动合并/发版
```
