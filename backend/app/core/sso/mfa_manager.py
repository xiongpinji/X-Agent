"""Multi-Factor Authentication (MFA) Manager."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MFAMethod(str, Enum):
    """Supported MFA methods."""

    TOTP = "totp"  # Time-based One-Time Password (Google Authenticator, Authy)
    SMS = "sms"  # SMS verification code
    EMAIL = "email"  # Email verification code
    WEBAUTHN = "webauthn"  # WebAuthn (FIDO2, YubiKey)


@dataclass
class MFAConfig:
    """MFA configuration."""

    enabled_methods: list[MFAMethod] = field(default_factory=lambda: [MFAMethod.TOTP, MFAMethod.EMAIL])
    totp_issuer: str = "X-Agent"
    totp_window: int = 1  # Allow ±1 time window
    sms_provider: str = "twilio"  # SMS provider
    sms_timeout: int = 300  # 5 minutes
    email_timeout: int = 600  # 10 minutes
    max_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes


class TOTPSecret(BaseModel):
    """TOTP secret configuration."""

    secret: str  # Base32-encoded secret
    backup_codes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified: bool = False


class MFAChallenge(BaseModel):
    """MFA challenge for verification."""

    challenge_id: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    user_id: str
    method: MFAMethod
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=10))
    attempts: int = 0
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TOTPManager:
    """Manages TOTP (Time-based One-Time Password) authentication."""

    def __init__(self, config: MFAConfig) -> None:
        """Initialize TOTP manager.

        Args:
            config: MFA configuration
        """
        self.config = config

    def generate_secret(self) -> str:
        """Generate TOTP secret.

        Returns:
            Base32-encoded secret
        """
        secret_bytes = secrets.token_bytes(20)
        secret = base64.b32encode(secret_bytes).decode("utf-8")
        return secret

    def get_provisioning_uri(self, secret: str, email: str) -> str:
        """Get provisioning URI for QR code generation.

        Args:
            secret: TOTP secret
            email: User email

        Returns:
            Provisioning URI (otpauth://)
        """
        label = f"{self.config.totp_issuer}:{email}"
        params = f"secret={secret}&issuer={self.config.totp_issuer}"
        return f"otpauth://totp/{label}?{params}"

    def verify_token(self, secret: str, token: str) -> bool:
        """Verify TOTP token.

        Args:
            secret: TOTP secret (base32-encoded)
            token: 6-digit token from authenticator

        Returns:
            True if token is valid
        """
        if not token.isdigit() or len(token) != 6:
            return False

        try:
            secret_bytes = base64.b32decode(secret)
        except Exception as e:
            logger.error(f"Failed to decode TOTP secret: {e}")
            return False

        # Check current and adjacent time windows
        current_time = int(time.time() // 30)

        for i in range(-self.config.totp_window, self.config.totp_window + 1):
            time_counter = current_time + i
            hmac_hash = hmac.new(
                secret_bytes,
                struct.pack(">Q", time_counter),
                hashlib.sha1,
            ).digest()

            offset = hmac_hash[-1] & 0x0F
            code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0]
            code = (code & 0x7FFFFFFF) % 1000000

            if str(code).zfill(6) == token:
                return True

        return False

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup codes for account recovery.

        Args:
            count: Number of backup codes to generate

        Returns:
            List of backup codes
        """
        codes = []
        for _ in range(count):
            code = "-".join(
                secrets.token_hex(2).upper() for _ in range(3)
            )  # Format: XXXX-XXXX-XXXX
            codes.append(code)
        return codes


class SMSManager:
    """Manages SMS-based MFA."""

    def __init__(self, config: MFAConfig) -> None:
        """Initialize SMS manager.

        Args:
            config: MFA configuration
        """
        self.config = config
        self._codes: dict[str, tuple[str, float]] = {}  # challenge_id -> (code, expiry)

    def generate_code(self) -> str:
        """Generate SMS verification code.

        Returns:
            6-digit code
        """
        return "".join(str(secrets.randbelow(10)) for _ in range(6))

    async def send_code(self, phone_number: str, code: str) -> bool:
        """Send SMS code to phone number.

        Args:
            phone_number: Phone number
            code: Verification code

        Returns:
            True if SMS sent successfully
        """
        # TODO: Implement SMS sending via Twilio or other provider
        logger.info(f"SMS code sent to {phone_number}: {code}")
        return True

    def verify_code(self, challenge_id: str, code: str) -> bool:
        """Verify SMS code.

        Args:
            challenge_id: Challenge ID
            code: Verification code

        Returns:
            True if code is valid
        """
        if challenge_id not in self._codes:
            return False

        stored_code, expiry = self._codes[challenge_id]
        if time.time() > expiry:
            del self._codes[challenge_id]
            return False

        return stored_code == code


class EmailManager:
    """Manages email-based MFA."""

    def __init__(self, config: MFAConfig) -> None:
        """Initialize email manager.

        Args:
            config: MFA configuration
        """
        self.config = config
        self._codes: dict[str, tuple[str, float]] = {}  # challenge_id -> (code, expiry)

    def generate_code(self) -> str:
        """Generate email verification code.

        Returns:
            6-digit code
        """
        return "".join(str(secrets.randbelow(10)) for _ in range(6))

    async def send_code(self, email: str, code: str) -> bool:
        """Send email verification code.

        Args:
            email: Email address
            code: Verification code

        Returns:
            True if email sent successfully
        """
        # TODO: Implement email sending
        logger.info(f"Email code sent to {email}: {code}")
        return True

    def verify_code(self, challenge_id: str, code: str) -> bool:
        """Verify email code.

        Args:
            challenge_id: Challenge ID
            code: Verification code

        Returns:
            True if code is valid
        """
        if challenge_id not in self._codes:
            return False

        stored_code, expiry = self._codes[challenge_id]
        if time.time() > expiry:
            del self._codes[challenge_id]
            return False

        return stored_code == code


class MFAManager:
    """Manages multi-factor authentication."""

    def __init__(self, config: MFAConfig | None = None) -> None:
        """Initialize MFA manager.

        Args:
            config: MFA configuration
        """
        self.config = config or MFAConfig()
        self.totp = TOTPManager(self.config)
        self.sms = SMSManager(self.config)
        self.email = EmailManager(self.config)
        self._challenges: dict[str, MFAChallenge] = {}
        self._user_mfa: dict[str, dict[str, Any]] = {}  # user_id -> {method -> config}
        self._lockouts: dict[str, float] = {}  # user_id -> lockout_expiry

    def setup_totp(self, user_id: str) -> tuple[str, str]:
        """Setup TOTP for user.

        Args:
            user_id: User ID

        Returns:
            Tuple of (secret, provisioning_uri)
        """
        secret = self.totp.generate_secret()
        provisioning_uri = self.totp.get_provisioning_uri(secret, user_id)

        if user_id not in self._user_mfa:
            self._user_mfa[user_id] = {}

        self._user_mfa[user_id][MFAMethod.TOTP] = {
            "secret": secret,
            "verified": False,
            "created_at": datetime.now(UTC),
        }

        logger.info(f"TOTP setup initiated for user: {user_id}")
        return secret, provisioning_uri

    def verify_totp_setup(self, user_id: str, token: str) -> bool:
        """Verify TOTP setup with token.

        Args:
            user_id: User ID
            token: TOTP token

        Returns:
            True if verification successful
        """
        if user_id not in self._user_mfa or MFAMethod.TOTP not in self._user_mfa[user_id]:
            return False

        totp_config = self._user_mfa[user_id][MFAMethod.TOTP]
        if self.totp.verify_token(totp_config["secret"], token):
            totp_config["verified"] = True
            totp_config["backup_codes"] = self.totp.generate_backup_codes()
            logger.info(f"TOTP verified for user: {user_id}")
            return True

        return False

    async def create_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """Create MFA challenge.

        Args:
            user_id: User ID
            method: MFA method
            metadata: Additional metadata

        Returns:
            MFA challenge
        """
        # Check lockout
        if user_id in self._lockouts and time.time() < self._lockouts[user_id]:
            raise ValueError("User is locked out due to too many failed attempts")

        challenge = MFAChallenge(
            user_id=user_id,
            method=method,
            metadata=metadata or {},
        )

        self._challenges[challenge.challenge_id] = challenge

        # Send code based on method
        if method == MFAMethod.TOTP:
            # TOTP doesn't require sending
            pass
        elif method == MFAMethod.SMS:
            phone = metadata.get("phone_number") if metadata else None
            if phone:
                code = self.sms.generate_code()
                self.sms._codes[challenge.challenge_id] = (code, time.time() + self.config.sms_timeout)
                await self.sms.send_code(phone, code)
        elif method == MFAMethod.EMAIL:
            email = metadata.get("email") if metadata else None
            if email:
                code = self.email.generate_code()
                self.email._codes[challenge.challenge_id] = (code, time.time() + self.config.email_timeout)
                await self.email.send_code(email, code)

        logger.debug(f"MFA challenge created: {challenge.challenge_id}")
        return challenge

    def verify_challenge(self, challenge_id: str, code: str) -> bool:
        """Verify MFA challenge.

        Args:
            challenge_id: Challenge ID
            code: Verification code

        Returns:
            True if verification successful
        """
        if challenge_id not in self._challenges:
            return False

        challenge = self._challenges[challenge_id]

        # Check expiry
        if datetime.now(UTC) > challenge.expires_at:
            del self._challenges[challenge_id]
            return False

        # Check attempts
        if challenge.attempts >= self.config.max_attempts:
            self._lockouts[challenge.user_id] = time.time() + self.config.lockout_duration
            del self._challenges[challenge_id]
            logger.warning(f"User locked out due to too many MFA attempts: {challenge.user_id}")
            return False

        challenge.attempts += 1

        # Verify based on method
        if challenge.method == MFAMethod.TOTP:
            if challenge.user_id in self._user_mfa and MFAMethod.TOTP in self._user_mfa[challenge.user_id]:
                secret = self._user_mfa[challenge.user_id][MFAMethod.TOTP]["secret"]
                if self.totp.verify_token(secret, code):
                    challenge.verified = True
                    logger.info(f"TOTP verified for challenge: {challenge_id}")
                    return True

        elif challenge.method == MFAMethod.SMS:
            if self.sms.verify_code(challenge_id, code):
                challenge.verified = True
                logger.info(f"SMS verified for challenge: {challenge_id}")
                return True

        elif challenge.method == MFAMethod.EMAIL:
            if self.email.verify_code(challenge_id, code):
                challenge.verified = True
                logger.info(f"Email verified for challenge: {challenge_id}")
                return True

        return False

    def get_challenge(self, challenge_id: str) -> MFAChallenge | None:
        """Get MFA challenge.

        Args:
            challenge_id: Challenge ID

        Returns:
            MFA challenge or None
        """
        return self._challenges.get(challenge_id)

    def cleanup_expired_challenges(self) -> int:
        """Clean up expired MFA challenges.

        Returns:
            Number of challenges cleaned up
        """
        now = datetime.now(UTC)
        expired = [
            cid for cid, challenge in self._challenges.items() if now > challenge.expires_at
        ]

        for cid in expired:
            del self._challenges[cid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired MFA challenges")

        return len(expired)
