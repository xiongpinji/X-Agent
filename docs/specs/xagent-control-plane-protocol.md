# X-Agent Control Plane Protocol

## Purpose

This document defines the first commercial control-plane contract for X-Agent.
It is inspired by the platform shape of Codex app-server, but it preserves
X-Agent's enterprise framework positioning.

The protocol is not a replacement for existing REST APIs. It is the typed
contract that Web Workbench, CLI, channels, future desktop clients, and
automation gateways should converge on.

## Design Rules

- One protocol object per product action, even when existing APIs are split.
- Every request must be auditable.
- Requests must not carry raw production secrets.
- Long-running actions must produce status/progress events.
- Dangerous actions must route through the unified approval model.
- Existing REST endpoints remain supported until a compatibility layer exists.

## Envelope

```json
{
  "id": "req_01J...",
  "method": "thread/start",
  "params": {},
  "context": {
    "tenant_id": "tenant_demo",
    "actor_id": "user_demo",
    "workspace_id": "workspace_demo",
    "trace_id": "trace_demo"
  }
}
```

Success response:

```json
{
  "id": "req_01J...",
  "ok": true,
  "result": {},
  "evidence": {
    "trace_id": "trace_demo",
    "audit_id": "audit_demo"
  }
}
```

Error response:

```json
{
  "id": "req_01J...",
  "ok": false,
  "error": {
    "code": "approval_required",
    "message": "This action requires approval.",
    "retryable": true
  },
  "evidence": {
    "trace_id": "trace_demo",
    "audit_id": "audit_demo"
  }
}
```

## Event Envelope

```json
{
  "event_id": "evt_01J...",
  "type": "tool/progress",
  "thread_id": "thread_demo",
  "turn_id": "turn_demo",
  "item_id": "item_demo",
  "payload": {},
  "created_at": "2026-06-08T00:00:00Z"
}
```

## Status Vocabulary

Use these values across thread, turn, tool, approval, channel, and runtime
surfaces:

- `queued`
- `running`
- `waiting_for_approval`
- `waiting_for_user`
- `completed`
- `failed`
- `cancelled`
- `blocked`

## Request Groups

### 1. Thread

Purpose: product-level durable work sessions.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `thread/start` | `/api/v1/agent/run`, `/api/v1/agents/run`, `/api/v1/runs/start` | mapped |
| `thread/resume` | `/api/v1/agents/{agent_id}/resume`, workflow resume endpoints | partial |
| `thread/read` | `/api/v1/runs/{trace_id}`, `/api/v1/traces/{trace_id}` | mapped |
| `thread/search` | `/api/v1/traces`, `/api/v1/runs`, audit search | partial |
| `thread/fork` | no unified endpoint | missing |
| `thread/rollback` | replay/version endpoints exist, no unified thread rollback | missing |
| `thread/compact` | session context compression exists under `/api/sessions/compress` | partial |

Example:

```json
{
  "method": "thread/start",
  "params": {
    "input": "Prepare a deployment smoke plan.",
    "mode": "commercial_pilot",
    "workspace_root": "D:/AI..."
  }
}
```

Required next work:

- Define canonical `thread_id`, `turn_id`, and `item_id`.
- Add a compatibility adapter over existing run/trace/session IDs.
- Add product rollback semantics that do not imply file-system rollback.

### 2. Turn

Purpose: a single user/agent interaction inside a thread.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `turn/start` | agent run endpoints | mapped |
| `turn/steer` | no unified endpoint | missing |
| `turn/interrupt` | cancel/pause endpoints | partial |
| `turn/events/list` | streaming/messages/debug endpoints | partial |

Required next work:

- Normalize streaming and debug events into turn events.
- Define interruption behavior for running workflow, browser, channel, and
  sandbox tasks.

### 3. Tool

Purpose: list and execute tools with progress and approval metadata.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `tool/list` | `/api/v1/tools`, `/api/v1/mcp/tools` | mapped |
| `tool/call` | `/api/v1/mcp/tools/execute`, tools batch execution | partial |
| `tool/progress` | streaming events and trace timeline | partial |
| `tool/execution/read` | `/api/v1/tools/executions/{execution_id}` | mapped |

Required next work:

- Add one tool-call payload format for native tools and MCP tools.
- Add approval metadata to tool schemas.

### 4. Approval

Purpose: one decision model for command, file, network, MCP, channel, browser,
and issue-to-PR actions.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `approval/list` | `/api/v1/approvals` | mapped |
| `approval/read` | `/api/v1/approvals/{approval_id}` | mapped |
| `approval/decide` | approve/reject endpoints | mapped |
| `approval/execute` | `/api/v1/approvals/{approval_id}/execute` | mapped |

Decision values:

- `approve_once`
- `approve_for_run`
- `approve_for_session`
- `deny`
- `abort`

Required next work:

- Extend the current approve/reject model to carry scope.
- Add risk explanation fields for UI and audit.

### 5. MCP

Purpose: expose MCP servers as governed resources and tools.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `mcp/status` | `/api/v1/mcp/status`, `/api/v1/mcp/health` | mapped |
| `mcp/tool/list` | `/api/v1/mcp/tools` | mapped |
| `mcp/tool/call` | `/api/v1/mcp/tools/execute` | mapped |
| `mcp/resource/read` | no unified endpoint | missing |
| `mcp/oauth/login` | no unified endpoint | missing |
| `mcp/elicitation/respond` | no unified endpoint | missing |

Required next work:

- Add MCP resource read and elicitation objects.
- Add OAuth status without storing secrets in reports.

### 6. Plugin

Purpose: govern plugin discovery, install, execution, and commercial review.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `plugin/list` | `/api/v1/plugins`, plugin market endpoints | mapped |
| `plugin/read` | plugin detail endpoints | mapped |
| `plugin/install` | install endpoints | mapped |
| `plugin/uninstall` | uninstall endpoints | mapped |
| `plugin/share` | no unified commercial sharing model | missing |
| `plugin/review` | plugin review/security-scan endpoints | partial |

Required next work:

- Choose one canonical plugin API path; current repo has overlapping plugin
  market surfaces.
- Require plugin metadata: owner, version, permissions, tools, dependencies,
  test command, rollback notes.

### 7. Skill

Purpose: convert Skill Curator from draft-only into a governed lifecycle.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `skill/list` | `/api/v1/skills`, skill market endpoints | mapped |
| `skill/analyze` | `/api/v1/skill-curator/analyze` | mapped |
| `skill/draft` | `/api/v1/skill-curator/draft` | mapped |
| `skill/validate` | no unified endpoint | missing |
| `skill/promote` | approve/install endpoints exist, no curator promotion | partial |
| `skill/rollback` | advanced skill market version rollback | partial |

Required next work:

- Add validate/review/promote/rollback states.
- Keep automatic skill creation review-gated.

### 8. Channel

Purpose: make non-REST entrypoints first-class product surfaces.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `channel/status` | Feishu status and enterprise IM status endpoints | partial |
| `channel/webhook/ingest` | Feishu events at `/api/v1/integrations/feishu/events` for the first domestic pilot; Telegram webhook remains optional preview | mapped |
| `channel/send` | Feishu send, enterprise IM send | mapped |
| `channel/readiness` | no unified endpoint | missing |

Required next work:

- Keep Feishu selected in the channel readiness matrix for the first domestic
  pilot.
- Map channel event to thread and audit IDs.
- Keep Telegram and other channels preview-only until separately proven.

### 9. Browser And Desktop

Purpose: expose visible automation as product evidence.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `browser/session/create` | `/api/v1/browser/sessions` | mapped |
| `browser/action` | goto/click/fill/screenshot endpoints | mapped |
| `browser/snapshot` | advanced snapshot endpoints | mapped |
| `desktop/session/create` | `/api/v1/desktop/sessions` | mapped |
| `desktop/action` | `/api/v1/desktop/sessions/{session_id}/actions` | mapped |

Required next work:

- Add evidence IDs for browser/desktop actions.
- Route high-risk actions through approvals.

### 10. Runtime Evidence

Purpose: keep commercial handoff machine-verifiable.

| Method | Current backing surface | Status |
| --- | --- | --- |
| `runtime/rc/status` | `scripts/rc_delivery_status.py` report | mapped |
| `runtime/smoke/run` | smoke scripts and pytest groups | partial |
| `runtime/evidence/read` | `.xagent_runtime/reports/*.json` | partial |
| `runtime/package/create` | RC evidence pack/source bundle scripts | mapped |

Required next work:

- Add a separate pilot evidence report so RC proof is not overwritten by
  experimental productization work.

## Codex-Alignment Table

| Codex primitive | X-Agent target | Current X-Agent status |
| --- | --- | --- |
| App Server protocol | Control-plane protocol | this spec |
| Threads/fork/search/rollback | Thread Workbench | partial |
| Plugins and skills | Governed plugin/skill lifecycle | partial |
| MCP tools/resources/elicitation | MCP governed tool/resource layer | partial |
| Browser/computer use | Browser and desktop automation | partial |
| Guardian approvals | Unified approval and risk model | partial |
| Cloud tasks/diffs | Issue-to-PR and sandbox tasks | partial |
| Memories/goals | Memory/session/workflow state | partial |
| Commercial handoff | RC and pilot evidence reports | strong RC, Feishu pilot evidence passed with owner live event proof |

## Acceptance Checklist

- [ ] Every method group has a REST mapping or an explicit missing status.
- [ ] Thread IDs and trace IDs have a compatibility rule.
- [ ] Approval scope is defined for dangerous actions.
- [ ] Plugin and skill lifecycle states are explicit.
- [ ] Channel events can be mapped to thread and audit evidence.
- [ ] Pilot evidence is separate from RC evidence.
