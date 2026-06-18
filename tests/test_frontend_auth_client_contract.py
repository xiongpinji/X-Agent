from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read_frontend(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_auth_header_helper_defines_single_storage_key_and_bearer_header():
    source = read_frontend("frontend/src/services/authHeaders.ts")

    assert "AUTH_TOKEN_STORAGE_KEY = 'auth_token'" in source
    assert "localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)" in source
    assert "Authorization: `Bearer ${token}`" in source


def test_fetch_api_client_uses_shared_auth_headers_for_json_and_downloads():
    source = read_frontend("frontend/src/services/apiClient.ts")

    assert "import { getAuthHeaders } from './authHeaders'" in source
    assert "const headers = { ...this.headers, ...getAuthHeaders(), ...options?.headers }" in source
    assert "headers: getAuthHeaders()" in source


def test_axios_clients_use_shared_auth_header_builder():
    for relative_path in [
        "frontend/src/services/api.ts",
        "frontend/src/services/feedback.ts",
    ]:
        source = read_frontend(relative_path)
        assert "getAuthHeaders" in source
        assert "config.headers.Authorization = authHeaders.Authorization" in source


def test_panda_resources_client_uses_shared_auth_headers():
    source = read_frontend("frontend/src/panda/api/resourcesHttpClient.ts")

    assert "import { getAuthHeaders, getStoredAuthToken } from '../../services/authHeaders'" in source
    assert "getToken = getStoredAuthToken" in source
    assert "Object.assign(headers, getAuthHeaders(getToken))" in source
    assert "localStorage.getItem('auth_token')" not in source


def test_sse_client_keeps_bearer_tokens_out_of_eventsource_urls():
    source = read_frontend("frontend/src/services/sseClient.ts")

    assert "export type SSEAuthMode = 'cookie-or-signed-url'" in source
    assert "getAuthMode(): SSEAuthMode" in source
    assert "createAgentStreamUrl(runId)" in source
    assert "new EventSource(url)" in source
    assert "auth_token" not in source
    assert "Bearer" not in source


def test_frontend_clients_do_not_duplicate_raw_bearer_token_construction():
    allowed_files = {"frontend/src/services/authHeaders.ts"}
    violations: list[str] = []
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed_files or "/__tests__/" in relative:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "localStorage.getItem('auth_token')" in source or 'localStorage.getItem("auth_token")' in source:
            violations.append(f"{relative}: direct auth_token read")
        if re.search(r"Authorization\s*[:=]\s*`Bearer", source):
            violations.append(f"{relative}: direct bearer Authorization construction")

    assert not violations


def test_frontend_eventsource_usage_goes_through_signed_url_client():
    violations: list[str] = []
    allowed_files = {
        "frontend/src/services/sseClient.ts",
        "frontend/src/hooks/useStreamingEvents.ts",
        "frontend/src/console/hooks/useConsoleRealtimeSync.ts",
        "frontend/src/components/streaming/RealtimeVisualization.tsx",
    }
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed_files or "/__tests__/" in relative:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "new EventSource" in source or "EventSource(" in source:
            violations.append(relative)

    assert not violations


def test_allowed_eventsource_clients_request_signed_urls_first():
    expected = {
        "frontend/src/services/sseClient.ts": "createAgentStreamUrl(runId)",
        "frontend/src/hooks/useStreamingEvents.ts": "createAgentStreamUrl(runId",
        "frontend/src/console/hooks/useConsoleRealtimeSync.ts": "createMessagesStreamUrl(getStreamUrl())",
        "frontend/src/components/streaming/RealtimeVisualization.tsx": "createAgentStreamUrl(runId)",
    }

    for relative, token in expected.items():
        source = read_frontend(relative)
        assert token in source


def test_protected_raw_fetches_use_shared_auth_headers():
    protected_prefixes = (
        "/api/v1/workbench",
        "/api/v1/messages",
        "/api/v1/execution-control",
        "/api/v1/tools-control",
        "/api/v1/memory-control",
        "/api/v1/organization-control",
        "/api/v1/navigation-control",
    )
    violations: list[str] = []
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if "/__tests__/" in relative:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"fetch\(\s*([`'\"])(/api/v1/[^`'\"]+)\1", source):
            api_path = match.group(2)
            if not api_path.startswith(protected_prefixes):
                continue
            line = source.count("\n", 0, match.start()) + 1
            start = max(0, match.start() - 200)
            end = min(len(source), match.end() + 500)
            snippet = source[start:end]
            uses_shared_headers_variable = (
                "getAuthHeaders()" in source[: match.start()]
                and re.search(r"const\s+headers\s*=\s*\{[^}]*getAuthHeaders\(\)", source[: match.start()], re.DOTALL)
                and re.search(r"headers\s*[,}]", snippet)
            )
            if "getAuthHeaders()" not in snippet:
                if uses_shared_headers_variable:
                    continue
                violations.append(f"{relative}:{line}: {api_path}")

    assert not violations
