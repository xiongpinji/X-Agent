from __future__ import annotations

import asyncio
import types
import sys
import urllib.error

import scripts.rc_external_smoke as rc_external_smoke
from scripts.rc_external_smoke import (
    _github_actions_run_artifacts_api_url,
    _github_actions_run_api_url,
    _github_actions_run_jobs_api_url,
    _github_issue_api_url,
    _github_repo_api_url,
    _provider_sentinel_matched,
    _run_openai_compatible_smoke,
    _run_ollama_smoke,
    run_github_dry_run_smoke,
    run_github_actions_preflight,
    run_github_execute_preflight,
    run_external_smoke,
    run_feishu_contract_smoke,
    run_provider_smoke,
    run_telegram_bot_preflight,
    run_telegram_contract_smoke,
)

EXPECTED_HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


def test_external_check_to_dict_sanitizes_details_and_error() -> None:
    token = "ghp_" + ("a" * 32)
    telegram_token = "123456:" + "ABCDEF0123456789"
    windows_user_path = "C:" + "\\Users\\" + "canqu" + "\\.codex\\secrets\\config.json"
    windows_model_path = "D:" + "\\AI模型库\\blobs\\sha256-" + ("b" * 32)
    posix_user_path = "/" + "home" + "/" + "canqu" + "/.config/xagent"
    check = rc_external_smoke.ExternalCheck(
        name="provider",
        status="failed",
        details={
            "path": windows_user_path,
            "nested": [windows_model_path, token, telegram_token],
        },
        missing=["Move OLLAMA_MODELS to D:\\ollama-models if needed."],
        error="token=" + token + " from " + posix_user_path,
    )

    payload = check.to_dict()

    assert payload["details"]["path"] == "<redacted-local-path>"
    assert payload["details"]["nested"][0] == "<redacted-local-path>"
    assert payload["details"]["nested"][1] == "<redacted-secret>"
    assert payload["details"]["nested"][2] == "<redacted-telegram-token>"
    assert payload["error"] == "token=<redacted-output>"
    assert payload["missing"] == ["Move OLLAMA_MODELS to D:\\ollama-models if needed."]


def test_provider_smoke_skips_mock_backend(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")

    check = asyncio.run(run_provider_smoke())

    assert check.name == "provider"
    assert check.status == "skipped"
    assert check.missing


def test_provider_sentinel_matching_is_case_insensitive() -> None:
    assert _provider_sentinel_matched("XAgent-RC-OK") is True
    assert _provider_sentinel_matched("provider is alive") is False


def test_openai_compatible_smoke_requires_sentinel(monkeypatch) -> None:
    class FakeResponse:
        content = "provider is alive"
        model = "fake-model"
        tokens_used = 1
        latency_ms = 2.0

    class FakeBackend:
        def __init__(self, **_: object) -> None:
            pass

        async def chat(self, *_: object) -> FakeResponse:
            return FakeResponse()

    fake_backends = types.ModuleType("backend.app.core.llm.backends")
    fake_backends.OpenAIBackend = FakeBackend
    monkeypatch.setitem(sys.modules, "backend.app.core.llm.backends", fake_backends)

    check = asyncio.run(
        _run_openai_compatible_smoke(
            provider="openai",
            api_key="sk-" + ("a" * 32),
            model="fake-model",
            base_url=None,
            timeout_seconds=1,
        )
    )

    assert check.status == "failed"
    assert check.details["sentinel_matched"] is False
    assert "sentinel" in str(check.error)


def test_ollama_smoke_passes_only_when_sentinel_present(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"response":"xagent-rc-ok"}'

    monkeypatch.setattr(rc_external_smoke.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    check = _run_ollama_smoke(timeout_seconds=1)

    assert check.status == "passed"
    assert check.details["sentinel_matched"] is True


def test_ollama_smoke_fails_when_sentinel_missing(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"response":"hello"}'

    monkeypatch.setattr(rc_external_smoke.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    check = _run_ollama_smoke(timeout_seconds=1)

    assert check.status == "failed"
    assert check.details["sentinel_matched"] is False


def test_ollama_smoke_reports_actionable_404_diagnostics(monkeypatch) -> None:
    def raise_404(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(rc_external_smoke.urllib.request, "urlopen", raise_404)

    check = _run_ollama_smoke(timeout_seconds=1)

    assert check.status == "skipped"
    assert check.details["http_status"] == 404
    assert check.details["endpoint"].endswith("/api/generate")
    assert any("OLLAMA_BASE_URL" in item for item in check.missing)
    assert any("ollama pull" in item for item in check.missing)


def test_ollama_smoke_reports_model_load_failure_diagnostics(monkeypatch) -> None:
    class ErrorBody:
        def read(self) -> bytes:
            return (
                '{"error":"llama-server process has terminated: error loading model: '
                'llama_model_loader failed to load model from D:\\\\AI�\\\\blobs\\\\sha256-deadbeef"}'
            ).encode("utf-8")

    def raise_500(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=ErrorBody(),
        )

    monkeypatch.setenv("XAGENT_OLLAMA_MODEL", "qwen2.5:1.5b")
    monkeypatch.setattr(rc_external_smoke.urllib.request, "urlopen", raise_500)

    check = _run_ollama_smoke(timeout_seconds=1)

    assert check.status == "skipped"
    assert check.details["http_status"] == 500
    assert "llama_model_loader" in check.details["response_sample"]
    assert "<redacted-local-path>" in check.details["response_sample"]
    assert "D:" + "\\AI" not in check.details["response_sample"]
    assert "�" not in check.details["response_sample"]
    assert any("model storage" in item for item in check.missing)
    assert any("ollama run qwen2.5:1.5b" in item for item in check.missing)
    assert any("ASCII-only local path" in item for item in check.missing)


def test_ollama_smoke_reports_reachable_endpoint_hint_for_connection_failure(monkeypatch) -> None:
    def raise_url_error(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(rc_external_smoke.urllib.request, "urlopen", raise_url_error)

    check = _run_ollama_smoke(timeout_seconds=1)

    assert check.status == "skipped"
    assert any("Start Ollama" in item for item in check.missing)
    assert any("/api/generate" in item for item in check.missing)


def test_telegram_contract_skips_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("XAGENT_TELEGRAM_SIGNING_SECRET", raising=False)

    check = asyncio.run(run_telegram_contract_smoke())

    assert check.name == "telegram_webhook_contract"
    assert check.status == "skipped"
    assert "XAGENT_TELEGRAM_WEBHOOK_SECRET" in check.missing[0]


def test_telegram_contract_passes_with_mocked_sender(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("XAGENT_TELEGRAM_BOT_TOKEN", "token")

    check = asyncio.run(run_telegram_contract_smoke())

    assert check.status == "passed"
    assert check.details["reply_sent"] is True
    assert check.details["outbound_mocked"] is True
    assert check.details["invalid_secret_rejected"] is True
    assert check.details["missing_secret_rejected"] is True
    assert check.details["negative_reply_sent"] is False


def test_telegram_bot_preflight_is_explicitly_opt_in() -> None:
    check = run_telegram_bot_preflight(enabled=False)

    assert check.status == "skipped"
    assert "--telegram-live-preflight" in check.missing[0]


def test_telegram_bot_preflight_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    check = run_telegram_bot_preflight(enabled=True)

    assert check.status == "skipped"
    assert "TELEGRAM_BOT_TOKEN" in check.missing[0]


def test_telegram_bot_preflight_passes_get_me_without_mutation(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_TELEGRAM_BOT_TOKEN", "123456:" + "ABCDEF0123456789")
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_telegram_get_me",
        lambda **_: {
            "ok": True,
            "result": {
                "id": 123456,
                "username": "xagent_rc_bot",
                "can_join_groups": True,
                "can_read_all_group_messages": False,
                "supports_inline_queries": False,
            },
        },
    )

    check = run_telegram_bot_preflight(enabled=True)

    assert check.status == "passed"
    assert check.details["mutation_performed"] is False
    assert check.details["bot_username"] == "xagent_rc_bot"
    assert check.details["token"] == "<redacted-telegram-token>"


def test_telegram_bot_preflight_fails_bad_get_me(monkeypatch) -> None:
    telegram_token = "123456:" + "ABCDEF0123456789"
    monkeypatch.setenv("XAGENT_TELEGRAM_BOT_TOKEN", telegram_token)

    def raise_token_url(**_: object) -> object:
        raise RuntimeError(f"https://api.telegram.org/bot{telegram_token}/getMe returned 401")

    monkeypatch.setattr(rc_external_smoke, "_read_telegram_get_me", raise_token_url)

    check = run_telegram_bot_preflight(enabled=True)
    payload = check.to_dict()

    assert check.status == "failed"
    assert "getMe" in str(check.error)
    assert telegram_token not in str(payload["error"])
    assert "<redacted-telegram-token>" in str(payload["error"])


def test_feishu_contract_skips_without_required_env(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("XAGENT_FEISHU_APP_SECRET", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    monkeypatch.delenv("XAGENT_FEISHU_ENCRYPT_KEY", raising=False)
    monkeypatch.delenv("FEISHU_ENCRYPT_KEY", raising=False)

    check = asyncio.run(run_feishu_contract_smoke())

    assert check.name == "feishu_webhook_contract"
    assert check.status == "skipped"
    assert any("XAGENT_FEISHU_APP_ID" in item for item in check.missing)
    assert any("XAGENT_FEISHU_APP_SECRET" in item for item in check.missing)
    assert any("XAGENT_FEISHU_ENCRYPT_KEY" in item for item in check.missing)


def test_feishu_contract_passes_with_signed_event(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_test")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "encrypt-key")

    check = asyncio.run(run_feishu_contract_smoke())

    assert check.status == "passed"
    assert check.details["signature_headers"] == [
        "X-Lark-Signature",
        "X-Lark-Request-Timestamp",
        "X-Lark-Request-Nonce",
    ]
    assert check.details["valid_signature_accepted"] is True
    assert check.details["invalid_signature_rejected"] is True
    assert check.details["missing_signature_rejected"] is True
    assert check.details["event_accepted"] is True
    assert check.details["duplicate_rejected"] is True
    assert check.details["mutation_performed"] is False


def test_external_smoke_defaults_to_feishu_not_telegram(monkeypatch) -> None:
    async def fake_provider(provider=None, timeout_seconds=20.0):
        return rc_external_smoke.ExternalCheck("provider", "skipped")

    async def fake_feishu_contract():
        return rc_external_smoke.ExternalCheck("feishu_webhook_contract", "skipped")

    monkeypatch.setattr(
        rc_external_smoke,
        "run_provider_smoke",
        fake_provider,
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "run_feishu_contract_smoke",
        fake_feishu_contract,
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "run_github_dry_run_smoke",
        lambda issue_url=None: rc_external_smoke.ExternalCheck("github_issue_to_pr_dry_run", "skipped"),
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "run_github_execute_preflight",
        lambda issue_url=None, enabled=False: rc_external_smoke.ExternalCheck("github_issue_to_pr_execute_preflight", "skipped"),
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "run_github_actions_preflight",
        lambda run_url=None, enabled=False: rc_external_smoke.ExternalCheck("hosted_github_actions_run", "skipped"),
    )

    report = asyncio.run(run_external_smoke())

    assert [check.name for check in report.checks] == [
        "provider",
        "feishu_webhook_contract",
        "github_issue_to_pr_dry_run",
        "github_issue_to_pr_execute_preflight",
        "hosted_github_actions_run",
    ]


def test_external_smoke_can_scope_to_github_dry_run_only(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_provider(provider=None, timeout_seconds=20.0):
        calls.append("provider")
        return rc_external_smoke.ExternalCheck("provider", "passed")

    monkeypatch.setattr(rc_external_smoke, "run_provider_smoke", fake_provider)
    monkeypatch.setattr(rc_external_smoke, "run_telegram_contract_smoke", lambda: calls.append("telegram"))
    monkeypatch.setattr(rc_external_smoke, "run_feishu_contract_smoke", lambda: calls.append("feishu"))
    monkeypatch.setattr(
        rc_external_smoke,
        "run_github_dry_run_smoke",
        lambda issue_url=None: rc_external_smoke.ExternalCheck("github_issue_to_pr_dry_run", "passed"),
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "run_github_execute_preflight",
        lambda issue_url=None, enabled=False: rc_external_smoke.ExternalCheck("github_issue_to_pr_execute_preflight", "failed"),
    )

    report = asyncio.run(run_external_smoke(checks=["github_issue_to_pr_dry_run"], require_configured=True))

    assert report.status == "passed"
    assert [check.name for check in report.checks] == ["github_issue_to_pr_dry_run"]
    assert calls == []


def test_github_dry_run_skips_without_test_issue(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_GITHUB_TEST_ISSUE_URL", raising=False)
    monkeypatch.delenv("GITHUB_TEST_ISSUE_URL", raising=False)

    check = run_github_dry_run_smoke()

    assert check.status == "skipped"
    assert check.missing


def test_github_dry_run_plans_from_issue_url() -> None:
    check = run_github_dry_run_smoke("https://github.com/acme/project/issues/42")

    assert check.status == "passed"
    assert check.details["repo_full_name"] == "acme/project"
    assert check.details["issue_number"] == 42
    assert check.details["execute_allowed"] is False


def test_github_issue_api_url_maps_issue_url() -> None:
    api_url, repo_full_name, issue_number = _github_issue_api_url("https://github.com/acme/project/issues/42")

    assert api_url == "https://api.github.com/repos/acme/project/issues/42"
    assert repo_full_name == "acme/project"
    assert issue_number == 42


def test_github_repo_api_url_maps_repo_full_name() -> None:
    assert _github_repo_api_url("acme/project") == "https://api.github.com/repos/acme/project"


def test_github_actions_run_api_url_maps_run_url() -> None:
    api_url, repo_full_name, run_id = _github_actions_run_api_url("https://github.com/acme/project/actions/runs/123")

    assert api_url == "https://api.github.com/repos/acme/project/actions/runs/123"
    assert repo_full_name == "acme/project"
    assert run_id == 123


def test_github_actions_related_api_urls_map_run_url() -> None:
    jobs_api_url, repo_full_name, run_id = _github_actions_run_jobs_api_url(
        "https://github.com/acme/project/actions/runs/123"
    )
    artifacts_api_url, _, _ = _github_actions_run_artifacts_api_url(
        "https://github.com/acme/project/actions/runs/123"
    )

    assert jobs_api_url == "https://api.github.com/repos/acme/project/actions/runs/123/jobs?per_page=100"
    assert artifacts_api_url == "https://api.github.com/repos/acme/project/actions/runs/123/artifacts?per_page=100"
    assert repo_full_name == "acme/project"
    assert run_id == 123


def test_github_execute_preflight_is_explicitly_opt_in() -> None:
    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=False)

    assert check.status == "skipped"
    assert "--github-execute-preflight" in check.missing[0]


def test_github_execute_preflight_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "skipped"
    assert "GITHUB_TOKEN" in check.missing[0]


def test_github_execute_preflight_passes_without_mutation_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_issue",
        lambda **_: {"state": "open", "title": "Disposable RC test issue"},
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_repo_permissions",
        lambda **_: {
            "default_branch": "main",
            "permissions": {"pull": True, "push": True, "admin": False, "maintain": False, "triage": True},
        },
    )

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "passed"
    assert check.details["mutation_performed"] is False
    assert check.details["read_probe"]["status"] == "passed"
    assert check.details["read_probe"]["state"] == "open"
    assert check.details["permission_probe"]["status"] == "passed"
    assert check.details["permission_probe"]["permissions"]["push"] is True
    assert check.details["permission_probe"]["least_privilege"] is True
    assert check.details["permission_probe"]["owner_context_permissions"] == []


def test_github_execute_preflight_fails_without_repo_push_permission(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_issue",
        lambda **_: {"state": "open", "title": "Disposable RC test issue"},
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_repo_permissions",
        lambda **_: {
            "default_branch": "main",
            "permissions": {"pull": True, "push": False, "admin": False},
        },
    )

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "failed"
    assert check.details["mutation_performed"] is False
    assert check.details["permission_probe"]["permissions"]["push"] is False
    assert "permissions.push=true" in str(check.error)


def test_github_execute_preflight_fails_when_test_issue_is_closed(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_issue",
        lambda **_: {"state": "closed", "title": "Disposable RC test issue"},
    )

    called_permissions = False

    def permissions_probe(**_: object) -> dict[str, object]:
        nonlocal called_permissions
        called_permissions = True
        return {"default_branch": "main", "permissions": {"pull": True, "push": True}}

    monkeypatch.setattr(rc_external_smoke, "_read_github_repo_permissions", permissions_probe)

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "failed"
    assert check.details["mutation_performed"] is False
    assert check.details["read_probe"]["status"] == "failed"
    assert check.details["read_probe"]["state"] == "closed"
    assert called_permissions is False
    assert "state=open" in str(check.error)


def test_github_execute_preflight_allows_owner_context_permissions_without_mutation(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_issue",
        lambda **_: {"state": "open", "title": "Disposable RC test issue"},
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_repo_permissions",
        lambda **_: {
            "default_branch": "main",
            "permissions": {"pull": True, "push": True, "admin": True, "maintain": False},
        },
    )

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "passed"
    assert check.details["mutation_performed"] is False
    assert check.details["permission_probe"]["least_privilege"] is True
    assert check.details["permission_probe"]["owner_context_permissions"] == ["admin"]
    assert "repository owners" in check.details["permission_probe"]["owner_context_note"]


def test_github_execute_preflight_fails_when_repo_permissions_are_missing(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_issue",
        lambda **_: {"state": "open", "title": "Disposable RC test issue"},
    )

    def malformed_repo_probe(**_: object) -> dict[str, object]:
        raise ValueError("GitHub repository API response did not include a permissions object")

    monkeypatch.setattr(rc_external_smoke, "_read_github_repo_permissions", malformed_repo_probe)

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "failed"
    assert check.details["mutation_performed"] is False
    assert "repository permission probe failed" in str(check.error)


def test_github_execute_preflight_fails_when_read_probe_fails(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)

    def fail_probe(**_: object) -> dict[str, object]:
        raise OSError("network unavailable")

    monkeypatch.setattr(rc_external_smoke, "_read_github_issue", fail_probe)

    check = run_github_execute_preflight("https://github.com/acme/project/issues/42", enabled=True)

    assert check.status == "failed"
    assert "read-only issue probe failed" in str(check.error)


def test_github_actions_preflight_is_explicitly_opt_in() -> None:
    check = run_github_actions_preflight(enabled=False)

    assert check.status == "skipped"
    assert "--github-actions-preflight" in check.missing[0]


def test_github_actions_preflight_requires_token_and_run_url(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", raising=False)
    monkeypatch.delenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", raising=False)

    check = run_github_actions_preflight(enabled=True)

    assert check.status == "skipped"
    assert len(check.missing) == 3
    assert check.details["expected_head_sha_configured"] is False
    assert check.details["expected_head_sha_valid"] is False


def test_github_actions_preflight_rejects_invalid_expected_head_sha_without_api_probe(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", "not-a-commit-sha")
    called_run_probe = False

    def run_probe(**_: object) -> dict[str, object]:
        nonlocal called_run_probe
        called_run_probe = True
        return {}

    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_run", run_probe)

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "skipped"
    assert any("40-character hex git commit SHA" in item for item in check.missing)
    assert check.details["expected_head_sha_configured"] is True
    assert check.details["expected_head_sha_valid"] is False
    assert called_run_probe is False


def test_github_actions_preflight_passes_successful_run(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/acme/project/actions/runs/123",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
            "head_sha": EXPECTED_HEAD_SHA,
            "head_branch": "codex/commercial-rc",
        },
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_jobs",
        lambda **_: {
            "jobs": [
                {"name": "commercial-rc-linux", "status": "completed", "conclusion": "success"},
                {"name": "commercial-rc-windows-installer", "status": "completed", "conclusion": "success"},
            ],
        },
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_artifacts",
        lambda **_: {"artifacts": [{"name": "commercial-rc-evidence"}]},
    )

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "passed"
    assert check.details["mutation_performed"] is False
    assert check.details["run_status"] == "completed"
    assert check.details["conclusion"] == "success"
    assert check.details["workflow_verified"] is True
    assert check.details["expected_head_sha"] == EXPECTED_HEAD_SHA
    assert check.details["head_sha"] == EXPECTED_HEAD_SHA
    assert check.details["head_sha_verified"] is True
    assert check.details["head_branch"] == "codex/commercial-rc"
    assert check.details["jobs_verified"] is True
    assert check.details["artifact_verified"] is True


def test_github_actions_preflight_fails_head_sha_mismatch_without_querying_jobs(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    wrong_head_sha = "f" * 40
    called_jobs = False
    called_artifacts = False

    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/acme/project/actions/runs/123",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
            "head_sha": wrong_head_sha,
        },
    )

    def jobs_probe(**_: object) -> dict[str, object]:
        nonlocal called_jobs
        called_jobs = True
        return {"jobs": []}

    def artifacts_probe(**_: object) -> dict[str, object]:
        nonlocal called_artifacts
        called_artifacts = True
        return {"artifacts": []}

    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_jobs", jobs_probe)
    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_artifacts", artifacts_probe)

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "failed"
    assert check.details["head_sha"] == wrong_head_sha
    assert check.details["head_sha_verified"] is False
    assert called_jobs is False
    assert called_artifacts is False
    assert "head_sha mismatch" in str(check.error)


def test_github_actions_preflight_fails_missing_run_head_sha_without_querying_jobs(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    called_jobs = False
    called_artifacts = False

    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/acme/project/actions/runs/123",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
        },
    )

    def jobs_probe(**_: object) -> dict[str, object]:
        nonlocal called_jobs
        called_jobs = True
        return {"jobs": []}

    def artifacts_probe(**_: object) -> dict[str, object]:
        nonlocal called_artifacts
        called_artifacts = True
        return {"artifacts": []}

    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_jobs", jobs_probe)
    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_artifacts", artifacts_probe)

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "failed"
    assert check.details["head_sha"] == ""
    assert check.details["head_sha_verified"] is False
    assert called_jobs is False
    assert called_artifacts is False
    assert "head_sha mismatch" in str(check.error)


def test_github_actions_preflight_fails_when_required_job_missing(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/acme/project/actions/runs/123",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
            "head_sha": EXPECTED_HEAD_SHA,
        },
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_jobs",
        lambda **_: {"jobs": [{"name": "commercial-rc-linux", "status": "completed", "conclusion": "success"}]},
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_artifacts",
        lambda **_: {"artifacts": [{"name": "commercial-rc-evidence"}]},
    )

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "failed"
    assert check.details["jobs_verified"] is False
    assert "commercial-rc-windows-installer" in str(check.error)


def test_github_actions_preflight_fails_when_required_artifact_missing(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/acme/project/actions/runs/123",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
            "head_sha": EXPECTED_HEAD_SHA,
        },
    )
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_jobs",
        lambda **_: {
            "jobs": [
                {"name": "commercial-rc-linux", "status": "completed", "conclusion": "success"},
                {"name": "commercial-rc-windows-installer", "status": "completed", "conclusion": "success"},
            ],
        },
    )
    monkeypatch.setattr(rc_external_smoke, "_read_github_actions_artifacts", lambda **_: {"artifacts": []})

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "failed"
    assert check.details["artifact_verified"] is False
    assert "commercial-rc-evidence" in str(check.error)


def test_github_actions_preflight_fails_unsuccessful_run(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_" + "a" * 32)
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setattr(
        rc_external_smoke,
        "_read_github_actions_run",
        lambda **_: {
            "status": "completed",
            "conclusion": "failure",
            "name": "Commercial RC Gate",
            "path": ".github/workflows/commercial-rc.yml",
            "head_sha": EXPECTED_HEAD_SHA,
        },
    )

    check = run_github_actions_preflight(
        "https://github.com/acme/project/actions/runs/123",
        enabled=True,
    )

    assert check.status == "failed"
    assert "run status=completed, conclusion=failure" in str(check.error)
