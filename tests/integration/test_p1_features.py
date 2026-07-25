"""Integration tests for P1 features.

Covers:
1. Goals API (CRUD + complete)
2. Code Review API (file review with mocked LLM)
3. Evolution API (stats, skills, trigger)
4. WebAuthn flow (registration + authentication challenges)
5. LDAP provider (init + fail-closed authenticate)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─── 1. Goals API ─────────────────────────────────────────────────────────────


class TestGoalsAPI:
    """Goals API integration tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create fresh app + clear in-memory store for each test."""
        from backend.app.api.goals import router as goals_router, _goals

        _goals.clear()
        app = FastAPI()
        app.include_router(goals_router)
        self.client = TestClient(app)

    def test_create_goal(self):
        """POST /api/v1/goals creates a goal and returns id/objective/status/checkpoints."""
        resp = self.client.post("/api/v1/goals", json={"objective": "Ship v2.0"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["objective"] == "Ship v2.0"
        assert data["status"] == "active"
        assert data["checkpoints"] == []

    def test_list_goals(self):
        """GET /api/v1/goals lists goals."""
        self.client.post("/api/v1/goals", json={"objective": "Goal A"})
        self.client.post("/api/v1/goals", json={"objective": "Goal B"})
        resp = self.client.get("/api/v1/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["objective"] == "Goal A"
        assert data[1]["objective"] == "Goal B"

    def test_get_goal_by_id(self):
        """GET /api/v1/goals/{id} returns specific goal."""
        create_resp = self.client.post("/api/v1/goals", json={"objective": "Find me"})
        goal_id = create_resp.json()["id"]
        resp = self.client.get(f"/api/v1/goals/{goal_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == goal_id
        assert resp.json()["objective"] == "Find me"

    def test_complete_goal(self):
        """POST /api/v1/goals/{id}/complete marks goal completed."""
        create_resp = self.client.post("/api/v1/goals", json={"objective": "Finish task"})
        goal_id = create_resp.json()["id"]
        resp = self.client.post(f"/api/v1/goals/{goal_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        # Verify persisted
        get_resp = self.client.get(f"/api/v1/goals/{goal_id}")
        assert get_resp.json()["status"] == "completed"

    def test_get_nonexistent_goal_404(self):
        """404 for non-existent goal."""
        resp = self.client.get("/api/v1/goals/goal-nonexistent")
        assert resp.status_code == 404

    def test_complete_nonexistent_goal_404(self):
        """404 for completing non-existent goal."""
        resp = self.client.post("/api/v1/goals/goal-nonexistent/complete")
        assert resp.status_code == 404


# ─── 2. Code Review API ──────────────────────────────────────────────────────


class TestCodeReviewAPI:
    """Code Review API integration tests with mocked LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create app with code-review router, mock LLM calls."""
        from backend.app.api.code_review import router as review_router

        app = FastAPI()
        app.include_router(review_router)
        self.client = TestClient(app)

    def test_review_file_returns_review(self):
        """POST /api/v1/code-review/file with valid Python content returns review."""
        from backend.app.api.code_review import _reviewer

        # Mock _llm_analyze to avoid real API calls
        with patch.object(_reviewer, "_llm_analyze", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []
            resp = self.client.post(
                "/api/v1/code-review/file",
                json={
                    "file_path": "example.py",
                    "content": "def hello():\n    print('world')\n",
                    "language": "python",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "review_id" in data
        assert "approval" in data
        assert "comments" in data
        assert isinstance(data["comments"], list)

    def test_review_file_response_structure(self):
        """Verify response has review_id, approval, comments fields."""
        from backend.app.api.code_review import _reviewer

        with patch.object(_reviewer, "_llm_analyze", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [
                {
                    "file": "example.py",
                    "line": 1,
                    "severity": "suggestion",
                    "message": "Add type hints",
                    "suggestion": "def hello() -> None:",
                }
            ]
            resp = self.client.post(
                "/api/v1/code-review/file",
                json={
                    "file_path": "example.py",
                    "content": "def hello():\n    print('world')\n",
                    "language": "python",
                    "focus_areas": ["style"],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "review_id" in data
        assert data["approval"] in ("approve", "request_changes", "comment")
        assert "comments" in data
        assert "risk_level" in data
        assert "blocking_count" in data
        assert "suggestion_count" in data

    def test_review_diff_endpoint(self):
        """POST /api/v1/code-review/diff with diff text returns review."""
        from backend.app.api.code_review import _reviewer

        diff_text = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,3 @@\n"
            " import os\n"
            "+import sys\n"
            " print('hi')\n"
        )
        with patch.object(_reviewer, "_llm_analyze", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []
            resp = self.client.post(
                "/api/v1/code-review/diff",
                json={"diff_text": diff_text},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "review_id" in data
        assert "approval" in data


# ─── 3. Evolution API ─────────────────────────────────────────────────────────


class TestEvolutionAPI:
    """Evolution API integration tests with auth override."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create app with evolution router, override auth dependency."""
        from backend.app.api.evolution import router as evolution_router
        from backend.app.dependencies import get_current_principal
        from backend.app.core.security import Principal

        app = FastAPI()
        app.include_router(evolution_router)

        # Override auth to return an authenticated admin principal
        def _override_principal():
            return Principal(
                user_id="test-admin",
                role="admin",
                scopes=["agent:read", "agent:write"],
                authenticated=True,
            )

        app.dependency_overrides[get_current_principal] = _override_principal
        self.client = TestClient(app)

    def test_get_stats(self):
        """GET /api/v1/evolution/stats returns stats structure."""
        resp = self.client.get("/api/v1/evolution/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_executions" in data
        assert "skill_drafts" in data
        assert "promoted_skills" in data
        assert "skill_names" in data
        assert isinstance(data["skill_names"], list)

    def test_list_skills(self):
        """GET /api/v1/evolution/skills returns list."""
        resp = self.client.get("/api/v1/evolution/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_trigger_evolution(self):
        """POST /api/v1/evolution/trigger with trajectory data."""
        resp = self.client.post(
            "/api/v1/evolution/trigger",
            json={
                "trajectory": {
                    "tool_calls": [
                        {"name": "read_file"},
                        {"name": "write_file"},
                        {"name": "run_tests"},
                    ]
                },
                "result": {"status": "completed", "output": "All tests passed"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "skipped")

    def test_trigger_evolution_unsuccessful_task(self):
        """POST /api/v1/evolution/trigger with failed task returns skipped."""
        resp = self.client.post(
            "/api/v1/evolution/trigger",
            json={
                "trajectory": {"tool_calls": []},
                "result": {"status": "failed"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"


# ─── 4. WebAuthn Flow ─────────────────────────────────────────────────────────


class TestWebAuthnFlow:
    """WebAuthn provider integration tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create WebAuthnProvider with test config."""
        from backend.app.core.sso.webauthn_provider import WebAuthnConfig, WebAuthnProvider

        self.config = WebAuthnConfig(
            rp_id="localhost",
            rp_name="X-Agent Test",
            origin="http://localhost:3000",
        )
        self.provider = WebAuthnProvider(self.config)

    def test_create_registration_challenge(self):
        """create_registration_challenge returns challenge."""
        options = self.provider.create_registration_challenge("user-1", "alice")
        assert "challenge" in options
        assert options["rp"]["id"] == "localhost"
        assert options["rp"]["name"] == "X-Agent Test"
        assert options["user"]["name"] == "alice"
        assert "pubKeyCredParams" in options
        assert len(options["challenge"]) > 0

    def test_verify_registration_stores_credential(self):
        """verify_registration stores credential."""
        # First create a challenge
        self.provider.create_registration_challenge("user-1", "alice")
        # Get the challenge_id from internal store
        challenge_id = list(self.provider._challenges.keys())[0]

        # Verify registration
        result = self.provider.verify_registration(
            challenge_id=challenge_id,
            credential_id="cred-abc123",
            public_key="dGVzdC1wdWJsaWMta2V5",  # base64 "test-public-key"
            device_name="Test Key",
            transports=["usb", "internal"],
        )
        assert result is True

        # Verify credential stored
        creds = self.provider.get_user_credentials("user-1")
        assert len(creds) == 1
        assert creds[0].credential_id == "cred-abc123"
        assert creds[0].device_name == "Test Key"

    def test_create_authentication_challenge(self):
        """create_authentication_challenge returns challenge."""
        # Register a credential first
        self.provider.create_registration_challenge("user-1", "alice")
        challenge_id = list(self.provider._challenges.keys())[0]
        self.provider.verify_registration(
            challenge_id=challenge_id,
            credential_id="cred-abc123",
            public_key="dGVzdC1wdWJsaWMta2V5",
        )

        # Now create auth challenge
        options = self.provider.create_authentication_challenge("user-1")
        assert "challenge" in options
        assert options["rpId"] == "localhost"
        assert "allowCredentials" in options
        assert len(options["allowCredentials"]) == 1
        assert options["allowCredentials"][0]["id"] == "cred-abc123"

    def test_verify_authentication_invalid_signature_fails(self):
        """verify_authentication with invalid signature fails (fail-closed)."""
        # Register credential
        self.provider.create_registration_challenge("user-1", "alice")
        reg_challenge_id = list(self.provider._challenges.keys())[0]
        self.provider.verify_registration(
            challenge_id=reg_challenge_id,
            credential_id="cred-abc123",
            public_key="dGVzdC1wdWJsaWMta2V5",
        )

        # Create auth challenge
        self.provider.create_authentication_challenge("user-1")
        auth_challenge_id = list(self.provider._challenges.keys())[-1]

        # Attempt authentication with invalid signature
        result = self.provider.verify_authentication(
            challenge_id=auth_challenge_id,
            credential_id="cred-abc123",
            signature="aW52YWxpZC1zaWduYXR1cmU",  # base64 "invalid-signature"
            client_data="aW52YWxpZC1jbGllbnQtZGF0YQ",  # base64 "invalid-client-data"
        )
        # Should fail (fail-closed) - either crypto verification fails or library unavailable
        assert result is False

    def test_verify_registration_invalid_challenge(self):
        """verify_registration with invalid challenge_id returns False."""
        result = self.provider.verify_registration(
            challenge_id="nonexistent",
            credential_id="cred-x",
            public_key="a2V5",
        )
        assert result is False

    def test_verify_authentication_wrong_credential(self):
        """verify_authentication with unknown credential fails."""
        self.provider.create_registration_challenge("user-1", "alice")
        reg_challenge_id = list(self.provider._challenges.keys())[0]
        self.provider.verify_registration(
            challenge_id=reg_challenge_id,
            credential_id="cred-abc123",
            public_key="dGVzdC1wdWJsaWMta2V5",
        )
        self.provider.create_authentication_challenge("user-1")
        auth_challenge_id = list(self.provider._challenges.keys())[-1]

        result = self.provider.verify_authentication(
            challenge_id=auth_challenge_id,
            credential_id="wrong-cred-id",
            signature="c2ln",
            client_data="ZGF0YQ",
        )
        assert result is False


# ─── 5. LDAP Provider ─────────────────────────────────────────────────────────


class TestLDAPProvider:
    """LDAP provider integration tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create LDAPProvider with test config."""
        from backend.app.core.sso.ldap_provider import LDAPConfig, LDAPProvider

        self.config = LDAPConfig(
            server_url="ldap://ldap.example.com:389",
            bind_dn="cn=admin,dc=example,dc=com",
            bind_password="admin-pass",
            base_dn="dc=example,dc=com",
        )
        self.provider = LDAPProvider(self.config)

    def test_initializes_with_config(self):
        """LDAPProvider initializes with config."""
        assert self.provider.config.server_url == "ldap://ldap.example.com:389"
        assert self.provider.config.base_dn == "dc=example,dc=com"
        assert self.provider._connection is None

    def test_authenticate_raises_when_ldap3_unavailable(self):
        """authenticate raises RuntimeError when ldap3 not available."""
        import backend.app.core.sso.ldap_provider as ldap_mod

        original = ldap_mod.LDAP3_AVAILABLE
        try:
            # Simulate ldap3 not installed
            ldap_mod.LDAP3_AVAILABLE = False
            with pytest.raises(RuntimeError, match="ldap3"):
                import asyncio
                asyncio.get_event_loop().run_until_complete(
                    self.provider.authenticate("testuser", "password")
                )
        finally:
            ldap_mod.LDAP3_AVAILABLE = original

    def test_ensure_ldap3_fail_closed(self):
        """_ensure_ldap3 raises RuntimeError when library missing."""
        import backend.app.core.sso.ldap_provider as ldap_mod

        original = ldap_mod.LDAP3_AVAILABLE
        try:
            ldap_mod.LDAP3_AVAILABLE = False
            with pytest.raises(RuntimeError, match="ldap3"):
                self.provider._ensure_ldap3()
        finally:
            ldap_mod.LDAP3_AVAILABLE = original

    def test_authenticate_with_mocked_ldap3(self):
        """authenticate with mocked ldap3 connection (search returns no user)."""
        import backend.app.core.sso.ldap_provider as ldap_mod

        original = ldap_mod.LDAP3_AVAILABLE
        try:
            ldap_mod.LDAP3_AVAILABLE = True

            # Mock connection that returns no entries
            mock_conn = MagicMock()
            mock_conn.entries = []
            mock_conn.search.return_value = True
            self.provider._connection = mock_conn
            self.provider._server = MagicMock()

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                self.provider.authenticate("nonexistent", "pass")
            )
            # User not found → returns None
            assert result is None
        finally:
            ldap_mod.LDAP3_AVAILABLE = original
            self.provider._connection = None
            self.provider._server = None
