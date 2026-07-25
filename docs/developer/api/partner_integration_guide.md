# Partner Integration Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [API Key Management](#api-key-management)
4. [Webhook Integration](#webhook-integration)
5. [Usage Monitoring](#usage-monitoring)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- X-Agent account with partner access
- API key for authentication
- Basic understanding of REST APIs
- Webhook endpoint (for event notifications)

### Registration Flow

1. **Register as Partner**
   ```bash
   curl -X POST https://api.x-agent.io/api/v1/partners/register \
     -H "Content-Type: application/json" \
     -d '{
       "company_name": "Your Company",
       "contact_email": "contact@yourcompany.com",
       "contact_name": "Your Name",
       "company_website": "https://yourcompany.com",
       "integration_type": "standard",
       "use_cases": ["workflow_automation"]
     }'
   ```

2. **Await Approval**
   - We'll review your registration
   - You'll receive an approval email
   - Status changes to "approved"

3. **Create API Key**
   - Once approved, create your first API key
   - Store it securely
   - Use it for all API requests

4. **Configure Webhooks** (Optional)
   - Set up webhook endpoints
   - Receive real-time event notifications
   - Implement signature verification

---

## Authentication

### API Key Format

X-Agent Partner API keys follow this format:
```
xag_partner_[32-character-hex-string]
```

Example:
```
xag_partner_abc123def456xyz789abc123def456
```

### Using API Keys

Include your API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer xag_partner_abc123def456xyz789abc123def456" \
  https://api.x-agent.io/api/v1/partners/{partner_id}/usage
```

### API Key Scopes

Control what your API key can access:

- `read:workflows` - Read workflow definitions
- `write:workflows` - Create and modify workflows
- `read:executions` - Read execution history
- `write:executions` - Trigger workflow executions
- `read:data` - Read data and artifacts
- `write:data` - Write data and artifacts
- `read:analytics` - Read usage analytics
- `manage:webhooks` - Manage webhook subscriptions
- `manage:keys` - Manage API keys

### Creating Scoped Keys

```bash
curl -X POST https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys \
  -H "Authorization: Bearer xag_partner_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Read-Only Key",
    "scopes": ["read:workflows", "read:executions"],
    "expires_in_days": 90
  }'
```

---

## API Key Management

### Creating API Keys

```bash
curl -X POST https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys \
  -H "Authorization: Bearer xag_partner_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "expires_in_days": 365,
    "rate_limit_rpm": 1000,
    "rate_limit_rph": 50000,
    "ip_whitelist": ["192.168.1.1"],
    "scopes": ["read:workflows", "write:workflows"]
  }'
```

**Response**:
```json
{
  "key_id": "key_xyz789abc123",
  "key": "xag_partner_abc123def456xyz789abc123def456",
  "key_prefix": "xag_partner_abc123de",
  "name": "Production Key",
  "created_at": "2026-05-29T10:00:00Z",
  "expires_at": "2027-05-29T10:00:00Z",
  "status": "active"
}
```

**Important**: Save the full key immediately. It won't be shown again.

### Listing API Keys

```bash
curl -X GET https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys \
  -H "Authorization: Bearer xag_partner_xxx"
```

### Rotating API Keys

Rotate a key to generate a new one while keeping the old one active temporarily:

```bash
curl -X POST https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys/{key_id}/rotate \
  -H "Authorization: Bearer xag_partner_xxx"
```

### Revoking API Keys

Immediately revoke a key:

```bash
curl -X DELETE https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys/{key_id} \
  -H "Authorization: Bearer xag_partner_xxx"
```

---

## Webhook Integration

### Setting Up Webhooks

Webhooks allow you to receive real-time notifications about events in your X-Agent account.

#### Step 1: Create Webhook Endpoint

Create an HTTPS endpoint that can receive POST requests:

```python
from flask import Flask, request
import hmac
import hashlib
import json

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

@app.route('/webhooks/xagent', methods=['POST'])
def handle_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    body = request.get_data()
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return {'error': 'Invalid signature'}, 401
    
    # Process event
    event = json.loads(body)
    event_type = event['event_type']
    
    if event_type == 'partner.api_key.created':
        handle_key_created(event['data'])
    elif event_type == 'partner.usage.updated':
        handle_usage_updated(event['data'])
    
    return {'status': 'ok'}, 200

def handle_key_created(data):
    print(f"New API key created: {data['key_prefix']}")

def handle_usage_updated(data):
    print(f"Usage updated: {data['total_requests']} requests")

if __name__ == '__main__':
    app.run(ssl_context='adhoc')
```

#### Step 2: Register Webhook

```bash
curl -X POST https://api.x-agent.io/api/v1/partners/{partner_id}/webhooks \
  -H "Authorization: Bearer xag_partner_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "partner.api_key.created",
    "url": "https://yourcompany.com/webhooks/xagent",
    "active": true,
    "retry_policy": {
      "max_retries": 5,
      "backoff_multiplier": 2,
      "initial_delay_seconds": 1
    }
  }'
```

### Supported Events

| Event Type | Description |
|-----------|-------------|
| `partner.api_key.created` | New API key created |
| `partner.api_key.rotated` | API key rotated |
| `partner.api_key.revoked` | API key revoked |
| `partner.usage.updated` | Usage statistics updated (daily) |
| `partner.quota.exceeded` | Monthly quota exceeded |
| `partner.status.changed` | Partner status changed |

### Webhook Payload Format

All webhooks follow this format:

```json
{
  "event_id": "evt_abc123def456",
  "event_type": "partner.api_key.created",
  "timestamp": "2026-05-29T10:00:00Z",
  "data": {
    "key_id": "key_xyz789abc123",
    "key_prefix": "xag_partner_abc123de",
    "partner_id": "partner_abc123def456",
    "created_at": "2026-05-29T10:00:00Z"
  }
}
```

### Signature Verification

All webhook requests include an `X-Webhook-Signature` header with an HMAC-SHA256 signature.

**Python Example**:
```python
import hmac
import hashlib

def verify_webhook_signature(request_body, signature, secret):
    expected_signature = hmac.new(
        secret.encode(),
        request_body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

**Node.js Example**:
```javascript
const crypto = require('crypto');

function verifyWebhookSignature(body, signature, secret) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(body)
    .digest('hex');
  return crypto.timingSafeEqual(signature, expectedSignature);
}
```

### Testing Webhooks

Test your webhook endpoint:

```bash
curl -X POST https://api.x-agent.io/api/v1/partners/{partner_id}/webhooks/{webhook_id}/test \
  -H "Authorization: Bearer xag_partner_xxx"
```

### Webhook Best Practices

1. **Always verify signatures** - Ensure requests come from X-Agent
2. **Return quickly** - Process webhooks asynchronously
3. **Implement idempotency** - Handle duplicate events gracefully
4. **Log all events** - Keep audit trail of webhook deliveries
5. **Monitor failures** - Alert on webhook delivery failures

---

## Usage Monitoring

### Getting Usage Statistics

```bash
curl -X GET "https://api.x-agent.io/api/v1/partners/{partner_id}/usage?period=current_month" \
  -H "Authorization: Bearer xag_partner_xxx"
```

**Response**:
```json
{
  "partner_id": "partner_abc123def456",
  "period_start": "2026-05-01T00:00:00Z",
  "period_end": "2026-05-29T23:59:59Z",
  "total_requests": 45230,
  "successful_requests": 44890,
  "failed_requests": 340,
  "average_response_time_ms": 245.5,
  "api_calls_by_endpoint": {
    "POST /workflows": 15000,
    "GET /workflows": 20000,
    "POST /executions": 10230
  },
  "errors_by_type": {
    "rate_limit_exceeded": 200,
    "invalid_request": 100,
    "server_error": 40
  },
  "bandwidth_used_mb": 1250.5
}
```

### Getting Daily Usage

```bash
curl -X GET "https://api.x-agent.io/api/v1/partners/{partner_id}/usage/daily?days=30" \
  -H "Authorization: Bearer xag_partner_xxx"
```

### Checking Quota

```bash
curl -X GET https://api.x-agent.io/api/v1/partners/{partner_id}/quota \
  -H "Authorization: Bearer xag_partner_xxx"
```

**Response**:
```json
{
  "partner_id": "partner_abc123def456",
  "monthly_limit": 10000,
  "monthly_used": 4523,
  "monthly_remaining": 5477,
  "reset_date": "2026-06-01T00:00:00Z",
  "quota_exceeded": false
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 1000,
      "window": "minute",
      "retry_after": 60
    }
  }
}
```

### Common Errors

| Code | Status | Solution |
|------|--------|----------|
| INVALID_REQUEST | 400 | Check request parameters |
| UNAUTHORIZED | 401 | Verify API key is valid |
| FORBIDDEN | 403 | Check API key scopes |
| NOT_FOUND | 404 | Verify resource ID |
| RATE_LIMIT_EXCEEDED | 429 | Wait before retrying |
| INTERNAL_ERROR | 500 | Retry with exponential backoff |

### Retry Strategy

Implement exponential backoff for retries:

```python
import time
import requests

def make_request_with_retry(url, headers, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                time.sleep(retry_after)
                continue
            
            if response.status_code >= 500:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            
            return response
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    
    raise Exception("Max retries exceeded")
```

---

## Best Practices

### 1. API Key Security

```python
# Good: Use environment variables
import os
api_key = os.environ.get('XAGENT_API_KEY')

# Bad: Hardcoded keys
api_key = "xag_partner_abc123def456xyz789abc123def456"
```

### 2. Rate Limiting

Monitor rate limit headers and implement backoff:

```python
def check_rate_limit(response):
    limit = int(response.headers.get('X-RateLimit-Limit', 0))
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    reset = int(response.headers.get('X-RateLimit-Reset', 0))
    
    if remaining < 100:
        print(f"Warning: Only {remaining} requests remaining")
    
    return remaining > 0
```

### 3. Batch Operations

Batch requests when possible to reduce API calls:

```python
# Good: Batch multiple operations
workflows = [
    {"name": "Workflow 1", ...},
    {"name": "Workflow 2", ...},
    {"name": "Workflow 3", ...}
]
response = requests.post(
    f"{BASE_URL}/workflows/batch",
    json={"workflows": workflows},
    headers=headers
)

# Avoid: Individual requests
for workflow in workflows:
    requests.post(f"{BASE_URL}/workflows", json=workflow, headers=headers)
```

### 4. Error Logging

```python
import logging

logger = logging.getLogger(__name__)

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
except requests.RequestException as e:
    logger.error(f"API request failed: {e}", extra={
        "url": url,
        "status_code": getattr(e.response, 'status_code', None),
        "response_body": getattr(e.response, 'text', None)
    })
```

### 5. Webhook Idempotency

```python
import hashlib

def process_webhook_event(event):
    # Create idempotency key from event
    idempotency_key = hashlib.sha256(
        f"{event['event_id']}{event['timestamp']}".encode()
    ).hexdigest()
    
    # Check if already processed
    if is_event_processed(idempotency_key):
        return {"status": "already_processed"}
    
    # Process event
    result = handle_event(event)
    
    # Mark as processed
    mark_event_processed(idempotency_key)
    
    return result
```

---

## Troubleshooting

### Common Issues

#### 1. "Unauthorized" Error

**Problem**: Getting 401 Unauthorized

**Solutions**:
- Verify API key is correct
- Check API key hasn't expired
- Ensure API key is in Authorization header
- Verify API key has required scopes

```bash
# Check API key status
curl -X GET https://api.x-agent.io/api/v1/partners/{partner_id}/api-keys \
  -H "Authorization: Bearer xag_partner_xxx"
```

#### 2. "Rate Limit Exceeded" Error

**Problem**: Getting 429 Too Many Requests

**Solutions**:
- Implement exponential backoff
- Batch requests when possible
- Upgrade to higher tier
- Check `X-RateLimit-Reset` header for reset time

```bash
# Check current usage
curl -X GET https://api.x-agent.io/api/v1/partners/{partner_id}/quota \
  -H "Authorization: Bearer xag_partner_xxx"
```

#### 3. Webhook Not Receiving Events

**Problem**: Webhooks registered but not receiving events

**Solutions**:
- Test webhook endpoint: `POST /partners/{partner_id}/webhooks/{webhook_id}/test`
- Verify endpoint is HTTPS
- Check firewall/network settings
- Verify signature verification logic
- Check webhook logs in dashboard

#### 4. Invalid Signature Error

**Problem**: Webhook signature verification failing

**Solutions**:
- Ensure using correct webhook secret
- Verify using raw request body (not parsed JSON)
- Check signature algorithm (HMAC-SHA256)
- Verify header name is `X-Webhook-Signature`

```python
# Correct: Use raw body
body = request.get_data()  # Raw bytes
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

# Incorrect: Don't use parsed JSON
body = json.dumps(request.json)  # Wrong!
```

### Getting Help

- **Documentation**: https://docs.x-agent.io/partners
- **Email**: partners@x-agent.io
- **Support Portal**: https://support.x-agent.io
- **Status Page**: https://status.x-agent.io

---

## Next Steps

1. Create your first API key
2. Set up webhook endpoints
3. Implement error handling
4. Monitor usage and quota
5. Contact support for enterprise features
