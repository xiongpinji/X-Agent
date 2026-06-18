# Verification Requests

## P0-01 enterprise.py 14 endpoints authorization

- Status: ready for ZCode verification.
- Scope fixed: `backend/app/api/enterprise.py`.
- Tests added: `tests/test_enterprise_api_auth.py`.
- Summary: enterprise router now enforces admin/security authorization, 14 write endpoints inject `principal: PrincipalDependency`, tenant-scoped write endpoints call the tenant access guard, and write operations include audit actor IDs.
- Validation run:
  - `uv run --isolated --python 3.11 pytest tests/test_enterprise_api_auth.py -q -o addopts=--no-cov` -> `4 passed`.
  - `uv run --isolated --python 3.11 python -m py_compile backend\app\api\enterprise.py tests\test_enterprise_api_auth.py` -> passed.
  - `$env:PYTHONIOENCODING='utf-8'; uv run --isolated --python 3.11 python audit_reports\verify_fixes.py P0-01` -> 5 passed / 0 failed.
- Notes: first `verify_fixes.py P0-01` run showed all checks PASS but exited on Windows GBK console encoding while printing `✓`; rerun with `PYTHONIOENCODING=utf-8` exited cleanly.
