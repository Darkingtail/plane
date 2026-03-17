# Plane 版本差异

> 更新于 2026-02-27

## 版本体系

Plane 有两个维度：**部署方式** × **功能层级**

| 版本名                 | 部署方式       | 授权           | 功能层级                           |
| ---------------------- | -------------- | -------------- | ---------------------------------- |
| Community Edition (CE) | 自托管         | AGPL v3.0 开源 | = Cloud Free                       |
| Commercial Edition     | 自托管         | 商业闭源       | = Cloud 全功能（含付费层）         |
| Airgapped Edition      | 自托管（离线） | 商业闭源       | 企业级                             |
| Cloud                  | 官方托管       | SaaS           | Free / Pro / Business / Enterprise |

**结论：GitHub clone 下来的 = CE = Cloud Free 功能等价**

## 功能对比（Cloud 各层级）

| 功能                                 | Free/CE | Pro ($6/seat/月) | Business ($13/seat/月) | Enterprise |
| ------------------------------------ | ------- | ---------------- | ---------------------- | ---------- |
| Issues / Cycles / Modules / Pages    | ✅      | ✅               | ✅                     | ✅         |
| Work Item Types                      | ❌      | ✅               | ✅                     | ✅         |
| **Custom Properties（项目级）**      | ❌      | ✅               | ✅                     | ✅         |
| **Custom Properties（工作区级）**    | ❌      | ❌               | ✅                     | ✅         |
| GitHub / GitLab / Slack 集成（官方） | ❌      | ✅               | ✅                     | ✅         |
| Time Tracking                        | ❌      | ✅               | ✅                     | ✅         |
| Epics / Initiatives                  | ❌      | ✅               | ✅                     | ✅         |
| Workflows & Approvals                | ❌      | ❌               | ✅                     | ✅         |
| Recurring Work Items                 | ❌      | ❌               | ✅                     | ✅         |
| SAML SSO                             | ❌      | ✅               | ✅                     | ✅         |
| 用户数限制                           | 12人    | 无限             | 无限                   | 无限       |
| AI credits/seat/月                   | 0       | 1000             | 2000                   | 弹性       |

## CE 源码中 Custom Fields 现状

- ❌ 无 `CustomField` / `CustomProperty` / `CustomAttribute` Model
- ❌ 无 feature flag 门控（不是被隐藏，是真的没实现）
- ⚠️ 有少量预留框架代码：
  - `apps/api/plane/utils/filters/filter_backend.py`：有 `customproperty_<id>__<lookup>` 注释占位
  - `apps/api/plane/utils/exporters/README.md`：有扩展自定义字段的示例框架

## 自定义字段的替代方案（CE 下）

1. **Labels**：用 `label_name:value` 格式模拟（当前 gitlab-bridge 用此方案关联仓库）
2. **自行实现**：在 CE 基础上添加 CustomField Django Model + API + 前端
3. **升级商业版**：Commercial Edition 含 Pro/Business 功能

## 参考链接

- [Plane Pricing](https://plane.so/pricing)
- [Plane Editions & Versions](https://developers.plane.so/self-hosting/editions-and-versions)
