from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_rc_first_version_scope_document_exists_and_defers_unshipped_surfaces():
    scope = _read("docs/RC_FIRST_VERSION_SCOPE.md")

    assert "Desktop client/runtime" in scope
    assert "Browser extension" in scope
    assert "Plugin marketplace" in scope
    assert "Skill marketplace" in scope
    assert "Templates marketplace" in scope
    assert "The frontend must not route users into deferred surfaces" in scope


def test_console_first_version_navigation_does_not_link_deferred_marketplace():
    shell = _read("frontend/src/console/ConsoleShell.tsx")
    overview = _read("frontend/src/console/pages/overview/OverviewPage.tsx")
    audit = _read("frontend/src/console/pages/audit/AuditReplayPage.tsx")

    assert 'onClick={() => dispatch({ type: "page/set", payload: "market_overview" })}' not in shell
    assert "/api/v1/marketplace-control/overview" not in shell
    assert "open_market" not in overview
    assert 'actionKey: "marketplace"' not in audit


def test_deferred_marketplace_pages_are_not_imported_by_first_version_shell():
    shell = _read("frontend/src/console/ConsoleShell.tsx")
    page_registry = _read("frontend/src/panda/pageRegistry.tsx")

    deferred_components = [
        "PluginMarket",
        "SkillMarket",
        "SkillMarketComplete",
        "TemplateMarketplacePage",
        "TemplateEditor",
        "TemplateInstantiationWizard",
        "ForumHome",
        "AnalyticsDashboard",
    ]

    for component in deferred_components:
        assert component not in shell
        assert component not in page_registry
