"""Tests for code quality improvements.

This module contains tests for the new quality improvement modules:
- constants.py
- exceptions.py
- logger_factory.py
- config.py
- repair_loop.py (refactored)
"""

from __future__ import annotations

import pytest

from backend.app.core.config import (
    CacheSettings,
    DatabaseSettings,
    ExecutionSettings,
    LogSettings,
    SecuritySettings,
    Settings,
    get_settings,
)
from backend.app.core.constants import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CapabilityName,
    ErrorType,
    ExecutionState,
    TaskKeyword,
    ToolName,
)
from backend.app.core.exceptions import (
    ConfigurationError,
    PermissionDeniedError,
    TimeoutError,
    ValidationError,
    XAgentException,
)
from backend.app.core.logger_factory import LogContext, LoggerFactory, get_logger
from backend.app.core.repair_loop import (
    ErrorClassifier,
    RepairLoop,
    RepairSuggestion,
    SuggestionGenerator,
)


class TestConstants:
    """Tests for constants module."""

    def test_error_type_enum(self) -> None:
        """Test ErrorType enum."""
        assert ErrorType.VALIDATION_ERROR.value == "validation_error"
        assert ErrorType.MISSING_RESOURCE.value == "missing_resource"
        assert ErrorType.TIMEOUT.value == "timeout"

    def test_tool_name_enum(self) -> None:
        """Test ToolName enum."""
        assert ToolName.READ_FILE.value == "read_file"
        assert ToolName.WRITE_FILE.value == "write_file"
        assert ToolName.APPLY_PATCH.value == "apply_text_patch"

    def test_execution_state_enum(self) -> None:
        """Test ExecutionState enum."""
        assert ExecutionState.INITIALIZING.value == "initializing"
        assert ExecutionState.COMPLETED.value == "completed"

    def test_capability_name_enum(self) -> None:
        """Test CapabilityName enum."""
        assert CapabilityName.APPROVAL.value == "approval"
        assert CapabilityName.BROWSER.value == "browser"

    def test_task_keyword_enum(self) -> None:
        """Test TaskKeyword enum."""
        assert TaskKeyword.MODIFY.value == "modify"
        assert TaskKeyword.SEARCH.value == "search"

    def test_confidence_thresholds(self) -> None:
        """Test confidence threshold constants."""
        assert CONFIDENCE_HIGH == 0.9
        assert CONFIDENCE_MEDIUM == 0.7
        assert CONFIDENCE_LOW == 0.5


class TestExceptions:
    """Tests for exceptions module."""

    def test_xagent_exception_creation(self) -> None:
        """Test XAgentException creation."""
        exc = XAgentException("Test error")
        assert exc.message == "Test error"
        assert exc.error_code == "internal_error"

    def test_validation_error(self) -> None:
        """Test ValidationError."""
        exc = ValidationError("Invalid input")
        assert exc.message == "Invalid input"
        assert "validation_error" in exc.error_code

    def test_timeout_error(self) -> None:
        """Test TimeoutError."""
        exc = TimeoutError("Operation timed out")
        assert exc.message == "Operation timed out"
        assert exc.is_retryable is True

    def test_permission_denied_error(self) -> None:
        """Test PermissionDeniedError."""
        exc = PermissionDeniedError("Access denied")
        assert exc.message == "Access denied"

    def test_configuration_error(self) -> None:
        """Test ConfigurationError."""
        exc = ConfigurationError("Missing config")
        assert exc.message == "Missing config"

    def test_error_context_conversion(self) -> None:
        """Test error to context conversion."""
        exc = ValidationError("Test error", details={"field": "name"})
        context = exc.to_context(user_id="123", trace_id="abc")
        assert context.user_id == "123"
        assert context.trace_id == "abc"
        assert context.details == {"field": "name"}


class TestLoggerFactory:
    """Tests for logger factory."""

    def test_get_logger(self) -> None:
        """Test getting a logger."""
        logger = get_logger("test_logger")
        assert logger is not None
        assert logger.name == "test_logger"

    def test_logger_factory_configure(self) -> None:
        """Test logger factory configuration."""
        import logging

        LoggerFactory.configure(level=logging.DEBUG, format_type="plain")
        logger = LoggerFactory.get_logger("test")
        assert logger.level == logging.DEBUG

    def test_log_context(self) -> None:
        """Test log context."""
        with LogContext(user_id="123", request_id="abc"):
            context = LogContext.get_current_context()
            assert context["user_id"] == "123"
            assert context["request_id"] == "abc"

    def test_log_context_nesting(self) -> None:
        """Test nested log contexts."""
        with LogContext(user_id="123"):
            context1 = LogContext.get_current_context()
            assert context1["user_id"] == "123"

            with LogContext(request_id="abc"):
                context2 = LogContext.get_current_context()
                assert context2["user_id"] == "123"
                assert context2["request_id"] == "abc"

            context3 = LogContext.get_current_context()
            assert context3["user_id"] == "123"
            assert "request_id" not in context3


class TestConfig:
    """Tests for configuration module."""

    def test_log_settings(self) -> None:
        """Test LogSettings."""
        settings = LogSettings(level="DEBUG", format="json")
        assert settings.level == "DEBUG"
        assert settings.format == "json"

    def test_database_settings(self) -> None:
        """Test DatabaseSettings."""
        settings = DatabaseSettings(pool_size=20)
        assert settings.pool_size == 20

    def test_database_settings_validation(self) -> None:
        """Test DatabaseSettings validation."""
        with pytest.raises(ValueError):
            DatabaseSettings(pool_size=0)

    def test_cache_settings(self) -> None:
        """Test CacheSettings."""
        settings = CacheSettings(enabled=True, backend="redis")
        assert settings.enabled is True
        assert settings.backend == "redis"

    def test_execution_settings(self) -> None:
        """Test ExecutionSettings."""
        settings = ExecutionSettings(max_iterations=10, timeout=600)
        assert settings.max_iterations == 10
        assert settings.timeout == 600

    def test_execution_settings_validation(self) -> None:
        """Test ExecutionSettings validation."""
        with pytest.raises(ValueError):
            ExecutionSettings(max_iterations=0)

    def test_security_settings(self) -> None:
        """Test SecuritySettings."""
        settings = SecuritySettings(api_key="test_key")
        assert settings.api_key == "test_key"

    def test_main_settings(self) -> None:
        """Test main Settings."""
        settings = Settings(app_name="TestApp", debug=True)
        assert settings.app_name == "TestApp"
        assert settings.debug is True

    def test_settings_environment_validation(self) -> None:
        """Test Settings environment validation."""
        with pytest.raises(ValueError):
            Settings(environment="invalid")

    def test_settings_is_production(self) -> None:
        """Test is_production method."""
        settings = Settings(environment="production")
        assert settings.is_production() is True

    def test_settings_is_development(self) -> None:
        """Test is_development method."""
        settings = Settings(environment="development")
        assert settings.is_development() is True

    def test_get_settings(self) -> None:
        """Test get_settings function."""
        settings = get_settings()
        assert settings is not None
        assert isinstance(settings, Settings)


class TestRepairLoop:
    """Tests for refactored repair loop."""

    def test_error_classifier_classify(self) -> None:
        """Test ErrorClassifier.classify."""
        error_type = ErrorClassifier.classify("validation_error")
        assert error_type == ErrorType.VALIDATION_ERROR

    def test_error_classifier_unknown(self) -> None:
        """Test ErrorClassifier with unknown error."""
        error_type = ErrorClassifier.classify("unknown_error")
        assert error_type == ErrorType.UNKNOWN

    def test_error_classifier_get_strategy(self) -> None:
        """Test ErrorClassifier.get_recovery_strategy."""
        strategy = ErrorClassifier.get_recovery_strategy("validation_error")
        assert strategy["should_retry"] is True
        assert strategy["confidence"] == 0.92

    def test_repair_suggestion_creation(self) -> None:
        """Test RepairSuggestion creation."""
        suggestion = RepairSuggestion(
            should_retry=True,
            tool_name="read_file",
            reason="Test reason",
            confidence=0.9,
        )
        assert suggestion.should_retry is True
        assert suggestion.tool_name == "read_file"
        assert suggestion.confidence == 0.9

    def test_suggestion_generator_validation_error(self) -> None:
        """Test SuggestionGenerator for validation error."""
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict
        from backend.app.core.verification import VerificationResult

        tool_call = ToolCallRecord(
            tool_name="read_file",
            arguments_preview={"path": "/test/file.py"},
            success=False,
            policy=ToolPolicyVerdict(allowed=True, reason="test"),
        )
        result = VerificationResult(
            passed=False,
            summary="validation failed",
            error_type="validation_error",
        )

        suggestion = SuggestionGenerator.generate(tool_call, result)
        assert suggestion.should_retry is True
        assert suggestion.error_type == "validation_error"

    def test_repair_loop_dump_model(self) -> None:
        """Test RepairLoop._dump_model."""
        from dataclasses import dataclass

        @dataclass
        class TestModel:
            value: str

        model = TestModel(value="test")
        dumped = RepairLoop._dump_model(model)
        assert dumped["value"] == "test"

    def test_repair_loop_dump_model_dict(self) -> None:
        """Test RepairLoop._dump_model with dict."""
        data = {"key": "value"}
        dumped = RepairLoop._dump_model(data)
        assert dumped == data


class TestIntegration:
    """Integration tests for quality improvements."""

    def test_constants_and_exceptions_integration(self) -> None:
        """Test integration of constants and exceptions."""
        error_type = ErrorType.VALIDATION_ERROR
        exc = ValidationError(f"Error: {error_type.value}")
        assert error_type.value in exc.message

    def test_config_and_logger_integration(self) -> None:
        """Test integration of config and logger."""
        settings = Settings(log=LogSettings(level="DEBUG"))
        logger = get_logger("integration_test")
        assert logger is not None

    def test_repair_loop_with_constants(self) -> None:
        """Test repair loop uses constants correctly."""
        strategy = ErrorClassifier.get_recovery_strategy(
            ErrorType.TIMEOUT.value
        )
        assert strategy["should_retry"] is True
        assert strategy["confidence"] == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
