"""P2-F Part 1: Language Server Protocol (LSP) server for IDE integration.

Implements a Language Server Protocol endpoint backed by X-Agent's LLM stack so
that any LSP-compatible editor (VS Code, Neovim, JetBrains via plugin, …) can
get AI-powered completion, hover explanations, diagnostics, code actions,
semantic symbol search and go-to-definition.

Transport
---------
The canonical LSP transport is JSON-RPC 2.0 framed with ``Content-Length``
headers over stdin/stdout.  This module implements that framing so the server
can run as a standalone process::

    python -m backend.app.core.lsp_server            # stdio (default)
    python -m backend.app.core.lsp_server --tcp 7777 # TCP (for debugging)

The same provider classes are reused by the HTTP bridge in
``backend/app/api/lsp.py`` so editors that cannot speak raw LSP can still call
the features over REST.

Design notes
------------
* Every feature degrades gracefully: if no LLM backend is configured the
  providers fall back to lightweight heuristics so the server is always usable.
* The server is intentionally dependency-light (stdlib only) so it can be
  launched by an editor without pulling the whole FastAPI app.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("xagent.lsp")

# JSON-RPC 2.0 error codes (LSP spec).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_NOT_INITIALIZED = -32002

LSP_PROTOCOL_VERSION = "2.0"

# ─── LLM access (optional) ────────────────────────────────────────────────────


def _get_llm_router() -> Any | None:
    """Return the shared LLM router if the full app is importable, else None.

    The standalone stdio server may run in a minimal environment; importing the
    container can fail (missing settings/env).  We never want that to crash the
    editor, so any failure degrades to heuristic mode.
    """
    try:  # pragma: no cover - environment dependent
        from backend.app.container import container

        return container.llm_router
    except Exception:
        return None


async def _llm_complete(prompt: str, *, system: str | None = None) -> str | None:
    """Ask the LLM router for a single completion string.

    Returns ``None`` when no backend is available so callers can fall back.
    """
    router = _get_llm_router()
    if router is None:
        return None
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:  # pragma: no cover - network/backend dependent
        response = await router.chat(messages, [])
        return getattr(response, "content", None)
    except Exception as exc:
        logger.debug("LLM completion failed: %s", exc)
        return None


# ─── Data types ───────────────────────────────────────────────────────────────


@dataclass
class TextDocument:
    """In-memory representation of an open document."""

    uri: str
    language_id: str = "plaintext"
    version: int = 0
    text: str = ""

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines(keepends=True)

    def line_text(self, line: int) -> str:
        lines = self.text.split("\n")
        if 0 <= line < len(lines):
            return lines[line]
        return ""

    def word_at(self, line: int, character: int) -> str:
        """Return the identifier under the cursor (used for hover/definition)."""
        text = self.line_text(line)
        if not text:
            return ""
        start = end = character
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_."):
            start -= 1
        while end < len(text) and (text[end].isalnum() or text[end] in "_."):
            end += 1
        return text[start:end]


@dataclass
class CompletionItem:
    label: str
    kind: int = 1  # 1 = Text
    detail: str = ""
    documentation: str = ""
    insert_text: str = ""
    sort_text: str = ""

    def to_lsp(self) -> dict[str, Any]:
        item: dict[str, Any] = {"label": self.label, "kind": self.kind}
        if self.detail:
            item["detail"] = self.detail
        if self.documentation:
            item["documentation"] = self.documentation
        item["insertText"] = self.insert_text or self.label
        if self.sort_text:
            item["sortText"] = self.sort_text
        return item


@dataclass
class Diagnostic:
    range: dict[str, Any]
    message: str
    severity: int = 1  # 1=Error 2=Warning 3=Info 4=Hint
    source: str = "xagent"
    code: str = ""

    def to_lsp(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "range": self.range,
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
        }
        if self.code:
            d["code"] = self.code
        return d


@dataclass
class CodeAction:
    title: str
    kind: str = "quickfix"
    detail: str = ""
    edit: dict[str, Any] | None = None

    def to_lsp(self) -> dict[str, Any]:
        action: dict[str, Any] = {"title": self.title, "kind": self.kind}
        if self.detail:
            action["detail"] = self.detail
        if self.edit:
            action["edit"] = self.edit
        return action


def _pos(line: int, character: int) -> dict[str, int]:
    return {"line": line, "character": character}


def _range(sl: int, sc: int, el: int, ec: int) -> dict[str, Any]:
    return {"start": _pos(sl, sc), "end": _pos(el, ec)}


# ─── Providers ────────────────────────────────────────────────────────────────


class CompletionProvider:
    """Context-aware completions using project knowledge + LLM."""

    KEYWORDS: dict[str, list[str]] = {
        "python": ["def ", "class ", "import ", "from ", "return ", "async def ", "await ", "yield "],
        "javascript": ["function ", "const ", "let ", "return ", "export ", "import ", "await "],
        "typescript": ["function ", "const ", "interface ", "type ", "export ", "import "],
    }

    async def complete(self, doc: TextDocument, line: int, character: int) -> list[CompletionItem]:
        prefix = doc.line_text(line)[:character]
        items: list[CompletionItem] = []

        # 1) Local symbols defined in the document (defs/classes/assignments).
        for sym, kind in self._local_symbols(doc):
            if sym.startswith(prefix.strip()) and sym not in {i.label for i in items}:
                items.append(CompletionItem(label=sym, kind=kind, detail="local symbol", sort_text="0"))

        # 2) Language keywords.
        lang = doc.language_id.lower()
        for kw in self.KEYWORDS.get(lang, []):
            items.append(CompletionItem(label=kw.strip(), kind=14, detail="keyword", insert_text=kw, sort_text="2"))

        # 3) AI-powered completion via LLM (best effort).
        ai = await self._ai_completion(doc, prefix)
        if ai:
            items.insert(0, CompletionItem(label=ai, kind=1, detail="AI suggestion", documentation="Generated by X-Agent", sort_text="0"))

        return items[:50]

    async def _ai_completion(self, doc: TextDocument, prefix: str) -> str | None:
        prompt = (
            f"Complete the following {doc.language_id} code. Return ONLY the code "
            f"that should follow the cursor, no explanations.\n\n{doc.text}\n# CURSOR: {prefix}"
        )
        raw = await _llm_complete(prompt, system="You are a precise code completion engine.")
        if not raw:
            return None
        return raw.strip().splitlines()[0].strip() if raw.strip() else None

    @staticmethod
    def _local_symbols(doc: TextDocument) -> list[tuple[str, int]]:
        symbols: list[tuple[str, int]] = []
        for ln in doc.text.split("\n"):
            stripped = ln.strip()
            m = re.match(r"(?:async\s+)?def\s+(\w+)", stripped)
            if m:
                symbols.append((m.group(1), 3))  # 3 = Function
                continue
            m = re.match(r"class\s+(\w+)", stripped)
            if m:
                symbols.append((m.group(1), 7))  # 7 = Class
                continue
            m = re.match(r"(\w+)\s*=", stripped)
            if m and not stripped.startswith(("def", "class", "return")):
                symbols.append((m.group(1), 6))  # 6 = Variable
        return symbols


class HoverProvider:
    """Explain the symbol under the cursor via LLM."""

    async def hover(self, doc: TextDocument, line: int, character: int) -> dict[str, Any] | None:
        word = doc.word_at(line, character)
        if not word:
            return None

        explanation = await _llm_complete(
            f"Explain the programming symbol '{word}' as used in this "
            f"{doc.language_id} snippet. Be concise (2-3 sentences).\n\n{doc.text}",
            system="You are a helpful code tutor. Respond in plain text.",
        )
        if not explanation:
            explanation = f"`{word}` — no AI explanation available (LLM offline)."

        return {
            "contents": {"kind": "markdown", "value": f"**{word}**\n\n{explanation}"},
            "range": _range(line, character - len(word), line, character),
        }


class DiagnosticProvider:
    """Background analysis of open files — heuristic + AI error detection."""

    async def diagnose(self, doc: TextDocument) -> list[Diagnostic]:
        diagnostics = self._heuristic(doc)
        ai_diags = await self._ai_diagnose(doc)
        diagnostics.extend(ai_diags)
        return diagnostics

    def _heuristic(self, doc: TextDocument) -> list[Diagnostic]:
        results: list[Diagnostic] = []
        for i, line in enumerate(doc.text.split("\n")):
            # Unbalanced brackets on a single line (rough but useful).
            if line.count("(") != line.count(")"):
                results.append(Diagnostic(
                    range=_range(i, 0, i, max(len(line), 1)),
                    message="Unbalanced parentheses on this line.",
                    severity=2, code="brackets",
                ))
            if re.search(r"\bTODO\b|\bFIXME\b", line):
                results.append(Diagnostic(
                    range=_range(i, 0, i, max(len(line), 1)),
                    message="Unresolved TODO/FIXME marker.",
                    severity=3, code="todo",
                ))
            if doc.language_id.lower() == "python" and re.search(r"\t", line) and "    " in line:
                results.append(Diagnostic(
                    range=_range(i, 0, i, max(len(line), 1)),
                    message="Mixed tabs and spaces in indentation.",
                    severity=2, code="indent",
                ))
        return results

    async def _ai_diagnose(self, doc: TextDocument) -> list[Diagnostic]:
        raw = await _llm_complete(
            "Analyze this code for likely bugs. Return a JSON array of objects "
            f'{{"line": int, "message": str, "severity": "error|warning"}}. '
            f"Return [] if none.\n\n{doc.text}",
            system="You are a static analysis engine. Output valid JSON only.",
        )
        if not raw:
            return []
        try:
            data = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
        except (ValueError, TypeError):
            return []
        out: list[Diagnostic] = []
        for entry in data if isinstance(data, list) else []:
            if not isinstance(entry, dict):
                continue
            ln = int(entry.get("line", 0))
            sev = 1 if str(entry.get("severity", "error")).lower() == "error" else 2
            out.append(Diagnostic(
                range=_range(ln, 0, ln, 1),
                message=str(entry.get("message", "Potential issue")),
                severity=sev, code="ai",
            ))
        return out


class CodeActionProvider:
    """Quick fixes and refactoring suggestions for a range/diagnostics."""

    async def actions(self, doc: TextDocument, rng: dict[str, Any], diagnostics: list[dict[str, Any]]) -> list[CodeAction]:
        actions: list[CodeAction] = []

        for diag in diagnostics:
            msg = str(diag.get("message", ""))
            if "parenthes" in msg.lower():
                actions.append(CodeAction(title="Auto-balance parentheses", kind="quickfix", detail=msg))
            if "todo" in msg.lower():
                actions.append(CodeAction(title="Resolve TODO", kind="quickfix", detail=msg))

        # Generic AI-driven refactor suggestions.
        raw = await _llm_complete(
            "Suggest up to 3 concrete refactoring actions for this code. Return a "
            f'JSON array of strings.\n\n{doc.text}',
            system="You are a refactoring expert. Output valid JSON only.",
        )
        if raw:
            try:
                data = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
                for title in data if isinstance(data, list) else []:
                    actions.append(CodeAction(title=str(title), kind="refactor"))
            except (ValueError, TypeError):
                pass

        if not actions:
            actions.append(CodeAction(title="Extract to function", kind="refactor.extract"))
            actions.append(CodeAction(title="Add type annotations", kind="refactor"))
        return actions


class SymbolProvider:
    """Semantic symbol search across open documents + workspace."""

    def __init__(self) -> None:
        self._docs: dict[str, TextDocument] = {}

    def register(self, docs: dict[str, TextDocument]) -> None:
        self._docs = docs

    def workspace_symbols(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        results: list[dict[str, Any]] = []
        pattern = re.compile(r"(?:async\s+)?(?:def|class)\s+(\w+)")
        for doc in self._docs.values():
            for i, line in enumerate(doc.text.split("\n")):
                m = pattern.search(line)
                if m and (not q or q in m.group(1).lower()):
                    kind = 12 if "class" in line else 13  # 12=Function 13=Variable-ish
                    results.append({
                        "name": m.group(1),
                        "kind": kind,
                        "location": {"uri": doc.uri, "range": _range(i, 0, i, len(line))},
                    })
        return results[:100]

    def definition(self, doc: TextDocument, line: int, character: int) -> list[dict[str, Any]]:
        word = doc.word_at(line, character)
        if not word:
            return []
        locations: list[dict[str, Any]] = []
        pattern = re.compile(rf"(?:async\s+)?(?:def|class)\s+{re.escape(word)}\b")
        for target in self._docs.values():
            for i, ln in enumerate(target.text.split("\n")):
                if pattern.search(ln):
                    locations.append({"uri": target.uri, "range": _range(i, 0, i, len(ln))})
        return locations


# ─── Server ───────────────────────────────────────────────────────────────────


@dataclass
class ServerCapabilities:
    completion: bool = True
    hover: bool = True
    code_action: bool = True
    diagnostic: bool = True
    workspace_symbol: bool = True
    definition: bool = True

    def to_lsp(self) -> dict[str, Any]:
        caps: dict[str, Any] = {"textDocumentSync": 1}  # 1 = Full
        if self.completion:
            caps["completionProvider"] = {"triggerCharacters": [".", "(", " "]}
        if self.hover:
            caps["hoverProvider"] = True
        if self.code_action:
            caps["codeActionProvider"] = True
        if self.diagnostic:
            caps["diagnosticProvider"] = {"interFileDependencies": False, "workspaceDiagnostics": False}
        if self.workspace_symbol:
            caps["workspaceSymbolProvider"] = True
        if self.definition:
            caps["definitionProvider"] = True
        return caps


class XAgentLSPServer:
    """Language Server Protocol server speaking JSON-RPC 2.0.

    Supports stdio (default, editor-facing) and TCP (debugging) transports.
    """

    def __init__(self, capabilities: ServerCapabilities | None = None) -> None:
        self.capabilities = capabilities or ServerCapabilities()
        self.completion = CompletionProvider()
        self.hover_provider = HoverProvider()
        self.diagnostics = DiagnosticProvider()
        self.code_actions = CodeActionProvider()
        self.symbols = SymbolProvider()
        self.documents: dict[str, TextDocument] = {}
        self.initialized = False
        self._shutdown_requested = False
        self.symbols.register(self.documents)

    # ── Public dispatch (also used by the HTTP bridge) ────────────────────────

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Dispatch a single JSON-RPC message; returns a response or None."""
        if "method" not in message:
            return self._error(message.get("id"), INVALID_REQUEST, "Missing method")

        method = message["method"]
        msg_id = message.get("id")
        params = message.get("params", {}) or {}

        handler = self._HANDLERS.get(method)
        if handler is None:
            if msg_id is None:  # unknown notification — ignore
                return None
            return self._error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        try:
            result = await handler(self, params)
        except _ExitServer:
            raise
        except Exception as exc:
            logger.exception("Handler error for %s", method)
            if msg_id is None:
                return None
            return self._error(msg_id, INTERNAL_ERROR, str(exc))

        if msg_id is None:  # notification — no response
            return None
        return {"jsonrpc": LSP_PROTOCOL_VERSION, "id": msg_id, "result": result}

    # ── Method handlers ───────────────────────────────────────────────────────

    async def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        self.initialized = True
        return {
            "capabilities": self.capabilities.to_lsp(),
            "serverInfo": {"name": "xagent-lsp", "version": "1.0.0"},
        }

    async def _initialized(self, params: dict[str, Any]) -> None:
        return None

    async def _shutdown(self, params: dict[str, Any]) -> None:
        self._shutdown_requested = True
        return None

    async def _exit(self, params: dict[str, Any]) -> None:
        raise _ExitServer()

    async def _did_open(self, params: dict[str, Any]) -> None:
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        self.documents[uri] = TextDocument(
            uri=uri,
            language_id=td.get("languageId", "plaintext"),
            version=td.get("version", 0),
            text=td.get("text", ""),
        )
        return None

    async def _did_change(self, params: dict[str, Any]) -> None:
        uri = params.get("textDocument", {}).get("uri", "")
        doc = self.documents.get(uri)
        if doc is None:
            return None
        changes = params.get("contentChanges", [])
        if changes:
            # Full sync: last change carries the whole text.
            doc.text = changes[-1].get("text", doc.text)
            doc.version = params.get("textDocument", {}).get("version", doc.version + 1)
        return None

    async def _did_close(self, params: dict[str, Any]) -> None:
        uri = params.get("textDocument", {}).get("uri", "")
        self.documents.pop(uri, None)
        return None

    async def _completion(self, params: dict[str, Any]) -> dict[str, Any]:
        doc, line, character = self._resolve_position(params)
        items = await self.completion.complete(doc, line, character)
        return {"isIncomplete": False, "items": [i.to_lsp() for i in items]}

    async def _hover(self, params: dict[str, Any]) -> dict[str, Any] | None:
        doc, line, character = self._resolve_position(params)
        return await self.hover_provider.hover(doc, line, character)

    async def _code_action(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        doc = self._resolve_doc(params)
        rng = params.get("range", _range(0, 0, 0, 0))
        diags = params.get("context", {}).get("diagnostics", [])
        actions = await self.code_actions.actions(doc, rng, diags)
        return [a.to_lsp() for a in actions]

    async def _diagnostic(self, params: dict[str, Any]) -> dict[str, Any]:
        doc = self._resolve_doc(params)
        diags = await self.diagnostics.diagnose(doc)
        return {"kind": "full", "items": [d.to_lsp() for d in diags]}

    async def _workspace_symbol(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self.symbols.workspace_symbols(params.get("query", ""))

    async def _definition(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        doc, line, character = self._resolve_position(params)
        return self.symbols.definition(doc, line, character)

    _HANDLERS: dict[str, Any] = {
        "initialize": _initialize,
        "initialized": _initialized,
        "shutdown": _shutdown,
        "exit": _exit,
        "textDocument/didOpen": _did_open,
        "textDocument/didChange": _did_change,
        "textDocument/didClose": _did_close,
        "textDocument/completion": _completion,
        "textDocument/hover": _hover,
        "textDocument/codeAction": _code_action,
        "textDocument/diagnostic": _diagnostic,
        "workspace/symbol": _workspace_symbol,
        "textDocument/definition": _definition,
    }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_doc(self, params: dict[str, Any]) -> TextDocument:
        uri = params.get("textDocument", {}).get("uri", "")
        doc = self.documents.get(uri)
        if doc is None:
            doc = TextDocument(uri=uri)
            self.documents[uri] = doc
        return doc

    def _resolve_position(self, params: dict[str, Any]) -> tuple[TextDocument, int, int]:
        doc = self._resolve_doc(params)
        position = params.get("position", {})
        return doc, int(position.get("line", 0)), int(position.get("character", 0))

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": LSP_PROTOCOL_VERSION,
            "id": msg_id,
            "error": {"code": code, "message": message},
        }

    # ── Transports ────────────────────────────────────────────────────────────

    async def serve_stdio(self) -> None:
        """Run the server over stdin/stdout using LSP Content-Length framing.

        Uses a thread executor for blocking stdio I/O.  This is the portable
        approach: asyncio's ``connect_read_pipe``/``connect_write_pipe`` are not
        reliable on Windows (Proactor event loop rejects redirected stdio
        handles with ``WinError 6``), so we keep the event loop for handler
        concurrency but perform the actual pipe I/O on worker threads.
        """
        loop = asyncio.get_event_loop()
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer
        logger.info("X-Agent LSP server listening on stdio")
        while True:
            message = await loop.run_in_executor(None, self._read_message_sync, stdin)
            if message is None:
                break
            try:
                response = await self.handle_message(message)
            except _ExitServer:
                break
            if response is not None:
                await loop.run_in_executor(None, self._write_message_sync, stdout, response)

    async def serve_tcp(self, host: str, port: int) -> None:
        """Run the server over TCP (one client at a time) for debugging."""
        async def _client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            logger.info("LSP TCP client connected")
            while True:
                message = await self._read_message(reader)
                if message is None:
                    break
                try:
                    response = await self.handle_message(message)
                except _ExitServer:
                    break
                if response is not None:
                    await self._write_message(writer, response)
            writer.close()

        server = await asyncio.start_server(_client, host, port)
        logger.info("X-Agent LSP server listening on tcp://%s:%d", host, port)
        async with server:
            await server.serve_forever()

    @staticmethod
    def _read_message_sync(stream: Any) -> dict[str, Any] | None:
        """Blocking read of one Content-Length framed message (stdio)."""
        headers: dict[str, str] = {}
        while True:
            line = stream.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            if b":" in line:
                key, _, value = line.partition(b":")
                headers[key.decode("ascii", "replace").strip().lower()] = value.decode("ascii", "replace").strip()

        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        chunks: list[bytes] = []
        remaining = length
        while remaining > 0:
            chunk = stream.read(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        try:
            return json.loads(b"".join(chunks).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    @staticmethod
    def _write_message_sync(stream: Any, message: dict[str, Any]) -> None:
        """Blocking write of one Content-Length framed message (stdio)."""
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        stream.write(header + body)
        stream.flush()

    @staticmethod
    async def _read_message(reader: asyncio.StreamReader) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            if b":" in line:
                key, _, value = line.partition(b":")
                headers[key.decode("ascii").strip().lower()] = value.decode("ascii").strip()

        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        body = await reader.readexactly(length)
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    @staticmethod
    async def _write_message(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        writer.write(header + body)
        await writer.drain()

    # ── Convenience for programmatic use / HTTP bridge ───────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "running": True,
            "initialized": self.initialized,
            "protocol_version": LSP_PROTOCOL_VERSION,
            "open_documents": len(self.documents),
            "capabilities": self.capabilities.to_lsp(),
            "llm_available": _get_llm_router() is not None,
        }


class _ExitServer(Exception):
    """Raised internally to break out of the serve loop on LSP exit."""


# ─── Module singletons ────────────────────────────────────────────────────────

_server_instance: XAgentLSPServer | None = None


def get_lsp_server() -> XAgentLSPServer:
    """Return the process-wide LSP server instance (created lazily)."""
    global _server_instance
    if _server_instance is None:
        _server_instance = XAgentLSPServer()
    return _server_instance


def _main() -> None:  # pragma: no cover - CLI entry point
    parser = argparse.ArgumentParser(description="X-Agent LSP server")
    parser.add_argument("--tcp", type=int, default=None, metavar="PORT", help="Listen on TCP port instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="TCP bind host (with --tcp)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        # Log to stderr so stdout stays clean for the LSP protocol.
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    server = get_lsp_server()
    try:
        if args.tcp:
            asyncio.run(server.serve_tcp(args.host, args.tcp))
        else:
            asyncio.run(server.serve_stdio())
    except KeyboardInterrupt:
        logger.info("LSP server stopped")


if __name__ == "__main__":  # pragma: no cover
    _main()
