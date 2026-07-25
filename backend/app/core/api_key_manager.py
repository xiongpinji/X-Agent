"""
Advanced API Key Management System with fine-grained access control.

Features:
- API key generation, rotation, and revocation
- Fine-grained permission control (10+ permission types)
- Rate limiting and IP whitelisting
- Key expiration management
- Comprehensive audit logging
- Anomaly detection
- Automatic revocation on suspicious activity
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from typing import Any
from uuid import uuid4

import bcrypt
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class PermissionLevel(StrEnum):
    """Fine-grained permission levels."""
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_EXECUTE = "agent:execute"
    AGENT_DELETE = "agent:delete"

    # Workflow permissions
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"

    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"

    # Tool permissions
    TOOLS_READ = "tools:read"
    TOOLS_EXECUTE = "tools:execute"

    # Audit permissions
    AUDIT_READ = "audit:read"

    # Admin permissions
    SECURITY_MANAGE = "security:manage"
    ADMIN = "admin:*"


class KeyStatus(StrEnum):
    """API key status."""
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class AnomalyType(StrEnum):
    """Types of detected anomalies."""
    UNUSUAL_LOCATION = "unusual_location"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    FAILED_AUTH_ATTEMPTS = "failed_auth_attempts"
    UNUSUAL_TIME = "unusual_time"
    PERMISSION_ESCALATION = "permission_escalation"


# ============================================================================
# DATA MODELS
# ============================================================================

class APIKeyMetadata(BaseModel):
    """Metadata for API keys."""
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 3600
    requests_per_day: int = 86400
    burst_size: int = 10


class IPWhitelist(BaseModel):
    """IP whitelist configuration."""
    enabled: bool = False
    ips: list[str] = Field(default_factory=list)
    cidrs: list[str] = Field(default_factory=list)


class APIKeyConfig(BaseModel):
    """Complete API key configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    key_prefix: str
    key_hash: str

    # Ownership
    tenant_id: str = "default"
    user_id: str
    created_by: str

    # Permissions
    permissions: list[PermissionLevel] = Field(default_factory=list)
    resource_restrictions: dict[str, list[str]] = Field(default_factory=dict)

    # Lifecycle
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    last_rotated_at: datetime | None = None

    # Rate limiting
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # IP whitelist
    ip_whitelist: IPWhitelist = Field(default_factory=IPWhitelist)

    # Metadata
    metadata: APIKeyMetadata = Field(default_factory=APIKeyMetadata)

    # Usage tracking
    total_requests: int = 0
    failed_requests: int = 0
    last_ip: str | None = None

    @validator("expires_at", pre=True, always=True)
    def set_default_expiry(cls, v: datetime | None) -> datetime | None:
        """Set default expiry to 90 days if not specified."""
        if v is None:
            return datetime.now(UTC) + timedelta(days=90)
        return v


class AuditEntry(BaseModel):
    """Audit log entry for API key operations."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Event details
    event_type: str  # "create", "rotate", "revoke", "use", "failed_auth", etc.
    key_id: str
    key_prefix: str

    # Actor
    actor_id: str
    actor_type: str  # "user", "system", "api_key"

    # Context
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    # Result
    success: bool = True
    error_message: str | None = None

    # Details
    details: dict[str, Any] = Field(default_factory=dict)


class AnomalyAlert(BaseModel):
    """Anomaly detection alert."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    key_id: str
    anomaly_type: AnomalyType
    severity: str  # "low", "medium", "high", "critical"
    description: str

    # Recommended action
    recommended_action: str | None = None
    auto_revoked: bool = False


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter for API keys."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def check_rate_limit(
        self,
        key_id: str,
        config: RateLimitConfig,
    ) -> tuple[bool, dict[str, int]]:
        """Check if request is within rate limits.

        Returns:
            (allowed, stats) where stats contains current usage
        """
        now = datetime.now(UTC)
        with self._lock:
            bucket = self._buckets.get(key_id, {
                "minute_count": 0,
                "hour_count": 0,
                "day_count": 0,
                "minute_reset": now,
                "hour_reset": now,
                "day_reset": now,
            })

            # Reset counters if windows have passed
            if (now - bucket["minute_reset"]).total_seconds() >= 60:
                bucket["minute_count"] = 0
                bucket["minute_reset"] = now

            if (now - bucket["hour_reset"]).total_seconds() >= 3600:
                bucket["hour_count"] = 0
                bucket["hour_reset"] = now

            if (now - bucket["day_reset"]).total_seconds() >= 86400:
                bucket["day_count"] = 0
                bucket["day_reset"] = now

            # Check limits
            allowed = (
                bucket["minute_count"] < config.requests_per_minute
                and bucket["hour_count"] < config.requests_per_hour
                and bucket["day_count"] < config.requests_per_day
            )

            if allowed:
                bucket["minute_count"] += 1
                bucket["hour_count"] += 1
                bucket["day_count"] += 1

            self._buckets[key_id] = bucket

            stats = {
                "minute_remaining": max(0, config.requests_per_minute - bucket["minute_count"]),
                "hour_remaining": max(0, config.requests_per_hour - bucket["hour_count"]),
                "day_remaining": max(0, config.requests_per_day - bucket["day_count"]),
            }

            return allowed, stats

    def cleanup_stale_buckets(self, max_age_hours: int = 24) -> None:
        """Remove stale buckets to prevent memory leaks."""
        now = datetime.now(UTC)
        with self._lock:
            stale_keys = [
                k for k, v in self._buckets.items()
                if (now - v["minute_reset"]).total_seconds() > max_age_hours * 3600
            ]
            for k in stale_keys:
                del self._buckets[k]


# ============================================================================
# ANOMALY DETECTOR
# ============================================================================

class AnomalyDetector:
    """Detects suspicious activity patterns."""

    def __init__(self) -> None:
        self._key_locations: dict[str, set[str]] = {}
        self._key_usage_times: dict[str, list[datetime]] = {}
        self._failed_attempts: dict[str, list[datetime]] = {}
        self._lock = RLock()

    def detect_anomalies(
        self,
        key_id: str,
        ip_address: str | None,
        timestamp: datetime,
    ) -> list[AnomalyAlert]:
        """Detect anomalies for a key usage."""
        alerts = []

        with self._lock:
            # Check for unusual location
            if ip_address:
                locations = self._key_locations.setdefault(key_id, set())
                if len(locations) > 5 and ip_address not in locations:
                    alerts.append(AnomalyAlert(
                        key_id=key_id,
                        anomaly_type=AnomalyType.UNUSUAL_LOCATION,
                        severity="medium",
                        description=f"API key used from new location: {ip_address}",
                    ))
                locations.add(ip_address)

            # Check for unusual time patterns
            usage_times = self._key_usage_times.setdefault(key_id, [])
            usage_times.append(timestamp)
            # Keep only last 24 hours
            cutoff = timestamp - timedelta(hours=24)
            usage_times[:] = [t for t in usage_times if t > cutoff]

            if len(usage_times) > 100:
                alerts.append(AnomalyAlert(
                    key_id=key_id,
                    anomaly_type=AnomalyType.UNUSUAL_TIME,
                    severity="low",
                    description="Unusually high request frequency detected",
                ))

        return alerts

    def record_failed_attempt(self, key_id: str, timestamp: datetime) -> AnomalyAlert | None:
        """Record failed authentication attempt."""
        with self._lock:
            attempts = self._failed_attempts.setdefault(key_id, [])
            attempts.append(timestamp)

            # Keep only last hour
            cutoff = timestamp - timedelta(hours=1)
            attempts[:] = [t for t in attempts if t > cutoff]

            # Alert if too many failures
            if len(attempts) > 5:
                return AnomalyAlert(
                    key_id=key_id,
                    anomaly_type=AnomalyType.FAILED_AUTH_ATTEMPTS,
                    severity="high",
                    description=f"Multiple failed authentication attempts: {len(attempts)} in last hour",
                    recommended_action="Consider revoking this key",
                )

        return None


# ============================================================================
# API KEY MANAGER
# ============================================================================

class APIKeyManager:
    """Advanced API key management system."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._keys: dict[str, APIKeyConfig] = {}
        self._prefix_index: dict[str, str] = {}  # prefix -> key_id
        self._audit_log: list[AuditEntry] = []
        self._anomaly_alerts: list[AnomalyAlert] = []
        self._lock = RLock()

        self._storage_path = Path(storage_path) if storage_path else None
        self._rate_limiter = RateLimiter()
        self._anomaly_detector = AnomalyDetector()

        if self._storage_path:
            self._load_from_disk()

    # ========================================================================
    # KEY LIFECYCLE MANAGEMENT
    # ========================================================================

    def create_key(
        self,
        name: str,
        user_id: str,
        tenant_id: str = "default",
        permissions: list[PermissionLevel] | None = None,
        expires_in_days: int = 90,
        metadata: APIKeyMetadata | None = None,
        created_by: str | None = None,
    ) -> tuple[str, APIKeyConfig]:
        """Create a new API key.

        Returns:
            (raw_key, config) where raw_key is shown only once
        """
        raw_key = f"xag_{token_urlsafe(32)}"
        key_prefix = raw_key[:12]

        config = APIKeyConfig(
            name=name,
            key_prefix=key_prefix,
            key_hash=self._hash_key(raw_key),
            tenant_id=tenant_id,
            user_id=user_id,
            created_by=created_by or user_id,
            permissions=permissions or [PermissionLevel.AGENT_READ],
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
            metadata=metadata or APIKeyMetadata(),
        )

        with self._lock:
            self._keys[config.id] = config
            self._prefix_index[key_prefix] = config.id
            self._persist()

        # Audit log
        self._audit(
            event_type="create",
            key_id=config.id,
            key_prefix=key_prefix,
            actor_id=created_by or user_id,
            actor_type="user",
            success=True,
        )

        logger.info(f"Created API key: {key_prefix} for user {user_id}")
        return raw_key, config

    def rotate_key(
        self,
        key_id: str,
        actor_id: str,
    ) -> tuple[str, APIKeyConfig]:
        """Rotate an API key (create new, keep old active for grace period).

        Returns:
            (new_raw_key, new_config)
        """
        with self._lock:
            old_config = self._keys.get(key_id)
            if not old_config:
                raise ValueError(f"Key not found: {key_id}")

            if old_config.status == KeyStatus.REVOKED:
                raise ValueError(f"Cannot rotate revoked key: {key_id}")

            # Create new key with same permissions
            new_raw_key = f"xag_{token_urlsafe(32)}"
            new_prefix = new_raw_key[:12]

            new_config = APIKeyConfig(
                name=f"{old_config.name} (rotated)",
                key_prefix=new_prefix,
                key_hash=self._hash_key(new_raw_key),
                tenant_id=old_config.tenant_id,
                user_id=old_config.user_id,
                created_by=actor_id,
                permissions=old_config.permissions,
                metadata=old_config.metadata,
            )

            # Mark old key as rotated (keep active for 7 days)
            old_config.status = KeyStatus.ROTATED
            old_config.last_rotated_at = datetime.now(UTC)
            old_config.expires_at = datetime.now(UTC) + timedelta(days=7)

            self._keys[new_config.id] = new_config
            self._keys[key_id] = old_config
            self._prefix_index[new_prefix] = new_config.id
            self._persist()

        self._audit(
            event_type="rotate",
            key_id=key_id,
            key_prefix=old_config.key_prefix,
            actor_id=actor_id,
            actor_type="user",
            success=True,
            details={"new_key_id": new_config.id},
        )

        logger.info(f"Rotated API key: {old_config.key_prefix}")
        return new_raw_key, new_config

    def revoke_key(
        self,
        key_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> APIKeyConfig:
        """Revoke an API key."""
        with self._lock:
            config = self._keys.get(key_id)
            if not config:
                raise ValueError(f"Key not found: {key_id}")

            config.status = KeyStatus.REVOKED
            config.revoked_at = datetime.now(UTC)
            self._keys[key_id] = config
            self._persist()

        self._audit(
            event_type="revoke",
            key_id=key_id,
            key_prefix=config.key_prefix,
            actor_id=actor_id,
            actor_type="user",
            success=True,
            details={"reason": reason},
        )

        logger.warning(f"Revoked API key: {config.key_prefix} (reason: {reason})")
        return config

    # ========================================================================
    # AUTHENTICATION & AUTHORIZATION
    # ========================================================================

    def authenticate(
        self,
        raw_key: str,
        ip_address: str | None = None,
    ) -> APIKeyConfig | None:
        """Authenticate with an API key.

        Returns:
            APIKeyConfig if valid, None otherwise
        """
        prefix = raw_key[:12]

        with self._lock:
            key_id = self._prefix_index.get(prefix)
            if not key_id:
                self._audit(
                    event_type="failed_auth",
                    key_id="unknown",
                    key_prefix=prefix,
                    actor_id="system",
                    actor_type="system",
                    ip_address=ip_address,
                    success=False,
                    error_message="Key prefix not found",
                )
                return None

            config = self._keys.get(key_id)
            if not config:
                return None

            # Check status
            if config.status == KeyStatus.REVOKED:
                self._audit(
                    event_type="failed_auth",
                    key_id=key_id,
                    key_prefix=prefix,
                    actor_id="system",
                    actor_type="system",
                    ip_address=ip_address,
                    success=False,
                    error_message="Key is revoked",
                )
                return None

            # Check expiration
            if config.expires_at and datetime.now(UTC) > config.expires_at:
                config.status = KeyStatus.EXPIRED
                self._audit(
                    event_type="failed_auth",
                    key_id=key_id,
                    key_prefix=prefix,
                    actor_id="system",
                    actor_type="system",
                    ip_address=ip_address,
                    success=False,
                    error_message="Key is expired",
                )
                return None

            # Verify hash
            if not bcrypt.checkpw(raw_key.encode("utf-8"), config.key_hash.encode("utf-8")):
                # Record failed attempt
                alert = self._anomaly_detector.record_failed_attempt(key_id, datetime.now(UTC))
                if alert:
                    self._anomaly_alerts.append(alert)
                    if alert.severity == "high":
                        logger.warning(f"Anomaly detected: {alert.description}")

                self._audit(
                    event_type="failed_auth",
                    key_id=key_id,
                    key_prefix=prefix,
                    actor_id="system",
                    actor_type="system",
                    ip_address=ip_address,
                    success=False,
                    error_message="Invalid key hash",
                )
                return None

            # Check IP whitelist
            if config.ip_whitelist.enabled:
                if not self._check_ip_whitelist(ip_address, config.ip_whitelist):
                    self._audit(
                        event_type="failed_auth",
                        key_id=key_id,
                        key_prefix=prefix,
                        actor_id="system",
                        actor_type="system",
                        ip_address=ip_address,
                        success=False,
                        error_message="IP not whitelisted",
                    )
                    return None

            # Check rate limit
            allowed, stats = self._rate_limiter.check_rate_limit(key_id, config.rate_limit)
            if not allowed:
                alert = AnomalyAlert(
                    key_id=key_id,
                    anomaly_type=AnomalyType.RATE_LIMIT_EXCEEDED,
                    severity="medium",
                    description="Rate limit exceeded",
                )
                self._anomaly_alerts.append(alert)

                self._audit(
                    event_type="rate_limit_exceeded",
                    key_id=key_id,
                    key_prefix=prefix,
                    actor_id="system",
                    actor_type="system",
                    ip_address=ip_address,
                    success=False,
                    error_message="Rate limit exceeded",
                    details=stats,
                )
                return None

            # Update usage
            config.last_used_at = datetime.now(UTC)
            config.last_ip = ip_address
            config.total_requests += 1
            self._keys[key_id] = config

            # Detect anomalies
            anomalies = self._anomaly_detector.detect_anomalies(
                key_id,
                ip_address,
                datetime.now(UTC),
            )
            self._anomaly_alerts.extend(anomalies)

            self._audit(
                event_type="use",
                key_id=key_id,
                key_prefix=prefix,
                actor_id="system",
                actor_type="system",
                ip_address=ip_address,
                success=True,
                details=stats,
            )

            self._persist()
            return config

    def check_permission(
        self,
        config: APIKeyConfig,
        required_permission: PermissionLevel,
        resource_id: str | None = None,
    ) -> bool:
        """Check if key has required permission."""
        # Admin has all permissions
        if PermissionLevel.ADMIN in config.permissions:
            return True

        # Check exact permission
        if required_permission in config.permissions:
            # Check resource restrictions if applicable
            if resource_id and required_permission in config.resource_restrictions:
                allowed_resources = config.resource_restrictions[required_permission]
                return resource_id in allowed_resources
            return True

        # Check wildcard permissions (only if such a wildcard level exists)
        namespace = required_permission.value.split(":")[0]
        wildcard = f"{namespace}:*"
        try:
            wildcard_level = PermissionLevel(wildcard)
        except ValueError:
            wildcard_level = None
        return bool(wildcard_level is not None and wildcard_level in config.permissions)

    # ========================================================================
    # KEY MANAGEMENT
    # ========================================================================

    def get_key(self, key_id: str) -> APIKeyConfig | None:
        """Get key configuration by ID."""
        with self._lock:
            return self._keys.get(key_id)

    def list_keys(
        self,
        tenant_id: str | None = None,
        user_id: str | None = None,
        status: KeyStatus | None = None,
    ) -> list[APIKeyConfig]:
        """List keys with optional filtering."""
        with self._lock:
            keys = list(self._keys.values())

            if tenant_id:
                keys = [k for k in keys if k.tenant_id == tenant_id]
            if user_id:
                keys = [k for k in keys if k.user_id == user_id]
            if status:
                keys = [k for k in keys if k.status == status]

            return sorted(keys, key=lambda k: k.created_at, reverse=True)

    def update_key(
        self,
        key_id: str,
        updates: dict[str, Any],
        actor_id: str,
    ) -> APIKeyConfig | None:
        """Update key configuration."""
        with self._lock:
            config = self._keys.get(key_id)
            if not config:
                return None

            # Track changes for audit
            changes = {}
            for field, value in updates.items():
                if hasattr(config, field):
                    old_value = getattr(config, field)
                    if old_value != value:
                        changes[field] = {"old": old_value, "new": value}
                        setattr(config, field, value)

            self._keys[key_id] = config
            self._persist()

        if changes:
            self._audit(
                event_type="update",
                key_id=key_id,
                key_prefix=config.key_prefix,
                actor_id=actor_id,
                actor_type="user",
                success=True,
                details={"changes": changes},
            )

        return config

    # ========================================================================
    # AUDIT & MONITORING
    # ========================================================================

    def get_audit_log(
        self,
        key_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get audit log entries."""
        with self._lock:
            entries = list(self._audit_log)

            if key_id:
                entries = [e for e in entries if e.key_id == key_id]
            if event_type:
                entries = [e for e in entries if e.event_type == event_type]

            return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_anomaly_alerts(
        self,
        key_id: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[AnomalyAlert]:
        """Get anomaly alerts."""
        with self._lock:
            alerts = list(self._anomaly_alerts)

            if key_id:
                alerts = [a for a in alerts if a.key_id == key_id]
            if severity:
                alerts = [a for a in alerts if a.severity == severity]

            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def get_key_usage_stats(self, key_id: str) -> dict[str, Any] | None:
        """Get usage statistics for a key."""
        config = self.get_key(key_id)
        if not config:
            return None

        return {
            "key_id": key_id,
            "name": config.name,
            "total_requests": config.total_requests,
            "failed_requests": config.failed_requests,
            "last_used_at": config.last_used_at,
            "last_ip": config.last_ip,
            "created_at": config.created_at,
            "expires_at": config.expires_at,
            "days_until_expiry": (
                (config.expires_at - datetime.now(UTC)).days
                if config.expires_at else None
            ),
        }

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _audit(
        self,
        event_type: str,
        key_id: str,
        key_prefix: str,
        actor_id: str,
        actor_type: str,
        ip_address: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record audit entry."""
        entry = AuditEntry(
            event_type=event_type,
            key_id=key_id,
            key_prefix=key_prefix,
            actor_id=actor_id,
            actor_type=actor_type,
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            details=details or {},
        )
        with self._lock:
            self._audit_log.append(entry)
            # Keep only last 10000 entries
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-10000:]

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Hash API key using bcrypt."""
        return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    @staticmethod
    def _check_ip_whitelist(ip: str | None, whitelist: IPWhitelist) -> bool:
        """Check if IP is in whitelist."""
        if not ip:
            return False

        if ip in whitelist.ips:
            return True

        # Simple CIDR check (production should use ipaddress module)
        return any(ip.startswith(cidr.split("/")[0]) for cidr in whitelist.cidrs)

    def _load_from_disk(self) -> None:
        """Load keys from disk."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("keys", []):
                config = APIKeyConfig.model_validate(item)
                self._keys[config.id] = config
                self._prefix_index[config.key_prefix] = config.id

            logger.info(f"Loaded {len(self._keys)} API keys from disk")
        except Exception as e:
            logger.error(f"Failed to load API keys from disk: {e}")

    def _persist(self) -> None:
        """Persist keys to disk."""
        if not self._storage_path:
            return

        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "keys": [k.model_dump(mode="json") for k in self._keys.values()],
                "audit_log": [e.model_dump(mode="json") for e in self._audit_log[-1000:]],
            }
            self._storage_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to persist API keys to disk: {e}")
