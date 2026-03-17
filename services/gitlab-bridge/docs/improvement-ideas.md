# plane-gitlab-bridge 优化思路记录

> 创建时间: 2026-02-27
> 状态: 想法收集，待评估优先级

---

## 已确定要做

### 1. 关联仓库自定义字段（替换 Label 方案）

**当前**: 用 Plane Label（如 `repo:jira1`）标记关联仓库，有以下问题：

- Label 有其他语义（标签/分类），被仓库关联占用后容易混乱
- 管理员需手动在 Plane 和 modules.yml 两处同步维护

**目标**: 在 Plane 项目中新增 Custom Property「关联仓库」

- 类型: multi-select
- 可选值: **直接从 GitLab API 拉取用户有权限的仓库列表**（不依赖 modules.yml）
- 项目管理员在项目设置 → Custom Properties 中配置可用仓库范围
- Bridge 启动时缓存一次仓库列表，定期刷新

**modules.yml 职责收窄**: 只保留工作流配置

```yaml
workflow:
  branches:
    main: "main"
    release: "release"
    test: "test"
    dev: "dev"
  branch_name_template: "feature/{issue_identifier}_{date}_{desc}"
```

---

### 2. 子 Issue「创建分支」触发（兼容 Jira 方式）

**当前**: 已实现，与 Jira 老项目保持一致

- 在父 Work Item 下创建子 Issue，标题含「创建分支 / create branch / 新建分支」
- 自动在「关联仓库」字段对应的 GitLab 仓库中创建 feature 分支
- 在父 Issue 下评论分支链接

---

## 待讨论的优化点

### 3. 状态驱动的自动分支管理（更直觉的 UX）

**想法**: 完全基于状态变化自动管理分支，无需手动创建子 Issue

| 状态变化                   | 触发动作                                |
| -------------------------- | --------------------------------------- |
| 任意 → In Progress         | 自动在关联仓库创建 feature 分支         |
| In Progress → Todo/Backlog | 自动删除 feature 分支（可配置是否开启） |
| 任意 → Integrating         | 将 feature 分支合并到 dev               |
| 任意 → Testing             | 将 feature 分支合并到 test              |
| 任意 → To Publish          | 记录测试通过，评论通知                  |

**优点**:

- 零手动操作，开发者只需拖拽状态
- 与 Plane 的看板工作流完全契合

**需要讨论**:

- In Progress → Todo 删除分支：有风险，分支上可能已有提交。建议只在分支无提交时删除，或改为「归档/禁用」而非删除
- 初次进入 In Progress 时分支不存在才创建，避免重复创建

---

### 4. 仓库列表缓存策略

- Bridge 启动时从 GitLab 拉取并缓存用户可访问仓库
- 提供 `/admin/refresh-repos` 接口手动刷新
- 缓存 TTL: 1 小时（可配置）

---

### 5. Webhook 双向同步

- GitLab MR 合并后，自动更新 Plane Issue 的状态（如 MR merged → 自动变 Testing）
- 需要在 GitLab 仓库配置 webhook 指向 bridge 的 GitLab webhook 端点

---

---

### 6. MR 显示开发者本人（Impersonation Token）

**背景**: 当前所有由 bridge 触发的 GitLab 操作（建分支、建 MR、合并）均以 service token 账号署名（如 gitlabbot），MR 创建人不是实际触发的开发者。Jira 老项目也是同样处理方式，团队未反馈问题。

**方案**: GitLab 管理员为每个用户生成 impersonation token，bridge 根据 Plane 当前操作用户找到对应 token，用该 token 调用 GitLab API，MR 则显示为开发者本人。

**结论**: 低优先级，锦上添花。管理成本较高（每人一个 token，需要定期轮换），当前 service token 方案足够用。

---

## 不做的事（已明确排除）

- modules.yml 维护仓库列表 → 改为 GitLab API 动态拉取
- 用 Label 关联仓库 → 改为 Custom Property
