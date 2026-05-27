---
id: audit_logging
name: Audit Logging Prompt
version: 1.0.0
purpose: Guidelines for audit trail maintenance
scope: audit
description: Ensures comprehensive audit logging of all operations
owner: x-agent
tags: [audit, logging, compliance]
deprecated: false
dependencies: [agent_system]
variables:
  log_level: INFO
  retention_days: 90
---

# Audit Logging Prompt

Maintain comprehensive audit trails for all operations.

## What to Log

1. **Operations**: All tool calls and decisions
2. **Changes**: File modifications, data updates
3. **Approvals**: Approval requests and decisions
4. **Errors**: Failures and recovery attempts
5. **Resources**: Resource usage and limits

## Log Format

```json
{
  "timestamp": "ISO 8601",
  "operation": "operation name",
  "actor": "agent or user",
  "resource": "affected resource",
  "action": "create/read/update/delete",
  "status": "success/failure",
  "details": "operation details",
  "trace_id": "correlation ID"
}
```

## Retention Policy

- Keep logs for {{retention_days}} days
- Archive old logs to cold storage
- Maintain immutable audit trail
- Support compliance queries

## Inputs

- event: The event to log
- context: Execution context
- metadata: Additional metadata

## Outputs

- log_entry: Formatted log entry
- stored: Boolean indicating successful storage
