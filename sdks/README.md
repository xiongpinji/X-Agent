# X-Agent Partner SDKs

Official SDKs for integrating with X-Agent Partner API.

> **分发方式(重要)**: 所有 SDK 当前以**本地构建 / 源码形式分发**,
> **均未发布到 PyPI / npm / Go 模块代理 / Maven Central**。
> 下方不提供 `pip install` / `npm install` / `go get` / Maven 坐标等线上安装方式,
> 请按各语言的"本地使用"说明操作。

## Available SDKs

| 语言 | 包名 / 模块 | 形态 |
|------|-------------|------|
| Python | `xagent-partner`(模块 `xagent_partner`) | pyproject.toml 打包, 本地构建 wheel/sdist |
| JavaScript/TypeScript | `xagent-partner` | tsc 编译产物 + 源码, 本地 `npm pack` / file: 依赖 |
| Go | `github.com/xagent/partner-sdk-go`(仅模块标识) | 单文件源码 + go.mod, replace 指令引用 |
| Java | `io.xagent.partner`(包名) | 两个 .java 源码文件, 拷贝引入 |

## Quick Start

### Python

```bash
# 从仓库根目录本地安装(或先构建 wheel: python -m pip wheel ./sdks/python --no-deps)
pip install ./sdks/python
```

```python
from xagent_partner import PartnerClient

client = PartnerClient(api_key="xag_partner_xxx", base_url="https://your-instance.example.com")
partner = client.get_partner("partner_id")
print(partner)
```

详见 [python/README.md](./python/README.md)。

### JavaScript/TypeScript

```bash
cd sdks/javascript && npm install && npm run build   # tsc 编译到 dist/
npm install ./sdks/javascript                        # 在宿主项目中以 file: 依赖引入
# 或: npm pack ./sdks/javascript 产出 tarball 后安装
```

```typescript
import { PartnerClient } from 'xagent-partner';

const client = new PartnerClient({
  apiKey: 'xag_partner_xxx',
  baseUrl: 'https://your-instance.example.com',
});
const partner = await client.getPartner('partner_id');
console.log(partner);
```

详见 [javascript/README.md](./javascript/README.md)。

### Go

```go.mod
// 仓库未公开托管, 通过本地 replace 引用
require github.com/xagent/partner-sdk-go v0.2.0-alpha
replace github.com/xagent/partner-sdk-go => /path/to/X-Agent/sdks/go
```

```go
import "github.com/xagent/partner-sdk-go"

client := xagent.NewPartnerClient(xagent.PartnerClientConfig{
    APIKey:  "xag_partner_xxx",
    BaseURL: "https://your-instance.example.com",
})
partner, err := client.GetPartner("partner_id")
```

详见 [go/README.md](./go/README.md)。

### Java

将 `java/PartnerClient.java` 与 `java/PartnerAPIException.java` 拷贝到你的项目
(保持 `io.xagent.partner` 包结构), 并添加依赖 `jackson-databind` 与 `jackson-datatype-jsr310`。

```java
PartnerClient client = new PartnerClient("xag_partner_xxx", "https://your-instance.example.com",
    Duration.ofSeconds(30), 3);
PartnerClient.PartnerResponse partner = client.getPartner("partner_id");
```

详见 [java/README.md](./java/README.md)。

## Features

All SDKs provide:

- **Partner Management**: Register, list, update, approve, suspend partners
- **API Key Management**: Create, list, rotate, revoke API keys
- **Webhook Management**: Register, list, update, delete, test webhooks
- **Usage Analytics**: Get usage statistics, daily breakdown, quota information
- **Support Tickets**: Create, list, get, update support tickets
- **Dashboard & Health**: Get dashboard data and integration health status
- **Webhook Verification**: Verify webhook signatures using HMAC-SHA256

## Authentication

All requests require an API key in the `Authorization` header:

```
Authorization: Bearer xag_partner_xxxxx
```

## Error Handling

All SDKs provide specific exception types:

| Exception | Status | Description |
|-----------|--------|-------------|
| `PartnerAPIError` | Any | Base exception |
| `PartnerAuthError` | 401 | Authentication failed |
| `PartnerNotFoundError` | 404 | Resource not found |
| `PartnerRateLimitError` | 429 | Rate limit exceeded |

后端错误响应为 FastAPI 形状(`{"detail": "..."}`), 各 SDK 的异常 `message`
会提取该 `detail` 字段(兼容 `{"error": {"message": "..."}}` 形状)。

## Rate Limiting

Default rate limits:

- **Standard**: 1,000 req/min, 50,000 req/hour
- **Professional**: 10,000 req/min, 500,000 req/hour
- **Enterprise**: 50,000 req/min, 2,000,000 req/hour

Rate limit headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1685353200
```

## Retry Logic

All SDKs implement automatic retry with exponential backoff:

- Retries on 5xx errors
- Retries on 429 (rate limit) with Retry-After header
- Configurable max retries (default: 3)
- Exponential backoff: 2^attempt seconds

## Webhook Integration

### Register Webhook

```python
webhook = client.register_webhook(
    partner_id="partner_id",
    event_type="partner.api_key.created",
    url="https://yourapp.com/webhooks/xagent"
)
```

### Supported Events

- `partner.api_key.created` - New API key created
- `partner.api_key.rotated` - API key rotated
- `partner.api_key.revoked` - API key revoked
- `partner.usage.updated` - Usage statistics updated
- `partner.quota.exceeded` - Monthly quota exceeded
- `partner.status.changed` - Partner status changed

### Verify Webhook Signature

```python
# Verify signature
if PartnerClient.verify_webhook_signature(request_body, signature, secret):
    # Process webhook
    pass
```

## Examples

See [SDK Examples](../docs/sdk_examples.md) for detailed examples in each language.

## Documentation

- **API Reference**: [Partner API Reference](../docs/partner_api_reference.md)
- **Integration Guide**: [Partner Integration Guide](../docs/partner_integration_guide.md)
- **Portal Overview**: [Partner Portal Overview](../docs/partner_portal_overview.md)
- **Examples**: [SDK Examples](../docs/sdk_examples.md)

## Support

- **Documentation**: https://docs.x-agent.io/partners
- **Email**: partners@x-agent.io
- **Support Portal**: https://support.x-agent.io

## License

MIT License - See LICENSE file for details

## Changelog

### 0.2.0-alpha (2026-07-20)

- Python: 新增 `pyproject.toml`(包名 `xagent-partner`, 版本动态读取 `__version__`), `pip wheel` 构建与 stub-server 行为验证通过
- JavaScript: 新增 `package.json` + `tsconfig.json`, `tsc --strict` 编译与 stub-server 行为验证通过
- Go/Java: 补充各自 README, 明确标注"源码形式分发, 未发布到包仓库"
- 修复四类 SDK 对后端 DELETE 端点 204 空响应体解析崩溃的问题
- 修复异常消息未提取后端 FastAPI `{"detail": ...}` 字段的问题
- 修复 Java SDK 列表端点按包装对象反序列化(后端实际返回裸数组)、Instant 缺少 jsr310 模块的问题
- 修复 JavaScript 异长签名 `timingSafeEqual` 抛异常、Java 签名比较非常量时间的问题
- README 移除 pip/npm/go get/Maven 线上安装方式的虚假宣称, 统一为本地构建/源码分发说明

### 0.2.0-alpha (2026-07-19)

- 版本口径统一至 `pyproject.toml` 单一事实源 (0.2.0-alpha, 商用修复中)
- 此前标记的 1.x 版本号为审计前过程性标记; SDK 尚未向 pip / npm / Go / Maven 任何包仓库实际发布 (见 commercial_audit/14)
- Partner management endpoints
- API key management
- Webhook management
- Usage analytics
- Support tickets
- Dashboard and health endpoints
- Webhook signature verification
- Automatic retry logic
- Rate limiting support
