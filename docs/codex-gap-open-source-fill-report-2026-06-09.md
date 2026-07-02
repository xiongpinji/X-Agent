# Codex Gap and Open-Source Fill Report

Date: 2026-06-09
Scope: X-Agent mainline secondary-thread assessment. This report does not integrate runtime code.

## Executive conclusion

Original-kernel migration is close to the safe boundary. The remaining original-kernel surfaces are mostly active runtime, database, API, worker, provider, security, or frontend entrypoints. Further direct migration from the original kernel has rising conflict risk and lower return.

The next useful path is competitor-gap driven: compare current Codex product capabilities against X-Agent mainline, then add detached advisory modules, reports, contracts, or importable helpers that prepare integration without touching active entrypoints.

## Sources checked

- OpenAI Codex official intro: https://openai.com/index/introducing-codex/
- OpenAI Codex use cases: https://developers.openai.com/codex/explore
- OpenAI Codex CLI help: https://help.openai.com/en/articles/11096431
- OpenAI code-generation guide: https://platform.openai.com/docs/guides/code-generation
- Linear Codex agent changelog: https://linear.app/changelog/2025-12-04-openai-codex-agent
- OpenHands repository: https://github.com/OpenHands/OpenHands
- SWE-agent repository: https://github.com/SWE-agent/SWE-agent
- Aider repository: https://github.com/aider-ai/aider
- browser-use repository: https://github.com/browser-use/browser-use

## Codex capability map

Codex now spans more than a terminal agent:

- Local agent: CLI and IDE extension for reading, modifying, and running code locally.
- Cloud delegation: cloud tasks in isolated repository environments, parallel task execution, PR proposal flow.
- Repository instructions: `AGENTS.md` guidance for task behavior.
- Review workflow: GitHub PR review and auto-review style usage.
- Collaboration surfaces: Slack and Linear task delegation are documented product directions.
- Skills and tools: task-specific skills, MCP/tool ecosystems, and user-configurable workflows.
- Browser/app work: browser-based app/game workflows and live testing.
- Knowledge-work expansion: OpenAI positions Codex beyond pure coding into connected workplace artifacts.

## Mainline X-Agent evidence snapshot

Observed in the mainline tree:

- Agent and subagent surfaces exist: `backend/app/api/agents_v2.py`, `backend/app/core/agent_orchestration_runtime.py`.
- MCP and governed tools exist: `backend/app/api/mcp.py`, `backend/app/core/mcp_plugin_adapter.py`, control-plane MCP contracts.
- Browser/desktop APIs exist: `backend/app/api/browser.py`, `backend/app/api/browser_advanced.py`, `backend/app/api/desktop.py`.
- Approval and sandbox policy surfaces exist: `backend/app/api/approvals.py`, `backend/app/core/approvals.py`, `backend/app/core/permission_profiles.py`.
- Skill/plugin systems exist: many `skill_*`, `skills_*`, and `plugin_*` modules plus skill-bundle candidate work.
- Open-source discovery exists: `open_source_base.py`, `open_source_store.py`, `open_source_wiring.py`, provider modules, and public `open_source_api`.
- Control-plane metadata already mentions worktree and automations.

This means the gap is not "no modules"; the gap is product-grade cohesion, task lifecycle, integration contracts, and visible orchestration.

## Priority gaps vs Codex

### P0: Cloud task / local worktree lifecycle

Codex strength:
- Separate task environments, parallel cloud delegation, review/apply flow.

Mainline state:
- Worktree metadata appears in control-plane helpers.
- Agent/subagent modules exist.
- There is no clear detached contract describing task environment lifecycle, isolation state, branch/worktree identity, artifact handoff, and merge readiness.

Open-source references:
- OpenHands: local GUI, SDK, hosted cloud, multi-user/RBAC/collaboration/integrations.
- SWE-agent: GitHub issue-to-fix task framing.

Recommended secondary candidate:
- `backend/app/core/task_environment_contracts.py`
- Pure analyzer/builder for `{task_id, repo, branch, worktree, sandbox, artifacts, tests, PR}` payloads.
- Output lifecycle state: `ready_to_start`, `running`, `needs_review`, `merge_ready`, `blocked`.
- No worktree creation, no git mutation, no API routing.

### P0: PR/code-review readiness contract

Codex strength:
- PR review and auto-review are product-facing workflows.

Mainline state:
- GitHub integration and issue-to-PR exist.
- Security and patch-risk helpers now exist as detached candidates.
- Missing: one review-readiness matrix that combines tests, diff risk, secrets, generated files, ownership, and artifact evidence.

Open-source references:
- SWE-agent for issue-to-fix structure.
- Aider for git-integrated iterative changes, lint/test feedback, and developer-controlled diffs.

Recommended secondary candidate:
- `backend/app/core/pr_review_readiness.py`
- Input-only report aggregator over diff stats, patch risk report, test results, redaction findings, and open-source/dependency findings.
- Output: `review_ready`, `needs_human_review`, `blocked`, with issue codes.
- No GitHub API call, no PR comment, no router changes.

### P1: Agent instruction and skill routing contract

Codex strength:
- Repository instructions via `AGENTS.md`, skills, and subagents.

Mainline state:
- `AGENTS.md`, `.agents`, `.codex`, and many skill/plugin modules exist.
- Missing: a single offline resolver that explains which instruction sources and skills would apply to a task.

Open-source references:
- OpenHands has `.agents/skills` and explicit SDK/CLI surfaces.
- Aider has codebase-map and configuration-driven workflows.

Recommended secondary candidate:
- `backend/app/core/instruction_source_audit.py`
- Consume file/path/task metadata and report applicable instruction layers, conflicts, missing owner docs, and skill suggestions.
- No automatic skill execution, no config write, no agent-loop change.

### P1: Browser task production readiness

Codex strength:
- Browser-based app/game workflows and live app testing are first-class use cases.

Mainline state:
- Browser APIs and advanced browser monitoring exist.
- Missing: detached readiness check for browser automation sessions: auth/session profile, screenshot evidence, console/network errors, retry budget, and selector stability.

Open-source references:
- browser-use for AI-browser orchestration, auth profiles, and production scaling concerns.
- Aider for web pages/images as development context.

Recommended secondary candidate:
- `backend/app/core/browser_task_readiness.py`
- Input-only analyzer over browser session/action/screenshot/console/network summaries.
- No Playwright/browser execution, no API changes.

### P1: Open-source adoption review board

Codex strength:
- Strong tool/skill ecosystem and curated workflows.

Mainline state:
- Open-source discovery exists, and `open_source_report_audit.py` is now a detached candidate.
- Missing: adoption decision rubric that combines license, maintenance, security, runtime dependency weight, fit, and integration blast radius.

Open-source references:
- OpenHands for full agent platform references.
- browser-use for browser automation.
- Aider for repo-map/git edit UX.
- SWE-agent for issue-to-fix benchmark framing.

Recommended secondary candidate:
- `backend/app/core/open_source_adoption_matrix.py`
- In-memory scoring matrix for candidate projects.
- No provider execution, no dependency install, no runtime import.

### P2: Evaluation/benchmark harness

Codex strength:
- OpenAI discusses internal SWE task benchmarks and product review loops.

Mainline state:
- `llm_evaluation.py`, `multimodal_evaluation.py`, and evaluation docs exist.
- Missing: compact, product-facing acceptance harness that maps tasks to evidence requirements and compares regressions across runs.

Open-source references:
- SWE-agent and Aider both emphasize benchmark/evaluation loops.
- OpenHands links evaluation infrastructure.

Recommended secondary candidate:
- `backend/app/core/agent_eval_matrix.py`
- Pure report builder over task outcomes, acceptance criteria, runtime evidence, and regression deltas.
- No model calls, no benchmark execution.

## What not to do next

- Do not replace active open-source discovery modules; mainline already has a modular surface.
- Do not wire new helpers into agent loop, API router, control plane, frontend, DB, workers, or provider selection from the secondary thread.
- Do not import large external agent projects directly into X-Agent. Use them as design references first.
- Do not add browser-use/OpenHands/SWE-agent/aider as runtime dependencies without mainline architecture approval.

## Recommended next secondary step

Implement `task_environment_contracts.py` as the next detached candidate.

Rationale:
- Highest overlap with Codex's strongest differentiator: durable local/cloud task environments.
- Low conflict if done as a pure payload contract.
- Useful to mainline regardless of whether the final runtime uses local worktrees, cloud sandboxes, Docker, or a hosted worker.

Proposed validation:
- Unit tests only.
- Include states for missing repo, missing branch/worktree, running task, failed tests, dirty diff needing review, and merge-ready evidence.
- Add handoff entry and keep it as `secondary_integration_candidate`.
