"""Unit tests for the HashMap implementation."""

import pytest

from hash_map import HashMap


def test_put_get_basic():
    m = HashMap()
    m["a"] = 1
    m["b"] = 2
    assert m["a"] == 1
    assert m["b"] == 2
    assert len(m) == 2


def test_overwrite_existing_key():
    m = HashMap()
    m["a"] = 1
    m["a"] = 2
    assert m["a"] == 2
    assert len(m) == 1


def test_missing_key_raises_keyerror():
    m = HashMap()
    with pytest.raises(KeyError):
        m["nope"]  # noqa: B018


def test_get_with_default():
    m = HashMap()
    assert m.get("missing") is None
    assert m.get("missing", 42) == 42
    m["present"] = 7
    assert m.get("present", 42) == 7


def test_contains():
    m = HashMap()
    m["x"] = 1
    assert "x" in m
    assert "y" not in m


def test_deletion():
    m = HashMap()
    m["a"] = 1
    m["b"] = 2
    del m["a"]
    assert len(m) == 1
    assert "a" not in m
    assert "b" in m
    with pytest.raises(KeyError):
        del m["a"]


def test_pop():
    m = HashMap()
    m["a"] = 1
    assert m.pop("a") == 1
    assert len(m) == 0
    assert m.pop("missing", 99) == 99
    with pytest.raises(KeyError):
        m.pop("missing")


def test_setdefault():
    m = HashMap()
    assert m.setdefault("a", 10) == 10
    assert m["a"] == 10
    assert m.setdefault("a", 20) == 10  # existing value preserved


def test_iteration_and_bulk():
    m = HashMap()
    for i in range(100):
        m[f"key_{i}"] = i
    assert len(m) == 100
    assert sorted(int(k.split("_")[1]) for k in m) == list(range(100))


def test_many_collisions_resize():
    # Force many entries to trigger growth and rehashing.
    m = HashMap(capacity=4, load_factor=0.75)
    for i in range(1000):
        m[i] = i * 2
    assert len(m) == 1000
    for i in range(1000):
        assert m[i] == i * 2


def test_clear():
    m = HashMap()
    m["a"] = 1
    m["b"] = 2
    m.clear()
    assert len(m) == 0
    assert "a" not in m


def test_keys_values_items():
    m = HashMap()
    m["a"] = 1
    m["b"] = 2
    assert sorted(m.keys()) == ["a", "b"]
    assert sorted(m.values()) == [1, 2]
    assert sorted(m.items()) == [("a", 1), ("b", 2)]


def test_equality():
    a = HashMap()
    b = HashMap()
    a["x"] = 1
    b["x"] = 1
    assert a == b
    b["y"] = 2
    assert a != b


def test_capacity_and_load_factor():
    m = HashMap(capacity=8)
    assert m.capacity() == 8
    assert m.load_factor() == 0.0
    for i in range(10):
        m[i] = i
    assert m.capacity() >= 8
    assert m.load_factor() > 0.0


def test_invalid_arguments():
    with pytest.raises(ValueError):
        HashMap(capacity=0)
    with pytest.raises(ValueError):
        HashMap(load_factor=0)
    with pytest.raises(ValueError):
        HashMap(load_factor=1.5)


def test_repr():
    m = HashMap()
    m["a"] = 1
    assert "a" in repr(m)
    assert "1" in repr(m)
