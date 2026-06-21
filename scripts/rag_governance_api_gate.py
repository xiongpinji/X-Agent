#!/usr/bin/env python3
"""Validate the API-only RAG governance delivery contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api.errors import XAgentAPIError
from backend.app.api.rag_governance import (
    LOCAL_PROVIDER_NAMES,
    RAGQueryRequest,
    list_rag_providers,
    query_rag,
)
from backend.app.core.audit import AuditStore
from backend.app.core.security import Principal, ROLE_SCOPES

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "rag-governance-api-gate.json"


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


def _principal(scopes: list[str] | None = None, *, tenant_id: str = "tenant-1") -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id="user-1",
        role="admin",
        authenticated=True,
        api_key_id="gate",
        scopes=scopes or list(ROLE_SCOPES["admin"]),
        permission_scope=scopes or list(ROLE_SCOPES["admin"]),
    )


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> GateCheck:
    return GateCheck(name=name, status="passed" if ok else "failed", details=details or {}, error=None if ok else error)


async def build_rag_governance_gate_report(root: Path = ROOT) -> GateReport:
    api_source = (root / "backend/app/api/rag_governance.py").read_text(encoding="utf-8")
    main_source = (root / "backend/app/main.py").read_text(encoding="utf-8")
    providers = await list_rag_providers(_principal())
    provider_names = {item["provider"] for item in providers["providers"]}
    audit = AuditStore()

    local_rejected = False
    try:
        await query_rag(
            RAGQueryRequest(provider="qdrant", query="governance"),
            _principal(),
            audit,
        )
    except XAgentAPIError as exc:
        local_rejected = exc.status_code == 400

    budget_rejected = False
    try:
        await query_rag(
            RAGQueryRequest(
                provider="tavily",
                query="governance",
                top_k=10,
                max_results=20,
                max_estimated_cost_usd=0,
            ),
            _principal(),
            audit,
        )
    except XAgentAPIError as exc:
        budget_rejected = exc.status_code == 429

    tenant_rejected = False
    try:
        await query_rag(
            RAGQueryRequest(provider="mock", query="private deployment", tenant_scope="tenant-2"),
            _principal(tenant_id="tenant-1"),
            audit,
        )
    except XAgentAPIError as exc:
        tenant_rejected = exc.status_code == 403

    success_response = await query_rag(
        RAGQueryRequest(provider="mock", query="api governance", top_k=3, max_results=5),
        _principal(tenant_id="tenant-1"),
        audit,
    )
    audit_error_codes = {record.details.get("error_code") for record in audit.list(limit=20)}
    checks = [
        _check(
            "route_is_mounted",
            "from backend.app.api.rag_governance import router as rag_governance_router" in main_source
            and "app.include_router(rag_governance_router)" in main_source,
            error="/api/v1/rag router is not mounted in backend.app.main",
        ),
        _check(
            "provider_surface_is_api_only",
            provider_names == {"openai-search", "tavily", "mock"}
            and not (provider_names & LOCAL_PROVIDER_NAMES)
            and providers.get("local_providers_blocked"),
            details={"providers": sorted(provider_names), "blocked": providers.get("local_providers_blocked")},
            error="provider surface exposes local retrieval providers or misses API-only providers",
        ),
        _check(
            "providers_require_memory_read",
            'enforce_scope(principal, "memory:read")' in api_source,
            error="/providers or /query does not enforce memory:read",
        ),
        _check(
            "local_provider_rejected_before_retrieval",
            local_rejected
            and any(record.outcome == "failure" and record.resource_id == "qdrant" for record in audit.list(limit=20)),
            error="local retrieval provider was not rejected and audited",
        ),
        _check(
            "budget_guard_rejects_before_provider_use",
            budget_rejected
            and any(record.details.get("error_code") == "budget_guard_rejected" for record in audit.list(limit=20)),
            error="RAG budget guard did not reject or audit over-budget request",
        ),
        _check(
            "tenant_scope_is_enforced",
            tenant_rejected
            and any(record.details.get("error_code") == "tenant_scope_rejected" for record in audit.list(limit=20)),
            error="RAG query can cross tenant scope or is not audited",
        ),
        _check(
            "mock_results_are_tenant_scoped",
            success_response.provider == "mock"
            and success_response.governance["tenant_scoped"] is True
            and {item.tenant_id for item in success_response.results} == {"tenant-1"},
            details={"result_count": len(success_response.results)},
            error="mock retrieval returned cross-tenant results",
        ),
        _check(
            "audit_records_policy_and_success",
            audit.count() == 4
            and audit_error_codes >= {"provider_rejected", "budget_guard_rejected", "tenant_scope_rejected", None},
            details={"audit_count": audit.count()},
            error="audit store does not contain expected RAG governance records",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="rag_governance_api_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        checks=checks,
        known_limits=[
            "This gate uses the mock retrieval provider and does not perform external search calls.",
            "This slice exposes read/query governance only; ingestion and indexing are deferred.",
            "Provider credentials and live retrieval staging require owner approval.",
        ],
        next_commands=[
            "python scripts/rag_governance_api_gate.py",
            "python -m pytest tests/test_rag_governance_api.py -q --no-cov",
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
    report = asyncio.run(build_rag_governance_gate_report())
    write_report(report, args.output)
    print(f"RAG governance API gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
