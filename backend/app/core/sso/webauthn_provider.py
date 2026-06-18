"""WebAuthn (FIDO2) Provider Implementation."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class WebAuthnConfig:
    """WebAuthn configuration."""

    rp_id: str  # Relying Party ID (domain)
    rp_name: str = "X-Agent"
    origin: str = ""  # Full origin URL
    timeout: int = 60000  # 60 seconds
    attestation: str = "direct"  # direct, indirect, none
    user_verification: str = "preferred"  # required, preferred, discouraged
    allow_unverified_attestation_for_tests: bool = False


class WebAuthnCredential(BaseModel):
    """WebAuthn credential."""

    credential_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    public_key: str  # Base64-encoded public key
    sign_count: int = 0
    transports: list[str] = Field(default_factory=list)  # usb, nfc, ble, internal
    device_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    backup_eligible: bool = False
    backup_state: bool = False


class WebAuthnChallenge(BaseModel):
    """WebAuthn challenge for registration or authentication."""

    challenge_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    challenge: str  # Base64-encoded challenge
    operation: str  # register or authenticate
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=10))
    verified: bool = False


class WebAuthnProvider:
    """WebAuthn (FIDO2) provider for passwordless authentication."""

    def __init__(self, config: WebAuthnConfig) -> None:
        """Initialize WebAuthn provider.

        Args:
            config: WebAuthn configuration
        """
        self.config = config
        self._credentials: dict[str, WebAuthnCredential] = {}  # credential_id -> credential
        self._user_credentials: dict[str, list[str]] = {}  # user_id -> [credential_ids]
        self._challenges: dict[str, WebAuthnChallenge] = {}

    def generate_challenge(self) -> str:
        """Generate WebAuthn challenge.

        Returns:
            Base64-encoded challenge
        """
        import secrets

        challenge_bytes = secrets.token_bytes(32)
        return base64.b64encode(challenge_bytes).decode("utf-8")

    def create_registration_challenge(self, user_id: str, username: str) -> dict[str, Any]:
        """Create registration challenge for new credential.

        Args:
            user_id: User ID
            username: Username

        Returns:
            Registration challenge options
        """
        challenge = self.generate_challenge()
        challenge_obj = WebAuthnChallenge(
            user_id=user_id,
            challenge=challenge,
            operation="register",
        )
        self._challenges[challenge_obj.challenge_id] = challenge_obj

        # Encode user ID
        user_id_bytes = user_id.encode("utf-8")
        user_id_b64 = base64.b64encode(user_id_bytes).decode("utf-8")

        return {
            "challenge": challenge,
            "rp": {
                "name": self.config.rp_name,
                "id": self.config.rp_id,
            },
            "user": {
                "id": user_id_b64,
                "name": username,
                "displayName": username,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": self.config.timeout,
            "attestation": self.config.attestation,
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "residentKey": "preferred",
                "userVerification": self.config.user_verification,
            },
        }

    def create_authentication_challenge(self, user_id: str) -> dict[str, Any]:
        """Create authentication challenge.

        Args:
            user_id: User ID

        Returns:
            Authentication challenge options
        """
        challenge = self.generate_challenge()
        challenge_obj = WebAuthnChallenge(
            user_id=user_id,
            challenge=challenge,
            operation="authenticate",
        )
        self._challenges[challenge_obj.challenge_id] = challenge_obj

        # Get user's credentials
        credential_ids = self._user_credentials.get(user_id, [])
        allow_credentials = [
            {
                "type": "public-key",
                "id": cid,
                "transports": self._credentials[cid].transports if cid in self._credentials else [],
            }
            for cid in credential_ids
        ]

        return {
            "challenge": challenge,
            "timeout": self.config.timeout,
            "rpId": self.config.rp_id,
            "userVerification": self.config.user_verification,
            "allowCredentials": allow_credentials,
        }

    def verify_registration(
        self,
        challenge_id: str,
        credential_id: str,
        public_key: str,
        device_name: str | None = None,
        transports: list[str] | None = None,
    ) -> bool:
        """Verify registration response.

        Args:
            challenge_id: Challenge ID
            credential_id: Credential ID
            public_key: Base64-encoded public key
            device_name: Device name
            transports: Transport types

        Returns:
            True if verification successful
        """
        if challenge_id not in self._challenges:
            logger.warning(f"Invalid challenge ID: {challenge_id}")
            return False

        challenge_obj = self._challenges[challenge_id]

        # Check challenge expiry
        if datetime.now(UTC) > challenge_obj.expires_at:
            logger.warning(f"Challenge expired: {challenge_id}")
            del self._challenges[challenge_id]
            return False

        # Check operation type
        if challenge_obj.operation != "register":
            logger.warning(f"Challenge is not for registration: {challenge_id}")
            return False

        if not self.config.allow_unverified_attestation_for_tests:
            logger.warning("WebAuthn registration rejected: attestation verification is not implemented")
            return False

        # Store credential
        credential = WebAuthnCredential(
            credential_id=credential_id,
            user_id=challenge_obj.user_id,
            public_key=public_key,
            device_name=device_name,
            transports=transports or [],
        )

        self._credentials[credential_id] = credential

        # Track user credentials
        if challenge_obj.user_id not in self._user_credentials:
            self._user_credentials[challenge_obj.user_id] = []
        self._user_credentials[challenge_obj.user_id].append(credential_id)

        # Mark challenge as verified
        challenge_obj.verified = True

        logger.info(f"WebAuthn credential registered: {credential_id} for user: {challenge_obj.user_id}")
        return True

    def verify_authentication(
        self,
        challenge_id: str,
        credential_id: str,
        signature: str,
        client_data: str,
    ) -> bool:
        """Verify authentication response.

        Args:
            challenge_id: Challenge ID
            credential_id: Credential ID
            signature: Base64-encoded signature
            client_data: Base64-encoded client data

        Returns:
            True if verification successful
        """
        if challenge_id not in self._challenges:
            logger.warning(f"Invalid challenge ID: {challenge_id}")
            return False

        challenge_obj = self._challenges[challenge_id]

        # Check challenge expiry
        if datetime.now(UTC) > challenge_obj.expires_at:
            logger.warning(f"Challenge expired: {challenge_id}")
            del self._challenges[challenge_id]
            return False

        # Check operation type
        if challenge_obj.operation != "authenticate":
            logger.warning(f"Challenge is not for authentication: {challenge_id}")
            return False

        # Get credential
        if credential_id not in self._credentials:
            logger.warning(f"Credential not found: {credential_id}")
            return False

        credential = self._credentials[credential_id]

        # Verify credential belongs to user
        if credential.user_id != challenge_obj.user_id:
            logger.warning(f"Credential does not belong to user: {challenge_obj.user_id}")
            return False

        logger.warning("WebAuthn authentication rejected: assertion signature verification is not implemented")
        return False

    def get_user_credentials(self, user_id: str) -> list[WebAuthnCredential]:
        """Get all credentials for user.

        Args:
            user_id: User ID

        Returns:
            List of credentials
        """
        credential_ids = self._user_credentials.get(user_id, [])
        return [self._credentials[cid] for cid in credential_ids if cid in self._credentials]

    def remove_credential(self, user_id: str, credential_id: str) -> bool:
        """Remove credential.

        Args:
            user_id: User ID
            credential_id: Credential ID

        Returns:
            True if removal successful
        """
        if credential_id not in self._credentials:
            return False

        credential = self._credentials[credential_id]
        if credential.user_id != user_id:
            logger.warning(f"Credential does not belong to user: {user_id}")
            return False

        del self._credentials[credential_id]

        if user_id in self._user_credentials:
            self._user_credentials[user_id] = [
                cid for cid in self._user_credentials[user_id] if cid != credential_id
            ]

        logger.info(f"WebAuthn credential removed: {credential_id}")
        return True

    def cleanup_expired_challenges(self) -> int:
        """Clean up expired challenges.

        Returns:
            Number of challenges cleaned up
        """
        now = datetime.now(UTC)
        expired = [cid for cid, challenge in self._challenges.items() if now > challenge.expires_at]

        for cid in expired:
            del self._challenges[cid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired WebAuthn challenges")

        return len(expired)
