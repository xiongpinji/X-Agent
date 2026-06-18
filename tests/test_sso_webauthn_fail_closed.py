from __future__ import annotations

import pytest

from backend.app.api.errors import XAgentAPIError
from backend.app.api.sso import (
    WebAuthnAuthenticationCompleteRequest,
    WebAuthnRegistrationCompleteRequest,
    WebAuthnRegistrationStartRequest,
    webauthn_authenticate_complete,
    webauthn_authenticate_start,
    webauthn_register_complete,
    webauthn_register_start,
)
from backend.app.core.security import Principal, ROLE_SCOPES


def _principal() -> Principal:
    return Principal(
        tenant_id="default",
        user_id="bootstrap-admin",
        agent_id="test-agent",
        request_id="test-request",
        trace_id="test-trace",
        permission_scope=list(ROLE_SCOPES["admin"]),
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
    )


@pytest.mark.asyncio
async def test_webauthn_placeholder_handlers_fail_closed() -> None:
    principal = _principal()

    calls = [
        lambda: webauthn_register_start(
            WebAuthnRegistrationStartRequest(username="user@example.com"),
            principal,
        ),
        lambda: webauthn_register_complete(
            WebAuthnRegistrationCompleteRequest(
                challenge_id="challenge",
                credential_id="credential",
                public_key="public-key",
                device_name="device",
            ),
            principal,
        ),
        lambda: webauthn_authenticate_start(),
        lambda: webauthn_authenticate_complete(
            WebAuthnAuthenticationCompleteRequest(
                challenge_id="challenge",
                credential_id="credential",
                signature="signature",
                client_data="client-data",
            )
        ),
    ]

    for call in calls:
        with pytest.raises(XAgentAPIError) as exc_info:
            await call()
        assert exc_info.value.status_code == 501
        assert "disabled until standards-compliant" in exc_info.value.message
