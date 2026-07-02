from __future__ import annotations

import pytest

from backend.app.core.url_safety import (
    browser_navigation_url_error_reason,
    external_https_url_error,
    is_browser_navigation_url_allowed,
    is_sensitive_query_key,
    sanitize_url,
    validate_external_https_url,
)


def test_validate_external_https_url_accepts_external_https_url() -> None:
    result = validate_external_https_url("https://github.com/acme/x-agent/actions/runs/1?attempt=1")

    assert result == {"ok": True, "error": None}


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("", "missing"),
        (None, "missing"),
        ("http://github.com/acme/x-agent", "must use https scheme"),
        ("https:///missing-host", "must include a host"),
        ("https://user:pass@github.com/acme/x-agent", "must not include credentials"),
        ("https://localhost/acme/x-agent", "must not point at localhost"),
        ("https://127.0.0.1/acme/x-agent", "must not point at localhost"),
        ("https://[::1]/acme/x-agent", "must not point at localhost"),
        ("https://10.0.0.5/acme/x-agent", "must not point at a private or local address"),
        ("https://169.254.1.1/acme/x-agent", "must not point at a private or local address"),
        ("https://example.com/acme/x-agent", "must not be a placeholder URL"),
        ("https://github.com/<org>/x-agent", "must not be a placeholder URL"),
        ("https://github.com/acme/x-agent?token=secret", "must not include sensitive query parameters"),
        ("https://github.com/acme/x-agent?artifact_signature=secret", "must not include sensitive query parameters"),
    ],
)
def test_validate_external_https_url_rejects_unsafe_url_shapes(value: object, error: str) -> None:
    result = validate_external_https_url(value)

    assert result == {"ok": False, "error": error}


def test_external_https_url_error_prefixes_field_name() -> None:
    assert external_https_url_error("", field_name="remote_upload_url") == "remote_upload_url is required"
    assert external_https_url_error("http://github.com/a", field_name="remote_upload_url") == (
        "remote_upload_url must use https scheme"
    )


def test_sanitize_url_removes_credentials_and_redacts_sensitive_query_values() -> None:
    sanitized = sanitize_url("https://user:password@github.com/acme/x-agent?token=secret&attempt=1")

    assert sanitized == "https://github.com/acme/x-agent?token=%3Credacted%3E&attempt=1"
    assert "password" not in sanitized
    assert "secret" not in sanitized


def test_sanitize_url_preserves_ipv6_host_and_port_without_credentials() -> None:
    sanitized = sanitize_url("https://user:pass@[2001:4860:4860::8888]:443/path?artifact-signature=sig")

    assert sanitized == "https://[2001:4860:4860::8888]:443/path?artifact-signature=%3Credacted%3E"


def test_sensitive_query_key_matches_aliases_and_suffixes() -> None:
    assert is_sensitive_query_key("api-key") is True
    assert is_sensitive_query_key("artifact_signature") is True
    assert is_sensitive_query_key("refresh-token") is True
    assert is_sensitive_query_key("attempt") is False


def test_browser_navigation_url_rejects_dns_rebinding_to_local_address() -> None:
    def resolver(host: str, port: int, type=None):  # noqa: ANN001, A002
        assert host == "rebind.example.test"
        assert port == 443
        return [(None, None, None, "", ("127.0.0.1", port))]

    assert (
        browser_navigation_url_error_reason(
            "https://rebind.example.test/path",
            resolver=resolver,
        )
        == "resolved host points at a private or local address"
    )


def test_browser_navigation_url_allows_public_resolved_address() -> None:
    def resolver(host: str, port: int, type=None):  # noqa: ANN001, A002
        assert host == "public.example.test"
        return [(None, None, None, "", ("93.184.216.34", port))]

    assert is_browser_navigation_url_allowed("https://public.example.test", resolver=resolver) is True


def test_browser_navigation_url_fails_closed_when_dns_resolution_fails() -> None:
    def resolver(host: str, port: int, type=None):  # noqa: ANN001, A002
        raise OSError("dns unavailable")

    assert (
        browser_navigation_url_error_reason(
            "https://unresolved.example.test",
            resolver=resolver,
        )
        == "host could not be resolved"
    )
