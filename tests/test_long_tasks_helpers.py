from backend.app.core.long_tasks_helpers import _context_string_list, _unique_strings


def test_context_string_list_normalizes_lists_only() -> None:
    assert _context_string_list([" a ", "", None, 3]) == ["a", "None", "3"]
    assert _context_string_list("not-a-list") == []
    assert _context_string_list(None) == []


def test_context_string_list_caps_at_twenty_items() -> None:
    values = [f" item-{index} " for index in range(25)]

    result = _context_string_list(values)

    assert result == [f"item-{index}" for index in range(20)]


def test_unique_strings_preserves_order_and_removes_empty_duplicates() -> None:
    result = _unique_strings([" app.py ", "tests/test_app.py", "app.py", "", None, " docs.md "])

    assert result == ["app.py", "tests/test_app.py", "docs.md"]
