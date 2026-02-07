# AI 驱动开发自动化路线图

## 总体目标

从半自动辅助开发逐步演进到全自动 AI 驱动的需求实现，最终实现：Issue 创建 → AI 编码 → 测试 → PR → 合并的全流程无人值守。

## 阶段一：opencode + Plane MCP

**目标**：打通 AI 编码工具与项目管理的数据通路，验证可行性。

**原理**：[Plane MCP Server](https://github.com/makeplane/plane-mcp-server) 是 Plane 官方提供的 MCP 协议桥接工具，将 Plane API 封装为 55+ 个 MCP 工具（列任务、读详情、更新状态等）。opencode 原生支持 MCP 协议，在配置文件中声明 MCP Server 后，opencode 启动时会自动拉起 MCP 进程，开发者无需手动运行任何额外服务。

**配置方式**：在项目根目录创建 `opencode.json`，一次配置即可：

```json
{
  "mcp": {
    "plane": {
      "type": "local",
      "command": ["uvx", "plane-mcp-server", "stdio"],
      "environment": {
        "PLANE_API_KEY": "<从 Plane 工作区 Settings > API Tokens 获取>",
        "PLANE_WORKSPACE_SLUG": "<URL 中的 workspace slug>",
        "PLANE_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

> `uvx` 是 Python 包管理器 [uv](https://github.com/astral-sh/uv) 的执行命令（类似 Node.js 的 `npx`），会自动下载并运行 `plane-mcp-server`，无需手动 pip install。首次使用前需安装 uv：`curl -LsSf https://astral.sh/uv/install.sh | sh`

**开发者工作流**：

1. 在项目目录启动 opencode
2. opencode 自动连接 Plane MCP Server（后台进程，无感）
3. 对 opencode 说"列出当前项目 Todo 状态的任务"
4. 选择一个任务，opencode 读取需求详情
5. opencode 编码实现 → 运行测试 → 提交代码
6. opencode 通过 MCP 更新 Issue 状态为"已完成"，添加实现说明评论

**产出**：开发者本地使用 opencode 获取任务、编码、更新状态的完整工作流。

**详细方案**：[plane-opencode-mcp.md](./plane-opencode-mcp.md)

## 阶段二：GitLab/GitHub 深度集成

**目标**：打通任务与代码分支的生命周期，状态驱动自动化操作。

**内容**：

- **OAuth 扩展**：GitLab/GitHub OAuth scope 扩展（`read_api` 等），token 持久化
- **仓库关联**：Plane 项目绑定 GitLab/GitHub 仓库
- **自动建分支**：创建任务时选择关联仓库，自动创建 `feature/` 或 `fix/` 分支
- **任务携带分支信息**：增强阶段一，opencode 通过 MCP 读到仓库和分支，直接切换到目标分支开发
- **Webhook 服务**：监听 Plane 状态变更事件，触发相应分支操作
  - "开发中" → "测试中"：feature 分支合并到 dev
  - 其他状态流转触发对应的分支/部署操作
- **MR/PR 回显**：Plane 内展示关联的 MR/PR 状态、CI/CD 结果

**产出**：任务创建即建分支，状态变更即触发分支操作，Plane 成为开发流程的中枢。

**详细方案**：[gitlab-integration-plan.md](./gitlab-integration-plan.md)

**基础设施**：轻量 Webhook 服务（Express.js），为阶段三复用。

## 阶段三：全自动 AI Agent

**目标**：AI 自动领取任务、编码实现、提交 PR，全流程无人值守。

**内容**：

- **Webhook 扩展**：复用阶段二的 Webhook 服务，新增任务创建/标签事件监听
- **自动触发**：Issue 添加 `ai-implement` 标签 → AI Agent 自动领取
- **AI 编码**：调用 opencode 在目标分支上实现需求
- **自动提 PR**：编码完成后自动创建 MR/PR
- **状态更新**：通过 Plane API 更新 Issue 状态、添加 PR 链接评论
- **错误处理**：失败重试、异常通知

**产出**：Issue 创建 → AI 编码 → PR → 人工审查 → 合并，仅审查环节需要人参与。

**详细方案**：[ai-agent-design.md](./ai-agent-design.md)

## 架构演进

```
阶段一                    阶段二                         阶段三

Plane ──MCP──▶ opencode   Plane ──MCP──▶ opencode        Plane ──Webhook──▶ AI Agent
  │                         │                               │                  │
  └─ 人工选任务              ├─ 人工选任务                    ├─ 自动领任务       │
                            ├─ 任务带分支信息                ├─ 任务带分支信息    │
                            └─ Webhook ──▶ 分支合并服务      └─ Webhook 服务 ◀──┘
                                                                    │
                                                              opencode 自动编码
                                                                    │
                                                              自动提 PR / 更新状态
```

## 基础设施复用关系

```
阶段一：Plane MCP Server + opencode ──────────────────────────────────────┐
阶段二：+ Webhook 服务 + GitLab/GitHub API 集成 ──────────────────────┐   │
阶段三：+ 同一 Webhook 服务扩展 + opencode SDK + 任务队列(BullMQ)    │   │
                                                                     │   │
        每一阶段的产出都是下一阶段的基础，不做无用功 ◀────────────────┘   │
        阶段一的 MCP 工作流在阶段二三中持续使用 ◀────────────────────────┘
```
