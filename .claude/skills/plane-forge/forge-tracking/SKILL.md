---
name: forge-tracking
description: Use when a new custom feature or source code modification to Plane CE is completed - guides updating docs/plane-forge/tracking/overview.md to record the change for upgrade safety
---

# Forge Tracking Update

## Overview

每当我们修改了 Plane 上游源码（非新增独立文件，而是改动上游已有代码），必须同步写入 `docs/plane-forge/tracking/overview.md`，确保升级时冲突可预见、可追踪。

## 上手前先收集这些信息

| 字段        | 来源                                       |
| ----------- | ------------------------------------------ |
| 改动编号    | 现有表格最大编号 +1                        |
| 状态        | `✅ 已提交` 或 `🔧 进行中`                 |
| 受影响文件  | 相对于仓库根目录的路径                     |
| 改动目的    | 一句话说清楚 what & why                    |
| 关联 commit | `git log --oneline -1` 获取 hash + message |
| 升级风险    | 见下方风险评级                             |

## 风险评级

| 风险  | 适用场景                                             |
| ----- | ---------------------------------------------------- |
| 🟢 低 | 新增独立文件、修改 local-only 配置、上游几乎不会触碰 |
| 🟡 中 | 修改现有函数/API、上游同一区域可能迭代               |
| 🔴 高 | 修改核心/共享逻辑，冲突概率高                        |

## 操作步骤

1. **读取** `docs/plane-forge/tracking/overview.md` 确认当前最大编号
2. **在快速汇总表格末尾追加一行**：
   ```
   | N | ✅ 已提交 | `path/to/file` | 功能简述 |
   ```
3. **在详细记录末尾追加新条目**，参照以下模板：

```markdown
---

### 改动 N：<改动标题>

**目的**：<为什么要做这个改动，解决什么问题>

**关联 commit**：`<hash> <commit message>`

**受影响文件（N 个）**：

#### `path/to/file`

- 改动点 1
- 改动点 2

**升级风险**：🟢/🟡/🔴 <级别>

- 具体风险说明（上游升级时需关注什么）
```

4. **如有必要**，在"升级操作流程 → 每条改动的升级检查点"表格末尾追加一行检查项

## 判断标准：哪些改动需要记录？

| 需要记录 ✅                       | 不需要记录 ❌                     |
| --------------------------------- | --------------------------------- |
| 修改上游已有文件                  | 新增与上游完全无关的独立文件      |
| 修改上游函数签名或返回值          | `services/`、`docs/` 下的扩展内容 |
| 在上游文件中添加新字段/配置       | 独立微服务（gitlab-bridge 等）    |
| 修改 Django settings / middleware |                                   |

## 进行中 → 已提交

改动从 `🔧 进行中` 完成后，更新两处：

1. 快速汇总表格中的状态列：`🔧 进行中` → `✅ 已提交`
2. 详细记录中补充 `**关联 commit**` 行
