#!/usr/bin/env python3
"""Run X-Agent release-candidate targeted verification.

This script intentionally avoids pytest.ini coverage addopts and uses temporary
JSONL/JSON stores so release validation does not depend on or mutate local data/
state files. It is a targeted correctness baseline, not a replacement for the
full workstation or CI suite.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEST_GROUPS: list[tuple[str, list[str]]] = [
    (
        "agent-core",
        [
            "tests/test_agent_loop.py::test_reflect_replan_prompt_prefers_mutating_tool_after_read",
            "tests/test_agent_loop.py::test_code_change_plan_inserts_reflect_before_final_after_read_only_plan",
            "tests/test_agent_fix_runner.py",
        ],
    ),
    (
        "mcp-and-channels",
        [
            "tests/test_channels.py",
            "tests/test_mcp_discovery.py",
            "tests/test_mcp_config.py",
        ],
    ),
    (
        "sandbox-api",
        [
            "tests/test_sandbox_api.py",
        ],
    ),
]

E2E_DEEPSEEK = ["tests/e2e/test_agent_fix_real_llm.py"]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    tmp = Path(tempfile.gettempdir())
    env.setdefault("XAGENT_QDRANT_URL", "")
    env.setdefault("XAGENT_LLM_BACKEND", "mock")
    env.setdefault("XAGENT_DEEPSEEK_API_KEY", "")
    env.setdefault("XAGENT_TOOL_EXECUTION_STORE_PATH", str(tmp / "xagent_tool_executions_test.json"))
    env.setdefault("XAGENT_AUDIT_STORE_PATH", str(tmp / "xagent_audit_test.jsonl"))
    env.setdefault("XAGENT_RUN_STORE_PATH", str(tmp / "xagent_runs_test.jsonl"))
    env.setdefault("XAGENT_MEMORY_STORE_PATH", str(tmp / "xagent_memory_test.jsonl"))
    for proxy_key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ftp_proxy",
        "grpc_proxy",
    ):
        env.pop(proxy_key, None)
    return env


def _clean_temp_stores(env: dict[str, str]) -> None:
    for key in (
        "XAGENT_TOOL_EXECUTION_STORE_PATH",
        "XAGENT_AUDIT_STORE_PATH",
        "XAGENT_RUN_STORE_PATH",
        "XAGENT_MEMORY_STORE_PATH",
    ):
        value = env.get(key)
        if value:
            Path(value).unlink(missing_ok=True)


def _pytest_cmd(paths: list[str], verbose: bool) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "-q" if not verbose else "-vv",
        "-o",
        "addopts=",
        "-p",
        "no:cov",
        "-p",
        "no:cacheprovider",
        "--tb=short",
    ]
    return cmd


def _run_group(name: str, paths: list[str], env: dict[str, str], verbose: bool) -> int:
    print(f"\n=== {name} ===", flush=True)
    cmd = _pytest_cmd(paths, verbose)
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run X-Agent release-candidate targeted baseline")
    parser.add_argument("--include-real-llm", action="store_true", help="also run the opt-in DeepSeek e2e test")
    parser.add_argument("--verbose", action="store_true", help="run pytest with -vv instead of -q")
    args = parser.parse_args()

    env = _base_env()
    _clean_temp_stores(env)

    failures: list[tuple[str, int]] = []
    for name, paths in TEST_GROUPS:
        code = _run_group(name, paths, env, args.verbose)
        if code != 0:
            failures.append((name, code))

    if args.include_real_llm:
        e2e_env = env.copy()
        e2e_env["XAGENT_E2E"] = "1"
        e2e_env["XAGENT_E2E_LLM"] = "1"
        e2e_env["XAGENT_ENABLE_HIGH_RISK_TOOLS"] = "true"
        code = _run_group("deepseek-real-llm-e2e", E2E_DEEPSEEK, e2e_env, args.verbose)
        if code != 0:
            failures.append(("deepseek-real-llm-e2e", code))

    if failures:
        print("\nFAILED GROUPS:")
        for name, code in failures:
            print(f"- {name}: exit {code}")
        return 1

    print("\nRelease-candidate targeted baseline passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
