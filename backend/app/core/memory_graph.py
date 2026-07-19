from __future__ import annotations

import re
from collections import Counter, defaultdict
from itertools import combinations


class MemoryGraph:
    """Small in-process co-occurrence graph for memory recall expansion."""

    def __init__(self, max_terms_per_item: int = 24) -> None:
        self.max_terms_per_item = max_terms_per_item
        self._edges: dict[str, Counter[str]] = defaultdict(Counter)

    def add_text(self, text: str) -> None:
        terms = self.extract_terms(text)[: self.max_terms_per_item]
        for left, right in combinations(sorted(set(terms)), 2):
            self._edges[left][right] += 1
            self._edges[right][left] += 1

    def related_terms(self, terms: set[str], limit: int = 12) -> set[str]:
        scored: Counter[str] = Counter()
        for term in terms:
            scored.update(self._edges.get(term, {}))
        for term in terms:
            scored.pop(term, None)
        return {term for term, _ in scored.most_common(limit)}

    @staticmethod
    def extract_terms(text: str) -> list[str]:
        normalized = text.casefold()
        return re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{1,4}", normalized)
