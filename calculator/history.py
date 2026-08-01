"""Calculator history module.

This module provides the :class:`History` class, which records every operation
performed by a :class:`~calculator.core.Calculator`. Each entry stores the
operation name, the operands, the result, and a timestamp.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Tuple

Operands = Tuple[Any, ...]


class History:
    """A record of operations performed by a calculator.

    Each recorded entry is stored as a dictionary with the keys ``operation``,
    ``operands``, ``result``, and ``timestamp``.

    Attributes:
        entries: The list of recorded operation entries.
    """

    def __init__(self) -> None:
        """Initialize an empty history."""
        self.entries: list[dict[str, Any]] = []

    def record(self, operation: str, operands: Operands, result: Any) -> None:
        """Record a single operation in the history.

        Args:
            operation: The name of the operation (e.g. ``"add"``).
            operands: A tuple of the operands used in the operation.
            result: The result of the operation.
        """
        self.entries.append(
            {
                "operation": operation,
                "operands": operands,
                "result": result,
                "timestamp": datetime.now(),
            }
        )

    def get_entries(self) -> list[dict[str, Any]]:
        """Return a copy of all recorded entries.

        Returns:
            A list of dictionaries representing each recorded operation.
        """
        return list(self.entries)

    def clear(self) -> None:
        """Remove all recorded entries from the history."""
        self.entries.clear()

    def __len__(self) -> int:
        """Return the number of recorded entries.

        Returns:
            The number of operations recorded in the history.
        """
        return len(self.entries)
