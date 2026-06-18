from __future__ import annotations

from backend.app.core.output_redaction import (
    coerce_output_text,
    looks_like_secret_leak,
    output_tail,
    redact_output_text,
    redact_payload,
)


def test_redact_output_text_masks_secret_assignments_and_tokens() -> None:
    text = "OPENAI_API_KEY=sk-liveSecretValue123 token:abc123 sk-tokenvalue12345"

    redacted = redact_output_text(text)

    assert "sk-liveSecretValue123" not in redacted
    assert "abc123" not in redacted
    assert "sk-tokenvalue12345" not in redacted
    assert "OPENAI_API_KEY=<redacted>" in redacted
    assert "token:<redacted>" in redacted
    assert "<redacted-token>" in redacted


def test_redact_output_text_replaces_explicit_and_env_secret_values() -> None:
    redacted = redact_output_text(
        "stdout contains alpha-secret and beta-secret",
        env={"XAGENT_AUDIT_HMAC_SECRET": "beta-secret"},
        secret_values=["alpha-secret"],
    )

    assert redacted == "stdout contains <redacted> and <redacted>"


def test_redact_payload_recurses_dicts_lists_and_tuples() -> None:
    payload = {
        "stdout_tail": "password=super-secret",
        "items": ["token=one", {"stderr": "created sk-testtoken123456"}],
        "tuple": ("secret:two", 3),
    }

    redacted = redact_payload(payload)

    assert redacted == {
        "stdout_tail": "password=<redacted>",
        "items": ["token=<redacted>", {"stderr": "created <redacted-token>"}],
        "tuple": ("secret:<redacted>", 3),
    }


def test_output_tail_redacts_before_cropping() -> None:
    text = "prefix " + ("x" * 20) + " token=very-secret-value"

    tail = output_tail(text, limit=16)

    assert tail == "token=<redacted>"
    assert "very-secret-value" not in tail


def test_output_tail_can_skip_redaction() -> None:
    assert output_tail("abcdef", limit=3, redact=False) == "def"


def test_looks_like_secret_leak_detects_assignments_and_tokens() -> None:
    assert looks_like_secret_leak("XAGENT_LLM_API_KEY=value") is True
    assert looks_like_secret_leak("created pk-secretvalue12345") is True
    assert looks_like_secret_leak("ordinary output") is False


def test_coerce_output_text_handles_bytes_and_none() -> None:
    assert coerce_output_text(None) == ""
    assert coerce_output_text(b"ok\xff") == "ok\ufffd"
