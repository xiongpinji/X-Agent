---
id: retry_recovery
name: Retry Recovery Prompt
version: 1.0.0
purpose: Recovery strategy for retryable failures
scope: recovery
description: Guides recovery when operations can be retried
owner: x-agent
tags: [recovery, retry, error-handling]
deprecated: false
dependencies: [agent_system]
variables:
  max_retries: 3
  backoff_factor: 2
---

# Retry Recovery Prompt

When an operation fails but is retryable, follow this recovery strategy.

## Recovery Steps

1. Analyze the failure reason
2. Determine if retry is appropriate
3. Apply backoff strategy
4. Retry with adjusted parameters
5. Log recovery attempt

## Retry Conditions

- Network timeouts: Retry with longer timeout
- Rate limits: Retry with exponential backoff
- Transient errors: Retry immediately
- Resource unavailable: Retry after delay

## Backoff Strategy

```
attempt 1: immediate
attempt 2: wait 2 seconds
attempt 3: wait 4 seconds
attempt 4: wait 8 seconds
```

## Inputs

- error: The error that occurred
- context: Execution context
- attempt_count: Number of attempts so far

## Outputs

- should_retry: Boolean indicating if retry should happen
- delay: Delay before retry in seconds
- adjusted_parameters: Modified parameters for retry
- reason: Explanation of recovery decision
