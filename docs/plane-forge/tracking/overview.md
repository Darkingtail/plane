# Plane 源码改动追踪

> 记录所有对 Plane 上游源码的定制改动，升级时逐条 diff 对照。
> 原则：改动越少越好；改了就在这里记录清楚。
>
> 基准版本：**v1.2.1**（2025-12-12，首次叠加定制改动的上游版本）
> 二开分支：`feature/dev`（不再纯净，已偏离上游，定制内容见下方记录）

---

## 快速汇总

| #   | 状态      | 文件                                             | 说明                                    |
| --- | --------- | ------------------------------------------------ | --------------------------------------- |
| 1   | ✅ 已提交 | `apps/admin/.../ai/form.tsx`                     | 自定义 LLM Provider 支持（前端）        |
| 2   | ✅ 已提交 | `apps/api/.../views/external/base.py`            | 自定义 LLM Provider 支持（后端）        |
| 3   | ✅ 已提交 | `apps/api/.../instance_config_variables/core.py` | 新增 `LLM_BASE_URL` 配置项              |
| 4   | ✅ 已提交 | `packages/types/src/instance/ai.ts`              | 新增 `LLM_PROVIDER`/`LLM_BASE_URL` 类型 |
| 5   | ✅ 已提交 | `apps/api/plane/settings/local.py`               | 本地开发禁用 CSRF                       |
| 6   | 🔧 进行中 | `apps/web/.../settings/(workspace)/gitlab/`      | GitLab 设置页面                         |

---

## 详细记录

---

### 改动 1-4：自定义 LLM Provider 支持

**目的**：Godmode 管理后台支持配置 OpenRouter、自托管 LLM 等第三方 AI 服务商。

**关联 commit**：`ee54a04e5c feat: add custom LLM provider support (OpenRouter, etc.)`

**受影响文件（4 个）**：

#### `apps/admin/app/(all)/(dashboard)/ai/form.tsx`

- 新增 `LLM_PROVIDER` 下拉选择框（openai / anthropic / gemini / custom）
- 选 "custom" 时显示 `LLM_BASE_URL` 输入框
- 新增 `useWatch` 响应式联动
- Model placeholder 随 Provider 联动变化
- 将 API key label/description 去除硬编码的 OpenAI 链接

#### `apps/api/plane/app/views/external/base.py`

- `get_llm_config()` 返回值扩展为 4-tuple：`(api_key, model, provider, base_url)`
- 新增自定义 provider 旁路逻辑：`base_url` 非空 或 `provider == "custom"` 时跳过 `SUPPORTED_PROVIDERS` 校验
- 自定义 provider 统一使用 OpenAI 兼容客户端（`provider = "openai"`），传入 `base_url`
- 所有调用方需适配新的 4-tuple 返回值

#### `apps/api/plane/utils/instance_config_variables/core.py`

- 新增配置项 `LLM_BASE_URL`（category=AI，非加密，默认从环境变量读取）

#### `packages/types/src/instance/ai.ts`

- `TInstanceAIConfigurationKeys` 增加 `"LLM_PROVIDER"` 和 `"LLM_BASE_URL"`

**升级风险**：🟡 中

- 若上游将 provider 支持纳入 EE/Pro 版本，需确认是否与我们的实现冲突
- `get_llm_config()` 返回值改动会影响所有调用点，升级时需检查上游是否也修改了该函数签名

---

### 改动 5：本地开发禁用 CSRF

**目的**：修复本地开发环境 Admin 前端登录时 POST 请求返回 403 的问题。

**关联 commit**：`0578af85ff fix: disable CSRF middleware in local dev settings`

**受影响文件**：`apps/api/plane/settings/local.py`

**改动内容**：

```python
# 禁用 CSRF middleware（仅 local.py，不影响生产）
MIDDLEWARE = [m for m in MIDDLEWARE if m != "django.middleware.csrf.CsrfViewMiddleware"]  # noqa
```

**原因**：Admin 前端与 API 跨域（127.0.0.1 ↔ localhost），SameSite=None 要求 HTTPS，在 HTTP 本地环境 Chrome 回退到 Lax 导致跨站 POST Cookie 被拦截，进而 CSRF 验证失败。

**升级风险**：🟢 低

- 仅影响 `local.py`，不影响生产配置（`common.py`/`production.py`）
- 上游升级时几乎不会触碰 local.py 的 MIDDLEWARE 逻辑
- 每次升级后检查 local.py 是否有新增 MIDDLEWARE 条目即可

---

### 改动 6：GitLab 设置页面（进行中）

**目的**：Workspace Settings 增加 GitLab 配置入口，供 gitlab-bridge 服务读取仓库映射配置。

**受影响文件**：`apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/gitlab/`（新建目录，未提交）

**状态**：🔧 进行中，尚未提交

**升级风险**：🟢 低（新增路由/页面，不改动现有文件）

---

## 非源码扩展（不影响升级）

| 扩展               | 位置                      | 说明                                                                                |
| ------------------ | ------------------------- | ----------------------------------------------------------------------------------- |
| GitLab Bridge 服务 | `services/gitlab-bridge/` | 独立 FastAPI 微服务，通过 Plane Webhook + REST API 与 Plane 交互，不修改 Plane 源码 |
| Wisedu 定制文档    | `wisedu/`                 | 策略、设计、计划文档，完全独立                                                      |

---

## 升级操作流程

```bash
# 1. 拉取上游最新代码
git fetch upstream

# 2. 在 preview 分支做 fast-forward（仅同步，无定制）
git checkout preview
git merge --ff-only upstream/preview
git push origin preview

# 3. 在 feature/dev 合并上游
git checkout feature/dev
git merge preview
# 处理冲突时，对照本文件每条改动逐一判断
```

### 每条改动的升级检查点

| #   | 检查内容                                                      |
| --- | ------------------------------------------------------------- |
| 1-4 | 上游是否原生支持多 Provider（若 EE 已支持，评估是否放弃自研） |
| 1-4 | `get_llm_config()` 函数签名是否有变化                         |
| 5   | `local.py` 的 MIDDLEWARE 列表是否有新增（需同步禁用）         |
| 6   | Workspace Settings 路由结构是否有变化                         |
