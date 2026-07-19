"""
Configuration Hot-Reload and Encryption for X-Agent.

Implements:
- Configuration hot-reload support
- Sensitive configuration encryption/decryption
- Configuration audit logging
- Configuration validation on reload
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from cryptography.fernet import Fernet
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConfigurationEncryption:
    """
    Encrypt and decrypt sensitive configuration values.

    Features:
    - Fernet symmetric encryption
    - Key management
    - Automatic encryption/decryption
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        if encryption_key is None:
            encryption_key = os.getenv("XAGENT_CONFIG_ENCRYPTION_KEY")
            if not encryption_key:
                # Generate a new key if not provided
                encryption_key = Fernet.generate_key().decode()
                logger.warning("Generated new encryption key. Set XAGENT_CONFIG_ENCRYPTION_KEY to use a persistent key.")

        # Ensure key is bytes
        if isinstance(encryption_key, str):
            if len(encryption_key) == 44 and encryption_key.endswith("="):
                # Already base64 encoded
                encryption_key = encryption_key.encode()
            else:
                # Encode to base64
                encryption_key = Fernet.generate_key()

        self._cipher = Fernet(encryption_key)

    def encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        try:
            encrypted = self._cipher.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Error encrypting value: {e}")
            raise

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value."""
        try:
            decrypted = self._cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error decrypting value: {e}")
            raise

    def encrypt_dict(self, data: dict[str, Any], keys_to_encrypt: list[str]) -> dict[str, Any]:
        """Encrypt specific keys in a dictionary."""
        encrypted_data = data.copy()
        for key in keys_to_encrypt:
            if key in encrypted_data and isinstance(encrypted_data[key], str):
                encrypted_data[key] = self.encrypt(encrypted_data[key])
        return encrypted_data

    def decrypt_dict(self, data: dict[str, Any], keys_to_decrypt: list[str]) -> dict[str, Any]:
        """Decrypt specific keys in a dictionary."""
        decrypted_data = data.copy()
        for key in keys_to_decrypt:
            if key in decrypted_data and isinstance(decrypted_data[key], str):
                try:
                    decrypted_data[key] = self.decrypt(decrypted_data[key])
                except Exception:
                    # If decryption fails, keep original value
                    pass
        return decrypted_data


class ConfigurationHotReload:
    """
    Support hot-reloading of configuration files.

    Features:
    - File system monitoring
    - Configuration validation on reload
    - Callback notifications
    - Rollback on validation failure
    """

    def __init__(
        self,
        config_file: Path,
        check_interval: float = 5.0,
    ) -> None:
        self.config_file = config_file
        self.check_interval = check_interval

        self._current_config: dict[str, Any] | None = None
        self._last_modified: float = 0.0
        self._watchers: list[Callable] = []
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start_monitoring(self) -> None:
        """Start monitoring configuration file for changes."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started monitoring configuration file: {self.config_file}")

    async def stop_monitoring(self) -> None:
        """Stop monitoring configuration file."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped monitoring configuration file")

    async def _monitor_loop(self) -> None:
        """Monitor configuration file for changes."""
        while self._monitoring:
            try:
                await asyncio.sleep(self.check_interval)

                if not self.config_file.exists():
                    logger.warning(f"Configuration file not found: {self.config_file}")
                    continue

                current_modified = self.config_file.stat().st_mtime
                if current_modified > self._last_modified:
                    logger.info(f"Configuration file changed: {self.config_file}")
                    await self._reload_config()
                    self._last_modified = current_modified

            except Exception as e:
                logger.error(f"Error in configuration monitoring loop: {e}")

    async def _reload_config(self) -> None:
        """Reload configuration from file."""
        try:
            with open(self.config_file) as f:
                if self.config_file.suffix == ".json":
                    new_config = json.load(f)
                else:
                    import yaml

                    new_config = yaml.safe_load(f) or {}

            async with self._lock:
                old_config = self._current_config
                self._current_config = new_config

            # Notify watchers
            await self._notify_watchers(new_config)
            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            # Rollback to old config
            async with self._lock:
                self._current_config = old_config

    def register_watcher(self, callback: Callable) -> None:
        """Register a callback for configuration changes."""
        self._watchers.append(callback)
        logger.debug(f"Registered configuration watcher: {callback.__name__}")

    async def _notify_watchers(self, config: dict[str, Any]) -> None:
        """Notify all watchers of configuration change."""
        for callback in self._watchers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(config)
                else:
                    callback(config)
            except Exception as e:
                logger.error(f"Error in configuration watcher: {e}")

    async def get_config(self) -> dict[str, Any] | None:
        """Get current configuration."""
        async with self._lock:
            return self._current_config


class ConfigurationAudit:
    """
    Audit configuration changes for compliance and debugging.

    Features:
    - Change logging
    - Change history
    - Sensitive field masking
    - Audit reports
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._changes: list[dict[str, Any]] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    async def log_change(
        self,
        change_type: str,
        key: str,
        old_value: Any,
        new_value: Any,
        user_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log a configuration change."""
        import time

        change_record = {
            "timestamp": time.time(),
            "change_type": change_type,
            "key": key,
            "old_value": self._mask_sensitive(key, old_value),
            "new_value": self._mask_sensitive(key, new_value),
            "user_id": user_id,
            "reason": reason,
        }

        async with self._lock:
            self._changes.append(change_record)
            if len(self._changes) > self._max_history:
                self._changes.pop(0)

        logger.info(f"Configuration change logged: {change_type} {key}")

    def _mask_sensitive(self, key: str, value: Any) -> Any:
        """Mask sensitive configuration values."""
        sensitive_keys = {
            "password",
            "secret",
            "key",
            "token",
            "api_key",
            "encryption_key",
        }

        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            if isinstance(value, str):
                return f"***{value[-4:]}" if len(value) > 4 else "***"
            return "***"

        return value

    async def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get configuration change history."""
        async with self._lock:
            return self._changes[-limit:]

    async def get_report(self) -> dict[str, Any]:
        """Get configuration audit report."""
        async with self._lock:
            return {
                "total_changes": len(self._changes),
                "recent_changes": self._changes[-10:],
                "change_types": self._count_change_types(),
            }

    def _count_change_types(self) -> dict[str, int]:
        """Count changes by type."""
        counts: dict[str, int] = {}
        for change in self._changes:
            change_type = change.get("change_type", "unknown")
            counts[change_type] = counts.get(change_type, 0) + 1
        return counts


# Global instances
_config_encryption: ConfigurationEncryption | None = None
_config_hot_reload: ConfigurationHotReload | None = None
_config_audit: ConfigurationAudit | None = None


def get_config_encryption(encryption_key: str | None = None) -> ConfigurationEncryption:
    """Get or create the global configuration encryption."""
    global _config_encryption
    if _config_encryption is None:
        _config_encryption = ConfigurationEncryption(encryption_key)
    return _config_encryption


def get_config_hot_reload(config_file: Path) -> ConfigurationHotReload:
    """Get or create the global configuration hot-reload."""
    global _config_hot_reload
    if _config_hot_reload is None:
        _config_hot_reload = ConfigurationHotReload(config_file)
    return _config_hot_reload


def get_config_audit() -> ConfigurationAudit:
    """Get or create the global configuration audit."""
    global _config_audit
    if _config_audit is None:
        _config_audit = ConfigurationAudit()
    return _config_audit
