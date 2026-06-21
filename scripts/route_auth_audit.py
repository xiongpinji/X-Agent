from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from fastapi import FastAPI
from fastapi.routing import APIRoute

from backend.app.api.rbac_enforcement import PermissionDependency
from backend.app import dependencies


AUTH_DEPENDENCY_REFS = {
    "backend.app.dependencies.get_current_principal",
    "backend.app.dependencies.get_refresh_principal",
    "backend.app.api.messages.get_messages_stream_principal",
    "backend.app.api.skill_curator.get_skill_curator_principal",
    "backend.app.api.streaming.get_stream_principal",
    "backend.app.api.workbench.get_workbench_principal",
    "backend.app.api.workbench_resources_bff.get_panda_workbench_principal",
    "backend.app.api.workflows.get_chat_principal",
}

SIGNATURE_DEPENDENCY_REFS = {
    "backend.app.api.channels.get_channel_router",
}

PUBLIC_ROUTES = {
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/login/oauth"),
    ("POST", "/api/v1/auth/reset-password"),
    ("POST", "/api/v1/enterprise/sso/saml/auth"),
    ("POST", "/api/v1/enterprise/sso/oauth/auth"),
    ("GET", "/api/v1/commercial-pilot/feishu/status"),
    ("GET", "/api/v1/commercial-pilot/feishu/reports"),
    ("GET", "/api/v1/commercial-pilot/feishu/reports/{report_name}"),
    ("GET", "/api/v1/workbench/resources/health"),
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("GET", "/api/v1/health/detailed"),
    ("GET", "/api/v1/agent/stream/health"),
    ("GET", "/api/i18n/supported-languages"),
    ("GET", "/api/i18n/supported-regions"),
    ("GET", "/api/i18n/locale"),
    ("GET", "/api/i18n/translations/{language}"),
    ("GET", "/api/i18n/translation"),
    ("GET", "/api/i18n/localization-config/{region}"),
    ("GET", "/api-key/status"),
    ("GET", "/ready"),
    ("GET", "/health"),
    ("GET", "/"),
    ("GET", "/chat"),
    ("POST", "/api/v1/csrf-token"),
}

SIGNATURE_ROUTES = {
    ("POST", "/api/v1/channels/telegram/webhook"),
    ("POST", "/api/v1/integrations/feishu/events"),
    ("POST", "/api/v1/sandbox/webhook/github"),
}


@dataclass(frozen=True)
class RouteAuditIssue:
    method: str
    path: str
    endpoint: str
    reason: str


def load_app(import_path: str = "backend.app.main:app") -> FastAPI:
    module_name, sep, attr_name = import_path.partition(":")
    if not sep or not module_name or not attr_name:
        raise ValueError("App import path must use module:attribute format.")
    module = importlib.import_module(module_name)
    app = getattr(module, attr_name)
    if not isinstance(app, FastAPI):
        raise TypeError(f"{import_path} did not resolve to a FastAPI app.")
    return app


def _call_name(call: Any) -> str:
    return getattr(call, "__name__", f"{type(call).__module__}.{type(call).__qualname__}")


def _call_ref(call: Any) -> str:
    module = getattr(call, "__module__", type(call).__module__)
    qualname = getattr(call, "__qualname__", getattr(call, "__name__", type(call).__qualname__))
    return f"{module}.{qualname}"


def _dependency_calls(route: APIRoute) -> set[Any]:
    calls: set[Any] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        calls.add(dependency.call)
        stack.extend(dependency.dependencies)
    return calls


def _auth_dependency_objects() -> set[Any]:
    calls = {dependencies.get_current_principal}
    refresh_principal = getattr(dependencies, "get_refresh_principal", None)
    if refresh_principal is not None:
        calls.add(refresh_principal)
    return calls


def _has_auth_dependency(route: APIRoute) -> bool:
    calls = _dependency_calls(route)
    if calls & _auth_dependency_objects():
        return True
    return bool({_call_ref(call) for call in calls} & AUTH_DEPENDENCY_REFS)


def _has_signature_strategy(route: APIRoute) -> bool:
    calls = _dependency_calls(route)
    return bool({_call_ref(call) for call in calls} & SIGNATURE_DEPENDENCY_REFS)


def _has_restrictive_permission_dependency(route: APIRoute) -> bool:
    calls = _dependency_calls(route)
    return any(
        isinstance(call, PermissionDependency)
        and call.permission not in {"agent:read", "task:read", "tool:read", "workflow:read", "memory:read", "skill:read", "sandbox:read", "chat:read"}
        for call in calls
    )


def _endpoint_ref(route: APIRoute) -> str:
    endpoint = route.endpoint
    return f"{getattr(endpoint, '__module__', '<unknown>')}.{getattr(endpoint, '__qualname__', _call_name(endpoint))}"


def audit_routes(
    app: FastAPI,
    *,
    public_routes: set[tuple[str, str]] | None = None,
    signature_routes: set[tuple[str, str]] | None = None,
) -> list[RouteAuditIssue]:
    public = public_routes if public_routes is not None else PUBLIC_ROUTES
    signature = signature_routes if signature_routes is not None else SIGNATURE_ROUTES
    issues: list[RouteAuditIssue] = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or []):
            route_key = (method, route.path)
            if route_key in public:
                continue
            if route_key in signature:
                continue
            if not route.path.startswith("/api/"):
                continue
            if not _has_auth_dependency(route) and not _has_restrictive_permission_dependency(route):
                issues.append(
                    RouteAuditIssue(
                        method=method,
                        path=route.path,
                        endpoint=_endpoint_ref(route),
                        reason="mounted API route lacks get_current_principal or an equivalent auth strategy",
                    )
                )

    return issues


def issues_to_dicts(issues: Iterable[RouteAuditIssue]) -> list[dict[str, str]]:
    return [asdict(issue) for issue in issues]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit mounted FastAPI routes for auth coverage.")
    parser.add_argument("--app", default="backend.app.main:app", help="FastAPI app import path, module:attribute.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    issues = audit_routes(load_app(args.app))
    if args.json:
        print(json.dumps({"ok": not issues, "issues": issues_to_dicts(issues)}, indent=2, sort_keys=True))
    elif issues:
        print("Mounted route auth audit failed:")
        for issue in issues:
            print(f"- {issue.method} {issue.path}: {issue.reason} ({issue.endpoint})")
    else:
        print("Mounted route auth audit passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
