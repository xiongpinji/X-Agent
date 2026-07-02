# P0-6 Env/Secret/Config Safety Audit

Generated: 2026-06-14

## Scope

- Audited tracked and untracked env/secrets/config risk in the current checkout.
- Commands used: `git status --short`, `git ls-files`, `git ls-files -o --exclude-standard`, and `rg` keyword scans for env/secrets/private-key/service URL patterns.
- Secret values were not recorded in this report. Findings list only paths, variable names, value classes, and risk.

## Git State

- The worktree already contained many unrelated modified/untracked files before this audit, including Langfuse, Panda UI, pyproject/requirements, delivery gate, and readiness packet areas.
- This audit changed only env/config safety files and this report.

## Tracked Env Files

Tracked env-like files currently present:

- `.env.development`
- `.env.example`
- `.env.performance`
- `.env.production`
- `.env.test`
- `deployment/.env.monitoring.example`
- `frontend/.env.example`
- `frontend/.env.production`
- `monitoring/.env.example`

Risk classification:

- Medium: tracked env files are delivery-sensitive even when values are examples or placeholders.
- No tracked `.pem`, `.key`, `.p12`, `.pfx`, `id_rsa`, or `id_ed25519` files were found by `git ls-files`.

## Findings

| Scope | Path | Variable / Pattern | Value class | Risk | Action |
| --- | --- | --- | --- | --- | --- |
| tracked | `.env.production` | production secret variables including `XAGENT_JWT_SECRET`, `XAGENT_ENCRYPTION_KEY`, `XAGENT_LANGFUSE_PUBLIC_KEY`, `XAGENT_LANGFUSE_SECRET_KEY`, `XAGENT_DINGTALK_WEBHOOK_URL` | explicit placeholder-like values | Medium | keep as template only; inject real values from secret manager/local env |
| tracked | `.env.development` | development secret variables including `XAGENT_AUDIT_HMAC_SECRET`, `XAGENT_JWT_SECRET`, `XAGENT_ENCRYPTION_KEY` | development placeholder-like values | Medium | keep for local/dev only; do not reuse in production |
| tracked | `.env.performance` | `DB_PASSWORD` | weak default value before this audit | Medium | replaced with `CHANGE_ME_PERFORMANCE_DB_PASSWORD` |
| tracked | `deployment/.env.monitoring.example` | `GF_SECURITY_ADMIN_PASSWORD` | weak default value before this audit | Medium | replaced with `CHANGE_ME_GRAFANA_ADMIN_PASSWORD` |
| tracked | `monitoring/.env.example` | `GF_SECURITY_ADMIN_PASSWORD` | weak default value before this audit | Medium | replaced with `CHANGE_ME_GRAFANA_ADMIN_PASSWORD` |
| tracked | `monitoring/.env.example` | `POSTGRES_PASSWORD` | weak default value before this audit | Medium | replaced with `CHANGE_ME_POSTGRES_PASSWORD` |
| tracked | `monitoring/.env.example` | `QDRANT_API_KEY` | weak default value before this audit | Medium | replaced with `CHANGE_ME_QDRANT_API_KEY` |
| untracked | `backend/app/core/codex_secrets_redaction_readiness_packet.py` | filename contains secrets/readiness terms | local untracked source artifact | Low | recorded only; not deleted |
| untracked | `tests/test_codex_secrets_redaction_readiness_packet.py` | filename contains secrets/readiness terms | local untracked test artifact | Low | recorded only; not deleted |

## Broad Rg Summary

The broad keyword scan intentionally over-matches names such as token counters, test fixtures, and documentation examples. The current summary is:

- tracked files with keyword matches: 1293
- tracked keyword match count: 23830
- untracked files with keyword matches: 164
- untracked keyword match count: 2067
- ignored/other files with keyword matches: 165
- ignored/other keyword match count: 3147

High-signal follow-up checks found:

- no tracked private-key files by sensitive filename scan
- no untracked env/private-key files visible after ignore rules were applied
- many URL-with-credentials matches are local examples, docs, tests, or templated deployment strings; do not promote them to production without secret injection

## Fixes Applied

- Replaced weak tracked defaults in `.env.performance`, `deployment/.env.monitoring.example`, and `monitoring/.env.example`.
- Added `.gitignore` coverage for local env overlays and private-key material:
  - `*.env.*`
  - `.env.*`
  - `!.env.example`
  - `*.pem`
  - `*.key`
  - `*.p12`
  - `*.pfx`
  - `id_rsa`
  - `id_ed25519`

## Real Secret Assessment

- No confirmed tracked real secret value was found in the high-signal env/private-key review.
- Tracked production/development env files still contain placeholder-like secrets; treat them as templates only.
- Because some tracked values had secret-like length/shape, if any of these placeholder values were ever copied into a real environment, rotate the corresponding production credential.

## Remaining Manual Actions

- Confirm `.env.production` is not used as a real deployment secret source.
- Inject production values through the deployment secret manager or local ignored env overlays.
- Rotate any real environment credential that reused values from tracked env files.
- Consider replacing tracked `.env.production` and `.env.development` with `.env.production.example` / `.env.development.example` in a separate cleanup, because renaming tracked env files has wider workflow impact.
