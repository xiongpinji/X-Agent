"""Distributed Session Management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Session configuration."""

    session_timeout: int = 3600  # 1 hour
    absolute_timeout: int = 86400  # 24 hours
    idle_timeout: int = 1800  # 30 minutes
    max_concurrent_sessions: int = 5
    enable_session_audit: bool = True
    enable_device_tracking: bool = True


class SessionAuditLog(BaseModel):
    """Session audit log entry."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str  # login, logout, activity, mfa_verified, etc.
    ip_address: str | None = None
    user_agent: str | None = None
    device_id: str | None = None
    location: str | None = None
    status: str = "success"  # success, failed, suspicious
    details: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    """User session."""

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    tenant_id: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(hours=1))
    absolute_expires_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(hours=24)
    )
    ip_address: str | None = None
    user_agent: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    location: str | None = None
    mfa_verified: bool = False
    mfa_method: str | None = None
    trusted_device: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    audit_logs: list[SessionAuditLog] = Field(default_factory=list)


class ConditionalAccessPolicy(BaseModel):
    """Conditional access policy."""

    policy_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    enabled: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    grant_controls: dict[str, Any] = Field(default_factory=dict)
    session_controls: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionManager:
    """Manages distributed sessions with Redis support."""

    def __init__(self, config: SessionConfig | None = None, redis_client: Any = None) -> None:
        """Initialize session manager.

        Args:
            config: Session configuration
            redis_client: Optional Redis client for distributed sessions
        """
        self.config = config or SessionConfig()
        self.redis_client = redis_client
        self._sessions: dict[str, Session] = {}  # In-memory fallback
        self._user_sessions: dict[str, list[str]] = {}  # user_id -> [session_ids]
        self._device_sessions: dict[str, list[str]] = {}  # device_id -> [session_ids]
        self._conditional_policies: dict[str, ConditionalAccessPolicy] = {}
        self._ip_whitelist: dict[str, list[str]] = {}  # user_id -> [ip_addresses]
        self._blocked_ips: set[str] = set()

    def create_session(
        self,
        user_id: str,
        tenant_id: str = "default",
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_id: str | None = None,
        device_name: str | None = None,
        location: str | None = None,
    ) -> Session:
        """Create new session.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            ip_address: Client IP address
            user_agent: Client user agent
            device_id: Device ID
            device_name: Device name
            location: Geographic location

        Returns:
            Created session

        Raises:
            ValueError: If max concurrent sessions exceeded
        """
        # Check concurrent session limit
        user_sessions = self._user_sessions.get(user_id, [])
        if len(user_sessions) >= self.config.max_concurrent_sessions:
            # Remove oldest session
            oldest_session_id = user_sessions[0]
            self.revoke_session(oldest_session_id)
            user_sessions = user_sessions[1:]

        session = Session(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
            device_name=device_name,
            location=location,
        )

        # Store session
        if self.redis_client:
            try:
                self._store_session_redis(session)
            except Exception as e:
                logger.warning(f"Failed to store session in Redis: {e}. Using in-memory fallback.")
                self._sessions[session.session_id] = session
        else:
            self._sessions[session.session_id] = session

        # Track user sessions
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session.session_id)

        # Track device sessions
        if device_id:
            if device_id not in self._device_sessions:
                self._device_sessions[device_id] = []
            self._device_sessions[device_id].append(session.session_id)

        # Audit log
        if self.config.enable_session_audit:
            self._add_audit_log(
                session.session_id,
                "login",
                ip_address,
                user_agent,
                device_id,
                location,
            )

        logger.info(f"Session created: {session.session_id} for user: {user_id}")
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None
        """
        if self.redis_client:
            try:
                return self._get_session_redis(session_id)
            except Exception as e:
                logger.warning(f"Failed to get session from Redis: {e}. Using in-memory fallback.")

        return self._sessions.get(session_id)

    def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity time.

        Args:
            session_id: Session ID

        Returns:
            True if update successful
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Check if session expired
        now = datetime.now(UTC)
        if now > session.absolute_expires_at:
            self.revoke_session(session_id)
            return False

        # Check idle timeout
        if now - session.last_activity > timedelta(seconds=self.config.idle_timeout):
            self.revoke_session(session_id)
            return False

        session.last_activity = now
        session.expires_at = now + timedelta(seconds=self.config.session_timeout)

        # Store updated session
        if self.redis_client:
            try:
                self._store_session_redis(session)
            except Exception as e:
                logger.warning(f"Failed to update session in Redis: {e}")
                self._sessions[session_id] = session
        else:
            self._sessions[session_id] = session

        return True

    def verify_mfa(self, session_id: str, mfa_method: str) -> bool:
        """Mark session as MFA verified.

        Args:
            session_id: Session ID
            mfa_method: MFA method used

        Returns:
            True if verification successful
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.mfa_verified = True
        session.mfa_method = mfa_method

        if self.redis_client:
            try:
                self._store_session_redis(session)
            except Exception as e:
                logger.warning(f"Failed to update session in Redis: {e}")
                self._sessions[session_id] = session
        else:
            self._sessions[session_id] = session

        if self.config.enable_session_audit:
            self._add_audit_log(session_id, "mfa_verified", details={"method": mfa_method})

        logger.info(f"MFA verified for session: {session_id}")
        return True

    def mark_device_trusted(self, session_id: str) -> bool:
        """Mark device as trusted.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.trusted_device = True

        if self.redis_client:
            try:
                self._store_session_redis(session)
            except Exception as e:
                logger.warning(f"Failed to update session in Redis: {e}")
                self._sessions[session_id] = session
        else:
            self._sessions[session_id] = session

        logger.info(f"Device marked as trusted: {session.device_id}")
        return True

    def revoke_session(self, session_id: str) -> bool:
        """Revoke session.

        Args:
            session_id: Session ID

        Returns:
            True if revocation successful
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Remove from tracking
        if session.user_id in self._user_sessions:
            self._user_sessions[session.user_id] = [
                sid for sid in self._user_sessions[session.user_id] if sid != session_id
            ]

        if session.device_id and session.device_id in self._device_sessions:
            self._device_sessions[session.device_id] = [
                sid for sid in self._device_sessions[session.device_id] if sid != session_id
            ]

        # Remove session
        if self.redis_client:
            try:
                self.redis_client.delete(f"session:{session_id}")
            except Exception as e:
                logger.warning(f"Failed to revoke session in Redis: {e}")
                self._sessions.pop(session_id, None)
        else:
            self._sessions.pop(session_id, None)

        if self.config.enable_session_audit:
            self._add_audit_log(session_id, "logout")

        logger.info(f"Session revoked: {session_id}")
        return True

    def revoke_user_sessions(self, user_id: str, exclude_session_id: str | None = None) -> int:
        """Revoke all sessions for user.

        Args:
            user_id: User ID
            exclude_session_id: Session ID to exclude from revocation

        Returns:
            Number of sessions revoked
        """
        session_ids = self._user_sessions.get(user_id, [])
        count = 0

        for session_id in session_ids:
            if exclude_session_id and session_id == exclude_session_id:
                continue
            if self.revoke_session(session_id):
                count += 1

        logger.info(f"Revoked {count} sessions for user: {user_id}")
        return count

    def get_user_sessions(self, user_id: str) -> list[Session]:
        """Get all active sessions for user.

        Args:
            user_id: User ID

        Returns:
            List of sessions
        """
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []

        for session_id in session_ids:
            session = self.get_session(session_id)
            if session:
                sessions.append(session)

        return sessions

    def add_ip_whitelist(self, user_id: str, ip_address: str) -> None:
        """Add IP to user's whitelist.

        Args:
            user_id: User ID
            ip_address: IP address
        """
        if user_id not in self._ip_whitelist:
            self._ip_whitelist[user_id] = []

        if ip_address not in self._ip_whitelist[user_id]:
            self._ip_whitelist[user_id].append(ip_address)
            logger.info(f"Added IP to whitelist for user {user_id}: {ip_address}")

    def is_ip_whitelisted(self, user_id: str, ip_address: str) -> bool:
        """Check if IP is whitelisted for user.

        Args:
            user_id: User ID
            ip_address: IP address

        Returns:
            True if IP is whitelisted
        """
        if user_id not in self._ip_whitelist:
            return False

        return ip_address in self._ip_whitelist[user_id]

    def block_ip(self, ip_address: str) -> None:
        """Block IP address.

        Args:
            ip_address: IP address to block
        """
        self._blocked_ips.add(ip_address)
        logger.warning(f"IP blocked: {ip_address}")

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked.

        Args:
            ip_address: IP address

        Returns:
            True if IP is blocked
        """
        return ip_address in self._blocked_ips

    def add_conditional_policy(self, policy: ConditionalAccessPolicy) -> None:
        """Add conditional access policy.

        Args:
            policy: Conditional access policy
        """
        self._conditional_policies[policy.policy_id] = policy
        logger.info(f"Added conditional access policy: {policy.name}")

    def evaluate_conditional_access(
        self,
        user_id: str,
        ip_address: str | None = None,
        device_id: str | None = None,
        location: str | None = None,
    ) -> tuple[bool, str]:
        """Evaluate conditional access policies.

        Args:
            user_id: User ID
            ip_address: Client IP address
            device_id: Device ID
            location: Geographic location

        Returns:
            Tuple of (allowed, reason)
        """
        for policy in self._conditional_policies.values():
            if not policy.enabled:
                continue

            # Check IP whitelist
            if "ip_whitelist" in policy.conditions:
                if ip_address and not self.is_ip_whitelisted(user_id, ip_address):
                    return False, f"IP not whitelisted: {ip_address}"

            # Check blocked IPs
            if ip_address and self.is_ip_blocked(ip_address):
                return False, f"IP blocked: {ip_address}"

            # Check device trust
            if "require_trusted_device" in policy.conditions and device_id:
                sessions = self._device_sessions.get(device_id, [])
                trusted = any(
                    self.get_session(sid) and self.get_session(sid).trusted_device
                    for sid in sessions
                )
                if not trusted:
                    return False, "Device not trusted"

        return True, "Access allowed"

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(UTC)
        expired = [
            sid for sid, session in self._sessions.items() if now > session.absolute_expires_at
        ]

        for sid in expired:
            self.revoke_session(sid)

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)

    def _store_session_redis(self, session: Session) -> None:
        """Store session in Redis."""
        if not self.redis_client:
            return

        key = f"session:{session.session_id}"
        ttl = int((session.absolute_expires_at - datetime.now(UTC)).total_seconds())
        self.redis_client.setex(key, ttl, session.model_dump_json())

    def _get_session_redis(self, session_id: str) -> Session | None:
        """Get session from Redis."""
        if not self.redis_client:
            return None

        key = f"session:{session_id}"
        data = self.redis_client.get(key)
        if data:
            return Session.model_validate_json(data)
        return None

    def _add_audit_log(
        self,
        session_id: str,
        event_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_id: str | None = None,
        location: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add audit log entry to session."""
        session = self.get_session(session_id)
        if not session:
            return

        log_entry = SessionAuditLog(
            event_type=event_type,
            ip_address=ip_address or session.ip_address,
            user_agent=user_agent or session.user_agent,
            device_id=device_id or session.device_id,
            location=location or session.location,
            details=details or {},
        )

        session.audit_logs.append(log_entry)

        # Keep only last 100 audit logs
        if len(session.audit_logs) > 100:
            session.audit_logs = session.audit_logs[-100:]

        # Update session
        if self.redis_client:
            try:
                self._store_session_redis(session)
            except Exception as e:
                logger.warning(f"Failed to update session audit log in Redis: {e}")
                self._sessions[session_id] = session
        else:
            self._sessions[session_id] = session
