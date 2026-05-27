"""Hot memory store using filesystem-based Markdown storage.

Features:
- Fast local access (<10ms)
- Markdown format for human readability
- Automatic indexing via MEMORY.md
- Memory categorization
- Quick text search
- Memory references with [[name]] syntax
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.app.core.hybrid_memory_system import Memory


class MemoryIndex(BaseModel):
    """Index entry for quick memory lookup."""

    id: str
    title: str
    category: str
    importance: float
    created_at: datetime
    tags: list[str]
    path: str


class HotMemoryStore:
    """Filesystem-based hot memory storage with Markdown format.

    Storage structure:
    - memories/
      - MEMORY.md (index)
      - user/
        - memory_id.md
      - feedback/
        - memory_id.md
      - project/
        - memory_id.md
      - reference/
        - memory_id.md
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else Path.home() / ".xagent" / "memories"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Create category directories
        for category in ("user", "feedback", "project", "reference"):
            (self.storage_path / category).mkdir(exist_ok=True)

        self._index: dict[str, MemoryIndex] = {}
        self._load_index()

    async def save(self, memory: Memory) -> str:
        """Save memory to filesystem.

        Args:
            memory: Memory to save

        Returns:
            Memory ID
        """
        # Ensure category directory exists
        category_dir = self.storage_path / memory.category
        category_dir.mkdir(exist_ok=True)

        # Create memory file
        memory_file = category_dir / f"{memory.id}.md"

        # Format memory as Markdown
        content = self._format_memory_markdown(memory)
        memory_file.write_text(content, encoding="utf-8")

        # Update index
        index_entry = MemoryIndex(
            id=memory.id,
            title=memory.content[:100],
            category=memory.category,
            importance=memory.importance,
            created_at=memory.created_at,
            tags=memory.tags,
            path=str(memory_file.relative_to(self.storage_path)),
        )
        self._index[memory.id] = index_entry

        # Rebuild index file
        await self.rebuild_index()

        return memory.id

    async def load(self, memory_id: str) -> Memory | None:
        """Load memory from filesystem.

        Args:
            memory_id: Memory ID to load

        Returns:
            Memory object or None if not found
        """
        # Search in all category directories
        for category_dir in self.storage_path.glob("*/"):
            if not category_dir.is_dir():
                continue

            memory_file = category_dir / f"{memory_id}.md"
            if memory_file.exists():
                content = memory_file.read_text(encoding="utf-8")
                return self._parse_memory_markdown(content, memory_id)

        return None

    async def search(self, query: str) -> list[Memory]:
        """Search memories by text.

        Args:
            query: Search query

        Returns:
            List of matching memories
        """
        results: list[Memory] = []
        query_lower = query.lower()

        for category_dir in self.storage_path.glob("*/"):
            if not category_dir.is_dir():
                continue

            for memory_file in category_dir.glob("*.md"):
                content = memory_file.read_text(encoding="utf-8")

                # Simple text search
                if query_lower in content.lower():
                    memory_id = memory_file.stem
                    memory = await self.load(memory_id)
                    if memory:
                        results.append(memory)

        return results

    async def list_by_category(self, category: str) -> list[Memory]:
        """List all memories in a category.

        Args:
            category: Category name ("user", "feedback", "project", "reference", "all")

        Returns:
            List of memories
        """
        results: list[Memory] = []

        if category == "all":
            categories = ("user", "feedback", "project", "reference")
        else:
            categories = (category,)

        for cat in categories:
            category_dir = self.storage_path / cat
            if not category_dir.exists():
                continue

            for memory_file in category_dir.glob("*.md"):
                memory_id = memory_file.stem
                memory = await self.load(memory_id)
                if memory:
                    results.append(memory)

        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete memory from filesystem.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Success status
        """
        for category_dir in self.storage_path.glob("*/"):
            if not category_dir.is_dir():
                continue

            memory_file = category_dir / f"{memory_id}.md"
            if memory_file.exists():
                memory_file.unlink()
                self._index.pop(memory_id, None)
                await self.rebuild_index()
                return True

        return False

    async def rebuild_index(self) -> None:
        """Rebuild MEMORY.md index file."""
        index_content = self._generate_index_markdown()
        index_file = self.storage_path / "MEMORY.md"
        index_file.write_text(index_content, encoding="utf-8")

    def _format_memory_markdown(self, memory: Memory) -> str:
        """Format memory as Markdown."""
        lines = [
            f"# {memory.content[:100]}",
            "",
            f"**ID:** `{memory.id}`",
            f"**Category:** {memory.category}",
            f"**Importance:** {memory.importance:.2f}",
            f"**Created:** {memory.created_at.isoformat()}",
            f"**Updated:** {memory.updated_at.isoformat()}",
            f"**Accessed:** {memory.accessed_at.isoformat()}",
            f"**Access Count:** {memory.access_count}",
            "",
        ]

        if memory.tags:
            lines.append(f"**Tags:** {', '.join(memory.tags)}")
            lines.append("")

        if memory.related_ids:
            lines.append("**Related Memories:**")
            for related_id in memory.related_ids:
                lines.append(f"- [[{related_id}]]")
            lines.append("")

        lines.append("## Content")
        lines.append("")
        lines.append(memory.content)
        lines.append("")

        if memory.metadata:
            lines.append("## Metadata")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(memory.metadata, indent=2, ensure_ascii=False))
            lines.append("```")

        return "\n".join(lines)

    def _parse_memory_markdown(self, content: str, memory_id: str) -> Memory:
        """Parse Markdown content back to Memory object."""
        lines = content.split("\n")

        # Extract metadata from header
        category = "reference"
        importance = 0.5
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)
        accessed_at = datetime.now(UTC)
        access_count = 0
        tags: list[str] = []
        related_ids: list[str] = []
        metadata: dict[str, Any] = {}

        # Parse header section
        in_metadata = False
        in_json = False
        json_lines: list[str] = []

        for line in lines:
            if line.startswith("**Category:**"):
                category = line.split(":", 1)[1].strip()
            elif line.startswith("**Importance:**"):
                try:
                    importance = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**Created:**"):
                try:
                    created_at = datetime.fromisoformat(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**Updated:**"):
                try:
                    updated_at = datetime.fromisoformat(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**Accessed:**"):
                try:
                    accessed_at = datetime.fromisoformat(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**Access Count:**"):
                try:
                    access_count = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**Tags:**"):
                tags_str = line.split(":", 1)[1].strip()
                tags = [t.strip() for t in tags_str.split(",")]
            elif line.startswith("- [["):
                # Extract related memory ID
                match = re.search(r"\[\[(.+?)\]\]", line)
                if match:
                    related_ids.append(match.group(1))
            elif line.startswith("```json"):
                in_json = True
            elif line == "```" and in_json:
                in_json = False
                try:
                    metadata = json.loads("\n".join(json_lines))
                except json.JSONDecodeError:
                    pass
                json_lines = []
            elif in_json:
                json_lines.append(line)

        # Extract content between ## Content and ## Metadata
        content_start = None
        metadata_start = None

        for i, line in enumerate(lines):
            if line.startswith("## Content"):
                content_start = i + 2
            elif line.startswith("## Metadata"):
                metadata_start = i
                break

        body_content = ""
        if content_start is not None:
            end = metadata_start if metadata_start else len(lines)
            body_content = "\n".join(lines[content_start:end]).strip()

        return Memory(
            id=memory_id,
            content=body_content or content[:500],
            category=category,
            importance=importance,
            tier="hot",
            tags=tags,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            accessed_at=accessed_at,
            access_count=access_count,
            related_ids=related_ids,
        )

    def _generate_index_markdown(self) -> str:
        """Generate MEMORY.md index file."""
        lines = [
            "# Memory Index",
            "",
            "Auto-generated index of all stored memories.",
            "",
        ]

        # Group by category
        by_category: dict[str, list[MemoryIndex]] = {}
        for entry in self._index.values():
            by_category.setdefault(entry.category, []).append(entry)

        # Sort by importance within each category
        for category in ("user", "feedback", "project", "reference"):
            entries = by_category.get(category, [])
            if not entries:
                continue

            entries.sort(key=lambda e: e.importance, reverse=True)

            lines.append(f"## {category.capitalize()}")
            lines.append("")

            for entry in entries:
                tags_str = f" `{', '.join(entry.tags)}`" if entry.tags else ""
                lines.append(
                    f"- [[{entry.id}]] - {entry.title[:60]}... "
                    f"(importance: {entry.importance:.2f}){tags_str}"
                )

            lines.append("")

        lines.append("---")
        lines.append(f"Last updated: {datetime.now(UTC).isoformat()}")

        return "\n".join(lines)

    def _load_index(self) -> None:
        """Load index from MEMORY.md."""
        index_file = self.storage_path / "MEMORY.md"
        if not index_file.exists():
            return

        content = index_file.read_text(encoding="utf-8")

        # Parse index entries
        for line in content.split("\n"):
            match = re.search(r"\[\[(.+?)\]\]", line)
            if match:
                memory_id = match.group(1)
                # Try to load the actual memory file to get full metadata
                for category_dir in self.storage_path.glob("*/"):
                    if not category_dir.is_dir():
                        continue
                    memory_file = category_dir / f"{memory_id}.md"
                    if memory_file.exists():
                        try:
                            memory_content = memory_file.read_text(encoding="utf-8")
                            memory = self._parse_memory_markdown(memory_content, memory_id)
                            self._index[memory_id] = MemoryIndex(
                                id=memory.id,
                                title=memory.content[:100],
                                category=memory.category,
                                importance=memory.importance,
                                created_at=memory.created_at,
                                tags=memory.tags,
                                path=str(memory_file.relative_to(self.storage_path)),
                            )
                        except Exception:
                            pass
