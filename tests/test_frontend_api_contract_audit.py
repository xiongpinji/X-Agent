from pathlib import Path

from scripts.frontend_api_contract_audit import (
    audit_frontend_api_contract,
    frontend_api_refs,
    mounted_api_routes,
)


def test_frontend_api_contract_has_no_unapproved_missing_routes():
    result = audit_frontend_api_contract(
        frontend_root=Path("frontend/src"),
        allowlist_path=Path("docs/API_CONTRACT_ALLOWLIST.md"),
    )

    assert result["ok"], result["missing"]


def test_frontend_api_contract_uses_mounted_routes_as_source_of_truth():
    routes = mounted_api_routes()

    assert "/api/v1/workbench" in routes
    assert "/api/v1/plugin-market/plugins" not in routes


def test_deferred_marketplace_sources_are_excluded_from_first_version_contract():
    refs = frontend_api_refs(Path("frontend/src"))
    paths = {ref.path for ref in refs}

    assert "/api/v1/plugin-market/plugins" not in paths
    assert "/api/v1/skill-market/skills" not in paths
    assert "/api/v1/templates" not in paths
