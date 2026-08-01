"""strutils 工具库的单元测试。

覆盖 transform 模块的四个命名转换函数与 validate 模块的四个验证函数。
"""

from __future__ import annotations

import unittest

from strutils import (
    camel_case,
    is_email,
    is_ipv4,
    is_uuid,
    is_url,
    kebab_case,
    pascal_case,
    snake_case,
)


class TestTransform(unittest.TestCase):
    """测试命名格式转换函数。"""

    def test_camel_case_from_snake(self) -> None:
        """camel_case 应从 snake_case 正确转换。"""
        self.assertEqual(camel_case("hello_world"), "helloWorld")

    def test_camel_case_from_kebab(self) -> None:
        """camel_case 应从 kebab-case 正确转换。"""
        self.assertEqual(camel_case("hello-world"), "helloWorld")

    def test_snake_case_from_camel(self) -> None:
        """snake_case 应从 camelCase 正确转换。"""
        self.assertEqual(snake_case("helloWorld"), "hello_world")

    def test_snake_case_from_pascal(self) -> None:
        """snake_case 应从 PascalCase 正确转换。"""
        self.assertEqual(snake_case("HelloWorld"), "hello_world")

    def test_kebab_case_from_camel(self) -> None:
        """kebab_case 应从 camelCase 正确转换。"""
        self.assertEqual(kebab_case("camelCase"), "camel-case")

    def test_pascal_case_from_snake(self) -> None:
        """pascal_case 应从 snake_case 正确转换。"""
        self.assertEqual(pascal_case("hello_world"), "HelloWorld")

    def test_pascal_case_from_kebab(self) -> None:
        """pascal_case 应从 kebab-case 正确转换。"""
        self.assertEqual(pascal_case("kebab-case"), "KebabCase")

    def test_empty_string(self) -> None:
        """空字符串应返回空字符串。"""
        self.assertEqual(camel_case(""), "")
        self.assertEqual(snake_case(""), "")
        self.assertEqual(kebab_case(""), "")
        self.assertEqual(pascal_case(""), "")


class TestValidate(unittest.TestCase):
    """测试字符串验证函数。"""

    def test_is_email_valid(self) -> None:
        """is_email 应识别合法邮箱。"""
        self.assertTrue(is_email("user@example.com"))
        self.assertTrue(is_email("first.last+tag@sub.domain.org"))

    def test_is_email_invalid(self) -> None:
        """is_email 应拒绝非法邮箱。"""
        self.assertFalse(is_email("not-an-email"))
        self.assertFalse(is_email("user@nodot"))

    def test_is_url_valid(self) -> None:
        """is_url 应识别合法 URL。"""
        self.assertTrue(is_url("https://example.com/path"))
        self.assertTrue(is_url("http://localhost:8080"))

    def test_is_url_invalid(self) -> None:
        """is_url 应拒绝缺少协议前缀的字符串。"""
        self.assertFalse(is_url("example.com"))

    def test_is_ipv4_valid(self) -> None:
        """is_ipv4 应识别合法 IPv4 地址。"""
        self.assertTrue(is_ipv4("192.168.1.1"))
        self.assertTrue(is_ipv4("255.255.255.255"))

    def test_is_ipv4_invalid(self) -> None:
        """is_ipv4 应拒绝越界值。"""
        self.assertFalse(is_ipv4("256.1.1.1"))
        self.assertFalse(is_ipv4("192.168.1"))

    def test_is_uuid_valid(self) -> None:
        """is_uuid 应识别合法 UUID。"""
        self.assertTrue(is_uuid("123e4567-e89b-12d3-a456-426614174000"))

    def test_is_uuid_invalid(self) -> None:
        """is_uuid 应拒绝非法 UUID。"""
        self.assertFalse(is_uuid("not-a-uuid"))
        self.assertFalse(is_uuid("123e4567-e89b-12d3-a456"))


if __name__ == "__main__":
    unittest.main()
