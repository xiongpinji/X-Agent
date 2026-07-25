# Partner API Reference

## Overview

The X-Agent Partner API enables third-party developers and organizations to integrate with X-Agent, manage API keys, monitor usage, and receive real-time event notifications through webhooks.

**Base URL**: `https://api.x-agent.io/api/v1/partners`

**Authentication**: All requests require a valid Partner API key in the `Authorization` header:
```
Authorization: Bearer xag_partner_xxxxx
```

## Table of Contents

1. [Partner Management](#partner-management)
2. [API Key Management](#api-key-management)
3. [Webhook Management](#webhook-management)
4. [Usage & Analytics](#usage--analytics)
5. [Support Tickets](#support-tickets)
6. [Integration Guides](#integration-guides)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)

---

## Partner Management

### Register Partner

Register a new partner organization.

**Endpoint**: `POST /partners/register`

**Request Body**:
```json
{
  "company_name": "Acme Corp",
  "contact_email": "contact@acme.com",
  "contact_name": "John Doe",
  "company_website": "https://acme.com",
  "description": "Enterprise automation platform",
  "integration_type": "standard",
  "use_cases": ["workflow_automation", "data_integration"],
  "expected_volume": "high"
}
```

**Response** (201 Created):
```json
{
  "partner_id": "partner_abc123def456",
  "company_name": "Acme Corp",
  "contact_email": "contact@acme.com",
  "contact_name": "John Doe",
  "company_website": "https://acme.com",
  "description": "Enterprise automation platform",
  "integration_type": "standard",
  "use_cases": ["workflow_automation", "data_integration"],
  "status": "pending",
  "created_at": "2026-05-29T10:00:00Z",
  "updated_at": "2026-05-29T10:00:00Z",
  "api_key_prefix": null,
  "webhook_url": null,
  "monthly_requests": 0,
  "monthly_limit": 10000
}
```

### Get Partner

Retrieve partner information.

**Endpoint**: `GET /partners/{partner_id}`

**Response** (200 OK):
```json
{
  "partner_id": "partner_abc123def456",
  "company_name": "Acme Corp",
  "status": "active",
  ...
}
```

### List Partners

List all partners with optional filtering.

**Endpoint**: `GET /partners`

**Query Parameters**:
- `status_filter` (optional): Filter by status (pending, approved, active, suspended, inactive)
- `integration_type` (optional): Filter by integration type (standard, enterprise, reseller)
- `skip` (optional, default: 0): Number of records to skip
- `limit` (optional, default: 50, max: 100): Number of records to return

**Response** (200 OK):
```json
[
  {
    "partner_id": "partner_abc123def456",
    "company_name": "Acme Corp",
    "status": "active",
    ...
  }
]
```

### Update Partner

Update partner information.

**Endpoint**: `PATCH /partners/{partner_id}`

**Request Body**:
```json
{
  "company_website": "https://new-acme.com",
  "description": "Updated description"
}
```

**Response** (200 OK): Updated partner object

### Approve Partner

Approve a pending partner registration.

**Endpoint**: `POST /partners/{partner_id}/approve`

**Response** (200 OK): Updated partner object with status "approved"

### Suspend Partner

Suspend a partner account.

**Endpoint**: `POST /partners/{partner_id}/suspend`

**Query Parameters**:
- `reason` (required): Reason for suspension

**Response** (200 OK): Updated partner object with status "suspended"

---

## API Key Management

### Create API Key

Create a new API key for a partner.

**Endpoint**: `POST /partners/{partner_id}/api-keys`

**Request Body**:
```json
{
  "name": "Production API Key",
  "expires_in_days": 365,
  "rate_limit_rpm": 1000,
  "rate_limit_rph": 50000,
  "ip_whitelist": ["192.168.1.1", "10.0.0.0/8"],
  "scopes": ["read:workflows", "write:workflows", "read:data"]
}
```

**Response** (201 Created):
```json
{
  "key_id": "key_xyz789abc123",
  "key": "xag_partner_abc123def456xyz789",
  "key_prefix": "xag_partner_abc123de",
  "name": "Production API Key",
  "partner_id": "partner_abc123def456",
  "created_at": "2026-05-29T10:00:00Z",
  "expires_at": "2027-05-29T10:00:00Z",
  "rate_limit_rpm": 1000,
  "rate_limit_rph": 50000,
  "ip_whitelist": ["192.168.1.1", "10.0.0.0/8"],
  "scopes": ["read:workflows", "write:workflows", "read:data"],
  "status": "active"
}
```

**Important**: The full API key is only shown once. Store it securely.

### List API Keys

List all API keys for a partner.

**Endpoint**: `GET /partners/{partner_id}/api-keys`

**Query Parameters**:
- `status_filter` (optional): Filter by status (active, revoked, expired)

**Response** (200 OK):
```json
[
  {
    "key_id": "key_xyz789abc123",
    "key_prefix": "xag_partner_abc123de",
    "name": "Production API Key",
    "partner_id": "partner_abc123def456",
    "created_at": "2026-05-29T10:00:00Z",
    "expires_at": "2027-05-29T10:00:00Z",
    "rate_limit_rpm": 1000,
    "rate_limit_rph": 50000,
    "status": "active"
  }
]
```

### Rotate API Key

Rotate an existing API key.

**Endpoint**: `POST /partners/{partner_id}/api-keys/{key_id}/rotate`

**Response** (200 OK): New API key object

### Revoke API Key

Revoke an API key.

**Endpoint**: `DELETE /partners/{partner_id}/api-keys/{key_id}`

**Response** (204 No Content)

---

## Webhook Management

### Register Webhook

Register a webhook to receive events.

**Endpoint**: `POST /partners/{partner_id}/webhooks`

**Request Body**:
```json
{
  "event_type": "partner.api_key.created",
  "url": "https://acme.com/webhooks/xagent",
  "active": true,
  "retry_policy": {
    "max_retries": 5,
    "backoff_multiplier": 2,
    "initial_delay_seconds": 1
  }
}
```

**Supported Event Types**:
- `partner.api_key.created` - New API key created
- `partner.api_key.rotated` - API key rotated
- `partner.api_key.revoked` - API key revoked
- `partner.usage.updated` - Usage statistics updated
- `partner.quota.exceeded` - Monthly quota exceeded
- `partner.status.changed` - Partner status changed

**Response** (201 Created):
```json
{
  "webhook_id": "webhook_def456ghi789",
  "partner_id": "partner_abc123def456",
  "event_type": "partner.api_key.created",
  "url": "https://acme.com/webhooks/xagent",
  "active": true,
  "created_at": "2026-05-29T10:00:00Z",
  "last_triggered_at": null,
  "retry_policy": {
    "max_retries": 5,
    "backoff_multiplier": 2,
    "initial_delay_seconds": 1
  },
  "delivery_count": 0,
  "failure_count": 0
}
```

### List Webhooks

List all webhooks for a partner.

**Endpoint**: `GET /partners/{partner_id}/webhooks`

**Response** (200 OK): Array of webhook objects

### Update Webhook

Update webhook configuration.

**Endpoint**: `PATCH /partners/{partner_id}/webhooks/{webhook_id}`

**Request Body**:
```json
{
  "url": "https://acme.com/webhooks/xagent-v2",
  "active": false
}
```

**Response** (200 OK): Updated webhook object

### Delete Webhook

Delete a webhook.

**Endpoint**: `DELETE /partners/{partner_id}/webhooks/{webhook_id}`

**Response** (204 No Content)

### Test Webhook

Send a test event to a webhook.

**Endpoint**: `POST /partners/{partner_id}/webhooks/{webhook_id}/test`

**Response** (200 OK):
```json
{
  "status": "sent",
  "delivery_time_ms": 150
}
```

### Webhook Payload Format

All webhook events follow this format:

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

### Webhook Signature Verification

All webhook requests include an `X-Webhook-Signature` header containing an HMAC-SHA256 signature of the request body.

**Verification Example (Python)**:
```python
import hmac
import hashlib
import json

def verify_webhook(request_body, signature, secret):
    expected_signature = hmac.new(
        secret.encode(),
        request_body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)

# In your webhook handler
signature = request.headers.get('X-Webhook-Signature')
body = request.get_data()
if verify_webhook(body, signature, WEBHOOK_SECRET):
    # Process webhook
    payload = json.loads(body)
```

---

## Usage & Analytics

### Get Partner Usage

Get API usage statistics for a partner.

**Endpoint**: `GET /partners/{partner_id}/usage`

**Query Parameters**:
- `period` (optional, default: "current_month"): current_month, last_month, custom
- `start_date` (optional): ISO format date for custom period
- `end_date` (optional): ISO format date for custom period

**Response** (200 OK):
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

### Get Daily Usage

Get daily usage breakdown.

**Endpoint**: `GET /partners/{partner_id}/usage/daily`

**Query Parameters**:
- `days` (optional, default: 30, max: 365): Number of days to retrieve

**Response** (200 OK):
```json
[
  {
    "date": "2026-05-29",
    "requests": 1500,
    "successful": 1480,
    "failed": 20,
    "average_response_time_ms": 240
  }
]
```

### Get Partner Quota

Get partner quota and usage.

**Endpoint**: `GET /partners/{partner_id}/quota`

**Response** (200 OK):
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

## Support Tickets

### Create Support Ticket

Create a support ticket.

**Endpoint**: `POST /partners/{partner_id}/support/tickets`

**Request Body**:
```json
{
  "subject": "API integration issue",
  "description": "Getting 500 errors when calling the workflows endpoint",
  "priority": "high",
  "category": "technical",
  "attachments": ["error_log.txt"]
}
```

**Priority Levels**: low, normal, high, critical

**Categories**: general, technical, billing, feature_request

**Response** (201 Created):
```json
{
  "ticket_id": "ticket_ghi789jkl012",
  "partner_id": "partner_abc123def456",
  "subject": "API integration issue",
  "description": "Getting 500 errors when calling the workflows endpoint",
  "priority": "high",
  "category": "technical",
  "status": "open",
  "created_at": "2026-05-29T10:00:00Z",
  "updated_at": "2026-05-29T10:00:00Z",
  "assigned_to": null,
  "resolution_notes": null
}
```

### List Support Tickets

List support tickets for a partner.

**Endpoint**: `GET /partners/{partner_id}/support/tickets`

**Query Parameters**:
- `status_filter` (optional): Filter by status (open, in_progress, resolved, closed)
- `priority_filter` (optional): Filter by priority (low, normal, high, critical)
- `skip` (optional, default: 0)
- `limit` (optional, default: 50, max: 100)

**Response** (200 OK): Array of ticket objects

### Get Support Ticket

Get ticket details.

**Endpoint**: `GET /partners/{partner_id}/support/tickets/{ticket_id}`

**Response** (200 OK): Ticket object

### Update Support Ticket

Update ticket status or add notes.

**Endpoint**: `PATCH /partners/{partner_id}/support/tickets/{ticket_id}`

**Request Body**:
```json
{
  "status": "in_progress",
  "assigned_to": "support_agent_123"
}
```

**Response** (200 OK): Updated ticket object

---

## Integration Guides

### List Integration Guides

List available integration guides.

**Endpoint**: `GET /partners/guides/integration`

**Query Parameters**:
- `language` (optional): python, javascript, java, go, curl
- `integration_type` (optional): standard, enterprise, reseller

**Response** (200 OK):
```json
[
  {
    "guide_id": "guide_001",
    "title": "Getting Started with X-Agent API",
    "description": "Learn how to authenticate and make your first API call",
    "integration_type": "standard",
    "language": "python",
    "code_example": "...",
    "documentation_url": "https://docs.x-agent.io/guides/getting-started",
    "created_at": "2026-05-01T00:00:00Z",
    "updated_at": "2026-05-29T10:00:00Z"
  }
]
```

### Get Integration Guide

Get specific integration guide.

**Endpoint**: `GET /partners/guides/integration/{guide_id}`

**Response** (200 OK): Guide object

---

## Partner Dashboard

### Get Dashboard

Get partner dashboard data.

**Endpoint**: `GET /partners/{partner_id}/dashboard`

**Response** (200 OK):
```json
{
  "partner_id": "partner_abc123def456",
  "status": "active",
  "api_keys_count": 3,
  "webhooks_count": 2,
  "monthly_requests": 4523,
  "monthly_limit": 10000,
  "open_tickets": 1,
  "recent_activity": [
    {
      "timestamp": "2026-05-29T10:00:00Z",
      "action": "api_key_created",
      "details": "Production API Key"
    }
  ]
}
```

### Get Health Status

Get partner integration health.

**Endpoint**: `GET /partners/{partner_id}/health`

**Response** (200 OK):
```json
{
  "partner_id": "partner_abc123def456",
  "status": "healthy",
  "api_keys_valid": true,
  "webhooks_operational": true,
  "last_api_call": "2026-05-29T09:55:00Z",
  "error_rate": 0.75
}
```

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid request parameters",
    "details": {
      "field": "company_name",
      "issue": "Field is required"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_REQUEST | 400 | Invalid request parameters |
| UNAUTHORIZED | 401 | Missing or invalid API key |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource already exists |
| RATE_LIMIT_EXCEEDED | 429 | Rate limit exceeded |
| INTERNAL_ERROR | 500 | Internal server error |

---

## Rate Limiting

All Partner API endpoints are rate limited based on your subscription tier.

**Rate Limit Headers**:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1685353200
```

**Default Limits**:
- Standard: 1,000 requests/minute, 50,000 requests/hour
- Enterprise: 10,000 requests/minute, 500,000 requests/hour
- Reseller: 50,000 requests/minute, 2,000,000 requests/hour

When rate limit is exceeded, you'll receive a 429 response:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "retry_after": 60
  }
}
```

---

## Best Practices

1. **API Key Security**
   - Store API keys securely (use environment variables)
   - Rotate keys regularly
   - Use IP whitelisting when possible
   - Never commit keys to version control

2. **Webhook Handling**
   - Always verify webhook signatures
   - Implement idempotency for webhook processing
   - Return 200 OK quickly, process asynchronously
   - Implement exponential backoff for retries

3. **Error Handling**
   - Implement proper error handling and logging
   - Use exponential backoff for retries
   - Monitor error rates and alert on anomalies

4. **Performance**
   - Batch requests when possible
   - Use pagination for large result sets
   - Cache responses appropriately
   - Monitor API usage and optimize

---

## Support

For questions or issues:
- Email: partners@x-agent.io
- Documentation: https://docs.x-agent.io/partners
- Status Page: https://status.x-agent.io
