---
name: plane-forge-todos
description: Use when adding a new Plane Forge todo, creating a requirement doc, or marking a todo as completed - manages docs/plane-forge/plans/todos.md and requirements/
---

# Plane Forge Todos

## Overview

管理 `docs/plane-forge/plans/todos.md` 和 `requirements/` 的完整工作流，包含新增 todo、编写需求文档、标记完成三个场景。

---

## 场景一：新增 Todo

### 第一步：确定 PF 编号

读取 `todos.md`，找出所有已有的 `PF-` 编号（含已完成区），取最大值 +1。

### 第二步：收集信息

| 字段           | 说明                                        |
| -------------- | ------------------------------------------- |
| 标题           | 简短描述功能                                |
| 优先级         | P0（紧急）/ P1（高）/ P2（中）/ P3（低）    |
| 状态           | 待开发 / 开发中 / 待评估                    |
| 是否有详细需求 | 有则同步创建 requirements/ 文件（见场景二） |

### 第三步：追加到对应区块

在 `todos.md` 的对应状态区块末尾追加一行：

```markdown
| PF-XXX | 标题 | P1 | 简短说明 或 [requirements/xxx.md](requirements/xxx.md) |
```

---

## 场景二：创建 Requirement 文档

在 `docs/plane-forge/plans/requirements/` 新建 `<功能名>.md`，按以下模板填写：

```markdown
# PF-XXX：<功能标题>

[TOC]

> 优先级：P1 | 状态：待开发

## 背景

<为什么要做这个功能>

## 目标

<做完之后达到什么效果>

## 需求详情

<具体需求描述>

## 实现步骤

1. 步骤一
2. 步骤二

## 影响范围

<涉及哪些文件或模块>

## 验收标准

- [ ] 条件一
- [ ] 条件二
```

创建完成后，在 `todos.md` 对应行的详情列填入文件链接：

```
[requirements/xxx.md](requirements/xxx.md)
```

---

## 场景三：标记 Todo 完成

### 第一步：将行从当前区块移到「已完成」区块

在「已完成」表格末尾追加，**格式与待开发/开发中不同**，多一列 Commit：

```markdown
| PF-XXX | 标题 | P1 | 功能说明 | `<commit hash>` |
```

Commit hash 通过 `git log --oneline -1` 获取；若无直接 commit（如外部服务）填 `—`。

从原区块删除该行。

### 第二步：requirement 文档保留，更新状态行

若该 todo 有对应的 `requirements/xxx.md`，**不要删除**，只更新文件顶部的状态：

```markdown
> 优先级：P1 | 状态：~~待开发~~ ✅ 已完成（2026-XX-XX）
```

### 第三步：若改动涉及上游源码，同步更新 tracking

若该功能修改了 Plane 上游文件，使用 `plane-forge:forge-tracking` skill 同步写入 `tracking/overview.md`。

---

## 快速参考

| 动作         | 改哪里                                                          |
| ------------ | --------------------------------------------------------------- |
| 新增 todo    | `todos.md` 对应状态区块追加一行                                 |
| 新增需求文档 | `requirements/` 新建文件 + `todos.md` 填链接                    |
| 完成 todo    | `todos.md` 移行到已完成区 + requirements 文件更新状态（不删除） |
| 涉及源码改动 | 另用 `plane-forge:forge-tracking` 记录                          |
