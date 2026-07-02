"""SSO and Enterprise Authentication Tests."""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.sso.oauth_provider import OAuthManager, OAuthProvider, OAuthConfig
from backend.app.core.sso.mfa_manager import MFAManager, MFAMethod, MFAConfig, MFAChallenge
from backend.app.core.sso.session_manager import SessionManager, SessionConfig
from backend.app.core.sso.webauthn_provider import WebAuthnProvider, WebAuthnConfig


class TestOAuthProvider:
    """OAuth provider tests."""

    def test_oauth_manager_initialization(self):
        """Test OAuth manager initialization."""
        manager = OAuthManager()
        assert manager is not None
        assert len(manager._clients) == 0

    def test_register_oauth_provider(self):
        """Test registering OAuth provider."""
        manager = OAuthManager()
        config = OAuthConfig(
            provider=OAuthProvider.GOOGLE,
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://example.com/callback",
        )
        manager.register_provider(config)
        assert OAuthProvider.GOOGLE in manager._clients

    def test_create_oauth_session(self):
        """Test creating OAuth session."""
        manager = OAuthManager()
        session = manager.create_session(OAuthProvider.GOOGLE)
        assert session.state is not None
        assert session.nonce is not None
        assert session.state in manager._sessions

    def test_get_authorization_url(self):
        """Test getting authorization URL."""
        manager = OAuthManager()
        config = OAuthConfig(
            provider=OAuthProvider.GOOGLE,
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://example.com/callback",
        )
        manager.register_provider(config)
        session = manager.create_session(OAuthProvider.GOOGLE)
        url = manager.get_authorization_url(OAuthProvider.GOOGLE, session)
        assert "https://accounts.google.com" in url
        assert "client_id=test_client_id" in url
        assert f"state={session.state}" in url

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired OAuth sessions."""
        manager = OAuthManager()
        session = manager.create_session(OAuthProvider.GOOGLE)
        # Manually expire session
        manager._sessions[session.state].expires_at = datetime.now(UTC) - timedelta(minutes=1)
        count = manager.cleanup_expired_sessions()
        assert count == 1
        assert session.state not in manager._sessions


class TestMFAManager:
    """MFA manager tests."""

    def test_mfa_manager_initialization(self):
        """Test MFA manager initialization."""
        manager = MFAManager()
        assert manager is not None
        assert manager.totp is not None
        assert manager.sms is not None
        assert manager.email is not None

    def test_setup_totp(self):
        """Test TOTP setup."""
        manager = MFAManager()
        secret, uri = manager.setup_totp("user123")
        assert secret is not None
        assert uri is not None
        assert "otpauth://totp/" in uri
        assert "user123" in manager._user_mfa

    def test_verify_totp_setup(self):
        """Test TOTP setup verification."""
        manager = MFAManager()
        secret, _ = manager.setup_totp("user123")

        # Generate valid TOTP token
        import time
        import hmac
        import hashlib
        import struct
        import base64

        secret_bytes = base64.b32decode(secret)
        current_time = int(time.time() // 30)
        hmac_hash = hmac.new(secret_bytes, struct.pack(">Q", current_time), hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0]
        token = str((code & 0x7FFFFFFF) % 1000000).zfill(6)

        result = manager.verify_totp_setup("user123", token)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_mfa_challenge(self):
        """Test creating MFA challenge."""
        manager = MFAManager()
        challenge = await manager.create_challenge("user123", MFAMethod.EMAIL, {"email": "user@example.com"})
        assert challenge is not None
        assert challenge.user_id == "user123"
        assert challenge.method == MFAMethod.EMAIL

    def test_verify_mfa_challenge(self):
        """Test verifying MFA challenge."""
        manager = MFAManager()
        # Create challenge
        import asyncio
        challenge = asyncio.run(manager.create_challenge("user123", MFAMethod.EMAIL, {"email": "user@example.com"}))

        # Manually set code for testing
        manager.email._codes[challenge.challenge_id] = ("123456", float('inf'))

        # Verify
        result = manager.verify_challenge(challenge.challenge_id, "123456")
        assert result is True

    def test_cleanup_expired_challenges(self):
        """Test cleaning up expired MFA challenges."""
        manager = MFAManager()
        challenge = MFAChallenge(user_id="user123", method=MFAMethod.EMAIL)
        challenge.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        manager._challenges[challenge.challenge_id] = challenge

        count = manager.cleanup_expired_challenges()
        assert count == 1
        assert challenge.challenge_id not in manager._challenges


class TestSessionManager:
    """Session manager tests."""

    def test_session_manager_initialization(self):
        """Test session manager initialization."""
        manager = SessionManager()
        assert manager is not None
        assert manager.config is not None

    def test_create_session(self):
        """Test creating session."""
        manager = SessionManager()
        session = manager.create_session(
            user_id="user123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            device_id="device123",
        )
        assert session is not None
        assert session.user_id == "user123"
        assert session.ip_address == "192.168.1.1"
        assert session.session_id in manager._sessions

    def test_get_session(self):
        """Test getting session."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123")
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.user_id == "user123"

    def test_update_session_activity(self):
        """Test updating session activity."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123")
        old_activity = session.last_activity

        # Wait a bit and update
        import time
        time.sleep(0.1)
        result = manager.update_session_activity(session.session_id)

        assert result is True
        updated = manager.get_session(session.session_id)
        assert updated.last_activity > old_activity

    def test_revoke_session(self):
        """Test revoking session."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123")
        result = manager.revoke_session(session.session_id)
        assert result is True
        assert manager.get_session(session.session_id) is None

    def test_revoke_user_sessions(self):
        """Test revoking all user sessions."""
        manager = SessionManager()
        session1 = manager.create_session(user_id="user123")
        session2 = manager.create_session(user_id="user123")

        count = manager.revoke_user_sessions("user123")
        assert count == 2
        assert manager.get_session(session1.session_id) is None
        assert manager.get_session(session2.session_id) is None

    def test_get_user_sessions(self):
        """Test getting user sessions."""
        manager = SessionManager()
        session1 = manager.create_session(user_id="user123")
        session2 = manager.create_session(user_id="user123")

        sessions = manager.get_user_sessions("user123")
        assert len(sessions) == 2

    def test_max_concurrent_sessions(self):
        """Test max concurrent sessions limit."""
        config = SessionConfig(max_concurrent_sessions=2)
        manager = SessionManager(config)

        session1 = manager.create_session(user_id="user123")
        session2 = manager.create_session(user_id="user123")
        session3 = manager.create_session(user_id="user123")

        # session1 should be revoked
        assert manager.get_session(session1.session_id) is None
        assert manager.get_session(session2.session_id) is not None
        assert manager.get_session(session3.session_id) is not None

    def test_verify_mfa(self):
        """Test verifying MFA for session."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123")
        result = manager.verify_mfa(session.session_id, "totp")
        assert result is True

        updated = manager.get_session(session.session_id)
        assert updated.mfa_verified is True
        assert updated.mfa_method == "totp"

    def test_mark_device_trusted(self):
        """Test marking device as trusted."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123", device_id="device123")
        result = manager.mark_device_trusted(session.session_id)
        assert result is True

        updated = manager.get_session(session.session_id)
        assert updated.trusted_device is True

    def test_ip_whitelist(self):
        """Test IP whitelist."""
        manager = SessionManager()
        manager.add_ip_whitelist("user123", "192.168.1.1")
        assert manager.is_ip_whitelisted("user123", "192.168.1.1") is True
        assert manager.is_ip_whitelisted("user123", "192.168.1.2") is False

    def test_block_ip(self):
        """Test blocking IP."""
        manager = SessionManager()
        manager.block_ip("192.168.1.1")
        assert manager.is_ip_blocked("192.168.1.1") is True
        assert manager.is_ip_blocked("192.168.1.2") is False

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions."""
        manager = SessionManager()
        session = manager.create_session(user_id="user123")
        # Manually expire session
        manager._sessions[session.session_id].absolute_expires_at = datetime.now(UTC) - timedelta(hours=1)

        count = manager.cleanup_expired_sessions()
        assert count == 1
        assert manager.get_session(session.session_id) is None


class TestWebAuthnProvider:
    """WebAuthn provider tests."""

    def test_webauthn_provider_initialization(self):
        """Test WebAuthn provider initialization."""
        config = WebAuthnConfig(
            rp_id="example.com",
            origin="https://example.com",
        )
        provider = WebAuthnProvider(config)
        assert provider is not None

    def test_generate_challenge(self):
        """Test generating WebAuthn challenge."""
        config = WebAuthnConfig(rp_id="example.com", origin="https://example.com")
        provider = WebAuthnProvider(config)
        challenge = provider.generate_challenge()
        assert challenge is not None
        assert len(challenge) > 0

    def test_create_registration_challenge(self):
        """Test creating registration challenge."""
        config = WebAuthnConfig(rp_id="example.com", origin="https://example.com")
        provider = WebAuthnProvider(config)
        options = provider.create_registration_challenge("user123", "user@example.com")

        assert options is not None
        assert "challenge" in options
        assert "rp" in options
        assert "user" in options
        assert options["rp"]["id"] == "example.com"

    def test_create_authentication_challenge(self):
        """Test creating authentication challenge."""
        config = WebAuthnConfig(rp_id="example.com", origin="https://example.com")
        provider = WebAuthnProvider(config)
        options = provider.create_authentication_challenge("user123")

        assert options is not None
        assert "challenge" in options
        assert "rpId" in options
        assert options["rpId"] == "example.com"

    def test_verify_registration_fails_closed_without_real_attestation(self):
        """WebAuthn registration must fail closed until real attestation verification is wired."""
        config = WebAuthnConfig(rp_id="example.com", origin="https://example.com")
        provider = WebAuthnProvider(config)

        # Create challenge
        provider.create_registration_challenge("user123", "user@example.com")
        challenge_id = list(provider._challenges.keys())[0]

        # Verify registration
        result = provider.verify_registration(
            challenge_id,
            "credential123",
            "public_key_data",
            "My Device",
        )
        assert result is False

    def test_get_user_credentials_for_test_mode_registered_credential(self):
        """Test getting user credentials when explicitly using non-production test mode."""
        config = WebAuthnConfig(
            rp_id="example.com",
            origin="https://example.com",
            allow_unverified_attestation_for_tests=True,
        )
        provider = WebAuthnProvider(config)

        # Register credential
        provider.create_registration_challenge("user123", "user@example.com")
        challenge_id = list(provider._challenges.keys())[0]
        provider.verify_registration(challenge_id, "credential123", "public_key_data")

        # Get credentials
        credentials = provider.get_user_credentials("user123")
        assert len(credentials) == 1
        assert credentials[0].credential_id == "credential123"

    def test_remove_credential(self):
        """Test removing credential."""
        config = WebAuthnConfig(
            rp_id="example.com",
            origin="https://example.com",
            allow_unverified_attestation_for_tests=True,
        )
        provider = WebAuthnProvider(config)

        # Register credential
        provider.create_registration_challenge("user123", "user@example.com")
        challenge_id = list(provider._challenges.keys())[0]
        provider.verify_registration(challenge_id, "credential123", "public_key_data")

        # Remove credential
        result = provider.remove_credential("user123", "credential123")
        assert result is True

        credentials = provider.get_user_credentials("user123")
        assert len(credentials) == 0

    def test_verify_authentication_fails_closed_without_real_signature_verification(self):
        """WebAuthn authentication must not accept placeholder signatures."""
        config = WebAuthnConfig(
            rp_id="example.com",
            origin="https://example.com",
            allow_unverified_attestation_for_tests=True,
        )
        provider = WebAuthnProvider(config)
        provider.create_registration_challenge("user123", "user@example.com")
        registration_challenge_id = list(provider._challenges.keys())[0]
        assert provider.verify_registration(
            registration_challenge_id,
            "credential123",
            "public_key_data",
        )
        provider.create_authentication_challenge("user123")
        auth_challenge_id = [
            challenge_id
            for challenge_id, challenge in provider._challenges.items()
            if challenge.operation == "authenticate"
        ][0]

        result = provider.verify_authentication(
            auth_challenge_id,
            "credential123",
            "placeholder-signature",
            "placeholder-client-data",
        )

        assert result is False

    def test_cleanup_expired_challenges(self):
        """Test cleaning up expired WebAuthn challenges."""
        config = WebAuthnConfig(rp_id="example.com", origin="https://example.com")
        provider = WebAuthnProvider(config)

        challenge_options = provider.create_registration_challenge("user123", "user@example.com")
        challenge_id = list(provider._challenges.keys())[0]

        # Manually expire challenge
        provider._challenges[challenge_id].expires_at = datetime.now(UTC) - timedelta(minutes=1)

        count = provider.cleanup_expired_challenges()
        assert count == 1
        assert challenge_id not in provider._challenges


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_oauth_login_flow(self):
        """Test complete OAuth login flow."""
        manager = OAuthManager()
        config = OAuthConfig(
            provider=OAuthProvider.GOOGLE,
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://example.com/callback",
        )
        manager.register_provider(config)

        # Create session
        session = manager.create_session(OAuthProvider.GOOGLE)
        assert session.state is not None

        # Get authorization URL
        url = manager.get_authorization_url(OAuthProvider.GOOGLE, session)
        assert "https://accounts.google.com" in url

    @pytest.mark.asyncio
    async def test_mfa_flow(self):
        """Test complete MFA flow."""
        manager = MFAManager()

        # Setup TOTP
        secret, uri = manager.setup_totp("user123")
        assert secret is not None

        # Create challenge
        challenge = await manager.create_challenge("user123", MFAMethod.EMAIL, {"email": "user@example.com"})
        assert challenge is not None

    def test_session_lifecycle(self):
        """Test complete session lifecycle."""
        manager = SessionManager()

        # Create session
        session = manager.create_session(user_id="user123", ip_address="192.168.1.1")
        assert session is not None

        # Update activity
        manager.update_session_activity(session.session_id)

        # Verify MFA
        manager.verify_mfa(session.session_id, "totp")

        # Mark device trusted
        manager.mark_device_trusted(session.session_id)

        # Get session
        retrieved = manager.get_session(session.session_id)
        assert retrieved.mfa_verified is True
        assert retrieved.trusted_device is True

        # Revoke session
        manager.revoke_session(session.session_id)
        assert manager.get_session(session.session_id) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
