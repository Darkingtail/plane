# Plane 应用分层概览 — 演讲稿

> Excalidraw 图（合并版）: https://excalidraw.com/#json=R5dK8wQdYDDryy3r5KPXq,JSbFMSFEOiKow3k-N-hBTA
> plane 以及 jira 能力对比 https://excalidraw.com/#json=wxHy_48oS_lw2NvSoarwP,FqZ9yAvnFOl3jEi51aa5Yg
> plane 的优势 https://excalidraw.com/#json=cRynoahxskSGa_mhlMJcr,ZLb0hudq2ygYybnm_SoMKQ
>
> 配合三张 Excalidraw 图使用，每张图对应一个章节。

---

## 第一章: 应用分层概览

> Excalidraw 图: https://excalidraw.com/#json=Cw2igxGJsjNqFJjv7l2vo,KvdZkeGwRZHcps5iHac7wA

Plane 按应用部署和用户角色可见性，可以分为四层：多实例部署层、God Mode 管理层、核心工作层和对外展示层。

### L1: 多实例部署层

最上面是多实例部署层。Plane 支持独立部署多个实例，每个实例拥有完全独立的数据库、配置和用户体系。比如我们公司可以部署多个实例，彼此之间数据完全隔离。对应的后端模型是 `Instance`、`InstanceAdmin` 和 `InstanceConfiguration`。

### L2: God Mode（实例管理面板）

往下是 God Mode，也就是实例管理面板。这是一个独立的前端应用 `apps/admin`，跑在 3001 端口。它是整个实例的"上帝视角"，实例管理员在这里做五件事：

- **用户管理**：管理实例级别的管理员账号
- **实例配置**：设置实例名称、域名、遥测开关等
- **认证管理**：配置 OAuth 登录方式，支持 GitHub、GitLab、Google、Gitea，以及密码策略
- **AI 配置**：对接 OpenAI 等大模型服务商，我们的版本还支持了 OpenRouter 等第三方服务
- **Workspace 总览**：查看和管理实例内所有 Workspace，控制是否允许创建新 Workspace 等开关

### L3: 核心工作层

L3 是核心工作层，也是用户日常使用最多的部分。主应用 `apps/web` 跑在 3000 端口。这一层的组织结构是 Workspace → Project → Work Item。一个实例下可以有多个 Workspace，每个 Workspace 下又有多个 Project。

<!-- 这里要特别说明一个关键设计：**Workspace 之间在业务层是完全隔离的**。虽然数据库层面并不阻止跨 Workspace 的数据关联，但业务逻辑和前端 UI 都限制在同一个 Workspace 内。所以如果你有跨团队的协作需求，应该把多个团队放在同一个 Workspace 下，用不同的 Project 来组织。同一个 Workspace 内，Work Item 可以跨 Project 建立关联关系，比如"阻塞"、"关联"、"重复"等，这个后面实体层级图会详细讲。 -->

### L4: Spaces（对外只读展示层）

最底层是 Spaces，对外只读展示层。独立应用 `apps/space`，跑在 3002 端口。它通过 `DeployBoard` 模型生成公开链接（anchor），可以把项目的路线图、工作进度、反馈收集等内容分享给外部用户。支持展示的内容类型包括 Project、Work Item、Module、Cycle、Page、View、Intake。外部用户可以评论、点赞、投票，但不能修改任何数据——这是一个纯只读的展示层。

### 小结

L1 管部署隔离，L2 管实例配置，L3 是日常工作的核心，L4 负责对外展示。四层各司其职，从上到下是管理粒度从粗到细的过程。

---

## 第二章: L3 实体层级

> Excalidraw 图: https://excalidraw.com/#json=sEYQ8moi67o-RQpKZ2BmT,uIO4ImiiOkdb0CV2yUSLjg

接下来我们深入 L3 核心工作层，看看里面的实体是怎么组织的。

### Workspace 层

最外层是 Workspace。Workspace 是 Plane 的顶层组织单元，类似于 Jira 里的 Site。一个 Workspace 包含以下几个核心概念：

- **成员管理（WorkspaceMember）**：三个角色——admin、member、guest，控制不同的权限范围
- **团队（Team）**：Pro 功能，CE 不支持
- **标签（Label）**：Workspace 级别的标签，所有 Project 共享
- **协作文档（Page）**：Workspace 级别的文档，可以通过 ProjectPage 多对多关联到多个 Project，支持嵌套和版本历史
- **个人便签（Sticky）**：个人使用的快速记录
- **筛选视图（View）**：预设筛选条件保存为视图，快速查看特定 Work Item 集合（如"分配给我的未完成任务"、"所有 P0 的 Work Item"）。分 Workspace 级（跨 Project）和 Project 级两种，预置 4 个默认视图：All Issues、Assigned、Created、Subscribed
- **分析（Analytics）**：Workspace 级数据统计面板，按项目/成员/优先级/标签等维度统计 Work Item 数量，支持自定义 X 轴、Y 轴、分组维度做交叉分析。简单说：View 是"筛选列表"，Analytics 是"统计图表"
- **Webhook**：Workspace 级别的事件推送，支持订阅 Project、Work Item、Cycle、Module、评论 5 类事件，状态变更时自动 POST 到指定 URL，带 HMAC-SHA256 签名验证。

### Project 层

Workspace 里面是 Project。每个 Project 有自己的：

- **成员（ProjectMember）**：Project 级别的成员和角色
- **状态（State）**：五个状态组——backlog、unstarted、started、completed、cancelled。每个组下可以自定义多个具体状态
- **估算（Estimate → EstimatePoint）**：用相对大小（而非时间）估算工作量的体系。在 Project Settings → Estimates 定义档位（如 1/2/3/5/8 故事点），开启后 Work Item 上出现 Estimate 字段可选点数。团队统计几轮迭代后得出速率（如"每轮 20 点"），用于排期预估
- **标签（Label）**：Project 级别的标签，与 Workspace 级标签共存
- **筛选视图（View）**：Project 级别的自定义视图

### 三大工作容器

Project 内有三大工作容器：

1. **Cycle（迭代）**：等同于 Jira 的 Sprint。它是时间盒——有明确的开始和结束日期。一个 Work Item 同一时间只能属于一个 Cycle（多对一）。迭代结束后，未完成的 Work Item 可通过 Transfer 功能转移到下一轮 Cycle，原 Cycle 生成进度快照存档。Cycle 自身只有 Lead（负责人），页面上显示的"受理人/负责人"列表是从 Cycle 内所有 Work Item 的 assignees 汇总而来。

2. **Module（模块）**：类似于 Jira 的 Epic。它是功能分组——按业务功能组织 Work Item，比如"用户管理模块"、"支付模块"。一个 Work Item 可以属于多个 Module（多对多）。Module 有自己的状态生命周期（backlog → planned → in-progress → paused → completed → cancelled），有 Lead + Members。

**Cycle vs Module 实际用法建议**：Cycle 是消耗性的（时间到了就归档翻篇），Module 是持久性的（功能没完成就一直挂着）。两者功能有重叠，小团队选一个用就行，不必两个都开。偏 Scrum 的团队用 Cycle（按 Sprint 节奏走），偏看板/功能交付的团队用 Module（按功能模块跟踪）。都要用的话：Module 管"功能全景"，Cycle 管"每轮排期"。

3. **Intake（收件箱）**：需求审批入口，需在 Project Settings → Features 中开启。项目成员在 Intake 里提交需求请求，状态流为 pending → accepted/rejected/snoozed/duplicate。accepted 后转为正式 Work Item。目前仅支持内部成员提交（source = IN_APP），模型预留了 `source_email`、`external_source` 等外部渠道字段但尚未实现。

### Work Item（后端模型: Issue）

核心实体是 Work Item。每个 Work Item 包含：

- **基本属性**：优先级、状态、负责人、标签、估算点数、开始日期、目标日期
- **子 Work Item**：通过 parent 自引用实现父子关系。注意：业务层限制子 Work Item 必须在同一个 Project 内，虽然数据库层面的 `ForeignKey("self")` 并没有这个约束
- **评论与表态**：支持评论，评论可以收到表情反应
- **变更日志**：IssueActivity 记录每一次字段变更，用于审计追踪
- **附件与链接**：支持文件附件和外部链接
- **快照历史**：IssueVersion 保存完整快照，可以回溯到任意历史版本

### Work Item 关联关系

Plane 支持 6 种关联类型：

| 正向关系                  | 反向关系               | 是否对称 |
| ------------------------- | ---------------------- | -------- |
| blocked_by（被阻塞）      | blocking（阻塞）       | 否       |
| relates_to（关联）        | relates_to（关联）     | 是       |
| duplicate（重复）         | duplicate（重复）      | 是       |
| start_before（需先开始）  | start_after（后开始）  | 否       |
| finish_before（需先完成） | finish_after（后完成） | 否       |
| implemented_by（由…实现） | implements（实现了）   | 否       |

### 关联范围：三层约束

关联的范围有三层约束，这是很多人关心的部分：

| 关联方式       | 数据库约束                                  | 业务层限制                    | 前端 UI                                          |
| -------------- | ------------------------------------------- | ----------------------------- | ------------------------------------------------ |
| 父子 Work Item | `ForeignKey("self")`，无 project 约束       | Serializer 校验必须同 Project | 只能选当前 Project                               |
| Work Item 关联 | 两个 `ForeignKey(Issue)`，无 workspace 约束 | 无显式 workspace 校验         | 有"Workspace Level"开关，打开后可跨 Project 搜索 |
| 跨 Workspace   | 数据库完全不阻止                            | 无实现                        | 无 UI 入口                                       |

也就是说，跨 Project 关联在同一个 Workspace 内是开箱即用的，只需要在添加关联时打开"Workspace Level"开关。而跨 Workspace 目前不支持，但数据库层面已经预留了扩展空间——只需要放宽 Serializer 校验和前端搜索范围即可。

---

## 第三章: L3 Work Item 工作流

> Excalidraw 图: https://excalidraw.com/#json=MAiLKVmWV0qbYARhPxIbE,AC0w-5rBknEgZglw-8q2eg

最后这张图展示的是 Work Item 从创建到完成的完整生命周期。

### 两个输入来源

Work Item 有两个输入来源：

1. **Intake（收件箱）**：外部请求先进入 Intake 队列，处于 pending 状态。产品经理或项目负责人审核后，accepted 的请求会转为正式 Work Item。被拒绝的标记为 rejected，暂时搁置的标记为 snoozed，重复的标记为 duplicate。这是一个需求漏斗——并非所有请求都会变成 Work Item。

2. **草稿 Work Item**：团队成员可以先创建草稿，信息不完整也没关系。草稿不会出现在正式的看板或列表中，等信息补充完整后 publish 为正式 Work Item。

### 两种工作容器

Work Item 创建后，可以被分配到两种容器中：

- **Cycle（迭代）**：按时间维度组织。"这个 Work Item 安排在第 3 轮迭代完成"。
- **Module（模块）**：按功能维度组织。"这个 Work Item 属于用户管理模块"。

一个 Work Item 可以同时属于某个 Cycle 和某个 Module，两者是正交的组织维度。

### 状态流转

状态流转是 Work Item 生命周期的核心。Plane CE 默认提供五个状态组：

1. **Backlog**：需求池，还没排上日程
2. **Unstarted**：已排期但未开始
3. **Started**：开发进行中
4. **Completed**：开发完成
5. **Cancelled**：已取消

目前 CE 版本的状态可以自由跳转，没有流转限制。但我们的二开计划（PF-009）会增加 Workflow 能力——定义合法的状态转换路径，比如"只有 Started 才能流转到 Completed"，类似于 Jira 的 Workflow。

### 工作过程中的操作

在工作过程中，Work Item 可以：

- **创建子 Work Item**：分解大任务为可执行的小任务，形成树状结构
- **建立关联**：与其他 Work Item 建立 6 种关联关系（阻塞、关联、重复、时序依赖、实现关系），支持跨 Project（同 Workspace 内）
- **归档**：完成或取消的 Work Item 可以归档，保持看板整洁

### 两个输出方向

Work Item 还有两个输出方向：

1. **Spaces（对外展示）**：通过 DeployBoard 将 Work Item 的状态和进度公开给外部用户，用于路线图展示或客户反馈收集
2. **View（筛选视图）**：通过自定义筛选条件创建视图，比如"所有 P0 的未完成 Work Item"、"分配给我的本周到期任务"，支持 Project 级和 Workspace 级

### 二开扩展方向

在这个工作流的基础上，我们正在规划三个增强：

- **PF-009 Workflow**：状态流转限制，比如"开发中"只能流转到"集成中"或"测试中"
- **PF-010 钉钉 A2A**：从钉钉群聊或文档中自动捕获需求，通过 Agent-to-Agent 协作录入 Plane 的 Intake
- **AI Agent 自动实现**：Work Item 打上 `ai-implement` 标签后，AI Agent 自动读取需求、生成代码、创建 PR

这三者串联起来就是完整的链路：**需求描述（钉钉）→ 工作项管理（Plane）→ 代码实现（AI Agent）**。
