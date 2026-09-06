"""Unit tests for the thread-safe LRUCache implementation."""

import threading
import unittest

from lru_cache import LRUCache


class LRUCacheBasicTests(unittest.TestCase):
    def test_put_and_get(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)

    def test_get_missing_returns_none(self) -> None:
        cache = LRUCache(capacity=3)
        self.assertIsNone(cache.get("missing"))

    def test_put_overwrite_same_key_no_eviction(self) -> None:
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 100)  # overwrite existing key
        self.assertEqual(len(cache), 2)
        self.assertIn("a", cache)
        self.assertIn("b", cache)
        self.assertEqual(cache.get("a"), 100)

    def test_eviction_order_oldest_first(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # should evict "a"
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertIn("c", cache)
        self.assertIn("d", cache)
        self.assertEqual(len(cache), 3)

    def test_get_refreshes_freshness(self) -> None:
        """Accessing an item keeps it fresh; the truly least used is evicted."""
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Refresh "a" so the LRU order becomes b, c, a.
        cache.get("a")
        cache.put("d", 4)  # should evict "b" (the real LRU)
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertIn("c", cache)
        self.assertIn("d", cache)

    def test_get_refresh_after_overwrite(self) -> None:
        """Overwriting an existing key also refreshes its recency."""
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Overwrite "a" -> refreshes its recency; order b, c, a.
        cache.put("a", 10)
        cache.put("d", 4)  # should evict "b"
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertIn("c", cache)
        self.assertIn("d", cache)

    def test_delete_removes_key(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertTrue(cache.delete("a"))
        self.assertNotIn("a", cache)
        self.assertIsNone(cache.get("a"))
        self.assertFalse(cache.delete("a"))  # already gone

    def test_len_and_contains(self) -> None:
        cache = LRUCache(capacity=5)
        self.assertEqual(len(cache), 0)
        self.assertNotIn("x", cache)
        cache.put("x", 1)
        self.assertEqual(len(cache), 1)
        self.assertIn("x", cache)

    def test_capacity_one_boundary(self) -> None:
        cache = LRUCache(capacity=1)
        cache.put("a", 1)
        cache.put("b", 2)  # evicts "a"
        self.assertEqual(len(cache), 1)
        self.assertNotIn("a", cache)
        self.assertEqual(cache.get("b"), 2)

    def test_stats_counts_hits_and_misses(self) -> None:
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.get("a")  # hit
        cache.get("a")  # hit
        cache.get("zz")  # miss
        stats = cache.stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 2 / 3)

    def test_stats_hit_rate_zero_when_empty(self) -> None:
        cache = LRUCache(capacity=3)
        stats = cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], 0.0)

    def test_invalid_capacity_raises(self) -> None:
        with self.assertRaises(ValueError):
            LRUCache(capacity=0)


class LRUCacheThreadSafetyTests(unittest.TestCase):
    def test_thread_safety_concurrent_puts(self) -> None:
        """Many threads write distinct keys; no data loss and no over-capacity.

        capacity is chosen >= total distinct keys so nothing is evicted.
        """
        num_threads = 8
        writes_per_thread = 1000
        total_keys = num_threads * writes_per_thread  # 8000 distinct keys
        cache = LRUCache(capacity=total_keys)

        def worker(thread_id: int) -> None:
            for i in range(writes_per_thread):
                key = thread_id * writes_per_thread + i
                cache.put(key, key)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No key lost and no over-capacity.
        self.assertEqual(len(cache), total_keys)
        stats = cache.stats()
        self.assertEqual(stats["size"], total_keys)
        # Every key present with correct value.
        for t in range(num_threads):
            for i in range(writes_per_thread):
                key = t * writes_per_thread + i
                self.assertIn(key, cache)
                self.assertEqual(cache.get(key), key)


if __name__ == "__main__":
    unittest.main()
