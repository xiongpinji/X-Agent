# X-Agent Roadmap

> Rewritten 2026-09-20 (convergence task T3). The previous roadmap (Q2 2025 – Q1 2026 calendar)
> was stale and contradicted actual project state; it is preserved in git history
> (`git log --follow ROADMAP.md`) and superseded by this milestone-based plan.

## Vision

An open-source (MIT), enterprise-grade autonomous agent framework: cloud-sandboxed execution,
Issue→PR automation, multi-agent collaboration, hybrid graph+vector memory, and enterprise
governance (multi-tenancy, RBAC, audit) — the self-hostable alternative to Codex-style
cloud agents and Devin.

## Current state (honest snapshot, 2026-09)

- Version: **0.1.x (alpha, internal-pilot quality)** — see `RELEASE_READINESS.md`
- Working & verified: agent loop (plan/observe/tool/reflect/replan/repair), MCP integration,
  CLI, hooks, context management, security stack (authn/authz/rate-limit/audit),
  cloud sandbox engine + Issue→PR scaffolding (Phase 5.5), channel adapters (Phase 5.6), web UI
- Governance pass completed 2026-09-20 (this branch): v1/v2 duplication resolved
  (W2/W3: 152 zombie files removed, 5 dormant routers mounted; API surface inventoried at
  323 paths / 361 ops — docs/API_INVENTORY.md), test baseline zeroed out (3028 passed /
  0 unexplained — docs/reports/T7_TEST_BASELINE.md), CI consolidated to one honest gate,
  frontend build+typecheck green and promoted to production UI (docs/reports/T12_FRONTEND.md),
  peripherals frozen with STATUS notes (desktop/mobile/sdks/cloud)
- Remaining debt: lint/format/mypy backlog (ruff ~7.7k findings, non-blocking CI report),
  dual storage paths pending D1-D7 implementation (M2), Phase 5.5 not yet verified against a
  real GitHub repo (needs user token/repo), 2 chartered production-risk items under M2,
  2 environment-dependent test failures + 2 PathMapper tests awaiting user decision

## Milestones (condition-based, not calendar-based)

### M1 — Convergence (complete, 2026-09-20)
Exit criteria:
- [x] Root-level doc sprawl archived; README/CLAUDE.md consistent with reality
- [x] Single CHANGELOG (Keep-a-Changelog format) — T4, ecc9343
- [x] v1/v2 duplication resolved: one agent implementation, one memory stack, one plugin
      system, one skill system, one audit path, one dependencies module, one middleware layout
      — W2/W3, 877eaa9 + b12a41e (114 + 38 zombie files removed, 5 dormant routers mounted)
- [x] Storage strategy decided and documented (local-first default vs PostgreSQL profile);
      README claims match the decision — T6, c79bd63 (D1-D7 adopted)
- [x] No `Duplicate Operation ID` warnings at startup — T9, d0fef66

### M2 — Trustworthy baseline → v0.2.0-beta
Exit criteria:
- [ ] Full test suite green in CI (0 fail / 0 err; security-cluster tests explicitly dispositioned)
- [ ] CI gate: pytest + coverage report + ruff on every PR; full suite on develop/main
- [ ] API surface audited: core vs UI-specific endpoints separated; API inventory published
- [ ] Phase 5.5 verified end-to-end against a real GitHub repo (Issue → sandbox → PR)
- [ ] Frontend `build` + `type-check` green in CI
- [ ] Tag **v0.2.0-beta**, installable package (`pip install` from wheel/sdist), release notes

Progress (2026-09-20 governance pass): local baseline 3028 passed / 0 unexplained
(docs/reports/T7_TEST_BASELINE.md); CI consolidated to one gate (fast-gate + frontend
blocking, lint/full-suite reporting); API inventory published (docs/API_INVENTORY.md,
323 paths / 361 ops); frontend build+typecheck green and promoted to the production
UI (docs/reports/T12_FRONTEND.md). Remaining: real-GitHub CI verification, Phase 5.5
e2e (needs user-provided token/repo), packaging.

**Chartered production-risk items (立项 2026-09-20, user-approved):**
1. **TestClient ~3MB/request retention** — measured during T7 (a 1000-request test
   peaked >1.5GB RSS). Suspect middleware chain holding references (CSRF store,
   rate limiter, exception handlers). Verify with tracemalloc whether the uvicorn
   path leaks too; fix or document as TestClient-only. Owner: unassigned.
   Evidence: docs/reports/T7_TEST_BASELINE.md §3.
2. **AgentLoop scaffold inflation starves the final step** — `_apply_execution_plan`
   can grow a 2-step plan to ~10 steps; under low `max_iterations` the "final" step
   never executes and the run silently degrades to the `_finalize_answer` fallback.
   Fix direction: budget-aware plan trimming (protect the final step) instead of
   unconditional injection. Evidence: docs/reports/T7_TEST_BASELINE.md §3,
   tests/test_resume_recovery.py note.
3. ~~**`POST /auth/register` returns an unusable access_token**~~ — RESOLVED
   (2026-09-21 audit round 2, commit 746d7ef): root cause was register never
   calling `_store_token_user`; it now mirrors login's binding. Verified live
   (register -> /auth/me 200) and the frontend workaround was removed.
6. **Dependency-declaration drift between pyproject and requirements.txt** —
   RESOLVED for runtime (746d7ef aligned base+dev extras; clean-venv install
   boots). Remaining: make one file the single source of truth (generate the
   other) so drift cannot recur.
7. **SSE stream frames carry Python-repr payloads, not JSON** — `POST
   /api/v1/agents/run/stream` emits `data: {'trace_id': ...}` (single quotes),
   which standards-compliant EventSource+JSON.parse clients cannot consume;
   also only 2 end-of-run frames (trace+completed, duplicated ~233KB each) —
   no incremental events. Extends item 4.
4. **Streaming contract not fulfilled** — `POST /api/v1/agents/run/stream` returns
   a plain JSON envelope after synchronous completion (no SSE frames), and
   `async_run: true` on `/api/v1/runs/start` is ignored (runs synchronously).
   Real-time UX (a headline capability) is therefore not actually delivered on
   these endpoints; GET /api/v1/agent/stream/{run_id} + /stream/health do work.
5. **Run response envelope triple-duplicates payload** — summary/metadata.run/
   snapshot embed the same ~134KB snapshot (472KB response for one run). Needs a
   single canonical envelope before any external API consumer is built.

### M3 — Focused differentiation → v0.3.x
Exit criteria:
- [ ] Async fire-and-forget task model production-hardened (queue durability, retries, observability)
- [ ] Multi-channel adapters (Feishu/Discord/Telegram/DingTalk) validated in real deployments
- [ ] Multi-agent collaboration: single implementation, capability matching, shared context
- [ ] PostgreSQL/Qdrant production profile load-tested; migration path documented
- [ ] Peripheral targets (desktop Tauri, mobile RN, Go/Java SDKs) explicitly frozen as
      experimental or removed

### M4 — GA (v1.0)
Exit criteria:
- [ ] 12-week stable API window with deprecation policy enforced
- [ ] Security review: dependency audit clean, secrets management documented, hardening guide
- [ ] Operations: backup/restore validated, monitoring dashboards shipped, HA deployment guide
- [ ] Documentation: single authoritative architecture guide; API reference 100% coverage
- [ ] At least 3 external pilot deployments with written feedback

## Versioning & breaking-change policy

- SemVer. Current: 0.1.x. Next: 0.2.0-beta at M2 exit.
- Breaking changes only in minor bumps pre-1.0, listed in CHANGELOG with migration notes.
- At v1.0: 12-month API stability commitment; deprecations get ≥1 minor cycle of warnings.

## Explicit non-goals (until M3+)

- VS Code extension (Chrome extension covers the browser surface)
- Custom model fine-tuning / RL
- Kubernetes-first deployment (compose/single-node is the supported path until M3)
- Plugin marketplace hosting (plugin system + local install only)

## Contributing areas

See `CONTRIBUTING.md`. High-leverage areas right now: test-suite stabilization (M2),
v1/v2 convergence (M1), API inventory (M2), real-world channel adapter validation (M3).
