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
    # 2026-08-02 实测甄别：以下文件依赖真实 LLM/浏览器/桌面负载或当前不稳定，
    # 保持 XAGENT_E2E=1 门禁；其余 e2e（60+ 用例）在 mock 环境实测全绿，默认放开。
    live_only = {
        "test_agent_fix_real_llm.py",
        "test_browser_e2e.py",
        "test_performance_security_e2e.py",
        "test_smoke_api.py",
        "test_user_journey.py",
        "test_user_journey_api.py",
    }
    for item in items:
        path = Path(str(item.path)).resolve()
        if path.is_relative_to(e2e_dir) and path.name in live_only:
            item.add_marker(skip_e2e)
