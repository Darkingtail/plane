# Plane + OpenCode AI Agent 服务设计方案

## 概述

该服务将 Plane 的 Webhook 系统与 OpenCode 集成，实现从 Issue 需求到 GitHub PR 的自动化代码实现。

## 架构图

```
┌─────────────┐     Webhook      ┌─────────────────┐     队列       ┌─────────────────┐
│   Plane     │ ──────────────►  │  AI Agent API   │ ────────────►  │  任务处理器     │
│  (Issues)   │   POST /webhook  │  (Express.js)   │    (BullMQ)    │                 │
└─────────────┘                  └─────────────────┘                └────────┬────────┘
                                                                             │
                                        ┌────────────────────────────────────┤
                                        │                                    │
                                        ▼                                    ▼
                               ┌─────────────────┐                  ┌─────────────────┐
                               │   OpenCode      │                  │   GitHub API    │
                               │   (AI 代码生成) │                  │   (创建 PR)     │
                               └─────────────────┘                  └─────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  本地 Git 仓库  │
                               └─────────────────┘
```

## 技术栈

| 组件        | 技术                                   | 用途           |
| ----------- | -------------------------------------- | -------------- |
| API 服务器  | Express.js + TypeScript                | Webhook 接收器 |
| 任务队列    | BullMQ + Redis                         | 异步任务处理   |
| AI 代码生成 | OpenCode SDK (`@opencode-ai/opencode`) | 代码实现       |
| Git 操作    | simple-git                             | 分支管理       |
| GitHub 集成 | Octokit                                | PR 创建        |
| Plane 集成  | REST API                               | 状态更新       |

## 项目结构

```
apps/ai-agent/
├── package.json
├── tsconfig.json
├── .env.example
├── src/
│   ├── index.ts                    # 入口文件
│   ├── config/
│   │   └── index.ts                # 环境配置
│   ├── api/
│   │   ├── server.ts               # Express 服务器设置
│   │   ├── routes/
│   │   │   └── webhook.ts          # Webhook 端点
│   │   └── middleware/
│   │       └── verify-signature.ts # HMAC 验证
│   ├── queue/
│   │   ├── connection.ts           # Redis/BullMQ 设置
│   │   ├── producer.ts             # 任务创建
│   │   └── worker.ts               # 任务处理
│   ├── services/
│   │   ├── opencode.ts             # OpenCode SDK 集成
│   │   ├── git.ts                  # Git 操作
│   │   ├── github.ts               # GitHub PR 创建
│   │   └── plane.ts                # Plane API 客户端
│   ├── types/
│   │   └── index.ts                # TypeScript 接口
│   └── utils/
│       └── logger.ts               # 日志工具
└── Dockerfile
```

## 核心组件设计

### 1. Webhook 端点

**文件: `src/api/routes/webhook.ts`**

```typescript
// 处理 Plane Webhook 事件
// 过滤 issue.created 和 issue.updated 事件
// 验证 HMAC-SHA256 签名
// 提取 Issue 数据并加入队列

interface PlaneWebhookPayload {
  event: string; // "issue"
  action: string; // "created" | "updated"
  webhook_id: string;
  workspace_id: string;
  data: {
    id: string;
    name: string;
    description_html: string;
    project: string;
    state: { name: string };
    labels: Array<{ name: string }>;
    // ... 其他 issue 字段
  };
}

// 触发条件:
// - action === "created" 且标签包含 "ai-implement"
// - action === "updated" 且新增标签 "ai-implement"
```

### 2. 任务队列

**文件: `src/queue/worker.ts`**

任务处理工作流:

1. 接收包含 Issue 数据的任务
2. 克隆/拉取目标仓库
3. 创建特性分支: `ai/issue-{issue_id}`
4. 调用 OpenCode 实现需求
5. 提交更改
6. 推送分支到远程
7. 创建 GitHub PR
8. 更新 Plane Issue 状态

### 3. OpenCode 集成

**文件: `src/services/opencode.ts`**

三种集成方式（推荐方案 B）:

**方案 A: CLI 调用**

```typescript
import { spawn } from "child_process";

async function implementWithCLI(requirement: string, repoPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const process = spawn("opencode", ["--yes", "--message", requirement], {
      cwd: repoPath,
      env: { ...process.env, ANTHROPIC_API_KEY: config.anthropicApiKey },
    });
    // 处理 stdout, stderr, exit
  });
}
```

**方案 B: SDK 集成（推荐）**

```typescript
import { Client } from "@opencode-ai/opencode";

const client = new Client({ url: "http://localhost:3007" }); // OpenCode 服务器

async function implementWithSDK(requirement: string, sessionId: string): Promise<void> {
  // 创建或恢复会话
  const session = await client.session.create({ path: repoPath });

  // 发送实现请求
  const stream = await client.chat.stream({
    sessionId: session.id,
    content: `实现以下需求:\n\n${requirement}`,
  });

  // 处理流式响应
  for await (const event of stream) {
    if (event.type === "part" && event.part.type === "tool-invocation") {
      // OpenCode 正在修改文件
      logger.info("工具:", event.part.toolName);
    }
  }
}
```

**方案 C: 直接 MCP 集成**

```typescript
// 将 OpenCode 作为 MCP 服务器运行，通过 stdio 通信
// 更复杂但提供更细粒度的控制
```

### 4. Git 服务

**文件: `src/services/git.ts`**

```typescript
import simpleGit, { SimpleGit } from "simple-git";

class GitService {
  private git: SimpleGit;

  async ensureRepo(repoUrl: string, localPath: string): Promise<void>;
  async createBranch(branchName: string, baseBranch?: string): Promise<void>;
  async commitAll(message: string): Promise<string>;
  async push(branchName: string): Promise<void>;
}
```

### 5. GitHub 服务

**文件: `src/services/github.ts`**

```typescript
import { Octokit } from "@octokit/rest";

class GitHubService {
  async createPullRequest(params: {
    owner: string;
    repo: string;
    head: string; // 特性分支
    base: string; // 目标分支 (main)
    title: string;
    body: string;
    issueUrl: string; // 链接回 Plane Issue
  }): Promise<{ url: string; number: number }>;
}
```

### 6. Plane 服务

**文件: `src/services/plane.ts`**

```typescript
class PlaneService {
  private baseUrl: string;
  private apiKey: string;

  // 更新 Issue 状态
  async updateIssue(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: {
      state_id?: string;
    }
  ): Promise<void>;

  // 添加评论到 Issue
  async addComment(workspaceSlug: string, projectId: string, issueId: string, comment: string): Promise<void>;

  // 获取项目详情（用于获取仓库 URL）
  async getProject(workspaceSlug: string, projectId: string): Promise<Project>;
}
```

## 配置文件

**文件: `.env.example`**

```env
# 服务器
PORT=3006
NODE_ENV=development

# Redis（用于 BullMQ）
REDIS_HOST=localhost
REDIS_PORT=6379

# Webhook 安全
WEBHOOK_SECRET=your-plane-webhook-secret

# OpenCode
OPENCODE_SERVER_URL=http://localhost:3007
# 或者使用 CLI 模式:
ANTHROPIC_API_KEY=your-anthropic-api-key

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_DEFAULT_BASE_BRANCH=main

# Plane API
PLANE_API_URL=http://localhost:8000/api/v1
PLANE_API_KEY=your-plane-api-key

# 仓库存储路径
REPOS_BASE_PATH=/var/repos
```

## 工作流程详解

```
1. 用户在 Plane 中创建/更新 Issue，添加 "ai-implement" 标签
2. Plane 发送 Webhook 到 AI Agent
3. AI Agent 验证签名并提取 Issue 数据
4. 任务加入 BullMQ 队列

5. Worker 处理任务:
   a. 从 Plane 获取项目信息（找到关联的 GitHub 仓库）
   b. 本地克隆/更新仓库
   c. 创建分支: ai/issue-{id}
   d. 解析 Issue 描述作为需求
   e. 调用 OpenCode 处理需求
   f. OpenCode 修改代码文件
   g. 提交更改: "feat: {issue 标题} (Plane #{id})"
   h. 推送分支
   i. 创建 GitHub PR:
      - 标题: Issue 标题
      - 内容: Issue 描述 + Plane Issue 链接
   j. 更新 Plane Issue:
      - 添加 PR 链接评论
      - 更改状态为"审核中"
```

## Plane Webhook 设置

在 Plane 工作区设置中创建 Webhook:

- **URL**: `https://your-agent-domain.com/webhook/plane`
- **Secret**: 强随机字符串（用于 HMAC 验证）
- **事件**:
  - [x] Issues（必选）
  - [ ] Projects（可选，用于仓库同步）

## GitHub 仓库关联

两种方式:

### 方式 A: 项目自定义字段

在 Plane 项目中添加自定义字段 "GitHub Repo"，格式: `owner/repo`

### 方式 B: 配置映射

```typescript
// config/repo-mapping.ts
export const repoMapping: Record<string, string> = {
  "project-uuid-1": "org/repo-name",
  "project-uuid-2": "org/another-repo",
};
```

## 错误处理

| 错误类型         | 处理方式                             |
| ---------------- | ------------------------------------ |
| Webhook 签名无效 | 返回 401，记录警告日志               |
| OpenCode 失败    | 重试 3 次，然后在 Issue 添加错误评论 |
| Git 推送失败     | 检查权限，通过 Plane 评论通知        |
| PR 创建失败      | 记录错误，更新 Issue 为失败状态      |
| 速率限制         | 队列中使用指数退避                   |

## 部署方案

### Docker Compose 配置

```yaml
# 添加到现有 docker-compose.yml
ai-agent:
  build:
    context: ./apps/ai-agent
    dockerfile: Dockerfile
  ports:
    - "3006:3006"
  environment:
    - REDIS_HOST=plane-redis
    - REDIS_PORT=6379
    - PLANE_API_URL=http://api:8000/api/v1
    - OPENCODE_SERVER_URL=http://opencode:3007
  depends_on:
    - plane-redis
    - api
  volumes:
    - ai-repos:/var/repos # 克隆的仓库

opencode:
  image: opencode-ai/opencode:latest
  ports:
    - "3007:3007"
  environment:
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  volumes:
    - ai-repos:/var/repos

volumes:
  ai-repos:
```

## 实施阶段

### 第一阶段: 核心基础设施

- [ ] 项目初始化 (package.json, tsconfig 等)
- [ ] Express 服务器与 Webhook 端点
- [ ] HMAC 签名验证
- [ ] BullMQ 队列设置

### 第二阶段: 服务集成

- [ ] Git 服务（克隆、分支、提交、推送）
- [ ] GitHub 服务（PR 创建）
- [ ] Plane 服务（状态更新、评论）

### 第三阶段: OpenCode 集成

- [ ] OpenCode SDK 客户端
- [ ] Issue 描述解析为需求
- [ ] 代码生成工作流

### 第四阶段: 完善与部署

- [ ] 错误处理与重试逻辑
- [ ] 日志与监控
- [ ] Docker 容器化
- [ ] 文档编写

## 安全考虑

1. **Webhook 验证**: 始终验证 HMAC-SHA256 签名
2. **API 密钥**: 存储在环境变量中，永不提交
3. **仓库访问**: 使用 Deploy Key 或 GitHub App，权限最小化
4. **网络**: AI Agent 应在私有网络中，仅暴露 Webhook 端点
5. **代码审查**: AI 生成的 PR 应在合并前进行人工审查

## 未来增强

- 支持 GitLab/Bitbucket
- 多 AI 提供商支持（不仅限于通过 OpenCode 使用 Anthropic）
- 测试生成与验证
- 代码审查反馈循环
- Issue 复杂度评估
- 多 Issue 并行处理
