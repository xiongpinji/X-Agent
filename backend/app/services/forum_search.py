"""Full-text search and indexing for forum posts and comments."""

from __future__ import annotations

import re
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchIndex:
    """Full-text search index for forum content."""

    # Inverted index: word -> set of (post_id, comment_id)
    word_index: dict[str, set[tuple[str, Optional[str]]]] = field(default_factory=dict)
    # Tag index: tag -> set of post_ids
    tag_index: dict[str, set[str]] = field(default_factory=dict)
    # Author index: author_id -> set of post_ids
    author_index: dict[str, set[str]] = field(default_factory=dict)
    # Category index: category -> set of post_ids
    category_index: dict[str, set[str]] = field(default_factory=dict)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        # Convert to lowercase and split on non-alphanumeric characters
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        }
        return [w for w in words if w not in stop_words and len(w) > 2]

    def index_post(self, post_id: str, title: str, content: str, tags: list[str], author_id: str, category: str) -> None:
        """Index a post."""
        # Index title and content
        text = f"{title} {content}"
        for word in self._tokenize(text):
            if word not in self.word_index:
                self.word_index[word] = set()
            self.word_index[word].add((post_id, None))

        # Index tags
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in self.tag_index:
                self.tag_index[tag_lower] = set()
            self.tag_index[tag_lower].add(post_id)

        # Index author
        if author_id not in self.author_index:
            self.author_index[author_id] = set()
        self.author_index[author_id].add(post_id)

        # Index category
        if category not in self.category_index:
            self.category_index[category] = set()
        self.category_index[category].add(post_id)

    def index_comment(self, post_id: str, comment_id: str, content: str) -> None:
        """Index a comment."""
        for word in self._tokenize(content):
            if word not in self.word_index:
                self.word_index[word] = set()
            self.word_index[word].add((post_id, comment_id))

    def search(self, query: str, limit: int = 20) -> list[tuple[str, Optional[str]]]:
        """Search for posts and comments.

        Returns:
            List of (post_id, comment_id) tuples, where comment_id is None for posts
        """
        words = self._tokenize(query)
        if not words:
            return []

        # Start with results for first word
        results = self.word_index.get(words[0], set()).copy()

        # Intersect with results for other words
        for word in words[1:]:
            results &= self.word_index.get(word, set())

        # Sort by relevance (posts before comments)
        sorted_results = sorted(results, key=lambda x: (x[1] is not None, x[0]))
        return sorted_results[:limit]

    def search_by_tag(self, tag: str, limit: int = 20) -> list[str]:
        """Search posts by tag."""
        tag_lower = tag.lower()
        posts = self.tag_index.get(tag_lower, set())
        return list(posts)[:limit]

    def search_by_author(self, author_id: str, limit: int = 20) -> list[str]:
        """Search posts by author."""
        posts = self.author_index.get(author_id, set())
        return list(posts)[:limit]

    def search_by_category(self, category: str, limit: int = 20) -> list[str]:
        """Search posts by category."""
        posts = self.category_index.get(category, set())
        return list(posts)[:limit]

    def remove_post(self, post_id: str) -> None:
        """Remove a post from the index."""
        # Remove from word index
        for word in list(self.word_index.keys()):
            self.word_index[word] = {(p, c) for p, c in self.word_index[word] if p != post_id}
            if not self.word_index[word]:
                del self.word_index[word]

        # Remove from tag index
        for tag in list(self.tag_index.keys()):
            self.tag_index[tag].discard(post_id)
            if not self.tag_index[tag]:
                del self.tag_index[tag]

        # Remove from author index
        for author in list(self.author_index.keys()):
            self.author_index[author].discard(post_id)
            if not self.author_index[author]:
                del self.author_index[author]

        # Remove from category index
        for category in list(self.category_index.keys()):
            self.category_index[category].discard(post_id)
            if not self.category_index[category]:
                del self.category_index[category]


# Global search index instance
search_index = SearchIndex()
