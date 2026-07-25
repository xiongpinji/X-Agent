# IDE Extension Roadmap

X-Agent should address the Codex and Claude Code IDE gap without changing its enterprise-agent positioning.

## Milestones

1. MVP spec and API gap review.
2. Local VS Code extension scaffold with `connect`, `open chat`, and `send selection`.
3. Run status panel backed by workflow/chat responses.
4. Patch preview with explicit apply approval.
5. Secret redaction and telemetry opt-in review.
6. Marketplace packaging after first-release acceptance matrix is green.

## Backend Dependencies

- Current: `/health`, `/ready`, `/api/v1/workbench`, `/api/v1/workflows/create/chat`.
- Needed next: stable run detail endpoint for `run_id` lookup.
- Needed next: patch proposal schema with file path, hunks, risk flags, and approval id.

## Release Position

The first release can ship with Web Chat, channel loop, GitHub dry-run, Skill Curator, Gateway, and installer evidence while the IDE extension remains a documented follow-up. This avoids blocking product delivery on marketplace review and IDE-specific packaging.

## Links

- MVP spec: `docs/specs/vscode-extension-mvp.md`
- Gap closure report: `docs/CODEX_HERMES_GAP_CLOSURE_REPORT.md`
