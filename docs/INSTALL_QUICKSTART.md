# X-Agent Install Quickstart

Windows dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-xagent.ps1 -DryRun
python scripts/xagent_doctor.py --json
```

Windows execute:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-xagent.ps1 -Execute
```

POSIX dry-run:

```sh
sh scripts/install-xagent.sh --dry-run
python scripts/xagent_doctor.py --json
```

Runtime smoke:

```sh
python scripts/rc_runtime_smoke.py
```

Commercial RC gate:

```sh
python scripts/codex_hermes_gap_matrix.py --write-report
cd frontend
npm audit --audit-level=moderate
npm run type-check
npm run build
cd ..
python scripts/rc_release_audit.py
python scripts/rc_release_diff_review_gate.py
python scripts/rc_deployment_docs_gate.py
python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env
python scripts/rc_owner_handoff_gate.py
python scripts/rc_runtime_smoke.py
python scripts/rc_final_gate.py
```

The installer prints exact backend and frontend commands. It does not modify
global PATH. Provider tokens such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GITHUB_TOKEN`, Feishu credentials, and optional Telegram credentials are only needed when those integrations are enabled. For production-like deployment, use
`docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`.
