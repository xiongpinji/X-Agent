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
- Known debt: v1/v2 module duplication (agent, memory, plugin, skill, audit, collaboration),
  317-operation API surface with UI-coupled `*_control` endpoints, dual storage paths
  (local JSONL/SQLite vs PostgreSQL), ~76 failing / 4 erroring tests in the historical full-suite
  baseline, over-broad peripheral targets (desktop/mobile/4 SDKs)

## Milestones (condition-based, not calendar-based)

### M1 — Convergence (in progress)
Exit criteria:
- [x] Root-level doc sprawl archived; README/CLAUDE.md consistent with reality
- [ ] Single CHANGELOG (Keep-a-Changelog format)
- [ ] v1/v2 duplication resolved: one agent implementation, one memory stack, one plugin
      system, one skill system, one audit path, one dependencies module, one middleware layout
- [ ] Storage strategy decided and documented (local-first default vs PostgreSQL profile);
      README claims match the decision
- [ ] No `Duplicate Operation ID` warnings at startup

### M2 — Trustworthy baseline → v0.2.0-beta
Exit criteria:
- [ ] Full test suite green in CI (0 fail / 0 err; security-cluster tests explicitly dispositioned)
- [ ] CI gate: pytest + coverage report + ruff on every PR; full suite on develop/main
- [ ] API surface audited: core vs UI-specific endpoints separated; API inventory published
- [ ] Phase 5.5 verified end-to-end against a real GitHub repo (Issue → sandbox → PR)
- [ ] Frontend `build` + `type-check` green in CI
- [ ] Tag **v0.2.0-beta**, installable package (`pip install` from wheel/sdist), release notes

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
