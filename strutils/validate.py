"""字符串验证工具模块。

提供 is_email、is_url、is_ipv4、is_uuid 四个验证函数。
"""

from __future__ import annotations

import re
import uuid

__all__ = ["is_email", "is_url", "is_ipv4", "is_uuid"]

# 简单但实用的邮箱正则
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# URL 正则：支持 http/https/ftp 等协议
_URL_RE = re.compile(
    r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+\-.]*)://"
    r"(?P<host>[a-zA-Z0-9.\-]+)"
    r"(?::(?P<port>\d+))?"
    r"(?P<path>/[^\s]*)?$"
)

# IPv4 正则：四段 0-255 的点分十进制
_IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
)

# UUID 正则：支持标准 8-4-4-4-12 格式
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_email(value: str) -> bool:
    """判断字符串是否为合法的邮箱地址。

    校验格式为 ``local@domain.tld``，local 部分允许字母、数字及
    ``._%+-`` 等字符，domain 部分需包含至少一个点。

    Args:
        value: 待验证的字符串。

    Returns:
        若为合法邮箱地址返回 True，否则返回 False。

    Examples:
        >>> is_email("user@example.com")
        True
        >>> is_email("not-an-email")
        False
    """
    if not isinstance(value, str):
        return False
    return bool(_EMAIL_RE.match(value.strip()))


def is_url(value: str) -> bool:
    """判断字符串是否为合法的 URL。

    要求包含协议前缀（如 http、https、ftp），并带有主机名。

    Args:
        value: 待验证的字符串。

    Returns:
        若为合法 URL 返回 True，否则返回 False。

    Examples:
        >>> is_url("https://example.com/path")
        True
        >>> is_url("example.com")
        False
    """
    if not isinstance(value, str):
        return False
    return bool(_URL_RE.match(value.strip()))


def is_ipv4(value: str) -> bool:
    """判断字符串是否为合法的 IPv4 地址。

    校验四段 0-255 的点分十进制格式。

    Args:
        value: 待验证的字符串。

    Returns:
        若为合法 IPv4 地址返回 True，否则返回 False。

    Examples:
        >>> is_ipv4("192.168.1.1")
        True
        >>> is_ipv4("256.1.1.1")
        False
    """
    if not isinstance(value, str):
        return False
    return bool(_IPV4_RE.match(value.strip()))


def is_uuid(value: str) -> bool:
    """判断字符串是否为合法的 UUID。

    校验标准 8-4-4-4-12 十六进制格式，不区分大小写。

    Args:
        value: 待验证的字符串。

    Returns:
        若为合法 UUID 返回 True，否则返回 False。

    Examples:
        >>> is_uuid("123e4567-e89b-12d3-a456-426614174000")
        True
        >>> is_uuid("not-a-uuid")
        False
    """
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not _UUID_RE.match(value):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True
