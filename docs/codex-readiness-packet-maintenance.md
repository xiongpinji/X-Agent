# Codex Readiness Packet Maintenance

This document defines the maintenance boundary for the Codex readiness packet
layer added for P0-3 test baseline recovery.

## Purpose

The `backend/app/core/codex_*_readiness_packet.py` modules are pure-payload
builders and summarizers. They convert caller-provided dictionaries or
dataclass-like objects into readiness packets with:

- `kind`
- `ok`
- `status`
- `summary`
- the configured item collection
- `findings`
- `packet_missing_refs`
- `next_actions`

They are evidence-shaping helpers only. They do not execute tools, dispatch
agents, mutate worktrees, query external services, stage commits, approve
delivery gates, or update runtime state.

## Files

- `backend/app/core/_codex_readiness_packet_specs.py`
  - Generated domain metadata: module names, public function names, collection
    keys, required packet refs, required item refs, summary keys, findings, and
    action names.
- `backend/app/core/_codex_readiness_packet_core.py`
  - Shared implementation for generated readiness domains.
  - Contains common normalization, missing-evidence detection, status mapping,
    live-operation blocker labeling, summaries, findings, and special cases
    needed by the packet contracts.
- `backend/app/core/codex_readiness_packet.py`
  - Compatibility facade used by thin modules.
  - Delegates known `codex_*_readiness_packet` kinds and prefixes to the spec
    engine, while keeping the older generic helper path available.
- `backend/app/core/codex_*_readiness_packet.py`
  - Thin domain modules that expose the names imported by
    `tests/test_codex_*_readiness_packet.py`.

## Boundary

Allowed:

- Add or adjust pure packet fields derived from input payload.
- Add missing ref aliases when test payloads use equivalent field names.
- Add status, warning, blocker, and next-action mappings that describe a
  payload state.
- Add maintenance documentation or generation notes.

Not allowed in this layer:

- Importing API routers, FastAPI app objects, agent loop code, frontend code,
  delivery scripts, or commercial gate scripts.
- Reading or writing `.xagent_runtime` reports.
- Calling shell commands, network clients, MCP tools, browsers, subprocesses,
  or file mutation APIs.
- Treating detached candidate readiness as mainline runtime capability.
- Treating a readiness packet as owner approval, stage approval, release
  approval, or delivery-ready evidence by itself.

## Validation

Primary validation:

```powershell
$files = Get-ChildItem -Path tests -Filter 'test_codex_*readiness_packet.py' |
  Sort-Object Name |
  ForEach-Object { $_.FullName }
uv run --isolated --python 3.11 --extra dev pytest $files -q -o addopts=--no-cov --tb=short
```

Expected result after P0-3 hardening:

```text
380 passed, 1 warning
```

Also run:

```powershell
git diff --check -- backend/app/core/codex_readiness_packet.py `
  backend/app/core/_codex_readiness_packet_core.py `
  backend/app/core/_codex_readiness_packet_specs.py `
  backend/app/core/codex_*_readiness_packet.py `
  docs/codex-readiness-packet-maintenance.md
```

## Adding A Readiness Domain

1. Add the test first under `tests/test_codex_*_readiness_packet.py`.
2. Add or regenerate the spec entry in `_codex_readiness_packet_specs.py`.
3. Add a thin `backend/app/core/codex_*_readiness_packet.py` module exposing
   the imported builder and summarizer names.
4. Prefer data-driven spec fields before adding special-case logic.
5. If special-case logic is necessary, keep it inside
   `_codex_readiness_packet_core.py` and document why the generic rule is not
   sufficient.
6. Re-run the full readiness packet validation command.

## Known Technical Debt

- `_codex_readiness_packet_specs.py` is generated metadata but the generator is
  not currently checked into this boundary. Until the generator is formalized,
  edits to specs should be reviewed as source changes.
- Some domain-specific status and blocker mappings live in
  `_codex_readiness_packet_core.py`. They should be consolidated into explicit
  spec metadata if more domains are added.
- Thin modules are intentionally repetitive. Do not manually refactor them into
  runtime registration or dynamic imports unless the test and packaging contract
  is changed first.
