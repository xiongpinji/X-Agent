import ast
from pathlib import Path

from fastapi.routing import APIRoute

from backend.app.main import app


ROOT = Path(__file__).resolve().parents[1]
DECISION_DOC = ROOT / "docs" / "API_ROUTE_SCOPE_DECISION_20260618.md"


def _api_route_modules() -> set[str]:
    modules: set[str] = set()
    for path in (ROOT / "backend" / "app" / "api").glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        has_router = False
        has_route_decorator = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                has_router = has_router or any(
                    isinstance(target, ast.Name) and target.id in {"router", "api_router"}
                    for target in node.targets
                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    func = decorator.func if isinstance(decorator, ast.Call) else decorator
                    if (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id in {"router", "api_router"}
                    ):
                        has_route_decorator = True
        if has_router or has_route_decorator:
            modules.add(path.stem)
    return modules


def _mounted_route_modules() -> set[str]:
    return {
        route.endpoint.__module__.split(".")[-1]
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.endpoint.__module__.startswith("backend.app.api.")
    }


def test_route_scope_decision_covers_every_unmounted_api_router_module():
    document = DECISION_DOC.read_text(encoding="utf-8")
    unmounted = _api_route_modules() - _mounted_route_modules()

    missing = [module for module in sorted(unmounted) if f"| `{module}` |" not in document]

    assert not missing


def test_route_scope_decision_keeps_first_version_promotions_closed():
    document = DECISION_DOC.read_text(encoding="utf-8")

    assert "| None | All first-version route needs are already covered" in document
    assert "No unmounted module is promoted in this slice." in document
