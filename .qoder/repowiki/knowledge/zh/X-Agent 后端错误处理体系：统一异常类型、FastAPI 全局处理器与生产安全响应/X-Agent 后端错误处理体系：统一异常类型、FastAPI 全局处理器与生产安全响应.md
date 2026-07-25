---
kind: error_handling
name: X-Agent 后端错误处理体系：统一异常类型、FastAPI 全局处理器与生产安全响应
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/api/errors.py
    - backend/app/core/contracts.py
    - backend/app/settings.py
    - backend/app/main.py
    - backend/app/web.py
    - backend/app/core/middleware/error_handler.py
    - backend/app/core/middleware/config.py
    - backend/app/core/middleware/integration.py
---

## 1. 采用的系统/方法

- **自定义 API 异常类**：`backend/app/api/errors.py` 中定义 `XAgentAPIError`，携带 `status_code`、`code`（来自 `ErrorCode` 枚举）、`message`、`details`、`trace_id`、`request_id` 等结构化字段。
- **工厂函数**：`api_error(...)` 用于快速构造带业务语义的错误实例，避免在业务代码中散落裸 `raise Exception`。
- **FastAPI 全局异常处理器**：通过 `@app.exception_handler(XAgentAPIError)`、`RequestValidationError`、`Pydantic.ValidationError` 三个处理器将不同来源的异常统一转换为 JSONResponse。
- **统一响应模型**：所有错误最终序列化为 `ErrorResponse`（定义于 `backend/app/core/contracts`），保证前端/SDK 对错误结构的一致性消费。
- **环境变量驱动的生产安全策略**：根据 `settings.app_mode == 'production'` 决定是否暴露 `details`、是否包含原始输入值，并在开发模式下对敏感输入做 `<redacted>` 脱敏。

## 2. 关键文件与包

| 文件 | 职责 |
|---|---|
| `backend/app/api/errors.py` | `XAgentAPIError`、`api_error()`、三类 FastAPI 异常处理器、`_error_response` 统一序列化 |
| `backend/app/core/contracts.py` | `ErrorCode` 枚举 + `ErrorResponse` Pydantic 模型（错误响应契约） |
| `backend/app/settings.py` | `get_settings().app_mode` 控制生产/开发模式下的错误细节泄露策略 |
| `backend/app/main.py` / `backend/app/web.py` | 注册上述异常处理器到 FastAPI app 入口 |
| `backend/app/core/middleware/error_handler.py` | 中间件层兜底捕获未处理异常，记录 trace_id 并返回标准错误体 |
| `backend/app/core/middleware/config.py` | 提供 `MiddlewareFactory.create_error_handler_middleware`，按配置注入错误处理中间件 |
| `backend/app/core/middleware/integration.py` | 在各集成场景下调用 `config.set_error_handler_config(include_traceback=...)` 动态调整行为 |

## 3. 架构与约定

### 3.1 异常分层
- **应用层**：业务逻辑抛出 `XAgentAPIError`（或调用 `api_error(...)`），由 FastAPI 顶层处理器拦截。
- **框架层**：FastAPI 的 `RequestValidationError` 与 Pydantic v2 的 `ValidationError` 被单独处理器接管，统一映射为 422 + `ErrorCode.VALIDATION_ERROR`。
- **中间件层**：`ErrorHandlingMiddleware` 作为最后防线，捕获任何未被显式处理的异常，附加 `trace_id`/`request_id` 后返回标准错误体。

### 3.2 错误码体系
`ErrorCode` 枚举集中管理所有业务错误码（如 `VALIDATION_ERROR`、`NOT_FOUND`、`UNAUTHORIZED` 等），每个错误码对应一个 HTTP 状态码与默认消息模板，确保前后端共享同一份“错误字典”。

### 3.3 可观测性贯穿
- 每个错误响应都附带 `request_id`（优先取自请求头 `x-request-id`，否则生成 UUID）。
- `trace_id` 由上游链路追踪中间件注入，便于跨服务关联日志与 Jaeger/SkyWalking 追踪。
- 中间件层在捕获异常时自动写入结构化日志（JSON），包含堆栈摘要与上下文快照。

### 3.4 生产安全策略
- `app_mode == 'production'`：`details` 字段置空，不暴露内部堆栈、SQL 片段、第三方 API 响应体。
- 非生产环境：保留 `errors` 列表并对 `input` 字段做脱敏；同时把 Pydantic v2 `ctx.error` 中的异常对象转为字符串，避免 JSON 序列化失败导致二次 500。

## 4. 开发者应遵循的规则

1. **禁止裸抛 `Exception` / `ValueError` 直接上送客户端**
   业务侧应使用 `api_error(status_code, ErrorCode.XXX, message, details=...)` 构造 `XAgentAPIError`，让全局处理器统一格式化。

2. **校验失败走 Pydantic 而非手动 raise**
   优先依赖 FastAPI 参数/Body 校验；若需手动校验，抛出 `Pydantic.ValidationError` 以便被专用处理器捕获。

3. **不要自行拼接 JSONResponse**
   所有对外错误必须经过 `_error_response` → `ErrorResponse.model_dump(mode="json")` 路径，确保字段稳定、可被 SDK 反序列化。

4. **不要在 handler 里 try/except 吞掉异常**
   如需重试/降级，应在调用链上层（工具执行器、工作流编排器）捕获并转换，而不是在路由层静默 swallow。

5. **敏感信息一律不入 `details`**
   密码、Token、用户隐私字段不应出现在 `details` 中；即使开发模式也建议由中间件统一脱敏。

6. **利用 `include_traceback=True` 仅在本地调试**
   通过 `config.set_error_handler_config(include_traceback=True)` 开启详细堆栈，但严禁在生产配置中启用。

7. **新增错误码先更新 `ErrorCode` 与文档**
   新增业务错误码时同步更新 `ErrorCode` 枚举、OpenAPI 错误示例以及前端 i18n 文案，保持三方一致。