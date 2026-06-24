# `bbagent/core/model.py` 设计文档

> 适用版本：`bbagent/core/model.py`（截至 2026-06-24）
> 目标读者：需要扩展新 provider、调试模型调用链路、或维护上层 `Agent` 调用契约的开发者。

## 1. 模块定位

把不同 LLM 服务商（Anthropic、OpenAI，未来可扩展任意兼容协议）封装为统一的同步 / 异步 / 流式调用接口，让上层 `Agent` 不必关心协议格式、HTTP 细节和重试策略。

## 2. 类继承关系

```
Model_Input (dataclass)        ← 纯输入数据容器
       │
       ▼
Model (ABC)                    ← 抽象基类，定义调用契约 + 共享基础设施
   ├── AnthropicModel          ← Anthropic Claude Messages API
   └── OpenAIModel             ← OpenAI Chat Completions API
```

模块级 `PROVIDER_REGISTRY: dict[str, type]` 把"provider 名"映射到具体类，文件末尾显式注册两个实现。`Model.from_config_dict` 用它做反射构造。

---

## 3. `Model_Input` — 调用输入包

`@dataclass`，**无状态**的一次性输入包。承载一次模型调用的全部信息。

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `prompt` | `str` | 系统提示词 |
| `tools` | `List[Tool]` | 可用工具列表 |
| `messages` | `List[Message]` | 对话历史（HumanMessage / ModelMessage / ToolMessage 混合） |

---

## 4. `Model` — 抽象基类

集中维护跨子类共享的基础设施（HTTP 客户端、并发限流、错误分类、配置序列化），并强制子类实现 5 个核心方法。

### 4.1 实例属性

| 属性 | 作用 |
| --- | --- |
| `model` | 模型名，原样透传 vendor |
| `api_key` | 鉴权密钥 |
| `base_url_raw` | 原始 base URL，供 `to_config_dict` 回写配置 |
| `max_context_tokens` | 上下文窗口大小 |
| `max_concurrent` | 最大并发数，用来构造 `_semaphore` |
| `_semaphore` | 异步调用的并发信号量 |
| `_async_client` | 复用的 `httpx.AsyncClient`，懒创建 |
| `_active_requests` | 活跃请求计数（只读观测用，不参与限流） |

> **隐含契约**（`to_config_dict` 文档注释）：子类必须在 `__init__` 设置 `self.provider / max_completion_tokens / temperature / top_p / thinking / extra_args` 这 6 个属性，基类不声明，违反时 `to_config_dict` 会抛 `AttributeError`。

### 4.2 类常量

| 常量 | 值 | 作用 |
| --- | --- | --- |
| `_DEFAULT_TIMEOUT` | `httpx.Timeout(60.0, read=300.0)` | 默认超时 |
| `_DEFAULT_LIMITS` | `httpx.Limits(100, 20, 30)` | 连接池：总容量 100 / 保留 20 条 keep-alive / 30s 过期 |

### 4.3 属性

| 属性 | 作用 |
| --- | --- |
| `async_client` | 懒构造 `httpx.AsyncClient`；关闭后自动重建 |
| `active_requests` | 返回 `_active_requests` |

### 4.4 抽象方法（子类必须实现）

| 方法 | 作用 |
| --- | --- |
| `invoke(model_input) → ModelMessage \| str` | 同步调用 |
| `async_invoke(model_input) → ModelMessage \| str` | 异步一次性调用 |
| `async_stream_invoke(model_input) → AsyncIterator[dict]` | 异步流式调用 |
| `payload_construct(model_input) → dict` | 把 `Model_Input` 翻译成 vendor 请求体 |
| `model_response_parse(response) → ModelMessage \| str` | 把 vendor 响应解析为 `ModelMessage` |

### 4.5 具体方法

| 方法 | 作用 |
| --- | --- |
| `async aclose()` | 关闭底层 `AsyncClient` |
| `to_config_dict() → dict` | 导出可序列化配置；依赖子类的 6 个属性 + `extra_args` |
| `from_config_dict(config) → Model` (static) | 通过 `PROVIDER_REGISTRY` 反射构造；构造前用 `_resolve_env_vars` 替换 `${VAR}` |
| `_resolve_env_vars(value) → str` (static) | `${VAR}` → `os.environ[VAR]` |
| `_is_retryable(status_code) → bool` (static) | 429 和 5xx 视为可重试 |
| `_classify_error(e) → str` (static) | 把 `HTTPStatusError` 分类成 rate limit / server / auth / client 四类可读消息 |

---

## 5. `AnthropicModel` vs `OpenAIModel` — 对比

两个具体实现**结构完全平行**，区别仅在 vendor 协议细节。

### 5.1 实例属性对比

| 属性 | `AnthropicModel` | `OpenAIModel` | 作用 |
| --- | --- | --- | --- |
| `provider` | `"anthropic"` | `"openai"` | provider 标识，参与 `PROVIDER_REGISTRY` 反查 |
| `base_url` | `base_url + '/v1/messages'` | `base_url.rstrip('/') + '/chat/completions'` | 实际 POST 目标（在 `super().__init__()` 之后被覆盖） |
| `max_completion_tokens` | `65536` | `65536` | 单次响应最大 token |
| `temperature` | `1` | `1.0` | 采样温度 |
| `top_p` | `1` | `1.0` | 核采样 |
| `thinking` | `True` | `True` | 是否启用扩展思考 |
| `extra_args` | `{}` | `{}` | 透传 `**kwargs` |
| `headers` | `Content-Type / anthropic-version / X-Api-Key` | `Content-Type / Authorization: Bearer ...` | HTTP 头 |
| `payload` | `{max_tokens, model, temperature, top_p, thinking}` | `{model, max_completion_tokens, temperature, top_p, thinking, n=1}` | 当前请求体（可能被多次调用污染） |
| `_base_payload` | `dict(payload)` | `dict(payload)` | 干净快照，`payload_construct` 每次从这里复制 |

### 5.2 方法对比

| 方法 | `AnthropicModel` | `OpenAIModel` |
| --- | --- | --- |
| `invoke(...)` | 同步 POST，指数退避重试 | 同步 POST，指数退避重试 |
| `async_invoke(...)` | 异步 POST，限流 + 计数 | 异步 POST，限流 + 计数 |
| `async_stream_invoke(...)` | SSE 流，按 `event_type` 切分（`message_start` / `content_block_start` / `content_block_delta` / `content_block_stop` / `message_delta` / `message_stop`） | SSE 流，按 `delta` 增量块切分（`delta.content` / `delta.reasoning_content` / `delta.tool_calls[i]`） |
| `payload_construct(model_input) → dict` | system 走顶层 `system` 字段；ToolMessage 走 `tool_result` | system 走 `role: system` 消息；ToolMessage 走 `role: tool` + `tool_call_id`；tools 转换为 function 格式 + 默认 `tool_choice="auto"` |
| `model_message_to_payload(message) → dict` | assistant content 块列表，含 `thinking + signature`（保扩展思考连续性） | assistant 消息 + `reasoning_content` + `tool_calls`（`arguments` 序列化为 JSON 字符串） |
| `content_block_parse(blocks) → ...` | `TextBlock` / `ImageBlock`（base64 source） | `TextBlock` / `ImageBlock`（`image_url` data URL） |
| `model_response_parse(response) → ModelMessage` | 解析 text / thinking+signature / image / tool_use；`input_tokens` 聚合 cache 字段 | 解析 content / `reasoning_content` / tool_calls；`finish_reason` 归一化（`stop`→`end_turn`, `tool_calls`→`tool_use`） |
| `_parse_content_parts(parts) → List[ContentBlock]` | — | 内部辅助：把 list 形式的 content parts 转成 `TextBlock` / `ImageBlock` |

### 5.3 流式 yield 事件类型（两实现对外统一）

| 事件 `type` | 含义 |
| --- | --- |
| `text` | 增量文本片段 |
| `thinking` | 增量思考片段 |
| `completed_tool_use` | 一个完整 tool call 已拼出，附 `ToolUseBlock` |
| `completed_message` | 整条响应已拼完，附 `ModelMessage` |

### 5.4 协议差异速查

| 维度 | Anthropic | OpenAI |
| --- | --- | --- |
| 端点 | `POST /v1/messages` | `POST /chat/completions` |
| system prompt 落点 | 顶层 `system` 字段 | `role: system` 消息 |
| 工具调用协议 | content 块内嵌 `tool_use`（`id/name/input`） | 顶层 `tool_calls` 数组（`id/type=function/function.{name,arguments}`） |
| 工具结果协议 | 下一轮 `role: user` 嵌 `tool_result` + `tool_use_id` | `role: tool` 消息 + `tool_call_id` |
| thinking 表达 | content 块 `type=thinking` + `signature`（必须带回以保连续性） | 顶层 `reasoning_content` 字段（无 signature 概念） |
| 图像 | content 块 `source.type=base64` | `image_url` data URL |
| 流式驱动 | 按 `event_type` 切分（content_block_start / delta / stop） | 按 `delta` 增量块切分 |
| 终止原因 | `end_turn` / `tool_use` / `max_tokens` | `stop` / `tool_calls` / `length`（在 `model_response_parse` 里归一化） |
| Token 计量 | `input_tokens + cache_read + cache_creation` / `output_tokens` | `prompt_tokens` / `completion_tokens` |

---

## 6. 关键设计点

1. **`Model_Input` ↔ `ModelMessage` 是输入输出两端的统一抽象**：基类只声明抽象方法 `payload_construct` / `model_response_parse`，把"vendor 协议 ↔ 内部结构"的所有差异收敛在子类里。
2. **错误处理两层**：基类 `_is_retryable` / `_classify_error` 提供统一的指数退避和错误分类；子类 `invoke / async_invoke / async_stream_invoke` 都按"429/5xx 可重试，其余抛"统一行为。
3. **流式对外事件类型严格收敛到 4 种**（`text` / `thinking` / `completed_tool_use` / `completed_message`），上层消费者只认这一套，与 vendor 协议解耦。
4. **`_base_payload` 模式**：每次 `payload_construct` 都从 `dict(self._base_payload)` 复制再填充，避免多次调用间污染共享的 `self.payload`。
5. **限流分层**：应用层 `_semaphore`（`max_concurrent=5`）管"业务并发数"，HTTP 层 `httpx.Limits(100,20,30)` 管"连接池"。默认配置下信号量是更紧的约束。
6. **同步 `invoke` 不走信号量**：它每次自建 `httpx.Client`，所以信号量只约束异步调用。
7. **`base_url` 在子类被重赋值**：基类只存 `base_url_raw`，endpoint 形状由子类决定（`super().__init__()` 之后再覆盖 `self.base_url`）。
8. **新 provider 接入 checklist**：继承 `Model` → 实现 5 个抽象方法 → 在 `__init__` 设置 6 个软契约属性 → 在文件尾部 `PROVIDER_REGISTRY["xxx"] = XxxModel` 注册。
