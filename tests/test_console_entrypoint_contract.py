from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_console_html_entrypoint_is_retired() -> None:
    assert not (PROJECT_ROOT / "frontend/console.html").exists()


def test_vite_does_not_register_a_legacy_console_input() -> None:
    vite_config = (PROJECT_ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")

    assert "console.html" not in vite_config


def test_modern_spa_owns_the_console_route_and_sidebar_link() -> None:
    app_source = (PROJECT_ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = (PROJECT_ROOT / "frontend/src/components/Layout.tsx").read_text(
        encoding="utf-8"
    )

    assert '<Route path="/console/*" element={<ConsoleApp />} />' in app_source
    assert "href: '/console'" in layout_source


def test_documented_nginx_fallback_serves_spa_routes() -> None:
    frontend_readme = (PROJECT_ROOT / "frontend/README.md").read_text(encoding="utf-8")

    assert "try_files $uri $uri/ /index.html;" in frontend_readme
