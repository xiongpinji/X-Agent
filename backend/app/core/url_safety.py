from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


LOCAL_URL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PLACEHOLDER_URL_TOKENS = ("<", ">", "example.", ".example", "placeholder", "replace-me", "todo")
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "code",
    "key",
    "password",
    "secret",
    "signature",
    "sig",
    "token",
}


def validate_external_https_url(value: Any) -> dict[str, Any]:
    error = external_https_url_error_reason(value)
    return {"ok": error is None, "error": error}


def browser_navigation_url_error_reason(
    value: Any,
    *,
    resolver: Any | None = None,
) -> str | None:
    if not isinstance(value, str) or not value:
        return "missing"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return "must use http or https scheme"
    if not parsed.netloc or not parsed.hostname:
        return "must include a host"
    if parsed.username or parsed.password:
        return "must not include credentials"

    host = parsed.hostname.lower()
    if host in LOCAL_URL_HOSTS or host == "0.0.0.0":
        return "must not point at localhost"

    literal_ip = _parse_ip_address(host)
    if literal_ip is not None:
        return "must not point at a private or local address" if _is_local_ip_address(literal_ip) else None

    resolve = resolver or socket.getaddrinfo
    try:
        infos = resolve(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        return "host could not be resolved"

    resolved_ips = _addresses_from_getaddrinfo(infos)
    if not resolved_ips:
        return "host could not be resolved"
    if any(_is_local_ip_address(address) for address in resolved_ips):
        return "resolved host points at a private or local address"
    return None


def is_browser_navigation_url_allowed(value: Any, *, resolver: Any | None = None) -> bool:
    return browser_navigation_url_error_reason(value, resolver=resolver) is None


def external_https_url_error(value: Any, *, field_name: str = "url") -> str | None:
    error = external_https_url_error_reason(value)
    if error is None:
        return None
    if error == "missing":
        return f"{field_name} is required"
    return f"{field_name} {error}"


def external_https_url_error_reason(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return "missing"

    parsed = urlparse(value)
    if parsed.scheme != "https":
        return "must use https scheme"
    if not parsed.netloc or not parsed.hostname:
        return "must include a host"
    if parsed.username or parsed.password:
        return "must not include credentials"

    host = parsed.hostname.lower()
    if host in LOCAL_URL_HOSTS:
        return "must not point at localhost"

    try:
        ip_address = ipaddress.ip_address(host)
    except ValueError:
        ip_address = None
    if ip_address is not None and _is_local_ip_address(ip_address):
        return "must not point at a private or local address"

    lowered = value.lower()
    if any(token in lowered for token in PLACEHOLDER_URL_TOKENS):
        return "must not be a placeholder URL"

    sensitive_keys = [
        key
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
        if is_sensitive_query_key(key)
    ]
    if sensitive_keys:
        return "must not include sensitive query parameters"
    return None


def sanitize_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = host
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    if parsed.query:
        query = urlencode(
            [
                (key, "<redacted>" if is_sensitive_query_key(key) else query_value)
                for key, query_value in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        parsed = parsed._replace(query=query)
    return urlunparse(parsed)


def is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in SENSITIVE_QUERY_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_signature")
    )


def _is_local_ip_address(value: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        value.is_private
        or value.is_loopback
        or value.is_link_local
        or value.is_unspecified
        or value.is_reserved
        or value.is_multicast
    )


def _parse_ip_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _addresses_from_getaddrinfo(infos: list[Any]) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            sockaddr = info[4]
            address = sockaddr[0]
        except (IndexError, TypeError):
            continue
        parsed = _parse_ip_address(address)
        if parsed is not None:
            addresses.append(parsed)
    return addresses
