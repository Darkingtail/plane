# Plane LLM 自定义提供商支持改动记录

## 概述

本次改动为 Plane 添加了对 OpenRouter 和自定义 LLM API 端点的支持，允许用户配置任意 OpenAI 兼容的 API 服务。

## 改动文件清单

### 后端 (Python/Django)

#### 1. `apps/api/plane/app/views/external/base.py`

**改动内容**:

- `get_llm_config()` 函数新增返回 `base_url` 参数
- 支持 `LLM_BASE_URL` 环境变量读取
- 当 `provider` 为 "custom" 或配置了 `base_url` 时，跳过提供商验证
- `get_llm_response()` 函数支持自定义 `base_url` 传入 OpenAI 客户端

**关键代码**:

```python
def get_llm_config() -> Tuple[str | None, str | None, str | None, str | None]:
    """
    返回: api_key, model, provider, base_url
    """
    # 如果配置了自定义 base_url 或 provider 为 "custom"，跳过提供商验证
    if base_url or provider_key.lower() == "custom":
        if not api_key:
            return None, None, None, None
        if not model:
            return None, None, None, None
        return api_key, model, "openai", base_url  # 使用 openai 客户端处理自定义提供商

def get_llm_response(task, prompt, api_key, model, provider, base_url=None):
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
```

#### 2. `apps/api/plane/utils/instance_config_variables/core.py`

**改动内容**:

- 在 `llm_config_variables` 列表中新增 `LLM_BASE_URL` 配置项

**关键代码**:

```python
llm_config_variables = [
    # ... 其他配置
    {
        "key": "LLM_BASE_URL",
        "value": os.environ.get("LLM_BASE_URL", ""),
        "category": "AI",
        "is_encrypted": False,
    },
]
```

### 前端 (TypeScript/React)

#### 3. `packages/types/src/instance/ai.ts`

**改动内容**:

- 类型定义新增 `LLM_BASE_URL` 和 `LLM_PROVIDER`

**关键代码**:

```typescript
export type TInstanceAIConfigurationKeys = "LLM_API_KEY" | "LLM_MODEL" | "LLM_PROVIDER" | "LLM_BASE_URL";
```

#### 4. `apps/admin/app/(all)/(dashboard)/ai/form.tsx`

**改动内容**:

- 新增 Provider 下拉选择框（OpenAI、Anthropic、Gemini、Custom）
- 当选择 Custom 时显示 Base URL 输入框
- 智能检测：如果已配置 `LLM_BASE_URL`，自动选择 Custom 提供商
- 保存时，非 Custom 提供商会清空 `LLM_BASE_URL`

**关键代码**:

```typescript
const hasCustomBaseUrl = Boolean(config["LLM_BASE_URL"]);
const initialProvider = hasCustomBaseUrl ? "custom" : config["LLM_PROVIDER"] || "openai";

const providerOptions = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
  { value: "custom", label: "Custom (OpenRouter, etc.)" },
];

// 保存时清空非 Custom 提供商的 base_url
if (payload.LLM_PROVIDER !== "custom") {
  payload.LLM_BASE_URL = "";
}
```

#### 5. `apps/admin/core/components/common/controller-input.tsx`

**改动内容**:

- 新增 `select` 类型输入组件支持
- 支持 `options` 属性传入选项列表

**关键代码**:

```typescript
{
  type === "select" && (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <CustomSelect value={field.value} onChange={field.onChange} buttonClassName="...">
          {options?.map((option) => (
            <CustomSelect.Option key={option.value} value={option.value}>
              {option.label}
            </CustomSelect.Option>
          ))}
        </CustomSelect>
      )}
    />
  );
}
```

### 配置文件

#### 6. `apps/api/.env`

**新增/修改配置**:

```env
# CORS 允许的来源（添加了 3003、3004 端口）
CORS_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:3004,http://localhost:3100"

# LLM 配置
LLM_PROVIDER="openai"
LLM_API_KEY="sk-or-v1-xxx"
LLM_MODEL="google/gemini-3-flash-preview"
LLM_BASE_URL="https://openrouter.ai/api/v1"
```

## 使用说明

### 方式一：环境变量配置

```env
# 使用 OpenRouter
LLM_PROVIDER="custom"
LLM_API_KEY="sk-or-v1-your-key"
LLM_MODEL="anthropic/claude-3.5-sonnet"
LLM_BASE_URL="https://openrouter.ai/api/v1"

# 使用本地 LLM（如 Ollama）
LLM_PROVIDER="custom"
LLM_API_KEY="ollama"
LLM_MODEL="llama2"
LLM_BASE_URL="http://localhost:11434/v1"
```

### 方式二：管理后台配置

1. 访问 Plane 管理后台 (`/god-mode`)
2. 进入 AI 配置页面
3. 在 Provider 下拉框选择 "Custom (OpenRouter, etc.)"
4. 填写 Model 名称（如 `anthropic/claude-3.5-sonnet`）
5. 填写 API Key
6. 填写 Base URL（如 `https://openrouter.ai/api/v1`）
7. 保存配置

## 支持的提供商

| 提供商        | Provider 值 | Base URL                                     | 说明               |
| ------------- | ----------- | -------------------------------------------- | ------------------ |
| OpenAI        | `openai`    | 不需要                                       | 官方 API           |
| Anthropic     | `anthropic` | 不需要                                       | 通过 OpenAI 兼容层 |
| Google Gemini | `gemini`    | 不需要                                       | 通过 OpenAI 兼容层 |
| OpenRouter    | `custom`    | `https://openrouter.ai/api/v1`               | 多模型聚合         |
| Azure OpenAI  | `custom`    | `https://your-resource.openai.azure.com/...` | 微软云             |
| 本地 LLM      | `custom`    | `http://localhost:port/v1`                   | Ollama 等          |

## 数据库迁移

如果是现有部署，需要运行以下命令将新配置项添加到数据库:

```bash
docker exec -it plane-api python manage.py configure_instance
```

或在开发环境:

```bash
python manage.py configure_instance
```

## 注意事项

1. **API Key 安全**: `LLM_API_KEY` 在数据库中加密存储（`is_encrypted: True`）
2. **Base URL 格式**: 必须是完整 URL，包含协议（http/https）
3. **模型名称**: 使用自定义提供商时，模型名称格式可能不同（如 OpenRouter 使用 `provider/model` 格式）
4. **CORS 配置**: 如果前端运行在非默认端口，需要将端口添加到 `CORS_ALLOWED_ORIGINS`
