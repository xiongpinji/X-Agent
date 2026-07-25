---
kind: logging_system
name: 结构化日志系统（structlog + logging + JSON 输出）
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/core/logging_config.py
    - backend/app/core/logger_factory.py
    - backend/app/core/log_sanitizer.py
    - backend/app/core/middleware/logging_middleware.py
    - backend/app/services/observability/logging_config.py
    - backend/app/main.py
---

## 1. 使用的框架与工具
- Python 标准库 `logging`：作为底层日志引擎，提供 Handler、Formatter、Filter 等基础能力。
- `python-json-logger` 的 `JsonFormatter`：用于将 `logging.LogRecord` 序列化为 JSON 行。
- `structlog`：在核心配置中启用，通过 `structlog.stdlib.LoggerFactory()` 桥接到标准 `logging`，并在处理器链中加入时间戳、堆栈、异常格式化、JSON 渲染等步骤。
- Starlette/FastAPI 中间件：在请求层注入 `request_id`、`user_id`、`tenant_id` 等上下文字段，并统一记录 HTTP 请求/响应日志。
- 可选远端日志：通过 `logging.handlers.HTTPHandler` 把 WARNING 及以上级别推送到外部收集服务。

## 2. 关键文件与包
- 核心配置与格式化器
  - `backend/app/core/logging_config.py`：定义 `StructuredFormatter`、`setup_logging`、`RequestContextFilter`、`SensitiveDataFilter`，并通过 structlog 初始化处理器链。
  - `backend/app/core/logger_factory.py`：提供 `LoggerFactory`、`LogContext`、`get_logger`，支持 plain/json 两种格式、按模块拆分文件轮转。
  - `backend/app/services/observability/logging_config.py`：面向可观测性场景的 JSON Formatter 与多 Sink（stdout、xagent.log、xagent-errors.log、Syslog、HTTP）。 
- 安全脱敏
  - `backend/app/core/log_sanitizer.py`：`LogSanitizer` / `LogFilter`，对字符串、字典、HTTP Header、URL 中的敏感信息做正则与字段名匹配脱敏。
- 请求层结构化日志中间件
  - `backend/app/core/middleware/logging_middleware.py`：`StructuredLoggingMiddleware`，输出包含 method/path/status/duration/correlation_id/user_id/tenant_id 的 JSON 事件；支持慢查询阈值与 body 大小限制。
  - `backend/app/main.py` 中的 `request_logging_middleware`：为每个请求生成 `x-request-id`，并以 `extra={...}` 方式附加到日志记录。
- 监控集成入口
  - `backend/app/monitoring/__init__.py`、`backend/app/monitoring/middleware.py`：从 `services.observability.logging_config` 导入 `setup_logging` 与 `log_request`，在监控启动时统一装配。

## 3. 架构与约定
- 双轨日志体系
  - 应用级：`backend.app.core.logging_config.setup_logging` 负责全局 root logger + structlog 处理器链，所有业务模块通过 `logging.getLogger(__name__)` 或 `logger_factory.get_logger(__name__)` 获取。
  - 可观测性级：`services.observability.logging_config.setup_logging` 提供生产态的多 Sink 输出（stdout + 文件轮转 + Syslog + HTTP），供监控子模块调用。
- 结构化字段约定
  - 通用字段：`timestamp`、`level`、`logger`、`module`、`function`、`line`、`message`。
  - 请求上下文：`request_id`、`user_id`、`tenant_id`、`correlation_id`、`trace_id`、`span_id`（由中间件/上下文注入到 LogRecord 的 `__dict__` 中，被 JSONFormatter 自动带出）。
  - HTTP 事件：`event=http_request|http_error`、`method`、`path`、`query`、`status_code`、`duration_ms`、`client_ip`、`slow_query` 等。
- 输出目标
  - 开发/本地：stdout JSON 行（便于容器 stdout 采集）。
  - 生产：`/var/log/xagent/xagent.log`（DEBUG+）、`xagent-errors.log`（ERROR+）、可选 Syslog 与 HTTP 远端推送。
  - 按模块分文件：`logger_factory` 模式下，每个 logger 对应 `<module>.log`，单文件最大 10MB，保留 5 份。
- 敏感数据保护
  - `StructuredFormatter._mask_sensitive_fields` 与 `SensitiveDataFilter` 基于键名黑名单（password/token/api_key/secret/authorization 等）递归替换为 `***MASKED***`。
  - `LogSanitizer` 额外提供 URL 参数、Bearer Token、JWT、邮箱、信用卡号等正则脱敏，配合 `LogFilter` 在记录前清洗 msg/args。
- 日志级别策略
  - root logger 默认 INFO，第三方库（urllib3、asyncio、sqlalchemy、uvicorn.access、asyncpg）统一降级到 WARNING/INFO，避免噪声。
  - 慢请求（> slow_query_threshold，默认 1s）以 WARNING 输出，错误路径以 ERROR 输出并附带 exc_info。

## 4. 开发者应遵循的规则
- 获取 Logger
  - 优先使用 `from backend.app.core.logger_factory import get_logger; logger = get_logger(__name__)`，或在需要 plain 文本时使用 `LoggerFactory.configure(format_type="plain")` 后同样方式获取。
  - 若处于 observability 子模块，可直接使用 `services.observability.logging_config.get_logger`。
- 结构化字段
  - 通过 `extra={...}` 传递业务上下文（如 `user_id`、`tenant_id`、`request_id`、`trace_id`），不要拼接进 message 字符串。
  - 不要在日志中直接打印密码、token、api_key、private_key、jwt_secret 等字段；如需记录对象，先经 `LogSanitizer.sanitize_dict` 处理。
- 中间件上下文
  - 依赖 `request_logging_middleware` 注入的 `request.state.correlation_id`、`user_id`、`tenant_id`，这些字段会自动出现在后续日志记录中。
- 性能相关日志
  - 耗时 > 1s 的请求会触发 WARNING 级别的 `http_request` 事件；如需调整阈值，通过 `StructuredLoggingMiddleware` 的 `slow_query_threshold` 配置。
- 文件与轮转
  - 使用 `logger_factory` 模式时，日志文件位于配置的 log_dir 下，按模块命名，单文件 10MB、保留 5 份；生产部署建议挂载 `/var/log/xagent` 并配合外部日志收集。
- 禁用/排除
  - 健康检查与文档路径（`/health`、`/ready`、`/metrics`、`/docs`、`/openapi.json`）默认不记录；可通过 `excluded_paths` 扩展。
- 测试与调试
  - 单元测试可使用 `LoggerFactory.configure(level=logging.DEBUG, format_type="json", log_dir=...)` 临时切换输出目录与格式，避免污染全局 root logger。