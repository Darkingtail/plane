# PF-009: Workflow 状态流转限制

## 背景

Plane CE 的状态可以随意跳转，缺少 Jira 类似的 Workflow 能力：限制状态只能按预定义路径流转。

Plane Pro 版有 Workflow 功能，但 CE 源码中只有空占位组件（`apps/web/ce/components/workflow/`），后端无任何实现。

## 目标

为 CE 实现状态流转限制，支持定义合法的状态转换路径。

## 参考流程

```
         ┌─── INTEGRATING ◄──┐
         │         │          │
         ▼         ▼          │
TODO → DEVELOPING ──────► TESTING → TO_PUBLISH → DONE
         │                    │
         ▼                    │
      DISCARDED ◄─────────────┘
```

- DEVELOPING 可到: INTEGRATING, TESTING, DISCARDED
- INTEGRATING 可到: DEVELOPING, TESTING
- TESTING 可到: DEVELOPING, INTEGRATING, TO_PUBLISH, DISCARDED
- TO_PUBLISH 可到: DONE

## 实现方案（待细化）

### 后端

- [ ] 新增 `WorkflowTransition` Model（project, from_state, to_state）
- [ ] State 变更时校验转换合法性，非法返回 400
- [ ] 提供 CRUD API 管理转换规则
- [ ] 未配置 workflow 时保持当前行为（不限制）

### 前端

- [ ] 状态选择器只显示当前状态的合法下一步
- [ ] 项目设置页新增 Workflow 配置入口
- [ ] （可选）可视化流程图编辑

### 数据模型草案

```python
class WorkflowTransition(ProjectBaseModel):
    from_state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="transitions_from")
    to_state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="transitions_to")

    class Meta:
        unique_together = ["project", "from_state", "to_state"]
```

## 现有代码参考

| 路径                                              | 说明                             |
| ------------------------------------------------- | -------------------------------- |
| `apps/api/plane/db/models/state.py`               | State 模型，无转换规则字段       |
| `apps/api/plane/api/views/state.py`               | State API，仅 CRUD               |
| `apps/web/ce/components/workflow/`                | CE 占位组件（空实现）            |
| `apps/web/core/constants/plans.tsx`               | Pro 版 Workflow 功能定义         |
| `apps/api/plane/bgtasks/issue_automation_task.py` | CE 仅有的自动化（定时归档/关闭） |

## 开放问题

- 是否需要角色权限控制（谁能执行哪些转换）？
- 是否需要转换条件（如必须填某字段才能流转）？
- 是否对接 gitlab-bridge（状态流转触发 Git 操作）？
