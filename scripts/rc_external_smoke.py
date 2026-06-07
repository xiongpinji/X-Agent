#!/usr/bin/env python3
"""Run safe external-resource smoke checks for the commercial RC.

The default mode is evidence-producing and non-destructive:

- Provider checks run only when the selected backend has the required
  credentials or local URL configured.
- Telegram verifies the local webhook secret contract with a mocked reply
  sender; it does not call Telegram unless a future explicit check is added.
- GitHub issue-to-PR validates dry-run planning from a test issue URL. Execute
  preflight is opt-in and still performs no repository writes.

Use ``--require-configured`` in the final release gate to fail when configured
external checks are missing, skipped, or fail.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "rc-external-smoke.json"
GITHUB_API_BASE_URL = "https://api.github.com"
TELEGRAM_API_BASE_URL = "https://api.telegram.org"
PROVIDER_SENTINEL = "xagent-rc-ok"
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")
TELEGRAM_TOKEN_OUTPUT_RE = re.compile(r"(?:(?<=bot)|\b)[0-9]{5,}:[A-Za-z0-9_-]{8,}\b")
WINDOWS_LOCAL_PATH_OUTPUT_RE = re.compile(
    r"(?i)\b[A-Z]:(?:\\\\|[\\/])+(?:(?!\\\\[nr])[^\"'\r\n])+"
)
POSIX_LOCAL_PATH_OUTPUT_RE = re.compile(
    r"(?<!\w)/(?:Users|home|tmp|var)/(?:[^/\s\"']+/)*[^/\s\"']*"
)
GITHUB_ACTIONS_RUN_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/actions/runs/(?P<run_id>[0-9]+)(?:[/?#][^\s]*)?$"
)
GITHUB_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
CHECK_CHOICES = {
    "provider",
    "feishu_webhook_contract",
    "telegram_webhook_contract",
    "telegram_bot_preflight",
    "github_issue_to_pr_dry_run",
    "github_issue_to_pr_execute_preflight",
    "hosted_github_actions_run",
}
DEFAULT_CHECKS = {
    "provider",
    "feishu_webhook_contract",
    "github_issue_to_pr_dry_run",
    "github_issue_to_pr_execute_preflight",
    "hosted_github_actions_run",
}
REQUIRED_HOSTED_ACTIONS_WORKFLOW_NAME = "Commercial RC Gate"
REQUIRED_HOSTED_ACTIONS_WORKFLOW_PATH = ".github/workflows/commercial-rc.yml"
REQUIRED_HOSTED_ACTIONS_JOBS = ("commercial-rc-linux", "commercial-rc-windows-installer")
REQUIRED_HOSTED_ACTIONS_ARTIFACT = "commercial-rc-evidence"


@dataclass(frozen=True)
class ExternalCheck:
    """Result of one external readiness check."""

    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["details"] = _sanitize_report_value(payload.get("details"))
        payload["error"] = _sanitize_report_value(payload.get("error"))
        return payload


@dataclass(frozen=True)
class ExternalSmokeReport:
    """Machine-readable external smoke report."""

    status: str
    generated_at: str
    duration_seconds: float
    require_configured: bool
    checks: list[ExternalCheck]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _getenv(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _selected_provider(explicit_provider: str | None = None) -> str:
    if explicit_provider:
        return explicit_provider.lower()
    return _getenv("XAGENT_LLM_BACKEND", "LLM_BACKEND").lower() or "mock"


def _redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _redact_telegram_token(value: str) -> str:
    return "<redacted-telegram-token>" if value else ""


def _redact_feishu_secret(value: str) -> str:
    return "<redacted-feishu-secret>" if value else ""


def _valid_git_commit_sha(value: str) -> bool:
    return bool(GITHUB_COMMIT_SHA_RE.fullmatch(value.strip()))


def _sanitize_report_sample(text: str, *, max_chars: int = 240) -> str:
    return _sanitize_report_text(text)[:max_chars]


def _sanitize_report_text(text: str) -> str:
    text = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", text)
    text = SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", text)
    text = TELEGRAM_TOKEN_OUTPUT_RE.sub("<redacted-telegram-token>", text)
    text = WINDOWS_LOCAL_PATH_OUTPUT_RE.sub("<redacted-local-path>", text)
    text = POSIX_LOCAL_PATH_OUTPUT_RE.sub("<redacted-local-path>", text)
    return text.replace("\ufffd", "<replacement-char>")


def _sanitize_report_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_report_text(value)
    if isinstance(value, list):
        return [_sanitize_report_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_report_value(item) for key, item in value.items()}
    return value


def _provider_prompt() -> str:
    return f"Reply with exactly: {PROVIDER_SENTINEL}"


def _provider_sentinel_matched(content: str) -> bool:
    return PROVIDER_SENTINEL in content.strip().lower()


async def run_provider_smoke(provider: str | None = None, *, timeout_seconds: float = 20.0) -> ExternalCheck:
    """Run one tiny configured provider check."""

    selected = _selected_provider(provider)
    if selected == "mock":
        return ExternalCheck(
            name="provider",
            status="skipped",
            details={"provider": selected},
            missing=["Set XAGENT_LLM_BACKEND to openai, deepseek, anthropic, or ollama for real-provider smoke."],
        )

    if selected == "openai":
        return await _run_openai_compatible_smoke(
            provider="openai",
            api_key=_getenv("XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
            model=_getenv("XAGENT_OPENAI_MODEL", "OPENAI_MODEL") or "gpt-4o-mini",
            base_url=_getenv("XAGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL") or None,
            timeout_seconds=timeout_seconds,
        )

    if selected == "deepseek":
        return await _run_openai_compatible_smoke(
            provider="deepseek",
            api_key=_getenv("XAGENT_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
            model=_getenv("XAGENT_DEEPSEEK_MODEL", "DEEPSEEK_MODEL") or "deepseek-chat",
            base_url=_getenv("XAGENT_DEEPSEEK_BASE_URL", "DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1",
            timeout_seconds=timeout_seconds,
        )

    if selected == "anthropic":
        return await _run_anthropic_smoke(timeout_seconds=timeout_seconds)

    if selected in {"ollama", "local"}:
        return _run_ollama_smoke(timeout_seconds=timeout_seconds)

    return ExternalCheck(
        name="provider",
        status="skipped",
        details={"provider": selected},
        missing=["Unsupported XAGENT_LLM_BACKEND for external smoke."],
    )


async def _run_openai_compatible_smoke(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    timeout_seconds: float,
) -> ExternalCheck:
    if not api_key:
        return ExternalCheck(
            name="provider",
            status="skipped",
            details={"provider": provider, "model": model, "base_url": base_url},
            missing=[f"Set XAGENT_{provider.upper()}_API_KEY or {provider.upper()}_API_KEY."],
        )

    try:
        from backend.app.core.llm.backends import OpenAIBackend

        backend = OpenAIBackend(
            api_key=api_key,
            model=model,
            base_url=base_url,
            name=provider,
            max_retries=0,
            timeout=timeout_seconds,
        )
        response = await backend.chat(
            [{"role": "user", "content": _provider_prompt()}],
            [],
        )
        content = response.content or ""
        ok = _provider_sentinel_matched(content)
        return ExternalCheck(
            name="provider",
            status="passed" if ok else "failed",
            details={
                "provider": provider,
                "model": response.model or model,
                "tokens_used": response.tokens_used,
                "latency_ms": round(response.latency_ms, 3),
                "api_key": _redact(api_key),
                "base_url": base_url,
                "sentinel": PROVIDER_SENTINEL,
                "sentinel_matched": ok,
                "content_sample": content[:80],
            },
            error=None if ok else f"Provider response did not contain sentinel {PROVIDER_SENTINEL!r}.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports provider-specific failures
        return ExternalCheck(
            name="provider",
            status="failed",
            details={"provider": provider, "model": model, "base_url": base_url},
            error=str(exc),
        )


async def _run_anthropic_smoke(*, timeout_seconds: float) -> ExternalCheck:
    api_key = _getenv("XAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    model = _getenv("XAGENT_ANTHROPIC_MODEL", "ANTHROPIC_MODEL") or "claude-3-5-haiku-latest"
    if not api_key:
        return ExternalCheck(
            name="provider",
            status="skipped",
            details={"provider": "anthropic", "model": model},
            missing=["Set XAGENT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY."],
        )

    try:
        from backend.app.core.llm_providers.anthropic import AnthropicProvider
        from backend.app.core.llm_providers.base import LLMConfig, LLMMessage, ProviderType

        provider = AnthropicProvider(
            LLMConfig(
                provider=ProviderType.ANTHROPIC,
                model=model,
                api_key=api_key,
                temperature=0,
                max_tokens=8,
                timeout=int(timeout_seconds),
                retry_attempts=1,
            )
        )
        response = await provider.complete(
            [LLMMessage(role="user", content=_provider_prompt())]
        )
        content = response.content or ""
        ok = _provider_sentinel_matched(content)
        return ExternalCheck(
            name="provider",
            status="passed" if ok else "failed",
            details={
                "provider": response.provider,
                "model": response.model,
                "usage": response.usage,
                "latency_ms": round(response.latency_ms, 3),
                "api_key": _redact(api_key),
                "sentinel": PROVIDER_SENTINEL,
                "sentinel_matched": ok,
                "content_sample": content[:80],
            },
            error=None if ok else f"Provider response did not contain sentinel {PROVIDER_SENTINEL!r}.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports provider-specific failures
        return ExternalCheck(
            name="provider",
            status="failed",
            details={"provider": "anthropic", "model": model},
            error=str(exc),
        )


def _run_ollama_smoke(*, timeout_seconds: float) -> ExternalCheck:
    base_url = _getenv("XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL") or "http://localhost:11434"
    model = _getenv("XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL") or "llama2"
    endpoint = f"{base_url.rstrip('/')}/api/generate"
    request = urllib.request.Request(
        endpoint,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "model": model,
                "prompt": _provider_prompt(),
                "stream": False,
                "options": {"num_predict": 8},
            }
        ).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
        content = str(payload.get("response") or "")
        ok = _provider_sentinel_matched(content)
        return ExternalCheck(
            name="provider",
            status="passed" if ok else "failed",
            details={
                "provider": "ollama",
                "model": model,
                "base_url": base_url,
                "sentinel": PROVIDER_SENTINEL,
                "sentinel_matched": ok,
                "content_sample": content[:80],
            },
            error=None if ok else f"Ollama response did not contain sentinel {PROVIDER_SENTINEL!r}.",
        )
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        missing = _ollama_http_missing_actions(exc.code, model=model, response_body=response_body)
        return ExternalCheck(
            name="provider",
            status="skipped",
            details={
                "provider": "ollama",
                "model": model,
                "base_url": base_url,
                "endpoint": endpoint,
                "http_status": exc.code,
                "response_sample": _sanitize_report_sample(response_body),
            },
            missing=missing,
            error=f"HTTP Error {exc.code}: {exc.reason}",
        )
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return ExternalCheck(
            name="provider",
            status="skipped",
            details={"provider": "ollama", "model": model, "base_url": base_url, "endpoint": endpoint},
            missing=[
                "Start Ollama or set XAGENT_OLLAMA_BASE_URL/OLLAMA_BASE_URL for local-model smoke.",
                f"Confirm the Ollama generate endpoint is reachable: {endpoint}",
            ],
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 - report malformed local responses
        return ExternalCheck(
            name="provider",
            status="failed",
            details={"provider": "ollama", "model": model, "base_url": base_url},
            error=str(exc),
        )


def _ollama_http_missing_actions(http_status: int, *, model: str, response_body: str = "") -> list[str]:
    normalized_body = response_body.lower()
    if http_status == 404:
        return [
            "Verify XAGENT_OLLAMA_BASE_URL/OLLAMA_BASE_URL points to the Ollama root URL, not a UI or proxy path.",
            f"Pull the selected model with `ollama pull {model}` or set XAGENT_OLLAMA_MODEL/OLLAMA_MODEL to an installed model.",
        ]
    if http_status >= 500:
        if "failed to load model" in normalized_body or "llama_model_loader" in normalized_body:
            actions = [
                "Ollama reported a model load failure; verify OLLAMA_MODELS/model storage points to readable, intact model blobs.",
                f"Reinstall or move the selected model, then confirm it works with `ollama run {model}` before rerunning provider smoke.",
            ]
            if "failed to load model from" in normalized_body or "\ufffd" in response_body:
                actions.append(
                    "If the failed model path contains non-ASCII, replacement characters, or a synced project directory, "
                    "move OLLAMA_MODELS to an ASCII-only local path such as %USERPROFILE%\\.ollama\\models or D:\\ollama-models, "
                    "restart Ollama, and rerun provider smoke."
                )
            return actions
        return [
            "Check the Ollama service logs for the local-model generation error.",
            f"Verify the selected model can generate locally with `ollama run {model}` or choose another installed model.",
        ]
    if http_status in {401, 403}:
        return [
            "Check authentication or proxy policy in front of the Ollama-compatible endpoint.",
            "Use a local Ollama endpoint or configure XAGENT_OLLAMA_BASE_URL/OLLAMA_BASE_URL with the required access path.",
        ]
    return [
        "Check the Ollama-compatible endpoint, selected model, and local service readiness.",
        f"Rerun provider smoke after confirming `ollama run {model}` works locally.",
    ]


async def run_feishu_contract_smoke() -> ExternalCheck:
    """Verify Feishu signed event callback contract without sending messages."""

    app_id = _getenv("XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID")
    app_secret = _getenv("XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET")
    encrypt_key = _getenv("XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY")
    missing: list[str] = []
    if not app_id:
        missing.append("Set XAGENT_FEISHU_APP_ID or FEISHU_APP_ID.")
    if not app_secret:
        missing.append("Set XAGENT_FEISHU_APP_SECRET or FEISHU_APP_SECRET.")
    if not encrypt_key:
        missing.append("Set XAGENT_FEISHU_ENCRYPT_KEY or FEISHU_ENCRYPT_KEY for signed event callbacks.")
    if missing:
        return ExternalCheck(
            name="feishu_webhook_contract",
            status="skipped",
            details={
                "app_id_configured": bool(app_id),
                "app_secret_configured": bool(app_secret),
                "encrypt_key_configured": bool(encrypt_key),
            },
            missing=missing,
        )

    try:
        from backend.app.core.feishu_bridge import FeishuBridge

        bridge = FeishuBridge()
        bridge.configure(app_id=app_id, app_secret=app_secret, encrypt_key=encrypt_key)
        payload = {
            "event_id": "rc-feishu-smoke",
            "schema": "2.0",
            "header": {
                "event_id": "rc-feishu-smoke",
                "event_type": "im.message.receive_v1",
                "tenant_key": "tenant-rc",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou_rc_smoke"}},
                "message": {
                    "message_id": "om_rc_smoke",
                    "chat_id": "oc_rc_smoke",
                    "message_type": "text",
                    "content": json.dumps({"text": "commercial rc smoke"}, ensure_ascii=False),
                },
            },
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        nonce = f"rc-feishu-{hashlib.sha256(body).hexdigest()[:12]}"
        signature = FeishuBridge.calculate_lark_signature(
            timestamp=timestamp,
            nonce=nonce,
            encrypt_key=encrypt_key,
            body=body,
        )
        valid_signature_accepted = bridge.verify_signature(
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
            mode="lark_sha256",
        )
        invalid_signature = f"{signature[:-1]}{'0' if signature[-1] != '0' else '1'}"
        invalid_signature_rejected = not bridge.verify_signature(
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=invalid_signature,
            mode="lark_sha256",
        )
        missing_signature_rejected = not bridge.verify_signature(
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature="",
            mode="lark_sha256",
        )
        result = await bridge.handle_event(payload) if valid_signature_accepted else {}
        duplicate_result = await bridge.handle_event(payload) if valid_signature_accepted else {}
        snapshot = await bridge.store.snapshot()
        ok = (
            valid_signature_accepted
            and invalid_signature_rejected
            and missing_signature_rejected
            and result.get("accepted") is True
            and result.get("event_id") == "rc-feishu-smoke"
            and result.get("event_type") == "im.message.receive_v1"
            and duplicate_result.get("accepted") is False
            and duplicate_result.get("reason") == "duplicate_event"
            and snapshot.get("event_count") == 1
        )
        return ExternalCheck(
            name="feishu_webhook_contract",
            status="passed" if ok else "failed",
            details={
                "app_id_configured": True,
                "app_secret_configured": True,
                "encrypt_key_configured": True,
                "app_id": _redact(app_id),
                "app_secret": _redact_feishu_secret(app_secret),
                "encrypt_key": _redact_feishu_secret(encrypt_key),
                "signature_headers": [
                    "X-Lark-Signature",
                    "X-Lark-Request-Timestamp",
                    "X-Lark-Request-Nonce",
                ],
                "signature_algorithm": "sha256(timestamp + nonce + encrypt_key + body)",
                "valid_signature_accepted": valid_signature_accepted,
                "invalid_signature_rejected": invalid_signature_rejected,
                "missing_signature_rejected": missing_signature_rejected,
                "event_accepted": result.get("accepted") is True,
                "duplicate_rejected": duplicate_result.get("reason") == "duplicate_event",
                "event_id": result.get("event_id"),
                "event_type": result.get("event_type"),
                "message_id": payload["event"]["message"]["message_id"],
                "chat_id": payload["event"]["message"]["chat_id"],
                "content_extracted": snapshot["recent_events"][0]["message_id"] == "om_rc_smoke"
                if snapshot.get("recent_events")
                else False,
                "mutation_performed": False,
                "outbound_mocked": True,
            },
            error=None if ok else "Feishu webhook contract did not accept valid signed events and reject invalid inputs.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports contract failure
        return ExternalCheck(
            name="feishu_webhook_contract",
            status="failed",
            details={
                "app_id_configured": bool(app_id),
                "app_secret_configured": bool(app_secret),
                "encrypt_key_configured": bool(encrypt_key),
                "mutation_performed": False,
            },
            error=str(exc),
        )


async def run_telegram_contract_smoke() -> ExternalCheck:
    """Verify Telegram inbound webhook contract without real Telegram calls."""

    secret = _getenv("XAGENT_TELEGRAM_WEBHOOK_SECRET", "XAGENT_TELEGRAM_SIGNING_SECRET")
    bot_token = _getenv("XAGENT_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    if not secret:
        return ExternalCheck(
            name="telegram_webhook_contract",
            status="skipped",
            details={"bot_token_configured": bool(bot_token)},
            missing=["Set XAGENT_TELEGRAM_WEBHOOK_SECRET before enabling Telegram webhook."],
        )

    try:
        from backend.app.core.channels import ChannelConfig, ChannelRegistry, TelegramAdapter
        from backend.app.core.channels.base import ChannelMessage
        from backend.app.core.channels.router import ChannelRouter, ChannelSignatureError

        sent: list[tuple[str, str]] = []

        async def dispatch_message(message: ChannelMessage) -> dict[str, Any]:
            return {
                "run_id": "rc-telegram-smoke",
                "status": "accepted",
                "reply_text": f"rc handled {message.text}",
                "dispatch": {"source": "rc_external_smoke", "task": message.text},
            }

        async def reply_sender(message: ChannelMessage, text: str) -> dict[str, Any]:
            sent.append((message.conversation_id, text))
            return {"ok": True, "mocked": True}

        registry = ChannelRegistry()
        registry.register(TelegramAdapter(ChannelConfig(token=bot_token, signing_secret=secret)))
        router = ChannelRouter(registry, dispatch_callable=dispatch_message, reply_sender=reply_sender)
        body = json.dumps(
            {
                "message": {
                    "message_id": 9001,
                    "text": "commercial rc smoke",
                    "chat": {"id": 321},
                    "from": {"id": 654},
                }
            }
        ).encode("utf-8")
        payload = json.loads(body.decode("utf-8"))

        async def rejected_without_reply(headers: dict[str, str]) -> tuple[bool, bool]:
            replies_before = len(sent)
            try:
                await router.process_inbound(
                    channel="telegram",
                    body=body,
                    headers=headers,
                    payload=payload,
                )
            except ChannelSignatureError:
                return True, len(sent) > replies_before
            return False, len(sent) > replies_before

        result = await router.process_inbound(
            channel="telegram",
            body=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            payload=payload,
        )
        invalid_secret_rejected, invalid_secret_reply_sent = await rejected_without_reply(
            {"X-Telegram-Bot-Api-Secret-Token": f"{secret}-invalid"}
        )
        missing_secret_rejected, missing_secret_reply_sent = await rejected_without_reply({})
        negative_reply_sent = invalid_secret_reply_sent or missing_secret_reply_sent
        ok = (
            result.status == "accepted"
            and result.reply_sent
            and result.run_id == "rc-telegram-smoke"
            and sent == [("321", "rc handled commercial rc smoke")]
            and invalid_secret_rejected
            and missing_secret_rejected
            and not negative_reply_sent
        )
        return ExternalCheck(
            name="telegram_webhook_contract",
            status="passed" if ok else "failed",
            details={
                "bot_token_configured": bool(bot_token),
                "secret_configured": True,
                "conversation_id": result.conversation_id,
                "message_id": result.message_id,
                "reply_sent": result.reply_sent,
                "outbound_mocked": True,
                "invalid_secret_rejected": invalid_secret_rejected,
                "missing_secret_rejected": missing_secret_rejected,
                "negative_reply_sent": negative_reply_sent,
            },
            error=None if ok else "Telegram webhook contract did not dispatch, reply, and fail closed as expected.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports contract failure
        return ExternalCheck(
            name="telegram_webhook_contract",
            status="failed",
            details={"bot_token_configured": bool(bot_token), "secret_configured": True},
            error=str(exc),
        )


def _read_telegram_get_me(*, token: str, timeout_seconds: float, api_base_url: str = TELEGRAM_API_BASE_URL) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{api_base_url.rstrip('/')}/bot{token}/getMe",
        method="GET",
        headers={"User-Agent": "xagent-commercial-rc-smoke"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("Telegram getMe returned a non-object payload")
    return payload


def run_telegram_bot_preflight(*, enabled: bool, timeout_seconds: float = 15.0) -> ExternalCheck:
    """Verify the disposable Telegram bot token with getMe only."""

    if not enabled:
        return ExternalCheck(
            name="telegram_bot_preflight",
            status="skipped",
            missing=["Pass --telegram-live-preflight to verify the disposable Telegram bot token with getMe."],
        )

    token = _getenv("XAGENT_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    if not token:
        return ExternalCheck(
            name="telegram_bot_preflight",
            status="skipped",
            missing=["Set XAGENT_TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN for Telegram getMe preflight."],
            details={"token_configured": False},
        )

    try:
        payload = _read_telegram_get_me(token=token, timeout_seconds=timeout_seconds)
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        ok = payload.get("ok") is True and bool(result.get("id")) and bool(result.get("username"))
        return ExternalCheck(
            name="telegram_bot_preflight",
            status="passed" if ok else "failed",
            details={
                "token_configured": True,
                "token": _redact_telegram_token(token),
                "bot_id": result.get("id"),
                "bot_username": result.get("username"),
                "can_join_groups": result.get("can_join_groups"),
                "can_read_all_group_messages": result.get("can_read_all_group_messages"),
                "supports_inline_queries": result.get("supports_inline_queries"),
                "mutation_performed": False,
            },
            error=None if ok else "Telegram getMe response did not include ok=true, id, and username.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports token/resource readiness failure
        return ExternalCheck(
            name="telegram_bot_preflight",
            status="failed",
            details={"token_configured": True, "mutation_performed": False},
            error=f"Telegram getMe preflight failed: {exc}",
        )


def run_github_dry_run_smoke(issue_url: str | None = None) -> ExternalCheck:
    """Validate GitHub issue-to-PR dry-run planning without network writes."""

    target = issue_url or _getenv("XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL")
    if not target:
        return ExternalCheck(
            name="github_issue_to_pr_dry_run",
            status="skipped",
            missing=["Set XAGENT_GITHUB_TEST_ISSUE_URL to a disposable test issue URL."],
        )

    try:
        from backend.app.core.pipelines.issue_to_pr import dry_run_issue_to_pr

        result = dry_run_issue_to_pr({"issue_url": target})
        payload = result.to_dict()
        ok = result.dry_run and result.status == "planned" and result.execute_allowed is False
        return ExternalCheck(
            name="github_issue_to_pr_dry_run",
            status="passed" if ok else "failed",
            details={
                "issue_url": target,
                "repo_full_name": payload["issue"]["repo_full_name"],
                "issue_number": payload["issue"]["issue_number"],
                "branch_name": payload["branch_name"],
                "execute_allowed": payload["execute_allowed"],
                "steps": payload["plan"]["steps"],
            },
            error=None if ok else "Dry-run planner returned an unexpected shape.",
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports dry-run readiness failure
        return ExternalCheck(
            name="github_issue_to_pr_dry_run",
            status="failed",
            details={"issue_url": target},
            error=str(exc),
        )


def _github_issue_api_url(issue_url: str, *, api_base_url: str = GITHUB_API_BASE_URL) -> tuple[str, str, int]:
    from backend.app.core.pipelines.issue_to_pr import parse_github_issue_url

    repo_full_name, issue_number = parse_github_issue_url(issue_url)
    owner, repo = repo_full_name.split("/", 1)
    return f"{api_base_url.rstrip('/')}/repos/{owner}/{repo}/issues/{issue_number}", repo_full_name, issue_number


def _github_repo_api_url(repo_full_name: str, *, api_base_url: str = GITHUB_API_BASE_URL) -> str:
    parts = repo_full_name.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GitHub repo full name must look like owner/repo")
    owner, repo = parts
    return f"{api_base_url.rstrip('/')}/repos/{owner}/{repo}"


def _github_actions_run_api_url(run_url: str, *, api_base_url: str = GITHUB_API_BASE_URL) -> tuple[str, str, int]:
    match = GITHUB_ACTIONS_RUN_URL_RE.fullmatch(run_url.strip())
    if not match:
        raise ValueError("GitHub Actions run URL must look like https://github.com/<owner>/<repo>/actions/runs/<id>")
    owner = match.group("owner")
    repo = match.group("repo")
    run_id = int(match.group("run_id"))
    return f"{api_base_url.rstrip('/')}/repos/{owner}/{repo}/actions/runs/{run_id}", f"{owner}/{repo}", run_id


def _github_actions_run_jobs_api_url(run_url: str, *, api_base_url: str = GITHUB_API_BASE_URL) -> tuple[str, str, int]:
    api_url, repo_full_name, run_id = _github_actions_run_api_url(run_url, api_base_url=api_base_url)
    return f"{api_url}/jobs?per_page=100", repo_full_name, run_id


def _github_actions_run_artifacts_api_url(run_url: str, *, api_base_url: str = GITHUB_API_BASE_URL) -> tuple[str, str, int]:
    api_url, repo_full_name, run_id = _github_actions_run_api_url(run_url, api_base_url=api_base_url)
    return f"{api_url}/artifacts?per_page=100", repo_full_name, run_id


def _read_github_issue(
    *,
    issue_url: str,
    token: str,
    timeout_seconds: float,
    api_base_url: str = GITHUB_API_BASE_URL,
) -> dict[str, Any]:
    api_url, _, _ = _github_issue_api_url(issue_url, api_base_url=api_base_url)
    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "xagent-commercial-rc-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub issue API returned a non-object payload")
    return payload


def _read_github_repo_permissions(
    *,
    repo_full_name: str,
    token: str,
    timeout_seconds: float,
    api_base_url: str = GITHUB_API_BASE_URL,
) -> dict[str, Any]:
    api_url = _github_repo_api_url(repo_full_name, api_base_url=api_base_url)
    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "xagent-commercial-rc-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub repository API returned a non-object payload")
    permissions = payload.get("permissions")
    if not isinstance(permissions, dict):
        raise ValueError("GitHub repository API response did not include a permissions object")
    return payload


def _read_github_actions_run(
    *,
    run_url: str,
    token: str,
    timeout_seconds: float,
    api_base_url: str = GITHUB_API_BASE_URL,
) -> dict[str, Any]:
    api_url, _, _ = _github_actions_run_api_url(run_url, api_base_url=api_base_url)
    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "xagent-commercial-rc-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub Actions run API returned a non-object payload")
    return payload


def _read_github_actions_jobs(
    *,
    run_url: str,
    token: str,
    timeout_seconds: float,
    api_base_url: str = GITHUB_API_BASE_URL,
) -> dict[str, Any]:
    api_url, _, _ = _github_actions_run_jobs_api_url(run_url, api_base_url=api_base_url)
    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "xagent-commercial-rc-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub Actions jobs API returned a non-object payload")
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("GitHub Actions jobs API response did not include a jobs list")
    return payload


def _read_github_actions_artifacts(
    *,
    run_url: str,
    token: str,
    timeout_seconds: float,
    api_base_url: str = GITHUB_API_BASE_URL,
) -> dict[str, Any]:
    api_url, _, _ = _github_actions_run_artifacts_api_url(run_url, api_base_url=api_base_url)
    request = urllib.request.Request(
        api_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "xagent-commercial-rc-smoke",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub Actions artifacts API returned a non-object payload")
    if not isinstance(payload.get("artifacts"), list):
        raise ValueError("GitHub Actions artifacts API response did not include an artifacts list")
    return payload


def _required_github_actions_job_probe(jobs: list[Any]) -> dict[str, Any]:
    required = {
        name: {"found": False, "status": "", "conclusion": "", "html_url": ""}
        for name in REQUIRED_HOSTED_ACTIONS_JOBS
    }
    for item in jobs:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in required:
            continue
        required[name] = {
            "found": True,
            "status": str(item.get("status") or ""),
            "conclusion": str(item.get("conclusion") or ""),
            "html_url": str(item.get("html_url") or ""),
        }
    missing_or_failed = [
        name
        for name, result in required.items()
        if not (
            result.get("found") is True
            and result.get("status") == "completed"
            and result.get("conclusion") == "success"
        )
    ]
    return {
        "verified": not missing_or_failed,
        "required_jobs": required,
        "missing_or_failed_jobs": missing_or_failed,
    }


def _required_github_actions_artifact_probe(artifacts: list[Any]) -> dict[str, Any]:
    artifact_names = sorted(
        {
            str(item.get("name") or "")
            for item in artifacts
            if isinstance(item, dict) and item.get("name")
        }
    )
    verified = REQUIRED_HOSTED_ACTIONS_ARTIFACT in artifact_names
    return {
        "verified": verified,
        "required_artifact": REQUIRED_HOSTED_ACTIONS_ARTIFACT,
        "artifact_names": artifact_names[:50],
        "missing_artifact": "" if verified else REQUIRED_HOSTED_ACTIONS_ARTIFACT,
    }


def run_github_execute_preflight(issue_url: str | None = None, *, enabled: bool) -> ExternalCheck:
    """Verify execute-mode prerequisites without mutating a repository."""

    if not enabled:
        return ExternalCheck(
            name="github_issue_to_pr_execute_preflight",
            status="skipped",
            missing=["Pass --github-execute-preflight to verify execute-mode readiness."],
        )

    token = _getenv("XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN")
    target = issue_url or _getenv("XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL")
    missing: list[str] = []
    if not token:
        missing.append("Set XAGENT_GITHUB_TOKEN or GITHUB_TOKEN.")
    if not target:
        missing.append("Set XAGENT_GITHUB_TEST_ISSUE_URL to a disposable test issue URL.")
    if missing:
        return ExternalCheck(
            name="github_issue_to_pr_execute_preflight",
            status="skipped",
            missing=missing,
            details={"token_configured": bool(token), "issue_url_configured": bool(target)},
        )

    dry_run = run_github_dry_run_smoke(target)
    if dry_run.status != "passed":
        return ExternalCheck(
            name="github_issue_to_pr_execute_preflight",
            status="failed",
            details={"token_configured": True, "issue_url": target, "dry_run": dry_run.to_dict()},
            error="Execute preflight requires a valid dry-run plan first.",
        )

    try:
        api_url, repo_full_name, issue_number = _github_issue_api_url(target)
        payload = _read_github_issue(issue_url=target, token=token, timeout_seconds=15.0)
        read_probe = {
            "status": "passed" if str(payload.get("state") or "") == "open" else "failed",
            "api_url": api_url,
            "repo_full_name": repo_full_name,
            "issue_number": issue_number,
            "state": payload.get("state"),
            "title_sample": str(payload.get("title") or "")[:120],
        }
        if read_probe["status"] != "passed":
            return ExternalCheck(
                name="github_issue_to_pr_execute_preflight",
                status="failed",
                details={
                    "token_configured": True,
                    "issue_url": target,
                    "dry_run_status": dry_run.status,
                    "read_probe": read_probe,
                    "mutation_performed": False,
                },
                error=f"GitHub read-only issue probe did not confirm state=open: state={read_probe['state']}.",
            )
    except Exception as exc:  # noqa: BLE001 - report token/resource readiness failure
        return ExternalCheck(
            name="github_issue_to_pr_execute_preflight",
            status="failed",
            details={"token_configured": True, "issue_url": target, "dry_run_status": dry_run.status},
            error=f"GitHub read-only issue probe failed: {exc}",
        )

    try:
        repo_api_url = _github_repo_api_url(repo_full_name)
        repo_payload = _read_github_repo_permissions(
            repo_full_name=repo_full_name,
            token=token,
            timeout_seconds=15.0,
        )
        permissions = repo_payload["permissions"]
        push_allowed = permissions.get("push") is True
        owner_context_permissions = [
            name for name in ("admin", "maintain") if permissions.get(name) is True
        ]
        permission_probe = {
            "status": "passed" if push_allowed else "failed",
            "api_url": repo_api_url,
            "repo_full_name": repo_full_name,
            "default_branch": repo_payload.get("default_branch"),
            "permissions": {
                "admin": permissions.get("admin") is True,
                "maintain": permissions.get("maintain") is True,
                "push": push_allowed,
                "triage": permissions.get("triage") is True,
                "pull": permissions.get("pull") is True,
            },
            "least_privilege": True,
            "owner_context_permissions": owner_context_permissions,
            "owner_context_note": (
                "GitHub repository API reports effective user permissions; "
                "admin/maintain can appear for repository owners even when a fine-grained token is repository-scoped."
            )
            if owner_context_permissions
            else "",
        }
        if not push_allowed:
            return ExternalCheck(
                name="github_issue_to_pr_execute_preflight",
                status="failed",
                details={
                    "token_configured": True,
                    "issue_url": target,
                    "dry_run_status": dry_run.status,
                    "read_probe": read_probe,
                    "permission_probe": permission_probe,
                    "mutation_performed": False,
                },
                error="GitHub repository permission probe did not confirm permissions.push=true.",
            )
    except Exception as exc:  # noqa: BLE001 - report token/resource readiness failure
        return ExternalCheck(
            name="github_issue_to_pr_execute_preflight",
            status="failed",
            details={
                "token_configured": True,
                "issue_url": target,
                "dry_run_status": dry_run.status,
                "read_probe": read_probe,
                "mutation_performed": False,
            },
            error=f"GitHub read-only repository permission probe failed: {exc}",
        )

    return ExternalCheck(
        name="github_issue_to_pr_execute_preflight",
        status="passed",
        details={
            "token_configured": True,
            "token": _redact(token),
            "issue_url": target,
            "dry_run_status": dry_run.status,
            "read_probe": read_probe,
            "permission_probe": permission_probe,
            "mutation_performed": False,
            "next_step": "Run execute only in a disposable test repository with an explicitly configured executor.",
        },
    )


def run_github_actions_preflight(run_url: str | None = None, *, enabled: bool) -> ExternalCheck:
    """Verify hosted GitHub Actions run evidence without mutating GitHub."""

    if not enabled:
        return ExternalCheck(
            name="hosted_github_actions_run",
            status="skipped",
            missing=["Pass --github-actions-preflight to verify the hosted Commercial RC workflow run."],
        )

    token = _getenv("XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN")
    target = run_url or _getenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL")
    expected_head_sha = _getenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA").strip()
    missing: list[str] = []
    if not token:
        missing.append("Set XAGENT_GITHUB_TOKEN or GITHUB_TOKEN for read-only GitHub Actions run verification.")
    if not target:
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL to the hosted Commercial RC workflow run URL.")
    if not expected_head_sha:
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to the commit SHA used by the hosted RC workflow run.")
    elif not _valid_git_commit_sha(expected_head_sha):
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to a 40-character hex git commit SHA.")
    if missing:
        return ExternalCheck(
            name="hosted_github_actions_run",
            status="skipped",
            missing=missing,
            details={
                "token_configured": bool(token),
                "run_url_configured": bool(target),
                "expected_head_sha_configured": bool(expected_head_sha),
                "expected_head_sha_valid": _valid_git_commit_sha(expected_head_sha) if expected_head_sha else False,
            },
        )

    try:
        api_url, repo_full_name, run_id = _github_actions_run_api_url(target)
        jobs_api_url, _, _ = _github_actions_run_jobs_api_url(target)
        artifacts_api_url, _, _ = _github_actions_run_artifacts_api_url(target)
        payload = _read_github_actions_run(run_url=target, token=token, timeout_seconds=15.0)
        run_status = str(payload.get("status") or "")
        conclusion = str(payload.get("conclusion") or "")
        html_url = str(payload.get("html_url") or target)
        workflow_name = str(payload.get("name") or "")
        workflow_path = str(payload.get("path") or "")
        head_sha = str(payload.get("head_sha") or "")
        head_branch = str(payload.get("head_branch") or "")
        run_ok = run_status == "completed" and conclusion == "success"
        workflow_verified = (
            workflow_name == REQUIRED_HOSTED_ACTIONS_WORKFLOW_NAME
            and workflow_path == REQUIRED_HOSTED_ACTIONS_WORKFLOW_PATH
        )
        head_sha_verified = _valid_git_commit_sha(head_sha) and head_sha.lower() == expected_head_sha.lower()
        job_probe: dict[str, Any] = {
            "verified": False,
            "required_jobs": {
                name: {"found": False, "status": "", "conclusion": "", "html_url": ""}
                for name in REQUIRED_HOSTED_ACTIONS_JOBS
            },
            "missing_or_failed_jobs": list(REQUIRED_HOSTED_ACTIONS_JOBS),
        }
        artifact_probe: dict[str, Any] = {
            "verified": False,
            "required_artifact": REQUIRED_HOSTED_ACTIONS_ARTIFACT,
            "artifact_names": [],
            "missing_artifact": REQUIRED_HOSTED_ACTIONS_ARTIFACT,
        }
        if run_ok and workflow_verified and head_sha_verified:
            jobs_payload = _read_github_actions_jobs(run_url=target, token=token, timeout_seconds=15.0)
            artifacts_payload = _read_github_actions_artifacts(run_url=target, token=token, timeout_seconds=15.0)
            job_probe = _required_github_actions_job_probe(jobs_payload["jobs"])
            artifact_probe = _required_github_actions_artifact_probe(artifacts_payload["artifacts"])
        ok = (
            run_ok
            and workflow_verified
            and head_sha_verified
            and job_probe["verified"] is True
            and artifact_probe["verified"] is True
        )
        problems: list[str] = []
        if not run_ok:
            problems.append(f"run status={run_status}, conclusion={conclusion}")
        if not workflow_verified:
            problems.append(
                "workflow identity did not match "
                f"{REQUIRED_HOSTED_ACTIONS_WORKFLOW_NAME} at {REQUIRED_HOSTED_ACTIONS_WORKFLOW_PATH}"
            )
        if not head_sha_verified:
            problems.append(f"head_sha mismatch: expected={expected_head_sha}, actual={head_sha or '<missing>'}")
        if job_probe["verified"] is not True:
            problems.append(f"required jobs not successful: {', '.join(job_probe['missing_or_failed_jobs'])}")
        if artifact_probe["verified"] is not True:
            problems.append(f"required artifact missing: {artifact_probe['missing_artifact']}")
        return ExternalCheck(
            name="hosted_github_actions_run",
            status="passed" if ok else "failed",
            details={
                "token_configured": True,
                "token": _redact(token),
                "run_url": target,
                "api_url": api_url,
                "repo_full_name": repo_full_name,
                "run_id": run_id,
                "html_url": html_url,
                "workflow_name": workflow_name,
                "workflow_path": workflow_path,
                "workflow_verified": workflow_verified,
                "expected_head_sha": expected_head_sha,
                "head_sha": head_sha,
                "head_sha_verified": head_sha_verified,
                "head_branch": head_branch,
                "jobs_api_url": jobs_api_url,
                "jobs_verified": job_probe["verified"],
                "required_jobs": job_probe["required_jobs"],
                "artifacts_api_url": artifacts_api_url,
                "artifact_verified": artifact_probe["verified"],
                "required_artifact": artifact_probe["required_artifact"],
                "artifact_names": artifact_probe["artifact_names"],
                "run_status": run_status,
                "conclusion": conclusion,
                "mutation_performed": False,
            },
            error=None if ok else f"Hosted GitHub Actions evidence is incomplete: {'; '.join(problems)}.",
        )
    except Exception as exc:  # noqa: BLE001 - report token/resource readiness failure
        return ExternalCheck(
            name="hosted_github_actions_run",
            status="failed",
            details={"token_configured": True, "run_url": target, "mutation_performed": False},
            error=f"GitHub Actions read-only run probe failed: {exc}",
        )


async def run_external_smoke(
    *,
    provider: str | None = None,
    issue_url: str | None = None,
    checks: list[str] | None = None,
    github_execute_preflight: bool = False,
    github_actions_preflight: bool = False,
    telegram_live_preflight: bool = False,
    require_configured: bool = False,
    timeout_seconds: float = 20.0,
) -> ExternalSmokeReport:
    start = time.perf_counter()
    selected = set(checks or DEFAULT_CHECKS)
    invalid = sorted(selected.difference(CHECK_CHOICES))
    if invalid:
        raise ValueError(f"unsupported external smoke checks: {', '.join(invalid)}")

    results: list[ExternalCheck] = []
    if "provider" in selected:
        results.append(await run_provider_smoke(provider, timeout_seconds=timeout_seconds))
    if "feishu_webhook_contract" in selected:
        results.append(await run_feishu_contract_smoke())
    if "telegram_webhook_contract" in selected:
        results.append(await run_telegram_contract_smoke())
    if "telegram_bot_preflight" in selected:
        results.append(run_telegram_bot_preflight(enabled=telegram_live_preflight, timeout_seconds=timeout_seconds))
    if "github_issue_to_pr_dry_run" in selected:
        results.append(run_github_dry_run_smoke(issue_url))
    if "github_issue_to_pr_execute_preflight" in selected:
        results.append(run_github_execute_preflight(issue_url, enabled=github_execute_preflight))
    if "hosted_github_actions_run" in selected:
        results.append(run_github_actions_preflight(enabled=github_actions_preflight))

    failed = [check for check in results if check.status == "failed"]
    skipped = [check for check in results if check.status == "skipped"]
    status = "failed" if failed or (require_configured and skipped) else "passed"
    return ExternalSmokeReport(
        status=status,
        generated_at=_utc_now(),
        duration_seconds=round(time.perf_counter() - start, 3),
        require_configured=require_configured,
        checks=results,
    )


def write_report(report: ExternalSmokeReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run X-Agent commercial RC external smoke checks")
    parser.add_argument("--provider", choices=["mock", "openai", "deepseek", "anthropic", "ollama", "local"])
    parser.add_argument(
        "--check",
        action="append",
        choices=sorted(CHECK_CHOICES),
        help="run only this check; repeat to run a scoped subset instead of the full smoke suite",
    )
    parser.add_argument("--github-issue-url", help="Disposable test GitHub issue URL for issue-to-PR dry-run")
    parser.add_argument("--github-execute-preflight", action="store_true", help="verify execute-mode prerequisites without writes")
    parser.add_argument("--github-actions-preflight", action="store_true", help="verify hosted Commercial RC GitHub Actions run without writes")
    parser.add_argument("--telegram-live-preflight", action="store_true", help="verify Telegram bot token with getMe without sending messages")
    parser.add_argument("--require-configured", action="store_true", help="fail if any external check is skipped")
    parser.add_argument("--timeout", type=float, default=20.0, help="provider/local-model timeout in seconds")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    report = await run_external_smoke(
        provider=args.provider,
        issue_url=args.github_issue_url,
        checks=args.check,
        github_execute_preflight=args.github_execute_preflight,
        github_actions_preflight=args.github_actions_preflight,
        telegram_live_preflight=args.telegram_live_preflight,
        require_configured=args.require_configured,
        timeout_seconds=args.timeout,
    )
    write_report(report, args.output)
    print(f"RC external smoke status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        suffix = f" ({check.error})" if check.error else ""
        print(f"- {check.name}: {check.status}{suffix}")
        if check.missing:
            for item in check.missing:
                print(f"  missing: {item}")
    return 0 if report.status == "passed" else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
