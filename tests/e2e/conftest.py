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
    if os.environ.get("XAGENT_E2E") == "1":
        return
    skip_e2e = pytest.mark.skip(reason="e2e tests are opt-in: set XAGENT_E2E=1")
    for item in items:
        if _is_e2e_item(item):
            item.add_marker(skip_e2e)


def _is_e2e_item(item: pytest.Item) -> bool:
    if item.get_closest_marker("e2e") is not None:
        return True
    path = Path(str(getattr(item, "path", getattr(item, "fspath", "")))).as_posix()
    return "/tests/e2e/" in f"/{path}" or path.startswith("tests/e2e/")
