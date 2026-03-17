# Sync — 上游版本同步记录

[TOC]

---

## 用途

追踪 makeplane/plane 上游发版节奏，记录每个版本的完整变更内容，并标注与本 fork（`feature/dev`）的差异和合并决策。

---

## 目录结构

```
sync/
  README.md        ← 本文件，说明规范
  overview.md      ← 所有版本汇总 + 当前同步状态
  v1.2.2.md        ← 单版本详细分析
  v1.2.1.md
  v1.2.0.md
  ...
```

---

## 文件命名规范

按上游 Plane 版本号命名，遵循 semver：

| 文件名      | 版本类型 | 说明                             |
| ----------- | -------- | -------------------------------- |
| `v1.2.2.md` | `patch`  | 安全修复或 bug 修复，无新功能    |
| `v1.2.0.md` | `minor`  | 新功能或增强，向下兼容           |
| `v1.0.0.md` | `major`  | 重大变更，可能有 breaking change |

---

## 每个版本文件的格式

每个版本文件分两部分：

**① Plane 原始发版信息**：忠实记录上游 release notes，包含 Features / Enhancements / Bug Fixes / Security / Chores / Breaking Changes 等所有类别。

**② 我们的评估**：基于本 fork 定制内容，给出合并优先级、冲突风险、同步状态。

---

## 同步状态标记

| 标记              | 含义                              |
| ----------------- | --------------------------------- |
| 🔴 待合并（高优） | 含安全漏洞修复，必须尽快合并      |
| 🟡 待合并（建议） | 有价值的功能或 bug 修复，建议合并 |
| ✅ 已合并         | 已合入 `feature/dev`              |
| ⏭️ 跳过           | 评估后决定不合并，注明原因        |

---

## 如何更新

每次上游发版后：

1. 查看上游 release notes：`gh release view vX.Y.Z --repo makeplane/plane`
2. 在此目录新建 `vX.Y.Z.md`，按格式填写两部分内容
3. 更新 `overview.md` 中的当前状态和该版本条目
4. 决定是否合并，执行后更新状态标记

```bash
# 查看落后情况
git log upstream/preview ^feature/dev --oneline | wc -l

# 合并上游
git checkout preview && git fetch upstream && git merge --ff-only upstream/preview
git checkout feature/dev && git merge preview
```
