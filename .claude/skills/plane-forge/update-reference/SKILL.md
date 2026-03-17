---
name: update-reference
description: Use when checking what Plane natively supports, verifying CE vs Pro feature boundaries, or updating docs/plane-forge/reference/ after a new Plane upstream release
---

# Update Plane Reference

## Overview

通过查询 Plane 官方资料，更新 `docs/plane-forge/reference/` 下的参考文档，确保"CE 原生支持什么、Pro 独占什么"的判断始终准确。

## 两个目标文件

| 文件                    | 更新时机                                |
| ----------------------- | --------------------------------------- |
| `plane-capabilities.md` | 上游新增功能、发现 CE 能力记录有误      |
| `plane-editions.md`     | 版本/定价结构变化、功能从 Pro 下放到 CE |

## 信息来源优先级

按可信度从高到低：

1. **Plane 源码**（最权威）— 直接搜索源码确认功能是否存在于 CE

   ```bash
   # 搜索功能关键词
   grep -r "custom_properties" apps/ --include="*.py" -l
   ```

2. **Plane 官方文档** — https://docs.plane.so
   - CE vs Pro 能力对比：https://docs.plane.so/self-hosting/editions
   - 功能列表：https://docs.plane.so/features

3. **Plane 定价页**（Cloud 层级对应功能）— https://plane.so/pricing

4. **GitHub Release Notes** — 确认某功能在哪个版本引入
   ```bash
   gh release list --repo makeplane/plane --limit 10
   gh release view v1.2.2 --repo makeplane/plane
   ```

## 操作流程

### 场景 A：验证某功能 CE 是否支持

1. 先查 `plane-editions.md` 中的对比表，有记录直接用
2. 若表中无记录或不确定，搜源码确认
3. 若确认与现有记录不符，更新对应条目并注明 `（已于 vX.Y.Z 更新）`

### 场景 B：合并上游新版本后更新

1. 查看该版本 release notes（参考 `docs/plane-forge/sync/`）
2. 对每条新功能/变化：
   - 判断是 CE 还是 Pro 引入
   - 更新 `plane-capabilities.md` 对应区块
   - 若涉及版本边界变化，更新 `plane-editions.md`
3. 更新文件顶部的 `> 更新于 YYYY-MM-DD`（通过 `date` 命令获取）

### 场景 C：定价/版本结构变化

1. 访问 https://plane.so/pricing 确认最新层级
2. 更新 `plane-editions.md` 中的功能对比表
3. 重点关注：是否有功能从付费层下放到 Free/CE

## 更新条目格式

在 `plane-capabilities.md` 中：

```markdown
| 功能名 | ✅/❌/⚠️ | 说明（如有限制注明）|
```

状态符号：

- `✅` CE 完整支持
- `❌` CE 不支持（Pro/Business 专属）
- `⚠️` CE 部分支持或有限制

在 `plane-editions.md` 中更新后在备注列标注版本：

```markdown
| 功能名 | ❌ | ✅ | ✅ | ✅ | 自 v1.2.0 引入 |
```

## 注意事项

- **不要依赖官方文档判断 CE 边界**——官方文档经常混淆 CE 和商业版，源码是最终裁判
- 占位注释 ≠ 已实现：CE 源码中存在 `# TODO: custom properties` 类注释，但功能未实装
- Cloud 定价页的功能层级 ≈ 对应自托管版本，但不完全等价
