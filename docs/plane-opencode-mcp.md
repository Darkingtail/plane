# Plane + opencode + MCP 自动化开发方案

## 架构概览

```
Plane (项目管理)  ──MCP──▶  opencode (AI 编码代理)  ──▶  本地代码仓库
     │                           │
     │  Issue/状态/评论           │  读取任务 → 编码 → 测试 → 提交
     │  通过 MCP 双向同步         │
     ▼                           ▼
Plane MCP Server            Git (commit/push)
(uvx plane-mcp-server stdio)
```

**核心思路**：保持 Plane 作为项目管理和 Issue 追踪工具，通过 Plane MCP Server 让 opencode 直接获取任务、读取需求、更新状态，实现 AI 驱动的本地开发闭环。

## 组件说明

| 组件                 | 角色                                     | 地址                  |
| -------------------- | ---------------------------------------- | --------------------- |
| **Plane**            | 项目管理、Issue 追踪、团队协作           | http://127.0.0.1:3000 |
| **Plane MCP Server** | MCP 协议桥接，暴露 Plane API 为 MCP 工具 | 本地 stdio 进程       |
| **opencode**         | AI 编码代理，获取任务并自动开发          | CLI 工具              |

## Plane MCP Server

### 安装前提

- Python 3.10+
- `uv` 包管理器（自动处理 `uvx` 命令）

```bash
# 安装 uv（如果没有）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 可用工具（55+ 个，8 大类）

| 类别                     | 工具数 | 核心工具                                                                                             |
| ------------------------ | ------ | ---------------------------------------------------------------------------------------------------- |
| **Projects**             | 9      | `list_projects`, `retrieve_project`, `get_project_members`                                           |
| **Work Items**           | 7      | `list_work_items`, `create_work_item`, `retrieve_work_item`, `update_work_item`, `search_work_items` |
| **Cycles**               | 12     | `list_cycles`, `list_cycle_work_items`, `add_work_items_to_cycle`                                    |
| **Modules**              | 11     | `list_modules`, `list_module_work_items`, `add_work_items_to_module`                                 |
| **Initiatives**          | 5      | `list_initiatives`, `retrieve_initiative`                                                            |
| **Intake Work Items**    | 5      | `list_intake_work_items`, `create_intake_work_item`                                                  |
| **Work Item Properties** | 5      | `list_work_item_properties`, `create_work_item_property`                                             |
| **Users**                | 1      | `get_me`                                                                                             |

### 关键能力与限制

**能做的**：

- 列出/搜索/读取 Work Item（Issue）详情
- 创建/更新/删除 Work Item
- 更新 Issue 状态（需要 state UUID）
- 管理 Cycles 和 Modules
- 获取项目成员信息

**做不到的**：

- Webhook 推送通知（MCP 是请求-响应模式，需轮询）
- 复杂的自定义查询/过滤（受 API 限制）
- 实时事件订阅

## opencode 配置

### 配置文件位置

opencode 配置文件为 `opencode.json`，查找顺序（后者覆盖前者）：

| 优先级    | 位置                               | 用途       |
| --------- | ---------------------------------- | ---------- |
| 1（最低） | `~/.config/opencode/opencode.json` | 全局配置   |
| 2         | `OPENCODE_CONFIG` 环境变量指定路径 | 自定义路径 |
| 3（最高） | 项目根目录 `opencode.json`         | 项目级配置 |

### Plane MCP 配置（stdio 本地模式）

在项目根目录创建 `opencode.json`：

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

### 获取配置参数

| 参数                   | 获取方式                                                               |
| ---------------------- | ---------------------------------------------------------------------- |
| `PLANE_API_KEY`        | Plane 工作区 → Settings → API Tokens → 创建新 Token                    |
| `PLANE_WORKSPACE_SLUG` | URL 中的 slug：`http://127.0.0.1:3000/<slug>/projects/...`             |
| `PLANE_BASE_URL`       | 本地部署：`http://localhost:8000`；Plane Cloud：`https://api.plane.so` |

### opencode 与 Claude Code 配置差异

| 方面         | Claude Code                 | opencode                             |
| ------------ | --------------------------- | ------------------------------------ |
| 顶层 key     | `"mcpServers"`              | `"mcp"`                              |
| command 格式 | 分离 `"command"` + `"args"` | 单数组 `"command": ["uvx", "..."]`   |
| 环境变量 key | `"env"`                     | `"environment"`                      |
| 传输类型     | 隐式推断                    | 显式 `"type": "local"` 或 `"remote"` |
| 启用/禁用    | 无内置                      | `"enabled": true/false`              |

## 开发工作流

### 典型流程

```
1. PM 在 Plane 创建 Issue（描述需求、验收标准）
2. 开发者启动 opencode
3. opencode 通过 MCP 获取待办 Issue 列表
4. 开发者选择一个 Issue
5. opencode 读取 Issue 详情（需求、上下文）
6. opencode 编码实现 → 运行测试 → 提交代码
7. opencode 通过 MCP 更新 Issue 状态（In Progress → Done）
8. opencode 通过 MCP 添加评论（实现说明、PR 链接等）
```

### opencode 中的 Prompt 示例

```
# 获取待办任务
请列出当前项目中状态为 "Todo" 的所有 Work Items

# 开始开发某个任务
请获取 Work Item PROJ-42 的详细描述，然后根据需求进行开发

# 完成后更新状态
将 PROJ-42 的状态更新为 "Done"，并添加评论说明实现方式
```

## 扩展：远程传输模式

如果使用 Plane Cloud（非自建），可以用远程 HTTP + OAuth：

```json
{
  "mcp": {
    "plane": {
      "type": "remote",
      "url": "https://mcp.plane.so/http/mcp"
    }
  }
}
```

首次连接会打开浏览器进行 OAuth 授权。

## 注意事项

1. **API Key 安全**：不要将 `opencode.json` 中的 API Key 提交到 Git，加入 `.gitignore`
2. **PLANE_BASE_URL**：本地部署用 `http://localhost:8000`，不需要加 `/api` 后缀
3. **uvx 自动安装**：`uvx plane-mcp-server` 会自动下载并在隔离环境运行，无需手动 pip install
4. **State UUID**：更新 Issue 状态需要 state 的 UUID，不是状态名称；先用 `list_work_items` 获取可用状态
5. **轮询 vs 推送**：MCP 不支持 webhook，opencode 每次需要主动查询最新任务状态
