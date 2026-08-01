"""字符串命名格式转换工具模块。

提供 camel_case、snake_case、kebab_case、pascal_case 四种命名转换函数。
"""

from __future__ import annotations

import re
from typing import List

__all__ = ["camel_case", "snake_case", "kebab_case", "pascal_case"]

# 匹配单词边界：下划线、连字符、空格或驼峰大小写转换点
_WORD_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])|[\s_\-]+")


def _split_words(text: str) -> List[str]:
    """将输入字符串拆分为单词列表。

    支持 snake_case、kebab-case、camelCase、PascalCase、空格分隔等格式，
    统一拆分为小写单词列表。

    Args:
        text: 待拆分的字符串。

    Returns:
        拆分后的小写单词列表。
    """
    if not text:
        return []
    # 在驼峰大小写转换点处插入分隔符
    spaced = _WORD_BOUNDARY_RE.sub(lambda m: m.group(1) + " " + m.group(2) if m.group(2) else " ", text)
    words = [w for w in spaced.split(" ") if w]
    return [w.lower() for w in words]


def camel_case(text: str) -> str:
    """将字符串转换为 camelCase（小驼峰命名）。

    首单词小写，后续每个单词首字母大写，其余字符去分隔符连接。

    Args:
        text: 任意格式的输入字符串。

    Returns:
        转换后的 camelCase 字符串。空输入返回空字符串。

    Examples:
        >>> camel_case("hello_world")
        'helloWorld'
        >>> camel_case("Hello-World")
        'helloWorld'
    """
    words = _split_words(text)
    if not words:
        return ""
    return words[0] + "".join(w.capitalize() for w in words[1:])


def snake_case(text: str) -> str:
    """将字符串转换为 snake_case（下划线命名）。

    所有单词小写，并用下划线连接。

    Args:
        text: 任意格式的输入字符串。

    Returns:
        转换后的 snake_case 字符串。空输入返回空字符串。

    Examples:
        >>> snake_case("HelloWorld")
        'hello_world'
        >>> snake_case("kebab-case")
        'kebab_case'
    """
    words = _split_words(text)
    return "_".join(words)


def kebab_case(text: str) -> str:
    """将字符串转换为 kebab-case（连字符命名）。

    所有单词小写，并用连字符连接。

    Args:
        text: 任意格式的输入字符串。

    Returns:
        转换后的 kebab-case 字符串。空输入返回空字符串。

    Examples:
        >>> kebab_case("camelCase")
        'camel-case'
        >>> kebab_case("snake_case")
        'snake-case'
    """
    words = _split_words(text)
    return "-".join(words)


def pascal_case(text: str) -> str:
    """将字符串转换为 PascalCase（大驼峰命名）。

    所有单词首字母大写，其余字符去分隔符连接。

    Args:
        text: 任意格式的输入字符串。

    Returns:
        转换后的 PascalCase 字符串。空输入返回空字符串。

    Examples:
        >>> pascal_case("hello_world")
        'HelloWorld'
        >>> pascal_case("kebab-case")
        'KebabCase'
    """
    words = _split_words(text)
    return "".join(w.capitalize() for w in words)
