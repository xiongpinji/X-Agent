# Codex Capability Alignment Matrix - 2026-06-12

This report is a detached secondary planning artifact. It does not wire any capability into X-Agent mainline.

## Source Baseline

- OpenAI Codex developer docs: https://developers.openai.com/codex/
- OpenAI Codex CLI docs: https://developers.openai.com/codex/cli/
- OpenAI Help Center: Using Codex with your ChatGPT plan: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI Codex release surface / changelog navigation: https://developers.openai.com/codex/

## Alignment Scope

This matrix tracks X-Agent secondary candidates against the current Codex product surface:

- Local coding agent workflow: CLI, IDE, local shell, patch application, permissions, rules, hooks, and AGENTS-style guidance.
- Cloud/background workflow: web tasks, managed environments, parallel tasks, review handoff, automations, and remote connections.
- Tool and extension workflow: MCP, plugins, skills, tool search, browser/computer use, app integrations, and external connectors.
- Governance workflow: sandboxing, approvals, cyber safety, enterprise governance, data boundaries, evidence, and release maturity.
- Agentic engineering workflow: subagents, workflows, memory/context, compaction, non-interactive mode, SDK/server automation, eval and repair loops.

## Current X-Agent Secondary Coverage

| Codex capability area | Current detached coverage | Mainline status | Gap |
| --- | --- | --- | --- |
| Integration candidate review | Extensive `integration_review_*` candidate modules and tests | Not integrated | Needs mainline selection, API/UI exposure, and lifecycle ownership |
| Handoff and owner routing | `owner_handoff`, reviewer assignment, action status, adoption tracker candidates | Not integrated | Needs real assignment persistence and owner workflow wiring |
| Acceptance and final packet gates | `acceptance_check`, `final_packet`, `digest`, `preview` chains through `#120` | Not integrated | Needs mainline adoption gate and final release packet contract |
| Governance and evidence | Read-only evidence, readiness, risk, closure, release, source-bundle, and audit candidates | Not integrated | Needs canonical evidence store and enforcement gates |
| Tool/plugin readiness | MCP/tool/skill/browser readiness candidates exist as detached artifacts | Not integrated | Needs executable connector registry, permission model, and runtime health checks |
| Local execution safety | Candidate modules cover policy, patch risk, URL safety, output redaction, task environment contracts | Not integrated | Needs execution-loop enforcement and user-visible approval model |
| Agent orchestration | Agent registry, orchestration runtime, subagent handoff matrix candidates exist | Not integrated | Needs scheduler, task runner, cancellation, concurrency limits, and audit trail |
| Memory/context | Some instruction source and traceability candidates exist | Not integrated | Needs persistent memory policy, compaction, provenance, and context budget controls |
| Browser/computer use | Browser task readiness exists as a candidate | Not integrated | Needs real browser session runtime, screenshot/appshot capture, and deterministic replay |
| Non-interactive automation | Some commercial delivery and RC gates exist | Partially separate | Needs stable SDK/server-style automation contract and CI-safe mode |

## Priority Gaps To Continue Filling As Detached Candidates

1. `#121 final_packet`: close the thirteen-layer acceptance/digest/preview chain with a read-only final packet candidate.
2. `#122 owner_handoff`: provide owner/reviewer grouping over the thirteen-layer final packet.
3. Codex alignment matrix gate: machine-readable summary of which candidate modules map to Codex capability areas and which remain not integrated.
4. Tool runtime readiness packet: read-only provider registry covering MCP, plugins, skills, browser, shell, patch, and computer-use readiness.
5. Permission and sandbox review packet: compare intended action class with approval, sandbox, and data-boundary requirements.
6. Background task/worktree packet: track detached candidates for task environment, worktree isolation, concurrency, cancellation, and resumption.
7. Memory/context packet: track rules, AGENTS guidance, instruction provenance, context compaction, and recall boundaries.
8. Evaluation/repair-loop packet: connect traces, eval evidence, failures, repair candidates, and re-run receipts as read-only payloads.

## Boundary

All items above are secondary integration candidates unless mainline explicitly adopts them. They must not mutate routers, agent loops, control plane, frontend, `backend/app/core/__init__.py`, task boards, databases, staging manifests, release manifests, or runtime executors from the secondary thread.

## Next Action

Continue the existing handoff sequence with `#121 final_packet`, then reassess whether the next best candidate is `#122 owner_handoff` or a new Codex alignment matrix gate module.
