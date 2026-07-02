# X-Agent First-Version Single-Machine Smoke

This is the acceptance path for the first version while public domain, ICP
filing, and public HTTPS evidence are intentionally out of scope.

## Acceptance Meaning

Passing this smoke means:

- one machine can run the backend stack;
- `/health` returns `ok`;
- `/ready` returns `ready`;
- required API security headers are present;
- `/api/v1/auth/me` rejects unauthenticated requests;
- optional authenticated `/api/v1/auth/me` can be checked without writing the token into evidence.

Passing this smoke does not mean public production launch, RC tag readiness,
or Stage3 public HTTPS readiness.

## Server Command

Run this on the single-machine server after Docker Compose is already up:

```bash
cd /opt/xagent-stage3/Panda-Agent-RC
python3 scripts/single_machine_smoke.py --base-url http://127.0.0.1:8899 --json
```

If testing the API container directly instead of NGINX:

```bash
python3 scripts/single_machine_smoke.py --base-url http://127.0.0.1:8000 --json
```

The report is written to:

```text
.xagent_runtime/reports/single-machine-smoke.json
```

## Optional Authenticated Check

If you already have a short-lived access token, put it in an environment
variable and reference only the variable name:

```bash
export XAGENT_SMOKE_BEARER_TOKEN="<paste-token-here>"
python3 scripts/single_machine_smoke.py \
  --base-url http://127.0.0.1:8899 \
  --bearer-token-env XAGENT_SMOKE_BEARER_TOKEN \
  --json
unset XAGENT_SMOKE_BEARER_TOKEN
```

The JSON report records only the token length, not the token value.

## Local Gate Bundle

Before treating a single-machine run as first-version evidence, refresh the
non-domain local gates from the repository checkout:

```powershell
python scripts/rc_single_user_local_gate.py --timeout 180
python scripts/desktop_first_version_smoke.py --json
python scripts/route_auth_audit.py --json
python scripts/frontend_api_contract_audit.py --json
python scripts/security_deployment_gate.py
```

Then keep these evidence files together:

```text
.xagent_runtime/reports/rc-single-user-local-gate.json
.xagent_runtime/reports/desktop-first-version-smoke.json
.xagent_runtime/reports/single-machine-smoke.json
```
