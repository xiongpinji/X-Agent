#!/usr/bin/env python3
"""Validate the external LLM API governance delivery contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api.errors import XAgentAPIError
from backend.app.api.llm_governance import (
    LLMCompletionRequest,
    LOCAL_PROVIDER_NAMES,
    complete,
    list_llm_providers,
    llm_stats,
)
from backend.app.core.audit import AuditStore
from backend.app.core.llm.cost_optimizer import CostTracker
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.settings import get_settings

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "llm-governance-api-gate.json"


@dataclass(frozen=True)
class GateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class GateReport:
    status: str
    generated_at: str
    evidence_type: str
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    full_release_claimed: bool
    checks: list[GateCheck]
    known_limits: list[str]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _principal(scopes: list[str] | None = None) -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        role="admin",
        authenticated=True,
        api_key_id="gate",
        scopes=scopes or list(ROLE_SCOPES["admin"]),
        permission_scope=scopes or list(ROLE_SCOPES["admin"]),
    )


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> GateCheck:
    return GateCheck(name=name, status="passed" if ok else "failed", details=details or {}, error=None if ok else error)


async def build_llm_governance_gate_report(root: Path = ROOT) -> GateReport:
    api_source = (root / "backend/app/api/llm_governance.py").read_text(encoding="utf-8")
    main_source = (root / "backend/app/main.py").read_text(encoding="utf-8")
    dependencies_source = (root / "backend/app/dependencies.py").read_text(encoding="utf-8")
    providers = await list_llm_providers(_principal())
    provider_names = {item["provider"] for item in providers["providers"]}
    tracker = CostTracker()
    audit = AuditStore()

    local_rejected = False
    try:
        await complete(
            LLMCompletionRequest(
                provider="ollama",
                messages=[{"role": "user", "content": "hello"}],
            ),
            _principal(),
            tracker,
            audit,
        )
    except XAgentAPIError as exc:
        local_rejected = exc.status_code == 400

    budget_rejected = False
    try:
        await complete(
            LLMCompletionRequest(
                provider="mock",
                messages=[{"role": "user", "content": "x" * 200}],
                max_input_tokens=2,
            ),
            _principal(),
            tracker,
            audit,
        )
    except XAgentAPIError as exc:
        budget_rejected = exc.status_code == 429

    auto_rejected = False
    try:
        await complete(
            LLMCompletionRequest(
                provider="auto",
                messages=[{"role": "user", "content": "hello"}],
                max_estimated_cost_usd=0,
            ),
            _principal(),
            tracker,
            audit,
        )
    except XAgentAPIError as exc:
        auto_rejected = exc.status_code == 400

    base_url_rejected = False
    old_api_key = os.environ.get("XAGENT_DEEPSEEK_API_KEY")
    old_base_url = os.environ.get("XAGENT_DEEPSEEK_BASE_URL")
    os.environ["XAGENT_DEEPSEEK_API_KEY"] = "gate-key"
    os.environ["XAGENT_DEEPSEEK_BASE_URL"] = "http://localhost:11434/v1"
    get_settings.cache_clear()
    try:
        try:
            await complete(
                LLMCompletionRequest(
                    provider="deepseek",
                    messages=[{"role": "user", "content": "hello"}],
                ),
                _principal(),
                tracker,
                audit,
            )
        except XAgentAPIError as exc:
            base_url_rejected = exc.status_code == 400
    finally:
        if old_api_key is None:
            os.environ.pop("XAGENT_DEEPSEEK_API_KEY", None)
        else:
            os.environ["XAGENT_DEEPSEEK_API_KEY"] = old_api_key
        if old_base_url is None:
            os.environ.pop("XAGENT_DEEPSEEK_BASE_URL", None)
        else:
            os.environ["XAGENT_DEEPSEEK_BASE_URL"] = old_base_url
        get_settings.cache_clear()

    success_response = await complete(
        LLMCompletionRequest(
            provider="mock",
            messages=[{"role": "user", "content": "Summarize API routing"}],
        ),
        _principal(),
        tracker,
        audit,
    )
    stats = await llm_stats(_principal(), tracker)

    checks = [
        _check(
            "route_is_mounted",
            "from backend.app.api.llm_governance import router as llm_governance_router" in main_source
            and "app.include_router(llm_governance_router)" in main_source,
            error="/api/v1/llm router is not mounted in backend.app.main",
        ),
        _check(
            "cost_tracker_dependency_exists",
            "def get_llm_cost_tracker" in dependencies_source and "CostTracker" in dependencies_source,
            error="LLM cost tracker dependency is missing",
        ),
        _check(
            "provider_surface_is_api_only",
            provider_names == {"openai", "deepseek", "mock"}
            and not (provider_names & LOCAL_PROVIDER_NAMES)
            and providers.get("local_providers_blocked"),
            details={"providers": sorted(provider_names), "blocked": providers.get("local_providers_blocked")},
            error="provider surface exposes local model providers or misses external provider contract",
        ),
        _check(
            "completion_requires_agent_run",
            'enforce_scope(principal, "agent:run")' in api_source,
            error="/complete does not enforce agent:run",
        ),
        _check(
            "stats_requires_audit_read",
            'enforce_scope(principal, "audit:read")' in api_source,
            error="/stats does not enforce audit:read",
        ),
        _check(
            "local_provider_rejected_before_network",
            local_rejected
            and tracker.records[0].provider == "ollama"
            and tracker.records[0].success is False,
            error="local provider was not rejected and recorded as a governance failure",
        ),
        _check(
            "budget_guard_rejects_before_provider_call",
            budget_rejected
            and any(record.success is False and record.provider == "mock" for record in tracker.records),
            error="budget guard did not reject or record over-budget request",
        ),
        _check(
            "auto_completion_rejected_until_costed",
            auto_rejected
            and any(record.success is False and record.provider == "auto" for record in tracker.records),
            error="auto provider completion can bypass explicit provider cost governance",
        ),
        _check(
            "deepseek_base_url_must_be_official_external_https",
            base_url_rejected
            and any(
                record.success is False and record.provider == "deepseek"
                for record in tracker.records
            ),
            error="deepseek provider can be routed to a local, non-HTTPS, or non-official base URL",
        ),
        _check(
            "mock_completion_records_success",
            success_response.provider == "mock"
            and success_response.governance["budget_checked"] is True
            and any(record.success is True and record.provider == "mock" for record in tracker.records),
            error="successful mock completion did not record cost governance",
        ),
        _check(
            "audit_records_policy_and_success",
            audit.count() == 5
            and {record.details.get("error_code") for record in audit.list(limit=10)} >= {
                "provider_rejected",
                "budget_guard_rejected",
                "provider_base_url_rejected",
                None,
            },
            details={"audit_count": audit.count()},
            error="audit store does not contain expected LLM governance records",
        ),
        _check(
            "stats_are_api_only",
            stats["api_only"] is True and "ollama" in stats["local_providers_blocked"],
            error="/stats does not preserve API-only/local-provider-blocked contract",
        ),
        _check(
            "provider_exception_is_sanitized",
            "LLM provider request failed." in api_source and "str(exc)" not in api_source,
            error="provider exception text may leak to API clients",
        ),
    ]

    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="llm_governance_api_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        checks=checks,
        known_limits=[
            "Cost tracking is process-local in this slice and is not billing truth.",
            "This gate uses the mock provider and does not perform real OpenAI or DeepSeek calls.",
            "Fine-grained llm:* scopes are deferred; this slice reuses agent:run and audit:read.",
        ],
        next_commands=[
            "python scripts/llm_governance_api_gate.py",
            "python -m pytest tests/test_llm_router.py tests/test_llm_providers.py tests/test_llm_governance_api.py tests/test_route_auth_audit.py -q --no-cov",
            "git diff --check",
        ],
    )


def write_report(report: GateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(build_llm_governance_gate_report())
    write_report(report, args.output)
    print(f"LLM governance API gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
