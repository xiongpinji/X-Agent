"""API endpoints for advanced browser monitoring and automation."""

from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.services.browser.advanced_monitoring import advanced_browser_monitoring

router = APIRouter(prefix="/api/v1/browser/advanced", tags=["browser-advanced"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _require_browser_read(principal: Principal) -> None:
    enforce_scope(principal, "tools:read")


def _require_browser_operation(principal: Principal) -> None:
    enforce_scope(principal, "agent:run")


# Request/Response models
class NetworkRequestsRequest(BaseModel):
    session_id: str
    url_pattern: Optional[str] = None


class NetworkRequestsResponse(BaseModel):
    requests: list[dict] = Field(default_factory=list)
    count: int = 0


class NetworkSummaryResponse(BaseModel):
    total_requests: int
    total_responses: int
    failed_responses: int
    total_duration_ms: float
    average_response_time_ms: float


class ElementTreeRequest(BaseModel):
    session_id: str


class ElementTreeResponse(BaseModel):
    root: dict
    elements: dict = Field(default_factory=dict)
    timestamp: float


class ElementRefRequest(BaseModel):
    session_id: str
    ref: str


class ElementRefResponse(BaseModel):
    ref: str
    tag_name: str
    element_type: str
    text: str
    visible: bool
    enabled: bool


class ElementActionRequest(BaseModel):
    session_id: str
    ref: str
    value: Optional[str] = None


class ElementActionResponse(BaseModel):
    success: bool
    message: str = ""


class ConsoleMessagesRequest(BaseModel):
    session_id: str
    pattern: Optional[str] = None
    only_errors: bool = False


class ConsoleMessageResponse(BaseModel):
    type: str
    text: str
    timestamp: float
    location: Optional[str] = None


class ConsoleMessagesResponse(BaseModel):
    messages: list[ConsoleMessageResponse] = Field(default_factory=list)
    count: int = 0


class ConsoleSummaryResponse(BaseModel):
    total_messages: int
    error_count: int
    warning_count: int
    log_count: int
    has_errors: bool
    has_warnings: bool


class FindElementRequest(BaseModel):
    session_id: str
    description: str
    limit: int = 5


class FoundElement(BaseModel):
    selector: str
    confidence: float
    reason: str
    text: Optional[str] = None
    tag_name: Optional[str] = None


class FindElementResponse(BaseModel):
    elements: list[FoundElement] = Field(default_factory=list)
    count: int = 0


class SnapshotRequest(BaseModel):
    session_id: str
    label: str = ""
    include_accessibility: bool = True
    include_network: bool = False
    include_console: bool = False


class SnapshotResponse(BaseModel):
    dom: dict
    accessibility: Optional[dict] = None
    network: Optional[dict] = None
    console: Optional[dict] = None
    timestamp: float
    label: str


class CompareSnapshotsRequest(BaseModel):
    session_id: str
    before_label: str
    after_label: str


class SnapshotDiffResponse(BaseModel):
    before_label: str
    after_label: str
    dom_changed: bool
    title_changed: bool
    url_changed: bool
    network_changed: bool
    console_changed: bool
    error_count_increased: bool


# Network monitoring endpoints
@router.post("/network/requests", response_model=NetworkRequestsResponse)
async def get_network_requests(
    request: NetworkRequestsRequest,
    principal: PrincipalDependency,
) -> NetworkRequestsResponse:
    """Get captured network requests."""
    _require_browser_read(principal)
    try:
        requests = await advanced_browser_monitoring.get_network_requests(
            request.session_id,
            request.url_pattern,
        )
        return NetworkRequestsResponse(requests=requests, count=len(requests))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/responses", response_model=NetworkRequestsResponse)
async def get_network_responses(
    request: NetworkRequestsRequest,
    principal: PrincipalDependency,
) -> NetworkRequestsResponse:
    """Get captured network responses."""
    _require_browser_read(principal)
    try:
        responses = await advanced_browser_monitoring.get_network_responses(
            request.session_id,
            request.url_pattern,
        )
        return NetworkRequestsResponse(requests=responses, count=len(responses))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/summary", response_model=NetworkSummaryResponse)
async def get_network_summary(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> NetworkSummaryResponse:
    """Get network activity summary."""
    _require_browser_read(principal)
    try:
        summary = await advanced_browser_monitoring.get_network_summary(request.session_id)
        return NetworkSummaryResponse(**summary)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/clear")
async def clear_network_history(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> dict:
    """Clear network history."""
    _require_browser_operation(principal)
    try:
        await advanced_browser_monitoring.clear_network_history(request.session_id)
        return {"success": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Element reference endpoints
@router.post("/elements/tree", response_model=ElementTreeResponse)
async def build_element_tree(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> ElementTreeResponse:
    """Build element reference tree."""
    _require_browser_read(principal)
    try:
        tree = await advanced_browser_monitoring.build_element_tree(request.session_id)
        return ElementTreeResponse(**tree)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/elements/{ref}", response_model=ElementRefResponse)
async def get_element_by_ref(
    session_id: str,
    ref: str,
    principal: PrincipalDependency,
) -> ElementRefResponse:
    """Get element by reference."""
    _require_browser_read(principal)
    try:
        elem = await advanced_browser_monitoring.get_element_by_ref(session_id, ref)
        if not elem:
            raise HTTPException(status_code=404, detail="Element not found")
        return ElementRefResponse(**elem)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/elements/{ref}/click", response_model=ElementActionResponse)
async def click_element_by_ref(
    session_id: str,
    ref: str,
    principal: PrincipalDependency,
) -> ElementActionResponse:
    """Click element by reference."""
    _require_browser_operation(principal)
    try:
        success = await advanced_browser_monitoring.click_by_ref(session_id, ref)
        return ElementActionResponse(
            success=success,
            message="Element clicked" if success else "Failed to click element",
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/elements/{ref}/fill", response_model=ElementActionResponse)
async def fill_element_by_ref(
    session_id: str,
    ref: str,
    request: ElementActionRequest,
    principal: PrincipalDependency,
) -> ElementActionResponse:
    """Fill element by reference."""
    _require_browser_operation(principal)
    try:
        if not request.value:
            raise HTTPException(status_code=400, detail="Value is required")
        success = await advanced_browser_monitoring.fill_by_ref(session_id, ref, request.value)
        return ElementActionResponse(
            success=success,
            message="Element filled" if success else "Failed to fill element",
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Console monitoring endpoints
@router.post("/console/messages", response_model=ConsoleMessagesResponse)
async def get_console_messages(
    request: ConsoleMessagesRequest,
    principal: PrincipalDependency,
) -> ConsoleMessagesResponse:
    """Get console messages."""
    _require_browser_read(principal)
    try:
        messages = await advanced_browser_monitoring.get_console_messages(
            request.session_id,
            request.pattern,
            request.only_errors,
        )
        return ConsoleMessagesResponse(
            messages=[ConsoleMessageResponse(**m) for m in messages],
            count=len(messages),
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/console/errors", response_model=ConsoleMessagesResponse)
async def get_console_errors(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> ConsoleMessagesResponse:
    """Get console errors."""
    _require_browser_read(principal)
    try:
        errors = await advanced_browser_monitoring.get_console_errors(request.session_id)
        return ConsoleMessagesResponse(
            messages=[ConsoleMessageResponse(**e) for e in errors],
            count=len(errors),
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/console/summary", response_model=ConsoleSummaryResponse)
async def get_console_summary(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> ConsoleSummaryResponse:
    """Get console summary."""
    _require_browser_read(principal)
    try:
        summary = await advanced_browser_monitoring.get_console_summary(request.session_id)
        return ConsoleSummaryResponse(**summary)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/console/clear")
async def clear_console_messages(
    request: ElementTreeRequest,
    principal: PrincipalDependency,
) -> dict:
    """Clear console messages."""
    _require_browser_operation(principal)
    try:
        await advanced_browser_monitoring.clear_console_messages(request.session_id)
        return {"success": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Natural language locator endpoints
@router.post("/elements/find", response_model=FindElementResponse)
async def find_elements_by_description(
    request: FindElementRequest,
    principal: PrincipalDependency,
) -> FindElementResponse:
    """Find elements by natural language description."""
    _require_browser_read(principal)
    try:
        elements = await advanced_browser_monitoring.find_elements_by_description(
            request.session_id,
            request.description,
            request.limit,
        )
        return FindElementResponse(
            elements=[FoundElement(**e) for e in elements],
            count=len(elements),
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Page snapshot endpoints
@router.post("/snapshot", response_model=SnapshotResponse)
async def capture_snapshot(
    request: SnapshotRequest,
    principal: PrincipalDependency,
) -> SnapshotResponse:
    """Capture page snapshot."""
    _require_browser_read(principal)
    try:
        snapshot = await advanced_browser_monitoring.capture_snapshot(
            request.session_id,
            request.label,
            request.include_accessibility,
            request.include_network,
            request.include_console,
        )
        return SnapshotResponse(**snapshot)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot/compare", response_model=SnapshotDiffResponse)
async def compare_snapshots(
    request: CompareSnapshotsRequest,
    principal: PrincipalDependency,
) -> SnapshotDiffResponse:
    """Compare two snapshots."""
    _require_browser_read(principal)
    try:
        diff = await advanced_browser_monitoring.compare_snapshots(
            request.session_id,
            request.before_label,
            request.after_label,
        )
        if not diff:
            raise HTTPException(status_code=404, detail="Snapshots not found")
        return SnapshotDiffResponse(**diff)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot/diff")
async def get_dom_diff(
    request: CompareSnapshotsRequest,
    principal: PrincipalDependency,
) -> dict:
    """Get DOM diff between snapshots."""
    _require_browser_read(principal)
    try:
        diff = await advanced_browser_monitoring.get_dom_diff(
            request.session_id,
            request.before_label,
            request.after_label,
        )
        if diff is None:
            raise HTTPException(status_code=404, detail="Snapshots not found")
        return {"diff_lines": diff, "count": len(diff)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
