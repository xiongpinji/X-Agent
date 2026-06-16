# Codex/Hermes Gap Closure Report

Generated evidence source: `.xagent_runtime/reports/codex-hermes-gap-closure.json`.

## What This Release Closes

- First-release `/chat`, `/api/v1/workbench`, health, readiness, and workflow chat contracts.
- Telegram webhook loop with signature verification, normalized inbound message, dispatch, and mocked reply sender tests.
- GitHub issue-to-PR dry-run flow with deterministic plan, branch metadata, PR draft payload, guarded execute endpoint, and CLI command.
- Hermes-style Skill Curator MVP with deterministic scoring, improvement proposals, and staged `SKILL.md` drafts only.
- Gateway once-run/status mode over existing scheduler and channel registry.
- Windows-first installer dry-run and Python doctor with JSON output.
- IDE extension roadmap and VS Code MVP specification.

## Evidence Commands

Run the matrix:

```powershell
python scripts/codex_hermes_gap_matrix.py --write-report
```

Targeted checks:

```powershell
python -m pytest tests/test_first_release_entrypoints.py tests/test_security.py -o addopts="" -p no:cov -q
python -m pytest tests/test_channels.py tests/test_channel_router.py tests/test_telegram_channel_api.py -o addopts="" -p no:cov -q
python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts="" -p no:cov -q
python -m pytest tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -o addopts="" -p no:cov -q
python -m pytest tests/test_scheduler.py tests/test_gateway_mode.py tests/test_xagent_doctor.py tests/test_codex_hermes_gap_matrix.py -o addopts="" -p no:cov -q
cd frontend
npm run type-check
```

## Claims

The generated matrix can support a P0 gap-closure claim when every required category is passing.

It does not prove full Codex, Claude Code, Hermes, OpenClaw, or IDE marketplace parity. Full parity still requires broader external provider coverage, production sandbox SLA evidence, broader channel count, native IDE extension delivery, and real-world user workflow validation.

## Remaining Gaps

- Full VS Code extension implementation and marketplace publishing.
- Native mobile or desktop companion app parity.
- Production cloud sandbox SLA and cross-platform workload benchmarks.
- Broad channel parity beyond the Telegram proof loop.
- External provider matrix across OpenAI, Anthropic, DeepSeek, local models, and failure modes.
- Long-running autonomous skill promotion with signing, review, and rollback.
