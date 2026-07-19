"""File-system based memory persistence with automatic indexing.

This module provides persistent storage of conversation memories using Markdown files,
similar to Claude Code's memory system. It includes automatic index generation and
incremental update mechanisms.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    category: str = "reference"  # user, feedback, project, reference
    content: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryIndex:
    """Index of all memories for quick lookup."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)
    tags: dict[str, list[str]] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryPersistence:
    """File-system based memory persistence with automatic indexing."""

    def __init__(self, memory_dir: str | Path) -> None:
        """Initialize memory persistence.

        Args:
            memory_dir: Directory to store memory files
        """
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "MEMORY.md"
        self.metadata_file = self.memory_dir / ".memory_metadata.json"
        self._index: MemoryIndex | None = None
        self._load_index()

    def _load_index(self) -> None:
        """Load index from disk."""
        if self.index_file.exists():
            try:
                content = self.index_file.read_text(encoding="utf-8")
                self._parse_index_from_markdown(content)
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")
                self._index = MemoryIndex()
        else:
            self._index = MemoryIndex()

    def _parse_index_from_markdown(self, content: str) -> None:
        """Parse index from MEMORY.md markdown format.

        Args:
            content: Markdown content
        """
        self._index = MemoryIndex()
        lines = content.split("\n")

        current_category = None
        for line in lines:
            line = line.strip()

            # Parse category headers (## Category)
            if line.startswith("## "):
                current_category = line[3:].strip()
                if current_category not in self._index.categories:
                    self._index.categories[current_category] = []

            # Parse memory entries (- [name](file.md) — description)
            elif line.startswith("- [") and current_category:
                try:
                    # Extract name and file reference
                    name_end = line.find("]")
                    name = line[3:name_end]

                    file_start = line.find("(", name_end)
                    file_end = line.find(")", file_start)
                    file_ref = line[file_start + 1 : file_end]

                    # Extract description
                    desc_start = line.find("—", file_end)
                    description = line[desc_start + 1 :].strip() if desc_start > 0 else ""

                    entry = {
                        "name": name,
                        "file": file_ref,
                        "category": current_category,
                        "description": description,
                    }
                    self._index.entries.append(entry)
                    self._index.categories[current_category].append(name)
                except Exception as e:
                    logger.warning(f"Failed to parse memory entry: {line}, error: {e}")

    def save_memory(self, entry: MemoryEntry) -> str:
        """Save a memory entry to disk.

        Args:
            entry: Memory entry to save

        Returns:
            File path where memory was saved
        """
        # Create filename from name or ID
        filename = entry.name.replace(" ", "_").lower() if entry.name else entry.id
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = self.memory_dir / filename

        # Create markdown content
        content = self._create_memory_markdown(entry)
        filepath.write_text(content, encoding="utf-8")

        # Update index
        self._update_index_entry(entry, filename)

        logger.info(f"Saved memory: {filepath}")
        return str(filepath)

    def _create_memory_markdown(self, entry: MemoryEntry) -> str:
        """Create markdown content for a memory entry.

        Args:
            entry: Memory entry

        Returns:
            Markdown formatted content
        """
        lines = [
            f"# {entry.name or 'Untitled Memory'}",
            "",
            f"**Category:** {entry.category}",
            f"**Created:** {entry.created_at.isoformat()}",
            f"**Updated:** {entry.updated_at.isoformat()}",
            "",
        ]

        if entry.tags:
            lines.append(f"**Tags:** {', '.join(entry.tags)}")
            lines.append("")

        if entry.metadata:
            lines.append("**Metadata:**")
            for key, value in entry.metadata.items():
                lines.append(f"- {key}: {json.dumps(value)}")
            lines.append("")

        lines.append("## Content")
        lines.append("")
        lines.append(entry.content)

        return "\n".join(lines)

    def _update_index_entry(self, entry: MemoryEntry, filename: str) -> None:
        """Update index with new or modified entry.

        Args:
            entry: Memory entry
            filename: Filename where entry is stored
        """
        if not self._index:
            self._index = MemoryIndex()

        # Remove old entry if exists
        self._index.entries = [e for e in self._index.entries if e.get("name") != entry.name]

        # Add new entry
        index_entry = {
            "name": entry.name,
            "file": filename,
            "category": entry.category,
            "description": entry.content[:100] + "..." if len(entry.content) > 100 else entry.content,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }
        self._index.entries.append(index_entry)

        # Update category index
        if entry.category not in self._index.categories:
            self._index.categories[entry.category] = []
        if entry.name not in self._index.categories[entry.category]:
            self._index.categories[entry.category].append(entry.name)

        # Update tag index
        for tag in entry.tags:
            if tag not in self._index.tags:
                self._index.tags[tag] = []
            if entry.name not in self._index.tags[tag]:
                self._index.tags[tag].append(entry.name)

        self._index.updated_at = datetime.now(UTC)
        self._save_index()

    def _save_index(self) -> None:
        """Save index to MEMORY.md."""
        if not self._index:
            return

        lines = ["# Memory Index", ""]

        # Group entries by category
        for category in sorted(self._index.categories.keys()):
            lines.append(f"## {category}")
            lines.append("")

            for entry in self._index.entries:
                if entry.get("category") == category:
                    name = entry.get("name", "Untitled")
                    file = entry.get("file", "")
                    desc = entry.get("description", "")
                    lines.append(f"- [{name}]({file}) — {desc}")

            lines.append("")

        content = "\n".join(lines)
        self.index_file.write_text(content, encoding="utf-8")
        logger.info(f"Updated index: {self.index_file}")

    def load_memory(self, name: str) -> MemoryEntry | None:
        """Load a memory entry by name.

        Args:
            name: Memory name

        Returns:
            MemoryEntry or None if not found
        """
        # Find file in index
        filename = None
        for entry in self._index.entries if self._index else []:
            if entry.get("name") == name:
                filename = entry.get("file")
                break

        if not filename:
            return None

        filepath = self.memory_dir / filename
        if not filepath.exists():
            logger.warning(f"Memory file not found: {filepath}")
            return None

        try:
            content = filepath.read_text(encoding="utf-8")
            return self._parse_memory_markdown(content, name)
        except Exception as e:
            logger.error(f"Failed to load memory {name}: {e}")
            return None

    def _parse_memory_markdown(self, content: str, name: str) -> MemoryEntry:
        """Parse memory entry from markdown.

        Args:
            content: Markdown content
            name: Memory name

        Returns:
            MemoryEntry
        """
        entry = MemoryEntry(name=name)
        lines = content.split("\n")

        in_content = False
        in_metadata = False
        content_lines = []

        for line in lines:
            if line.startswith("## Content"):
                in_content = True
                in_metadata = False
                continue

            if in_content:
                content_lines.append(line)
                continue

            # Parse the "**Metadata:**" block written by _create_memory_markdown
            # (each item formatted as "- {key}: {json.dumps(value)}"). Without
            # this, save->load silently drops all metadata.
            if line.startswith("**Metadata:**"):
                in_metadata = True
                continue

            if in_metadata:
                stripped = line.strip()
                if stripped.startswith("- "):
                    key, sep, raw_value = stripped[2:].partition(":")
                    if sep:
                        key = key.strip()
                        raw_value = raw_value.strip()
                        try:
                            entry.metadata[key] = json.loads(raw_value)
                        except (json.JSONDecodeError, ValueError):
                            entry.metadata[key] = raw_value
                    continue
                # Any blank or non-list line ends the metadata block.
                in_metadata = False

            if line.startswith("**Category:**"):
                entry.category = line.split(":", 1)[1].strip()
            elif line.startswith("**Tags:**"):
                tags_str = line.split(":", 1)[1].strip()
                entry.tags = [t.strip() for t in tags_str.split(",")]
            elif line.startswith("**Created:**"):
                try:
                    entry.created_at = datetime.fromisoformat(line.split(":", 1)[1].strip())
                except Exception:
                    pass
            elif line.startswith("**Updated:**"):
                try:
                    entry.updated_at = datetime.fromisoformat(line.split(":", 1)[1].strip())
                except Exception:
                    pass

        entry.content = "\n".join(content_lines).strip()
        return entry

    def list_memories(self, category: str | None = None) -> list[MemoryEntry]:
        """List all memories, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of MemoryEntry objects
        """
        memories = []

        for entry_data in self._index.entries if self._index else []:
            if category and entry_data.get("category") != category:
                continue

            name = entry_data.get("name")
            if name:
                memory = self.load_memory(name)
                if memory:
                    memories.append(memory)

        return memories

    def delete_memory(self, name: str) -> bool:
        """Delete a memory entry.

        Args:
            name: Memory name

        Returns:
            True if deleted, False if not found
        """
        # Find and delete file
        filename = None
        for entry in self._index.entries if self._index else []:
            if entry.get("name") == name:
                filename = entry.get("file")
                break

        if not filename:
            return False

        filepath = self.memory_dir / filename
        try:
            filepath.unlink()
            # Update index
            self._index.entries = [e for e in self._index.entries if e.get("name") != name]
            self._save_index()
            logger.info(f"Deleted memory: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {name}: {e}")
            return False

    def search_memories(self, query: str) -> list[MemoryEntry]:
        """Search memories by name, tags, or content.

        Args:
            query: Search query

        Returns:
            List of matching MemoryEntry objects
        """
        query_lower = query.lower()
        results = []

        for entry_data in self._index.entries if self._index else []:
            name = entry_data.get("name", "").lower()
            tags = [t.lower() for t in entry_data.get("tags", [])]
            desc = entry_data.get("description", "").lower()

            if query_lower in name or query_lower in desc or any(query_lower in t for t in tags):
                memory = self.load_memory(entry_data.get("name"))
                if memory:
                    results.append(memory)

        return results

    def get_index_markdown(self) -> str:
        """Get the current index as markdown.

        Returns:
            Markdown formatted index
        """
        if self.index_file.exists():
            return self.index_file.read_text(encoding="utf-8")
        return "# Memory Index\n\nNo memories yet."
