# Plane GitLab 仓库集成方案

## 现状分析

### 当前 GitLab 支持

Plane 当前仅支持 GitLab OAuth 登录（SSO），不支持仓库关联和 Issue 同步。

- **OAuth Provider**：`apps/api/plane/authentication/provider/oauth/gitlab.py`
- **Scope**：`read_user`（仅获取用户信息）
- **Token 使用**：登录后丢弃，不持久化
- **God Mode 配置**：`http://localhost:3001/god-mode/authentication/gitlab/`

### GitHub 集成（历史遗留）

Plane 历史版本曾有 GitHub 集成（仓库关联、Issue 同步、评论同步），但当前版本已从侧边栏移除，功能不可用。相关代码仍残留在：

- `apps/api/plane/db/models/integration/github.py`
- `apps/web/core/components/integration/`
- `apps/web/core/services/integrations/github.service.ts`

### Integrations 页面状态

- 路由文件存在：`apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/integrations/page.tsx`
- 侧边栏菜单无入口（`packages/constants/src/settings/workspace.ts` 中未注册）
- 页面访问 404

## 集成方案

### 核心思路

利用已有的 GitLab OAuth 流程，扩大 scope 并持久化 token，通过 GitLab API 获取仓库信息，实现项目级别的仓库关联。

### 需要修改的内容

#### 1. 扩大 OAuth Scope

**文件**：`apps/api/plane/authentication/provider/oauth/gitlab.py`

```python
# 当前
scope = "read_user"

# 改为
scope = "read_user read_api"
```

`read_api` scope 允许以只读方式访问 GitLab API，包括：

- `GET /api/v4/projects`（用户可见的仓库列表）
- `GET /api/v4/projects/:id`（仓库详情）
- `GET /api/v4/projects/:id/merge_requests`（MR 列表）
- `GET /api/v4/projects/:id/repository/branches`（分支列表）

#### 2. 持久化 Access Token

登录成功后将 access_token 和 refresh_token 存储到数据库，关联到用户和 workspace。

需要新建模型或复用已有的 `WorkspaceIntegration` 模型：

```python
# 需要存储的字段
- user（关联用户）
- workspace（关联工作区）
- provider = "gitlab"
- access_token
- refresh_token
- access_token_expired_at
- gitlab_host（私有 GitLab 地址）
```

#### 3. 后端 API

新增接口：

| 接口                                                    | 方法   | 说明                           |
| ------------------------------------------------------- | ------ | ------------------------------ |
| `/api/workspaces/{slug}/gitlab/repositories/`           | GET    | 获取用户可见的 GitLab 仓库列表 |
| `/api/workspaces/{slug}/gitlab/repositories/{id}/`      | GET    | 获取仓库详情                   |
| `/api/workspaces/{slug}/projects/{id}/gitlab-link/`     | POST   | 项目关联 GitLab 仓库           |
| `/api/workspaces/{slug}/projects/{id}/gitlab-link/`     | DELETE | 取消关联                       |
| `/api/workspaces/{slug}/projects/{id}/gitlab-link/mrs/` | GET    | 获取关联仓库的 MR 列表         |

后端通过保存的 token 调用 GitLab API：

```
GET {GITLAB_HOST}/api/v4/projects?membership=true&per_page=20&page=1
```

#### 4. 前端页面

- **Workspace Settings**：添加 GitLab 集成入口（恢复 Integrations 侧边栏菜单或新建入口）
- **Project Settings**：选择并关联 GitLab 仓库
- **Project 详情页**：展示关联仓库信息、最近 MR 等

### 技术架构

```
用户登录（GitLab OAuth，scope: read_user read_api）
    ↓
Plane 存储 access_token（关联 user + workspace）
    ↓
Workspace Settings → GitLab 集成状态展示
    ↓
Project Settings → 选择 GitLab 仓库关联
    ↓
Plane 后端 → 用 token 调 GitLab API → 返回仓库/MR 数据
    ↓
前端展示仓库信息、MR 列表
```

### 私有 GitLab 支持

由于使用公司私有 GitLab，需注意：

1. **GITLAB_HOST** 环境变量指向私有地址（已支持，在 God Mode 中配置）
2. **网络连通性**：Plane API 容器需能访问私有 GitLab 地址
3. **自签名证书**：如果 GitLab 使用自签名 SSL，需在 API 容器中信任该证书
4. **Token 刷新**：私有 GitLab 的 token 过期策略可能不同，需处理 refresh_token 逻辑

## 可选扩展

### Issue ↔ GitLab 同步

参考已有的 GitHub 模型（`GithubIssueSync`、`GithubCommentSync`），实现：

- Plane Issue 关联 GitLab Issue
- MR 创建/合并时自动更新 Plane Issue 状态
- 通过 GitLab Webhook 实现实时同步

### 与 MCP 方案结合

在 Plane + opencode + MCP 工作流中：

- opencode 开发完成后 `git push` 到 GitLab
- opencode 通过 Plane MCP 更新 Issue 状态
- GitLab Webhook 通知 Plane 更新 MR 信息
