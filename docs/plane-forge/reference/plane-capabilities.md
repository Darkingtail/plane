# Plane CE 能力文档

> 基于 Plane Community Edition（CE）源码实测
> CE = GitHub 开源版 = Cloud Free 功能等价

---

## 一、版本说明

| 版本                       | 授权           | 功能层级             |
| -------------------------- | -------------- | -------------------- |
| **Community Edition (CE)** | AGPL v3.0 开源 | = Cloud Free         |
| Commercial Edition         | 商业闭源       | = Cloud Pro/Business |

**我们使用的是 CE**，可完全自托管，数据主权完全自控。

---

## 二、CE 原生能力

### 核心工作管理

| 能力                   | CE 支持 | 说明                                                           |
| ---------------------- | ------- | -------------------------------------------------------------- |
| Issues（工作项）       | ✅      | 完整 CRUD，支持优先级/状态/负责人/标签                         |
| Sub Issues（子工作项） | ✅      | Issue 下挂子 Issue，对应 Jira Sub-task                         |
| 自定义状态机           | ✅      | 每个项目可定义独立状态流转（Backlog/Todo/In Progress/Done 等） |
| Labels（标签）         | ✅      | 多标签，支持工作区级和项目级                                   |
| 优先级                 | ✅      | Urgent/High/Medium/Low/None                                    |
| 截止日期               | ✅      |                                                                |
| 附件 / 链接            | ✅      |                                                                |
| 评论                   | ✅      | 支持 @mention                                                  |

### 视图与可视化

| 能力                 | CE 支持 | 说明                   |
| -------------------- | ------- | ---------------------- |
| Board 看板视图       | ✅      | Kanban 拖拽            |
| List 列表视图        | ✅      |                        |
| Spreadsheet 表格视图 | ✅      | 类 Notion 表格         |
| Gantt 甘特图         | ✅      |                        |
| Calendar 日历视图    | ✅      |                        |
| Analytics 分析       | ✅      | 内置图表，替代自建看板 |

### 迭代与模块管理

| 能力            | CE 支持 | Jira 对应             |
| --------------- | ------- | --------------------- |
| Cycles（迭代）  | ✅      | Sprint                |
| Modules（模块） | ✅      | Component/Epic 的平替 |
| Pages（文档）   | ✅      | Confluence 轻量替代   |

### API 与集成

| 能力          | CE 支持 | 说明                             |
| ------------- | ------- | -------------------------------- |
| 完整 REST API | ✅      | 所有端点开放，文档公开           |
| Webhook 出站  | ✅      | 支持任意 HTTP 端点               |
| MCP Server    | ✅      | `uvx plane-mcp-server`，55+ 工具 |
| 移动端 App    | ✅      | iOS / Android 官方应用           |

---

## 三、CE 不具备的能力（Pro/Business 功能）

| 功能                                   | CE                  | Pro  | 对我们的影响                                           |
| -------------------------------------- | ------------------- | ---- | ------------------------------------------------------ |
| **Work Item Types**（Issue Type 分类） | ❌                  | ✅   | 中等——无法原生区分 Story/Bug/Epic 类型                 |
| **Custom Properties**（自定义字段）    | ❌                  | ✅   | **高**——无法直接对应 Jira 的 30+ 自定义字段            |
| **Epics**（史诗）                      | ⚠️ 骨架在，UI 锁 EE | ✅   | 低——后端模型已有 `is_epic` 字段，CE 前端空壳可二开填实 |
| **Time Tracking**（工时跟踪）          | ❌                  | ✅   | 低——可用描述字段临时记录                               |
| **GitHub/GitLab 官方集成**             | ❌                  | ✅   | 无影响——我们自研 gitlab-bridge 替代                    |
| **Workflows & Approvals**              | ❌                  | ✅   | 低——状态机已够用                                       |
| 用户数                                 | 12人限制            | 无限 | **高**——团队超过 12 人必须解决                         |

---

## 四、CE 能力缺口的应对方案

### 缺口一：Custom Properties（自定义字段）

**应对**：在 CE 源码基础上二开，实现 CustomField 系统（已有完整设计方案）

- 后端：新建 `CustomField` / `CustomFieldValue` Model + API
- 前端：Settings 页面管理字段，Issue Detail 侧边栏展示
- 工作量：约 2 周

### 缺口二：Work Item Types（Issue 类型）

**应对**：

- 短期：用 **Label** 区分类型（`type:Story`、`type:Bug`）
- 长期：与 Custom Properties 一起做（IssueType 的 Model 在 CE 源码中已存在，需补齐 API + 前端）

### 缺口三：Epics

**应对**：CE 已有完整骨架（后端 `IssueType.is_epic=True`，前端 store/组件目录均存在但为空壳），二开填实即可，工作量约 3-5 天，比自定义字段简单得多。短期可用 Module 临时平替。

### 缺口四：用户数 12 人限制

**应对**：CE 源码中用户数限制可通过修改配置或二开解除（明确标注为 CE 限制，可改）

---

## 五、我们的差异化优势（vs 官方 CE）

通过 `feature/dev` 分支二开，我们在 CE 基础上额外具备：

| 扩展能力            | 实现方式                           | 状态                             |
| ------------------- | ---------------------------------- | -------------------------------- |
| GitLab 全流程自动化 | `services/gitlab-bridge/` 独立服务 | 进行中（分支创建✅、联调合并✅） |
| 自定义 LLM Provider | Godmode 源码改动                   | 已完成                           |
| 自定义字段系统      | 源码二开（IssueType+CustomField）  | 设计中，暂停评估                 |
| MCP + AI 编码接入   | opencode + plane-mcp-server        | 已完成                           |
