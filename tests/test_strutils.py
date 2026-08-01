"""Tests for strutils.slugify."""

from strutils import slugify


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_multiple_spaces():
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_slugify_special_chars():
    assert slugify("Special!@#Chars") == "specialchars"


def test_slugify_empty_string():
    assert slugify("") == ""


def test_slugify_already_slugged():
    assert slugify("already-slugged") == "already-slugged"
