# PF-007: CE 版本无 12 人用户数限制

[TOC]

**结论：** Plane CE 自托管版本 **没有** 12 人成员限制。可以无限添加成员。

---

## 调研过程

### 1. 后端代码审查

**邀请入口** `apps/api/plane/app/views/workspace/invite.py` — `WorkspaceInvitationsViewset.create()`：

```
接收 emails → 校验角色权限 → 校验邮箱格式 → 检查是否已是成员 → 创建邀请 → 发送邮件
```

- 全流程 **无** `member_count` / `limit` / `max` 上限检查
- 通过 Django `manage.py shell` + `inspect.getsource()` 运行时审查源码，确认无限制关键字
- `WorkspaceMember` Model 仅有 `unique(workspace, member)` 约束，无数量限制
- Django `pre_save` / `post_save` signals 中无成员数量检查

### 2. 前端代码审查

**计划对比常量** `apps/web/core/constants/plans.tsx`：

| 部署方式      | Free 计划显示 | 实际含义                        |
| ------------- | ------------- | ------------------------------- |
| Cloud（SaaS） | `"12"`        | SaaS 后端强制执行（非开源代码） |
| Self-hosted   | `"~50"`       | 性能建议值，**非硬限制**        |

**关键发现：self-hosted Billing 页面过滤掉了 Free 列**

- CE 构建硬编码 `isSelfManaged = true`（`apps/web/ce/components/workspace/billing/comparison/root.tsx`）
- `PlansComparisonBase` 只渲染 Pro / Business / Enterprise 列
- Free 计划的 `"12"` 或 `"~50"` **在 self-hosted 页面上完全不可见**

**邀请弹窗** `apps/web/ce/components/workspace/members/invite-modal.tsx`：

- 无 `isInviteDisabled` prop
- 无成员数量校验

### 3. 实际验证

在本地 CE 实例的 `wisfe` workspace 上批量创建 15 个测试用户：

```
Workspace: wisfe
Before: 3 members
After: 18 members
Errors: 0
```

**突破 12 人无任何拦截。**

---

## 结论

| 验证维度          | 结果                             |
| ----------------- | -------------------------------- |
| 后端 API 源码     | 无成员数量校验                   |
| Django Model      | 无数量约束                       |
| Django Signals    | 无限制 hook                      |
| 前端邀请弹窗      | 无禁用逻辑                       |
| 前端 Billing 页面 | self-hosted 模式下不展示 Free 列 |
| 实际测试 18 人    | 全部成功                         |

**PF-007 无需实施。** CE 自托管版本没有 12 人限制，`plans.tsx` 中的 `"12"` 仅为 Cloud SaaS 的显示文案，对 self-hosted 不可见也不生效。

---

## 辅助脚本

批量添加测试成员脚本：[`scripts/add-test-members.sh`](../scripts/add-test-members.sh)
