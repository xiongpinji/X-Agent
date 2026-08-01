"""字符串工具库包入口。

导出所有转换与验证函数，方便使用者通过 ``strutils`` 直接访问。
"""

from __future__ import annotations

from .transform import camel_case, kebab_case, pascal_case, snake_case
from .validate import is_email, is_ipv4, is_uuid, is_url

__all__ = [
    "camel_case",
    "snake_case",
    "kebab_case",
    "pascal_case",
    "is_email",
    "is_url",
    "is_ipv4",
    "is_uuid",
]

__version__ = "0.1.0"
