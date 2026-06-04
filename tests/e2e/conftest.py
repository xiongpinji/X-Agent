"""E2E test gating.

E2E tests are environment-dependent and can call real services or long-running
agent loops. Keep the default baseline deterministic; opt in explicitly with
XAGENT_E2E=1. Real-LLM tests may require their own additional key/env gates.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("XAGENT_E2E") == "1":
        return
    skip_e2e = pytest.mark.skip(reason="e2e tests are opt-in: set XAGENT_E2E=1")
    for item in items:
        item.add_marker(skip_e2e)
