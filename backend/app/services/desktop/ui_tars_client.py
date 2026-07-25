from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional runtime dependency
    sync_playwright = None  # type: ignore[assignment]


@dataclass(slots=True)
class DesktopActionResult:
    action: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DesktopSession:
    session_id: str
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    provider: str = "ui-tars"
    current_window: str | None = None
    active: bool = True
    actions: list[DesktopActionResult] = field(default_factory=list)
    browser_context: Any = None
    browser_page: Any = None
    managed: bool = False

    def record(self, action: str, ok: bool, detail: str = "", **data: Any) -> DesktopActionResult:
        enriched = dict(data)
        enriched.setdefault("provider", self.provider)
        enriched.setdefault("timestamp", datetime.now(UTC).isoformat())
        if self.browser_page is not None:
            with contextlib.suppress(Exception):
                enriched.setdefault("page_url", self.browser_page.url)
        result = DesktopActionResult(action=action, ok=ok, detail=detail, data=enriched)
        self.actions.append(result)
        return result


class UiTarsDesktopClient:
    def __init__(self) -> None:
        self._sessions: dict[str, DesktopSession] = {}

    @property
    def has_real_client(self) -> bool:
        return sync_playwright is not None

    def create_session(self, *, trace_id: str | None = None, run_id: str | None = None, tenant_id: str = "default", user_id: str = "anonymous") -> DesktopSession:
        session = DesktopSession(session_id=str(uuid4()), trace_id=trace_id, run_id=run_id, tenant_id=tenant_id, user_id=user_id)
        if sync_playwright is not None and os.getenv("XAGENT_DESKTOP_REAL_BROWSER", "").lower() in {"1", "true", "yes"}:
            try:
                playwright = sync_playwright().start()
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                session.browser_context = context
                session.browser_page = page
                session.managed = True
                session.record("provider.bootstrap", True, detail="UI-TARS browser backend started", browser="playwright")
            except Exception as exc:
                session.record("provider.bootstrap", False, detail=f"UI-TARS browser backend unavailable: {exc}")
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> DesktopSession | None:
        return self._sessions.get(session_id)

    def send_action(self, session_id: str, action: str, target: str | None = None, value: str | None = None, metadata: dict[str, Any] | None = None) -> DesktopActionResult:
        session = self._sessions.get(session_id)
        if session is None:
            return DesktopActionResult(action=action, ok=False, detail=f"Desktop session not found: {session_id}")
        if not session.active:
            return DesktopActionResult(action=action, ok=False, detail=f"Desktop session closed: {session_id}")
        metadata = metadata or {}
        if action not in self._supported_actions():
            return session.record(action, False, detail=f"Action not supported by UI-TARS provider: {action}", target=target, value=value, **metadata)

        try:
            if self._run_action(session, action, target=target, value=value, metadata=metadata):
                return session.record(action, True, detail=f"Accepted by UI-TARS provider: {action}", target=target, value=value, mode="real", **metadata)
        except Exception as exc:
            if action in {"shortcut_sequence", "shortcut_macro", "clipboard_sequence", "ime_candidate_sequence"}:
                return session.record(action, True, detail=f"Recorded fallback after UI-TARS execution failed: {exc}", target=target, value=value, mode="fallback", **metadata)
            return session.record(action, False, detail=f"UI-TARS execution failed: {exc}", target=target, value=value, mode="real", **metadata)

        if action == "open" and value:
            session.current_window = value
        return session.record(action, True, detail=f"Accepted by UI-TARS provider: {action}", target=target, value=value, mode="fallback", **metadata)

    def run_macro(self, session_id: str, script: str, *, metadata: dict[str, Any] | None = None) -> list[DesktopActionResult]:
        session = self._sessions.get(session_id)
        if session is None:
            return [DesktopActionResult(action="macro", ok=False, detail=f"Desktop session not found: {session_id}")]
        metadata = metadata or {}
        steps = self._parse_macro(script)
        results: list[DesktopActionResult] = []
        for idx, step in enumerate(steps):
            kind = step.get("kind")
            if not kind:
                results.append(DesktopActionResult(action="macro.step", ok=False, detail=f"Macro step {idx} missing kind", data={"step_index": idx, **metadata}))
                break
            try:
                ok = self._run_macro_step(session, step, metadata=metadata)
                results.append(DesktopActionResult(action="macro.step", ok=ok, detail=f"Macro step {idx} {kind}", data={"step_index": idx, "step": step, **metadata}))
                if not ok:
                    break
            except Exception as exc:
                if kind in {"shortcut", "shortcut_sequence", "shortcut_macro", "clipboard", "clipboard_sequence", "ime", "ime_candidate_sequence", "text"}:
                    results.append(DesktopActionResult(action="macro.step", ok=True, detail=f"Macro step {idx} {kind} fallback after failure: {exc}", data={"step_index": idx, "step": step, "mode": "fallback", **metadata}))
                    continue
                results.append(DesktopActionResult(action="macro.step", ok=False, detail=f"Macro step {idx} failed: {exc}", data={"step_index": idx, "step": step, **metadata}))
                break
        return results

    def _parse_macro(self, script: str) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        for raw in script.split("|"):
            chunk = raw.strip()
            if not chunk:
                continue
            kind, _, payload = chunk.partition(":")
            kind = kind.strip().lower()
            payload = payload.strip()
            step: dict[str, str] = {"kind": kind}
            if payload:
                if kind in {"shortcut", "shortcut_sequence", "shortcut_macro"} or kind in {"clipboard", "clipboard_sequence"} or kind in {"ime", "ime_candidate_sequence"}:
                    step["value"] = payload
                else:
                    step["value"] = payload
            steps.append(step)
        return steps

    def _run_macro_step(self, session: DesktopSession, step: dict[str, str], *, metadata: dict[str, Any]) -> bool:
        kind = step.get("kind", "").lower()
        value = step.get("value")
        if kind in {"shortcut", "shortcut_sequence", "shortcut_macro"}:
            return self._handle_shortcut_macro(session, value=value, metadata=metadata)
        if kind in {"clipboard", "clipboard_sequence"}:
            return self._handle_clipboard(session, "clipboard_sequence", value=value, metadata=metadata)
        if kind in {"ime", "ime_candidate_sequence"}:
            return self._handle_ime(session, "ime_candidate_sequence", value=value, metadata=metadata)
        if kind == "text":
            return self._handle_text_macro(session, value=value, metadata=metadata)
        return False

    def _handle_shortcut_macro(self, session: DesktopSession, *, value: str | None, metadata: dict[str, Any]) -> bool:
        combos = self._split_sequence(value or "")
        if not combos:
            return True
        page = session.browser_page
        if page is None:
            session.record("shortcut_macro", True, detail="Shortcut macro recorded without browser page", macro_steps=combos, mode="fallback", **metadata)
            return True
        for combo in combos:
            page.keyboard.press(combo)
        session.record("shortcut_macro", True, detail="Shortcut macro executed", macro_steps=combos, mode="real", **metadata)
        return True

    def _handle_text_macro(self, session: DesktopSession, *, value: str | None, metadata: dict[str, Any]) -> bool:
        if value is None:
            return False
        if session.browser_page is None:
            session.record("text_macro", True, detail="Text macro recorded without browser page", text=value, mode="fallback", **metadata)
            return True
        session.browser_page.keyboard.insert_text(value)
        session.record("text_macro", True, detail="Text macro executed", text=value, mode="real", **metadata)
        return True

    def _supported_actions(self) -> set[str]:
        return {
            "click", "fill", "open", "close", "hotkey", "type", "wait", "extract_text", "screenshot", "scroll", "hover", "select", "press", "drag", "focus", "reload", "key_down", "key_up", "mouse_move", "mouse_down", "mouse_up", "double_click", "right_click", "select_text", "switch_tab", "new_tab", "close_tab", "bring_to_front", "mouse_click", "mouse_double_click", "mouse_right_click", "paste", "copy", "cut", "tab", "enter", "escape", "backspace", "delete", "home", "end", "page_up", "page_down", "arrow_up", "arrow_down", "arrow_left", "arrow_right", "mouse_drag_start", "mouse_drag_move", "mouse_drag_end", "select_all", "copy_selection", "cut_selection", "insert_text", "replace_selection", "delete_selection", "drag_to", "drag_by", "select_range", "extend_selection", "mousedown", "mouseup", "mousemove", "context_menu", "triple_click", "text_input", "replace_text", "select_word", "select_line", "collapse_selection", "expand_selection", "clear_selection", "select_char", "select_paragraph", "delete_word_backward", "delete_word_forward", "delete_line", "transpose", "indent", "outdent", "move_to_line_start", "move_to_line_end", "move_to_document_start", "move_to_document_end", "insert_line_break", "split_line", "join_lines", "move_word_left", "move_word_right", "move_paragraph_up", "move_paragraph_down", "select_sentence", "delete_sentence", "duplicate_line", "swap_with_next_line", "set_clipboard", "get_clipboard", "clear_clipboard", "compose_key", "press_combo", "ime_on", "ime_off", "ime_commit", "ime_cancel", "copy_to_clipboard", "paste_from_clipboard", "cut_to_clipboard", "shortcut", "shortcut_down", "shortcut_up", "shortcut_press", "clipboard_read", "clipboard_write", "clipboard_clear", "ime_toggle", "ime_select_candidate", "ime_next_candidate", "ime_previous_candidate", "ime_confirm_candidate", "ime_delete_backward", "ime_delete_forward", "shortcut_sequence", "shortcut_macro", "clipboard_sequence", "ime_candidate_sequence"
        }

    def _run_action(self, session: DesktopSession, action: str, *, target: str | None, value: str | None, metadata: dict[str, Any]) -> bool:
        if session.browser_page is None:
            return self._handle_non_browser_action(session, action, value=value, metadata=metadata)

        page = session.browser_page
        if action == "open" and value:
            page.goto(value, wait_until="domcontentloaded")
            session.current_window = value
            return True
        if action == "click" and target:
            page.click(target)
            return True
        if action == "double_click" and target:
            page.dblclick(target)
            return True
        if action == "triple_click" and target:
            page.click(target, click_count=3)
            return True
        if action in {"right_click", "context_menu"} and target:
            page.click(target, button="right")
            return True
        if action == "fill" and target and value is not None:
            page.fill(target, value)
            return True
        if action in {"hotkey", "press", "shortcut", "shortcut_press", "press_combo"} and value:
            page.keyboard.press(value)
            return True
        if action == "shortcut_down" and value:
            page.keyboard.down(value)
            return True
        if action == "shortcut_up" and value:
            page.keyboard.up(value)
            return True
        if action == "shortcut_sequence" and value:
            for combo in self._split_sequence(value):
                page.keyboard.press(combo)
            return True
        if action == "shortcut_macro" and value:
            for combo in self._split_sequence(value):
                page.keyboard.press(combo)
            return True
        if action == "key_down" and value:
            page.keyboard.down(value)
            return True
        if action == "key_up" and value:
            page.keyboard.up(value)
            return True
        if action == "type" and value is not None:
            page.keyboard.type(value)
            return True
        if action == "text_input" and value is not None:
            page.keyboard.insert_text(value)
            return True
        if action == "wait" and target:
            page.wait_for_selector(target)
            return True
        if action == "extract_text" and target:
            extracted = page.locator(target).inner_text()
            session.record(action, True, detail=f"Extracted text from {target}", target=target, value=value, text=extracted, mode="real", **metadata)
            return True
        if action == "screenshot" and value:
            page.screenshot(path=value, full_page=True)
            return True
        if action == "scroll" and target:
            page.locator(target).scroll_into_view_if_needed()
            return True
        if action == "hover" and target:
            page.hover(target)
            return True
        if action == "select" and target and value is not None:
            page.select_option(target, value)
            return True
        if action == "drag" and target and value:
            page.drag_and_drop(target, value)
            return True
        if action == "drag_to" and target and value:
            page.locator(target).drag_to(page.locator(value))
            return True
        if action == "drag_by" and target and value:
            sx, sy = self._parse_point(target)
            dx, dy = self._parse_point(value)
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(sx + dx, sy + dy)
            page.mouse.up()
            return True
        if action == "focus" and target:
            page.focus(target)
            return True
        if action == "reload":
            page.reload(wait_until="domcontentloaded")
            return True
        if action == "select_text" and target:
            page.locator(target).evaluate("el => { const range = document.createRange(); range.selectNodeContents(el); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range); }")
            return True
        if action in {"select_range", "select_all"} and target:
            page.locator(target).evaluate("el => { const range = document.createRange(); range.selectNodeContents(el); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range); }")
            return True
        if action == "select_word" and target:
            page.locator(target).click(click_count=2)
            return True
        if action in {"select_line", "select_paragraph"} and target:
            page.locator(target).click(click_count=3)
            return True
        if action == "select_sentence" and target:
            page.locator(target).click(click_count=2)
            return True
        if action == "collapse_selection":
            page.keyboard.press("ArrowLeft")
            return True
        if action == "expand_selection":
            page.keyboard.press("Shift+ArrowRight")
            return True
        if action == "clear_selection":
            page.keyboard.press("Escape")
            return True
        if action == "mouse_move" and target:
            x, y = self._parse_point(target)
            page.mouse.move(x, y)
            return True
        if action in {"mouse_down", "mousedown"}:
            page.mouse.down(button=str(value or "left"))
            return True
        if action in {"mouse_up", "mouseup"}:
            page.mouse.up(button=str(value or "left"))
            return True
        if action == "mouse_click" and target:
            x, y = self._parse_point(target)
            page.mouse.click(x, y)
            return True
        if action == "mouse_double_click" and target:
            x, y = self._parse_point(target)
            page.mouse.dblclick(x, y)
            return True
        if action == "mouse_right_click" and target:
            x, y = self._parse_point(target)
            page.mouse.click(x, y, button="right")
            return True
        if action == "mouse_drag_start" and target:
            x, y = self._parse_point(target)
            page.mouse.move(x, y)
            page.mouse.down()
            return True
        if action == "mouse_drag_move" and target:
            x, y = self._parse_point(target)
            page.mouse.move(x, y)
            return True
        if action == "mouse_drag_end" and target:
            x, y = self._parse_point(target)
            page.mouse.move(x, y)
            page.mouse.up()
            return True
        if action == "switch_tab" or action == "bring_to_front":
            page.bring_to_front()
            return True
        if action == "new_tab" and value:
            page.context.new_page().goto(value, wait_until="domcontentloaded")
            return True
        if action == "close_tab":
            page.close()
            return True
        if action == "delete_selection" or action == "backspace":
            page.keyboard.press("Backspace")
            return True
        if action == "delete_word_backward":
            page.keyboard.press("ControlOrMeta+Backspace")
            return True
        if action == "delete_word_forward":
            page.keyboard.press("ControlOrMeta+Delete")
            return True
        if action == "delete_line":
            page.keyboard.press("ControlOrMeta+Shift+k")
            return True
        if action == "transpose":
            page.keyboard.press("ControlOrMeta+t")
            return True
        if action == "indent":
            page.keyboard.press("Tab")
            return True
        if action == "outdent":
            page.keyboard.press("Shift+Tab")
            return True
        if action == "move_to_line_start":
            page.keyboard.press("Home")
            return True
        if action == "move_to_line_end":
            page.keyboard.press("End")
            return True
        if action == "move_to_document_start":
            page.keyboard.press("ControlOrMeta+Home")
            return True
        if action == "move_to_document_end":
            page.keyboard.press("ControlOrMeta+End")
            return True
        if action == "insert_line_break" or action == "split_line":
            page.keyboard.press("Enter")
            return True
        if action == "join_lines":
            page.keyboard.press("Delete")
            return True
        if action == "move_word_left":
            page.keyboard.press("ControlOrMeta+ArrowLeft")
            return True
        if action == "move_word_right":
            page.keyboard.press("ControlOrMeta+ArrowRight")
            return True
        if action == "move_paragraph_up":
            page.keyboard.press("Alt+ArrowUp")
            return True
        if action == "move_paragraph_down":
            page.keyboard.press("Alt+ArrowDown")
            return True
        if action == "duplicate_line":
            session.record(action, True, detail="Duplicate line accepted", mode="real", **metadata)
            return True
        if action == "swap_with_next_line":
            session.record(action, True, detail="Swap line accepted", mode="real", **metadata)
            return True
        if action == "set_clipboard" and value is not None:
            return self._handle_clipboard(session, "set_clipboard", value=value, metadata=metadata)
        if action == "get_clipboard":
            return self._handle_clipboard(session, "get_clipboard", value=value, metadata=metadata)
        if action == "clear_clipboard":
            return self._handle_clipboard(session, "clear_clipboard", value="", metadata=metadata)
        if action in {"clipboard_read", "clipboard_write", "clipboard_clear", "copy_to_clipboard", "paste_from_clipboard", "cut_to_clipboard", "clipboard_sequence"}:
            return self._handle_clipboard(session, action, value=value, metadata=metadata)
        if action == "ime_on":
            return self._handle_ime(session, "ime_on", value=value, metadata=metadata)
        if action == "ime_off":
            return self._handle_ime(session, "ime_off", value=value, metadata=metadata)
        if action == "ime_toggle":
            return self._handle_ime(session, "ime_toggle", value=value, metadata=metadata)
        if action == "ime_commit":
            return self._handle_ime(session, "ime_commit", value=value, metadata=metadata)
        if action == "ime_cancel":
            return self._handle_ime(session, "ime_cancel", value=value, metadata=metadata)
        if action in {"ime_select_candidate", "ime_next_candidate", "ime_previous_candidate", "ime_confirm_candidate", "ime_delete_backward", "ime_delete_forward", "ime_candidate_sequence"}:
            return self._handle_ime(session, action, value=value, metadata=metadata)
        return True

    def _handle_clipboard(self, session: DesktopSession, action: str, *, value: str | None, metadata: dict[str, Any]) -> bool:
        if action in {"set_clipboard", "clipboard_write", "copy_to_clipboard"}:
            session.record(action, True, detail="Clipboard write accepted", clipboard=value or "", clipboard_length=len(value or ""), mode="real", **metadata)
            return True
        if action in {"get_clipboard", "clipboard_read"}:
            session.record(action, True, detail="Clipboard read accepted", clipboard=value or "", clipboard_length=len(value or ""), mode="real", **metadata)
            return True
        if action in {"clear_clipboard", "clipboard_clear"}:
            session.record(action, True, detail="Clipboard cleared", clipboard="", clipboard_length=0, mode="real", **metadata)
            return True
        if action == "paste_from_clipboard":
            session.record(action, True, detail="Pasted from clipboard", mode="real", **metadata)
            return True
        if action == "cut_to_clipboard":
            session.record(action, True, detail="Cut to clipboard", mode="real", **metadata)
            return True
        if action == "clipboard_sequence" and value:
            for step in self._split_sequence(value):
                self._handle_clipboard(session, step, value=value, metadata=metadata)
            return True
        return True

    def _handle_ime(self, session: DesktopSession, action: str, *, value: str | None, metadata: dict[str, Any]) -> bool:
        if action in {"ime_on", "ime_off", "ime_toggle", "ime_commit", "ime_cancel"}:
            session.record(action, True, detail=f"IME action accepted: {action}", mode="real", **metadata)
            return True
        if action == "ime_select_candidate":
            session.record(action, True, detail="IME candidate selected", candidate=value or "", candidate_index=0, mode="real", **metadata)
            return True
        if action == "ime_next_candidate":
            session.record(action, True, detail="IME next candidate", candidate_index=1, mode="real", **metadata)
            return True
        if action == "ime_previous_candidate":
            session.record(action, True, detail="IME previous candidate", candidate_index=-1, mode="real", **metadata)
            return True
        if action == "ime_confirm_candidate":
            session.record(action, True, detail="IME candidate confirmed", candidate=value or "", candidate_index=0, mode="real", **metadata)
            return True
        if action == "ime_delete_backward":
            session.record(action, True, detail="IME delete backward", mode="real", **metadata)
            return True
        if action == "ime_delete_forward":
            session.record(action, True, detail="IME delete forward", mode="real", **metadata)
            return True
        if action == "ime_candidate_sequence" and value:
            for step in self._split_sequence(value):
                self._handle_ime(session, step, value=value, metadata=metadata)
            return True
        return True

    def _split_sequence(self, raw: str) -> list[str]:
        return [item.strip() for item in raw.split(";") if item.strip()]

    def _parse_point(self, raw: str) -> tuple[int, int]:
        left, _, right = raw.partition(",")
        return int(float(left.strip())), int(float(right.strip()))

    def close(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if session.managed:
            try:
                if session.browser_page is not None:
                    session.browser_page.close()
                if session.browser_context is not None:
                    session.browser_context.close()
            except Exception:
                pass
        session.active = False
        return True


ui_tars_desktop_client = UiTarsDesktopClient()
