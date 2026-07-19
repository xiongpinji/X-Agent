# X-Agent Partner SDKs

Official SDKs for integrating with X-Agent Partner API.

## Available SDKs

- **Python**: `xagent-partner-sdk`
- **JavaScript/TypeScript**: `xagent-partner-sdk`
- **Go**: `github.com/xagent/partner-sdk-go`
- **Java**: `io.xagent:partner-sdk`

## Quick Start

### Python

```bash
pip install xagent-partner-sdk
```

```python
from xagent_partner import PartnerClient

client = PartnerClient(api_key="xag_partner_xxx")
partner = client.get_partner("partner_id")
print(partner)
```

### JavaScript/TypeScript

```bash
npm install xagent-partner-sdk
```

```typescript
import { PartnerClient } from 'xagent-partner-sdk';

const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });
const partner = await client.getPartner('partner_id');
console.log(partner);
```

### Go

```bash
go get github.com/xagent/partner-sdk-go
```

```go
import "github.com/xagent/partner-sdk-go"

client := xagent.NewPartnerClient(xagent.PartnerClientConfig{
    APIKey: "xag_partner_xxx",
})
partner, err := client.GetPartner("partner_id")
```

### Java

Add to `pom.xml`:

```xml
<dependency>
    <groupId>io.xagent</groupId>
    <artifactId>partner-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

```java
PartnerClient client = new PartnerClient("xag_partner_xxx");
PartnerClient.PartnerResponse partner = client.getPartner("partner_id");
```

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

See [SDK Examples](./sdk_examples.md) for detailed examples in each language.

## Documentation

- **API Reference**: [Partner API Reference](./partner_api_reference.md)
- **Integration Guide**: [Partner Integration Guide](./partner_integration_guide.md)
- **Portal Overview**: [Partner Portal Overview](./partner_portal_overview.md)
- **Examples**: [SDK Examples](./sdk_examples.md)

## Support

- **Documentation**: https://docs.x-agent.io/partners
- **Email**: partners@x-agent.io
- **GitHub Issues**: https://github.com/xagent/partner-sdk-*/issues
- **Support Portal**: https://support.x-agent.io

## License

MIT License - See LICENSE file for details

## Changelog

### v1.0.0 (May 29, 2026)

- Initial release
- Partner management endpoints
- API key management
- Webhook management
- Usage analytics
- Support tickets
- Dashboard and health endpoints
- Webhook signature verification
- Automatic retry logic
- Rate limiting support
