"""E2E test gating.

E2E tests are environment-dependent and can call real services or long-running
agent loops. Keep the default baseline deterministic; opt in explicitly with
XAGENT_E2E=1. Real-LLM tests may require their own additional key/env gates.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip e2e tests unless XAGENT_E2E=1.

    pytest_collection_modifyitems receives the session-wide item list (not just
    this directory's items), so the skip marker must be filtered by path —
    otherwise it leaks onto every collected test in the session.
    """
    if os.environ.get("XAGENT_E2E") == "1":
        return
    skip_e2e = pytest.mark.skip(reason="e2e tests are opt-in: set XAGENT_E2E=1")
    e2e_dir = Path(__file__).parent.resolve()
    for item in items:
        if Path(str(item.path)).resolve().is_relative_to(e2e_dir):
            item.add_marker(skip_e2e)
