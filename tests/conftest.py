from __future__ import annotations

import os

os.environ.setdefault("APP_MODE", "development")
os.environ.setdefault("XAGENT_AUDIT_HMAC_SECRET", "test-audit-secret")
os.environ.setdefault("XAGENT_BOOTSTRAP_API_KEY", "bootstrap")

import pytest


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Reset global in-memory state before each test to avoid cross-test pollution."""
    from backend.app.main import _rate_limiter
    _rate_limiter._windows.clear()

    from backend.app.api import auth
    with getattr(auth, "_token_lock", pytest.importorskip("threading").Lock()):
        auth._revoked_tokens.clear()
        auth._token_expiry.clear()
        auth._token_users.clear()

    from backend.app.core.admin import tenant_store, user_store
    user_store._records.clear()
    tenant_store._records.clear()

    yield
