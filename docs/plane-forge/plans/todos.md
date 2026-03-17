# Forge Todos

[TOC]

> 记录所有对 Plane CE 的二开功能，包含待办与已完成。详细需求见 `requirements/`。

---

## 说明

**ID 前缀**：`PF-`（Plane Forge）— 所有对 Plane CE 的二开功能统一编号。

---

## 状态说明

| 状态   | 含义                 |
| ------ | -------------------- |
| 待开发 | 需求明确，等待排期   |
| 开发中 | 正在实现             |
| 已完成 | 开发完成，已提交     |
| 待评估 | 需要进一步调研或讨论 |

---

## 功能增强 — 开发中

| ID     | 标题            | 优先级 | 详情                                                                   |
| ------ | --------------- | ------ | ---------------------------------------------------------------------- |
| PF-003 | GitLab 设置页面 | P1     | Workspace Settings 新增 GitLab 配置入口，供 gitlab-bridge 读取仓库映射 |

---

## 功能增强 — 待开发

| ID         | 标题                        | 优先级 | 详情                                                                       |
| ---------- | --------------------------- | ------ | -------------------------------------------------------------------------- |
| PF-004     | Custom Fields + Issue Type  | P2     | [requirements/custom-fields.md](requirements/custom-fields.md)             |
| PF-008     | 组织架构同步与选人增强      | P2     | 待评估 — Godmode 维护组织架构或同步钉钉/企微，首登必选部门，选人按部门筛选 |
| PF-009     | Workflow 状态流转限制       | P2     | [requirements/workflow.md](requirements/workflow.md)                       |
| PF-010     | 钉钉 → Plane 需求录入 (A2A) | P2     | [requirements/dingtalk-a2a.md](requirements/dingtalk-a2a.md)               |
| ~~PF-007~~ | ~~解除 CE 12 人用户数限制~~ | —      | 调研结论：CE 无此限制，无需实施。[详情](requirements/member-limit.md)      |

---

## 功能增强 — 已完成

| ID     | 标题                      | 优先级 | 说明                                       | Commit       |
| ------ | ------------------------- | ------ | ------------------------------------------ | ------------ |
| PF-001 | 自定义 LLM Provider       | P1     | Godmode 支持 OpenRouter 等第三方 AI 服务商 | `ee54a04e5c` |
| PF-002 | 本地开发禁用 CSRF         | P0     | 修复 Admin 登录 403，仅影响 local.py       | `0578af85ff` |
| PF-005 | GitLab Bridge 基础工作流  | P1     | 状态变更触发分支操作（开发中→测试中）      | —            |
| PF-006 | opencode + Plane MCP 打通 | P1     | AI 编码工具直接读写 Plane 任务             | —            |
