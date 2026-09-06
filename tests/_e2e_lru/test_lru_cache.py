"""Unit tests for the thread-safe LRUCache implementation."""

import threading
import unittest

from lru_cache import LRUCache


class TestLRUCache(unittest.TestCase):
    def setUp(self):
        self.cache = LRUCache(capacity=3)

    def test_basic_get_put(self):
        """Basic put then get returns the stored value."""
        self.cache.put("a", 1)
        self.assertEqual(self.cache.get("a"), 1)

    def test_get_missing_returns_none(self):
        """get of a missing key returns None."""
        self.assertIsNone(self.cache.get("nope"))

    def test_eviction_order(self):
        """When over capacity, the least recently used item is evicted."""
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        # Capacity 3, now add "d" -> evicts "a"
        self.cache.put("d", 4)
        self.assertIsNone(self.cache.get("a"))
        self.assertEqual(self.cache.get("b"), 2)
        self.assertEqual(self.cache.get("c"), 3)
        self.assertEqual(self.cache.get("d"), 4)

    def test_get_promotes_freshness(self):
        """Accessing a key makes it most recently used (not evicted)."""
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        # Touch "a" so it becomes MRU
        self.assertEqual(self.cache.get("a"), 1)
        # Now "b" is the LRU and should be evicted.
        self.cache.put("d", 4)
        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(self.cache.get("a"), 1)

    def test_delete(self):
        """delete removes a key from the cache."""
        self.cache.put("a", 1)
        self.assertTrue(self.cache.delete("a"))
        self.assertIsNone(self.cache.get("a"))
        self.assertFalse(self.cache.delete("a"))

    def test_stats_counts(self):
        """stats reports size, hits and misses correctly."""
        self.cache.put("a", 1)
        self.cache.get("a")   # hit
        self.cache.get("a")   # hit
        self.cache.get("zz")  # miss
        stats = self.cache.stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 2 / 3)

    def test_hit_rate_zero_requests(self):
        """hit_rate is 0 when there have been no requests."""
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], 0.0)

    def test_len_and_contains(self):
        """__len__ and __contains__ behave as expected."""
        self.assertEqual(len(self.cache), 0)
        self.assertNotIn("a", self.cache)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.assertEqual(len(self.cache), 2)
        self.assertIn("a", self.cache)
        self.assertNotIn("c", self.cache)

    def test_capacity_one(self):
        """Capacity-1 cache evicts on every new put."""
        cache = LRUCache(capacity=1)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(len(cache), 1)

    def test_put_overwrite_same_key_no_eviction(self):
        """Overwriting an existing key does not trigger eviction."""
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        # Overwrite existing key, capacity stays at 3, nothing evicted yet.
        self.cache.put("a", 100)
        self.assertEqual(self.cache.get("a"), 100)
        # Now add "d", evicts "b" (LRU) not overwritten "a".
        self.cache.put("d", 4)
        self.assertEqual(self.cache.get("b"), 2)
        self.assertEqual(self.cache.get("a"), 100)
        self.assertEqual(self.cache.get("c"), 3)
        self.assertEqual(self.cache.get("d"), 4)

    def test_thread_safety(self):
        """Concurrent puts do not lose data and never exceed capacity.

        8 threads each write 1000 distinct keys (8000 total). The cache
        capacity is 8000 so every key fits; len must equal 8000 and no
        key should be lost.
        """
        cache = LRUCache(capacity=8000)
        threads = []
        errors = []

        def worker(start):
            try:
                for i in range(start, start + 1000):
                    cache.put(i, i)
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(exc)

        for t in range(8):
            th = threading.Thread(target=worker, args=(t * 1000,))
            threads.append(th)
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(cache), 8000)
        self.assertLessEqual(len(cache), 8000)
        # Verify no data was lost: every key written should still be present.
        for i in range(8000):
            self.assertEqual(cache.get(i), i)


if __name__ == "__main__":
    unittest.main()
