"""
Architecture Optimization Tests for X-Agent.

Tests for:
- Event bus integration
- Configuration management
- Error handling
"""

import asyncio
import pytest

from backend.app.core.event_bus import Event, EventType, get_event_bus
from backend.app.core.event_bus_integration import (
    EventBusIntegration,
    get_event_bus_integration,
)
from backend.app.core.config_hot_reload import (
    ConfigurationEncryption,
    ConfigurationHotReload,
    ConfigurationAudit,
)
from backend.app.core.error_handling import (
    CircuitBreaker,
    ExponentialBackoffRetry,
    ErrorTracker,
)


class TestEventBusIntegration:
    """Test event bus integration."""

    @pytest.mark.asyncio
    async def test_agent_started_event(self):
        """Test publishing agent started event."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.AGENT_STARTED, handler)
        await integration.publish_agent_started(
            agent_id="test_agent",
            task="test_task",
            user_id="user1",
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["agent_id"] == "test_agent"

    @pytest.mark.asyncio
    async def test_workflow_completed_event(self):
        """Test publishing workflow completed event."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.WORKFLOW_COMPLETED, handler)
        await integration.publish_workflow_completed(
            workflow_id="wf1",
            result={"status": "success"},
            duration_seconds=10.5,
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["workflow_id"] == "wf1"

    @pytest.mark.asyncio
    async def test_security_event(self):
        """Test publishing security events."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.AUTHENTICATION_FAILED, handler)
        await integration.publish_authentication_failed(
            reason="Invalid credentials",
            user_id="user1",
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["reason"] == "Invalid credentials"


class TestConfigurationManagement:
    """Test configuration management."""

    def test_config_encryption(self):
        """Test configuration encryption."""
        encryption = ConfigurationEncryption()

        original = "secret_password_123"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_config_encrypt_dict(self):
        """Test encrypting dictionary values."""
        encryption = ConfigurationEncryption()

        data = {
            "username": "admin",
            "password": "secret123",
            "api_key": "key_abc123",
        }

        encrypted = encryption.encrypt_dict(data, ["password", "api_key"])

        assert encrypted["username"] == "admin"
        assert encrypted["password"] != "secret123"
        assert encrypted["api_key"] != "key_abc123"

    @pytest.mark.asyncio
    async def test_config_audit(self):
        """Test configuration audit logging."""
        audit = ConfigurationAudit()

        await audit.log_change(
            change_type="update",
            key="database.password",
            old_value="old_pass",
            new_value="new_pass",
            user_id="admin",
            reason="Security update",
        )

        history = await audit.get_history()
        assert len(history) == 1
        assert history[0]["key"] == "database.password"
        assert "***" in str(history[0]["new_value"])


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self):
        """Test exponential backoff retry strategy."""
        retry_strategy = ExponentialBackoffRetry(
            max_attempts=3,
            initial_delay=0.1,
            exponential_base=2.0,
        )

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = await retry_strategy.execute(failing_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)

        async def failing_func():
            raise ValueError("Service error")

        # Trigger failures
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        # Circuit should be open
        state = breaker.get_state()
        assert state["state"] == "open"

    @pytest.mark.asyncio
    async def test_error_tracker(self):
        """Test error tracking."""
        tracker = ErrorTracker()

        from backend.app.core.error_handling import (
            AuthenticationError,
            ValidationError,
        )

        await tracker.record(AuthenticationError("Invalid token"))
        await tracker.record(ValidationError("Invalid input"))

        stats = tracker.get_stats()
        assert stats["total_errors"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
