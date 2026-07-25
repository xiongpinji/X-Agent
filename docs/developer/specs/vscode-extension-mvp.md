# VS Code Extension MVP Spec

## Goal

Provide a thin IDE surface for X-Agent without blocking the first-release product loops.

## Commands

- `X-Agent: Connect` stores the backend URL and optional API key in VS Code SecretStorage.
- `X-Agent: Open Chat` opens a webview or external `/chat` entrypoint.
- `X-Agent: Send Selection` sends selected code and file metadata to `/api/v1/workflows/create/chat`.
- `X-Agent: Show Run Status` reads run metadata from workflow/chat responses.
- `X-Agent: Apply Patch Preview` shows a diff preview and requires explicit user approval before writing.

## UX Flow

1. User runs `X-Agent: Connect`.
2. Extension checks `/health` and `/ready`.
3. User opens chat or sends selected code.
4. Extension shows `run_id`, status, tool events, and approval state.
5. Patch output is displayed in a VS Code diff editor before apply.

## API Calls

- `GET /health`
- `GET /ready`
- `GET /api/v1/workbench`
- `POST /api/v1/workflows/create/chat`
- Future: `GET /api/v1/workflows/runs/{run_id}`
- Future: `POST /api/v1/approvals/{approval_id}/approve`

## Security Model

- Store API keys only in VS Code SecretStorage.
- Never auto-apply patches.
- Never send full workspace contents without explicit user action.
- Redact secrets before sending selected text when local detection flags likely credentials.
- Treat execute/write actions as approval-gated, matching X-Agent backend policy.

## Test Plan

- Unit-test command registration.
- Mock backend responses for health, workbench, chat, and run status.
- Verify selected-code payload construction.
- Verify patch preview never writes files before approval.
- Run extension host smoke test locally before marketplace packaging.

## Gaps

Marketplace packaging is deferred until Web Chat, Telegram loop, GitHub dry-run, Skill Curator, Gateway mode, installer, and acceptance matrix are green.
