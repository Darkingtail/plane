# Plane 上游版本同步总览

[TOC]

> 每个版本分两部分：**① Plane 原始发版信息**（客观存档）+ **② 我们的评估**（合并决策）
> 详细单版本分析见同目录各 `vX.Y.Z.md` 文件。

---

## 当前状态

| 项目                 | 值                                                                       |
| -------------------- | ------------------------------------------------------------------------ |
| 上游最新版本         | v1.2.2（2026-02-23）                                                     |
| feature/dev 基于版本 | v1.2.1                                                                   |
| 落后上游             | 43 commits                                                               |
| 领先上游（定制）     | 7 commits                                                                |
| 版本纯净性           | ⚠️ **不再纯净** — feature/dev 在 v1.2.1 基础上叠加了定制改动，已偏离上游 |

> `feature/dev` 不跟随上游版本号，是以 v1.2.1 为基线的 Wisedu 定制分支。
> 合并上游时需逐条对照 `docs/plane-forge/tracking/overview.md` 处理冲突。

---

## v1.2.2（2026-02-23）`patch` 🔴 待合并

### ① Plane 发版信息

**类型**：Security patch

| 类别        | 内容                                                                    |
| ----------- | ----------------------------------------------------------------------- |
| 🔒 Security | Fixed arbitrary modification of API token rate limits（服务端校验缺失） |
| 🔒 Security | Mitigated SSRF vulnerability in work item link handling（URL 未验证）   |
| 🔒 Security | Fixed member information disclosure via publicly accessible endpoint    |
| 🔒 Security | Resolved IDOR vulnerabilities in asset and attachment endpoints         |
| 🔒 Security | Django 升级至 4.2.28                                                    |
| 🔒 Security | cryptography 升级至 46.0.5                                              |

### ② 我们的评估

| 项目             | 内容                                           |
| ---------------- | ---------------------------------------------- |
| 合并优先级       | 🔴 必须——4 个安全漏洞影响生产环境              |
| 与定制的冲突风险 | 🟢 低——纯 API 层安全修复，不涉及我们改动的文件 |
| 状态             | ⬜ 待合并                                      |

---

## v1.2.1（2025-12-12）`patch` ✅ 当前版本

### ① Plane 发版信息

| 类别        | 内容                                                                |
| ----------- | ------------------------------------------------------------------- |
| 🔒 Security | Removed underlying Next.js dependencies（配合 v1.2.0 框架迁移收尾） |

### ② 我们的评估

| 项目       | 内容         |
| ---------- | ------------ |
| 合并优先级 | — 已在此版本 |
| 状态       | ✅ 已合并    |

---

## v1.2.0（2025-12-11）`minor` ✅ 已包含

### ① Plane 发版信息

**✨ Features**

| 功能                               | 说明                                                                   |
| ---------------------------------- | ---------------------------------------------------------------------- |
| Next.js → React Router + Vite 迁移 | 全面替换构建工具，热更新更快，工具链统一                               |
| 新顶部导航栏                       | Search/Inbox 移至顶部全局栏；项目功能变横向 Tab；左侧栏可折叠/图标模式 |
| Power K 增强                       | 键盘驱动全局操作：创建 Issue/Cycle/Module、切换侧边栏、复制链接等      |
| Intake Triage 状态                 | Intake 新增单一 Triage 状态，待分流请求不混入项目状态组                |

**⬆️ Enhancements**

- Simplified user filtering in SearchEndpoint
- Added workspace invitations & project member management endpoints
- Project Icon 创建时自动填充
- 富文本表格块新增全宽选项
- Magic code 改为 6 位纯数字
- 实现 Stickies 外部 API
- 项目标识符字符上限提升至 10
- 支持 onboarding 多选用例步骤

**🐞 Bug Fixes**

- 编辑器断连时数据丢失（新增 fallback 机制）
- 修复 get work item activity 外部接口
- 修复 activity timeline 编辑评论排序
- 修复日历周视图加载失败
- 修复 Pages emoji 插入方式
- 修复 peek overview 添加父级时重新加载
- 修复 list toolbar 和 slash command 排序/分组
- 修复切换 workspace 时 Favourites 缓存残留
- 修复 callout emoji 搜索
- 修复已删除 Pages 被 API 返回
- 修复非 Admin 可选时区
- 限制 workspace 成员信息对 Guest 的可见性

**🔒 Security**

- Next.js CVE-2025-66478（未授权 RCE）
- React CVE-2025-55182（Server Components RCE）
- Django 升至 4.2.27（SQL 注入修复）
- Nginx 版本升级

### ② 我们的评估

| 项目         | 内容                                                                 |
| ------------ | -------------------------------------------------------------------- |
| 主要合并风险 | React Router + Vite 迁移是大改动，需检查 LLM form.tsx 定制是否受影响 |
| 已验证       | LLM Provider 定制改动已与此版本兼容                                  |
| 状态         | ✅ 已合并                                                            |

---

## v1.1.0（2025-10-23）`minor` ✅ 已包含

### ① Plane 发版信息

**✨ Features**

- 全局过滤器增强：支持 assignee、priority、dates、labels 跨视图过滤

**⬆️ Enhancements**

- Activity 支持 state/assignee 过滤
- Guest Admin 可将自己升级为 Admin
- Bar chart 新增 fill/stroke 样式
- 项目创建时可禁用部分功能模块
- 富文本编辑器新增 block menu（删除/复制块）
- 团队成员列表支持按角色过滤和排序
- 项目列表外部接口性能优化
- 暂停用户在 workspace 成员列表中显示为已移除
- 新增文档上传 MIME 类型检测
- 更新全平台图标集

**🐞 Bug Fixes**

- 修复 Module 排序顺序
- 修复外部用户评论/reactions 不显示
- 统一全平台 Label 添加流程
- 更新错误页 UI
- 修复未订阅 Work Items 出现在订阅过滤结果中
- 修复 onboarding 布局和滚动问题
- 修复已删除成员出现在 Module 列表
- 修复 Spreadsheet 列宽分布异常
- 修复编辑器回车换行多余空行
- 修复 Cycle 外部 API 创建失败
- 修复 Spreadsheet 附件和链接计数

**🔒 Security**

- Axios 升至 1.12.0
- Django 最新稳定版
- pnpm 版本升级
- Valkey 镜像升至 7.2.11-alpine

### ② 我们的评估

| 项目     | 内容                           |
| -------- | ------------------------------ |
| 合并价值 | 过滤器增强对日常使用有明显提升 |
| 冲突风险 | 🟢 低                          |
| 状态     | ✅ 已合并                      |

---

## v1.0.0（2025-09-10）`major` ✅ 已包含

### ① Plane 发版信息

Plane CE 正式 GA，新品牌视觉上线。

**⬆️ Enhancements**

- 新增土耳其语支持
- 编辑器 HTML 安全性检查增强
- `Your Work` 固定在 Inbox 下方
- Module 过滤器本地存储持久化
- 表格支持行列重排
- 新用户默认开启邮件通知
- Hyper mode API 性能提升

**🐞 Bug Fixes**

- 修复全屏图片被模态框遮挡
- 修复只读编辑器图片对齐
- 修复 Work Item 弹窗中选择/取消选择按钮错位
- 修复滚动时 Work Item 状态计数不准
- 修复 Work Item 附件 patch 接口无响应
- 修复 Intake 邮件跳转链接失效
- 修复触屏设备 Pages 图片对齐 tooltip
- 修复触屏设备 emoji 弹窗
- 修复草稿 Work Item 状态更新不准
- 修复 Pages 仅悬停也被加入 Recents
- 修复 Work Item 描述版本历史加载失败

**🛠 Chores**

- 外部 API 结构重构，提升可维护性
- yarn → pnpm 迁移
- nprogress → bprogress 替换
- 安装脚本 API 服务就绪检查改进

**🔒 Security**

- Node 升至 v22，Python 升至 3.12.10
- 修复 on-headers 漏洞
- workspace 名称 URL 检测逻辑增强

### ② 我们的评估

| 项目   | 内容                              |
| ------ | --------------------------------- |
| 重要性 | GA 版本，品牌升级，基础架构稳定化 |
| 状态   | ✅ 已合并                         |

---

## 同步操作记录

| 日期       | 操作                           | 结果                                |
| ---------- | ------------------------------ | ----------------------------------- |
| 2026-02-28 | 初始建档，覆盖 v1.0.0 ~ v1.2.2 | feature/dev = v1.2.1，待合并 v1.2.2 |

---

## 合并操作

```bash
git checkout preview
git fetch upstream
git merge --ff-only upstream/preview
git push origin preview

git checkout feature/dev
git merge preview
# 冲突参考 docs/plane-forge/tracking/overview.md 逐条处理
```
