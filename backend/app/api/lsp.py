"""P2-F Part 1: HTTP bridge for the X-Agent LSP server.

Editors that cannot speak raw LSP over stdio/TCP (e.g. web-based IDEs) can call
the same language features through these REST endpoints.  Internally they reuse
the provider classes from :mod:`backend.app.core.lsp_server` so behaviour is
identical to the standalone LSP process.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from backend.app.core.lsp_server import TextDocument, get_lsp_server
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/lsp", tags=["lsp"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _doc_from_body(body: dict[str, Any]) -> TextDocument:
    """Build a TextDocument from an HTTP request body."""
    return TextDocument(
        uri=body.get("uri", "untitled:buffer"),
        language_id=body.get("language", body.get("languageId", "plaintext")),
        version=int(body.get("version", 0)),
        text=body.get("text", body.get("content", "")),
    )


@router.post("/initialize")
async def lsp_initialize(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: LSP handshake — returns server capabilities."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    result = await server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": body,
    })
    return {
        "capabilities": (result or {}).get("result", {}).get("capabilities", {}),
        "serverInfo": {"name": "xagent-lsp", "version": "1.0.0"},
    }


@router.post("/completion")
async def lsp_completion(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: AI-powered code completion at a cursor position."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    doc = _doc_from_body(body)
    server.documents[doc.uri] = doc

    line = int(body.get("line", body.get("position", {}).get("line", 0)))
    character = int(body.get("character", body.get("position", {}).get("character", 0)))
    items = await server.completion.complete(doc, line, character)
    return {
        "uri": doc.uri,
        "isIncomplete": False,
        "items": [i.to_lsp() for i in items],
    }


@router.post("/hover")
async def lsp_hover(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Explain the symbol under the cursor."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    doc = _doc_from_body(body)
    server.documents[doc.uri] = doc

    line = int(body.get("line", body.get("position", {}).get("line", 0)))
    character = int(body.get("character", body.get("position", {}).get("character", 0)))
    hover = await server.hover_provider.hover(doc, line, character)
    return {"uri": doc.uri, "hover": hover}


@router.post("/diagnostic")
async def lsp_diagnostic(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: AI-powered diagnostics for a document."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    doc = _doc_from_body(body)
    server.documents[doc.uri] = doc

    diagnostics = await server.diagnostics.diagnose(doc)
    return {
        "uri": doc.uri,
        "kind": "full",
        "items": [d.to_lsp() for d in diagnostics],
    }


@router.post("/code-action")
async def lsp_code_action(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Quick fixes and refactoring suggestions."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    doc = _doc_from_body(body)
    server.documents[doc.uri] = doc

    rng = body.get("range", {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}})
    diagnostics = body.get("diagnostics", [])
    actions = await server.code_actions.actions(doc, rng, diagnostics)
    return {"uri": doc.uri, "actions": [a.to_lsp() for a in actions]}


@router.post("/symbol")
async def lsp_workspace_symbol(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Semantic workspace symbol search."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    server = get_lsp_server()
    symbols = server.symbols.workspace_symbols(body.get("query", ""))
    return {"query": body.get("query", ""), "symbols": symbols}


@router.get("/status")
async def lsp_status(principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: LSP server status and capabilities."""
    enforce_scope(principal, "agent:run")
    return get_lsp_server().status()
