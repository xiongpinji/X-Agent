"""Regression tests for the four fixes shipped together in this pass.

  1. ``LocalKMS.health_check`` no longer deletes a probe file — the startup
     blocker (a delete got intercepted and raised ``SystemExit``, a
     ``BaseException`` that cancels the whole app lifespan).
  2. ``get_sandbox_status`` reports Docker **CLI** vs Python **SDK** availability
     separately instead of conflating them.
  3. ``configure_root_logging`` actually wires the root logger, so
     ``XAGENT_LOG_FORMAT=json`` produces parseable JSON lines.
  4. ``OTelExporter.status`` names *why* export is off rather than a blanket
     "disabled".

Each test pins one behaviour that was previously broken or absent.
"""

from __future__ import annotations

import json
import logging

import pytest


class TestKmsHealthCheckHasNoDeleteSideEffect:
    """``health_check`` runs on app startup, so it must be side-effect free."""

    def test_probe_file_is_retained(self, tmp_path):
        from backend.app.core.kms.local import LocalKMS

        kms = LocalKMS(key_dir=str(tmp_path / "keys"))
        assert kms.health_check() is True
        # The old implementation unlinked the probe; it must now persist.
        assert (tmp_path / "keys" / ".health_check").exists()

    def test_never_calls_unlink(self, tmp_path, monkeypatch):
        """Stronger than file-persistence: make any delete explode."""
        from backend.app.core.kms.local import LocalKMS

        def _boom(self, *args, **kwargs):
            raise AssertionError("health_check must not delete files")

        monkeypatch.setattr("pathlib.Path.unlink", _boom)
        kms = LocalKMS(key_dir=str(tmp_path / "keys"))
        assert kms.health_check() is True

    def test_is_idempotent(self, tmp_path):
        from backend.app.core.kms.local import LocalKMS

        kms = LocalKMS(key_dir=str(tmp_path / "keys"))
        for _ in range(3):
            assert kms.health_check() is True
        assert (tmp_path / "keys" / ".health_check").exists()


class TestSandboxStatusSeparatesCliFromSdk:
    """The sandbox backend is CLI-based; the container pool is SDK-based.

    NOTE: this handler lives on ``extended_router``, which is currently
    **unmounted** (a deliberate C2 consolidation), so the tests call it directly
    rather than over HTTP.
    """

    @staticmethod
    def _prepare(monkeypatch, *, history=None, cli=True, sdk=False):
        """Authz + manager are stubbed: this test targets status composition only.

        Stubbing the manager also keeps the test off the real sandbox pools, which
        ``get_sandbox_manager`` lazily initializes.
        """
        import backend.app.api.agents as agents
        from backend.app.core.sandbox import docker_sandbox
        from backend.app.core.sandbox import manager as manager_mod

        monkeypatch.setattr(agents, "enforce_scope", lambda principal, scope: None)
        monkeypatch.setattr(docker_sandbox, "is_docker_available", lambda: cli)
        monkeypatch.setattr(docker_sandbox, "is_docker_sdk_available", lambda: sdk)

        class _FakeManager:
            _execution_history = list(history or [])

        async def _fake_get_manager(*args, **kwargs):
            return _FakeManager()

        monkeypatch.setattr(manager_mod, "get_sandbox_manager", _fake_get_manager)
        return agents

    async def test_cli_present_sdk_absent(self, monkeypatch):
        agents = self._prepare(monkeypatch, cli=True, sdk=False)
        monkeypatch.setenv("XAGENT_SANDBOX_POOL_SIZE", "2")

        result = await agents.get_sandbox_status(principal=None)

        assert result["docker_available"] is True
        assert result["pool_sdk_available"] is False
        assert result["effective_backend"] == "docker"
        # The old bug reported the pool as merely "not initialized".
        assert result["pool"].get("error") != "pool not initialized"
        assert "sdk" in str(result["pool"].get("error", "")).lower()

    async def test_no_pool_error_when_nothing_requested(self, monkeypatch):
        agents = self._prepare(monkeypatch, cli=True, sdk=False)
        monkeypatch.setenv("XAGENT_SANDBOX_POOL_SIZE", "0")

        result = await agents.get_sandbox_status(principal=None)

        assert "error" not in result["pool"]

    async def test_network_isolation_reflects_backend(self, monkeypatch):
        """``network_isolated`` used to be the tautology ``not docker_ok or True``."""
        agents = self._prepare(monkeypatch, cli=False, sdk=False)

        result = await agents.get_sandbox_status(principal=None)

        assert result["effective_backend"] == "subprocess"
        assert result["security"]["network_isolated"] is False

    async def test_execution_history_is_surfaced(self, monkeypatch):
        """``get_sandbox_manager`` is a coroutine; skipping the await left
        ``recent_executions`` permanently empty."""
        agents = self._prepare(monkeypatch, history=[{"execution_id": "abc"}])

        result = await agents.get_sandbox_status(principal=None)

        assert result["recent_executions"] == [{"execution_id": "abc"}]


class TestRootLoggingWiring:
    """The app used to configure no logging at all, so ``lastResort`` (WARNING+
    → stderr) swallowed INFO records and a JSON format switch did nothing."""

    @pytest.fixture(autouse=True)
    def _remove_our_handler(self):
        yield
        root = logging.getLogger()
        for handler in list(root.handlers):
            if getattr(handler, "_xagent_root_handler", False):
                root.removeHandler(handler)

    def test_json_format_emits_parseable_lines(self, capsys):
        from backend.app.core.logger_factory import configure_root_logging

        configure_root_logging(level=logging.INFO, format_type="json")
        logging.getLogger("xagent.test.json").info("hello %s", "world")

        line = capsys.readouterr().out.strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "xagent.test.json"

    def test_plain_format_emits_non_json(self, capsys):
        from backend.app.core.logger_factory import configure_root_logging

        configure_root_logging(level=logging.INFO, format_type="plain")
        logging.getLogger("xagent.test.plain").info("plain line")

        line = capsys.readouterr().out.strip().splitlines()[-1]
        assert "plain line" in line
        with pytest.raises(json.JSONDecodeError):
            json.loads(line)

    def test_repeated_configuration_does_not_stack_handlers(self):
        from backend.app.core.logger_factory import configure_root_logging

        configure_root_logging(format_type="plain")
        configure_root_logging(format_type="json")

        root = logging.getLogger()
        ours = [h for h in root.handlers if getattr(h, "_xagent_root_handler", False)]
        assert len(ours) == 1


class TestOtelStatusReporting:
    def test_disabled_reports_disabled(self):
        from backend.app.core.otel_exporter import OTelConfig, OTelExporter

        exporter = OTelExporter(OTelConfig(enabled=False))
        assert exporter.is_active is False
        assert exporter.status == "disabled"

    def test_enabled_but_unrunnable_names_the_missing_prerequisite(self):
        from backend.app.core.otel_exporter import OTelConfig, OTelExporter

        exporter = OTelExporter(OTelConfig(enabled=True))
        if exporter.status == "active":
            pytest.skip("OpenTelemetry fully installed; missing-prerequisite path not reachable")

        assert exporter.is_active is False
        # Must not be the misleading blanket "disabled" the old startup log implied.
        assert exporter.status != "disabled"
        assert exporter.status in {
            "sdk-not-installed",
            "otlp-exporter-missing",
        } or exporter.status.startswith("init-failed")
