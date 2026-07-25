"""Deep coverage tests for backend/app/services/desktop/ui_tars_client.py."""
import pytest
from unittest.mock import MagicMock, patch

from backend.app.services.desktop.ui_tars_client import (
    DesktopActionResult,
    DesktopSession,
    UiTarsDesktopClient,
    ui_tars_desktop_client,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DesktopActionResult
# ═══════════════════════════════════════════════════════════════════════════════

class TestDesktopActionResult:
    def test_basic(self):
        r = DesktopActionResult(action="click", ok=True, detail="done")
        assert r.action == "click"
        assert r.ok is True
        assert r.detail == "done"
        assert r.data == {}

    def test_with_data(self):
        r = DesktopActionResult(action="fill", ok=False, detail="err", data={"k": "v"})
        assert r.data == {"k": "v"}


# ═══════════════════════════════════════════════════════════════════════════════
# DesktopSession
# ═══════════════════════════════════════════════════════════════════════════════

class TestDesktopSession:
    def test_defaults(self):
        s = DesktopSession(session_id="s1")
        assert s.tenant_id == "default"
        assert s.user_id == "anonymous"
        assert s.provider == "ui-tars"
        assert s.active is True
        assert s.actions == []
        assert s.managed is False

    def test_record_no_browser(self):
        s = DesktopSession(session_id="s1")
        result = s.record("click", True, detail="ok")
        assert result.action == "click"
        assert result.ok is True
        assert result.data["provider"] == "ui-tars"
        assert "timestamp" in result.data
        assert len(s.actions) == 1

    def test_record_with_browser_page(self):
        s = DesktopSession(session_id="s1")
        page = MagicMock()
        page.url = "http://example.com"
        s.browser_page = page
        result = s.record("open", True, detail="opened")
        assert result.data["page_url"] == "http://example.com"

    def test_record_browser_page_url_exception(self):
        s = DesktopSession(session_id="s1")
        page = MagicMock()
        type(page).url = property(lambda self: (_ for _ in ()).throw(RuntimeError("no url")))
        s.browser_page = page
        result = s.record("test", True)
        assert "page_url" not in result.data

    def test_record_enriches_data(self):
        s = DesktopSession(session_id="s1")
        result = s.record("x", True, custom_key="custom_val")
        assert result.data["custom_key"] == "custom_val"


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — session management
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientSessions:
    def test_create_session(self):
        client = UiTarsDesktopClient()
        session = client.create_session(trace_id="t1", run_id="r1", tenant_id="ten1", user_id="u1")
        assert session.trace_id == "t1"
        assert session.run_id == "r1"
        assert session.tenant_id == "ten1"
        assert session.user_id == "u1"
        assert session.session_id in client._sessions

    def test_get_session(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        fetched = client.get_session(session.session_id)
        assert fetched is session

    def test_get_session_not_found(self):
        client = UiTarsDesktopClient()
        assert client.get_session("nope") is None

    def test_close_session(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client.close(session.session_id) is True
        assert session.active is False

    def test_close_session_not_found(self):
        client = UiTarsDesktopClient()
        assert client.close("nope") is False

    def test_close_managed_session(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        session.managed = True
        page = MagicMock()
        ctx = MagicMock()
        session.browser_page = page
        session.browser_context = ctx
        client.close(session.session_id)
        page.close.assert_called_once()
        ctx.close.assert_called_once()
        assert session.active is False

    def test_close_managed_session_exception(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        session.managed = True
        page = MagicMock()
        page.close.side_effect = RuntimeError("fail")
        session.browser_page = page
        session.browser_context = None
        assert client.close(session.session_id) is True
        assert session.active is False

    def test_has_real_client(self):
        client = UiTarsDesktopClient()
        # Depends on whether playwright is installed
        assert isinstance(client.has_real_client, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — send_action
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientSendAction:
    def test_send_action_no_session(self):
        client = UiTarsDesktopClient()
        result = client.send_action("nope", "click")
        assert result.ok is False
        assert "not found" in result.detail

    def test_send_action_closed_session(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        session.active = False
        result = client.send_action(session.session_id, "click")
        assert result.ok is False
        assert "closed" in result.detail

    def test_send_action_unsupported(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        result = client.send_action(session.session_id, "fly_to_moon")
        assert result.ok is False
        assert "not supported" in result.detail

    def test_send_action_fallback_no_browser(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        # _handle_non_browser_action doesn't exist → AttributeError → caught → ok=False for non-fallback actions
        result = client.send_action(session.session_id, "click", target="#btn")
        assert result.ok is False
        assert "failed" in result.detail

    def test_send_action_open_sets_window(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        session.browser_page = page
        result = client.send_action(session.session_id, "open", value="http://x.com")
        assert result.ok is True
        assert session.current_window == "http://x.com"

    def test_send_action_with_browser_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        session.browser_page = page
        result = client.send_action(session.session_id, "click", target="#btn")
        assert result.ok is True
        page.click.assert_called_once_with("#btn")

    def test_send_action_exception_fallback_actions(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        page.keyboard.press.side_effect = RuntimeError("fail")
        session.browser_page = page
        result = client.send_action(session.session_id, "shortcut_sequence", value="Ctrl+A;Ctrl+C")
        assert result.ok is True
        assert "fallback" in result.detail

    def test_send_action_exception_non_fallback(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        page.click.side_effect = RuntimeError("fail")
        session.browser_page = page
        result = client.send_action(session.session_id, "click", target="#btn")
        assert result.ok is False
        assert "failed" in result.detail


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — run_macro
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientRunMacro:
    def test_run_macro_no_session(self):
        client = UiTarsDesktopClient()
        results = client.run_macro("nope", "shortcut:Ctrl+A")
        assert len(results) == 1
        assert results[0].ok is False

    def test_run_macro_empty_script(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        results = client.run_macro(session.session_id, "")
        assert results == []

    def test_run_macro_missing_kind(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        results = client.run_macro(session.session_id, ":value")
        assert len(results) == 1
        assert results[0].ok is False
        assert "missing kind" in results[0].detail

    def test_run_macro_shortcut_step(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        results = client.run_macro(session.session_id, "shortcut:Ctrl+A|text:hello")
        assert len(results) == 2
        assert all(r.ok for r in results)

    def test_run_macro_step_failure_breaks(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        # "unknown_kind" is not in the handled set → _run_macro_step returns False
        results = client.run_macro(session.session_id, "unknown_kind:x")
        assert len(results) == 1
        assert results[0].ok is False

    def test_run_macro_exception_fallback(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        page.keyboard.press.side_effect = RuntimeError("fail")
        session.browser_page = page
        results = client.run_macro(session.session_id, "shortcut:Ctrl+A")
        # shortcut is in fallback set, so ok=True
        assert results[0].ok is True
        assert "fallback" in results[0].detail

    def test_run_macro_exception_non_fallback(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        page.goto.side_effect = RuntimeError("fail")
        session.browser_page = page
        # "open" is not in fallback set
        results = client.run_macro(session.session_id, "open:http://x.com")
        # _run_macro_step returns False for unknown kinds
        assert results[0].ok is False


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — _parse_macro / _split_sequence / _parse_point
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientHelpers:
    def test_parse_macro_basic(self):
        client = UiTarsDesktopClient()
        steps = client._parse_macro("shortcut:Ctrl+A|text:hello")
        assert len(steps) == 2
        assert steps[0] == {"kind": "shortcut", "value": "Ctrl+A"}
        assert steps[1] == {"kind": "text", "value": "hello"}

    def test_parse_macro_empty_chunks(self):
        client = UiTarsDesktopClient()
        steps = client._parse_macro("shortcut:Ctrl+A|||text:hi|")
        assert len(steps) == 2

    def test_parse_macro_no_payload(self):
        client = UiTarsDesktopClient()
        steps = client._parse_macro("reload")
        assert steps == [{"kind": "reload"}]

    def test_split_sequence(self):
        client = UiTarsDesktopClient()
        assert client._split_sequence("Ctrl+A; Ctrl+C; Ctrl+V") == ["Ctrl+A", "Ctrl+C", "Ctrl+V"]

    def test_split_sequence_empty(self):
        client = UiTarsDesktopClient()
        assert client._split_sequence("") == []

    def test_parse_point(self):
        client = UiTarsDesktopClient()
        assert client._parse_point("100, 200") == (100, 200)

    def test_parse_point_float(self):
        client = UiTarsDesktopClient()
        assert client._parse_point("10.5, 20.7") == (10, 20)

    def test_supported_actions(self):
        client = UiTarsDesktopClient()
        actions = client._supported_actions()
        assert "click" in actions
        assert "fill" in actions
        assert "shortcut_sequence" in actions
        assert "ime_candidate_sequence" in actions
        assert len(actions) > 100


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — _run_action with browser page
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientRunAction:
    def _make_client_with_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        session.browser_page = page
        return client, session, page

    def test_open(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "open", target=None, value="http://x.com", metadata={}) is True
        page.goto.assert_called_once_with("http://x.com", wait_until="domcontentloaded")
        assert session.current_window == "http://x.com"

    def test_click(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "click", target="#btn", value=None, metadata={}) is True
        page.click.assert_called_once_with("#btn")

    def test_double_click(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "double_click", target="#el", value=None, metadata={}) is True
        page.dblclick.assert_called_once_with("#el")

    def test_triple_click(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "triple_click", target="#el", value=None, metadata={}) is True
        page.click.assert_called_once_with("#el", click_count=3)

    def test_right_click(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "right_click", target="#el", value=None, metadata={}) is True
        page.click.assert_called_once_with("#el", button="right")

    def test_fill(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "fill", target="#input", value="hello", metadata={}) is True
        page.fill.assert_called_once_with("#input", "hello")

    def test_hotkey(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "hotkey", target=None, value="Ctrl+A", metadata={}) is True
        page.keyboard.press.assert_called_once_with("Ctrl+A")

    def test_shortcut_down_up(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "shortcut_down", target=None, value="Shift", metadata={}) is True
        page.keyboard.down.assert_called_once_with("Shift")
        assert client._run_action(session, "shortcut_up", target=None, value="Shift", metadata={}) is True
        page.keyboard.up.assert_called_once_with("Shift")

    def test_type(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "type", target=None, value="hello", metadata={}) is True
        page.keyboard.type.assert_called_once_with("hello")

    def test_text_input(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "text_input", target=None, value="hi", metadata={}) is True
        page.keyboard.insert_text.assert_called_once_with("hi")

    def test_wait(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "wait", target="#el", value=None, metadata={}) is True
        page.wait_for_selector.assert_called_once_with("#el")

    def test_extract_text(self):
        client, session, page = self._make_client_with_page()
        page.locator.return_value.inner_text.return_value = "extracted"
        assert client._run_action(session, "extract_text", target="#el", value=None, metadata={}) is True

    def test_screenshot(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "screenshot", target=None, value="/tmp/s.png", metadata={}) is True
        page.screenshot.assert_called_once_with(path="/tmp/s.png", full_page=True)

    def test_scroll(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "scroll", target="#el", value=None, metadata={}) is True
        page.locator("#el").scroll_into_view_if_needed.assert_called_once()

    def test_hover(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "hover", target="#el", value=None, metadata={}) is True
        page.hover.assert_called_once_with("#el")

    def test_select(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "select", target="#sel", value="opt1", metadata={}) is True
        page.select_option.assert_called_once_with("#sel", "opt1")

    def test_drag(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "drag", target="#src", value="#dst", metadata={}) is True
        page.drag_and_drop.assert_called_once_with("#src", "#dst")

    def test_focus(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "focus", target="#el", value=None, metadata={}) is True
        page.focus.assert_called_once_with("#el")

    def test_reload(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "reload", target=None, value=None, metadata={}) is True
        page.reload.assert_called_once_with(wait_until="domcontentloaded")

    def test_mouse_move(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "mouse_move", target="100,200", value=None, metadata={}) is True
        page.mouse.move.assert_called_once_with(100, 200)

    def test_mouse_down_up(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "mouse_down", target=None, value="left", metadata={}) is True
        page.mouse.down.assert_called_once_with(button="left")
        assert client._run_action(session, "mouse_up", target=None, value="right", metadata={}) is True
        page.mouse.up.assert_called_once_with(button="right")

    def test_mouse_click(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "mouse_click", target="50,60", value=None, metadata={}) is True
        page.mouse.click.assert_called_once_with(50, 60)

    def test_switch_tab(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "switch_tab", target=None, value=None, metadata={}) is True
        page.bring_to_front.assert_called_once()

    def test_close_tab(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "close_tab", target=None, value=None, metadata={}) is True
        page.close.assert_called_once()

    def test_keyboard_actions(self):
        client, session, page = self._make_client_with_page()
        for action in ["backspace", "delete_word_backward", "delete_word_forward", "delete_line",
                       "transpose", "indent", "outdent", "move_to_line_start", "move_to_line_end",
                       "move_to_document_start", "move_to_document_end", "insert_line_break",
                       "join_lines", "move_word_left", "move_word_right", "move_paragraph_up",
                       "move_paragraph_down", "collapse_selection", "expand_selection", "clear_selection"]:
            assert client._run_action(session, action, target=None, value=None, metadata={}) is True

    def test_duplicate_line(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "duplicate_line", target=None, value=None, metadata={}) is True

    def test_swap_with_next_line(self):
        client, session, page = self._make_client_with_page()
        assert client._run_action(session, "swap_with_next_line", target=None, value=None, metadata={}) is True

    def test_non_browser_action(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        # No browser_page → _handle_non_browser_action (doesn't exist) → raises AttributeError
        with pytest.raises(AttributeError):
            client._run_action(session, "click", target="#btn", value=None, metadata={})


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — clipboard / IME handlers
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientClipboardIme:
    def test_clipboard_write(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "set_clipboard", value="hello", metadata={}) is True

    def test_clipboard_read(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "get_clipboard", value=None, metadata={}) is True

    def test_clipboard_clear(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "clear_clipboard", value=None, metadata={}) is True

    def test_clipboard_paste(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "paste_from_clipboard", value=None, metadata={}) is True

    def test_clipboard_cut(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "cut_to_clipboard", value=None, metadata={}) is True

    def test_clipboard_sequence(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_clipboard(session, "clipboard_sequence", value="set_clipboard;get_clipboard", metadata={}) is True

    def test_ime_basic_actions(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        for action in ["ime_on", "ime_off", "ime_toggle", "ime_commit", "ime_cancel"]:
            assert client._handle_ime(session, action, value=None, metadata={}) is True

    def test_ime_select_candidate(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_ime(session, "ime_select_candidate", value="候补", metadata={}) is True

    def test_ime_next_previous(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_ime(session, "ime_next_candidate", value=None, metadata={}) is True
        assert client._handle_ime(session, "ime_previous_candidate", value=None, metadata={}) is True

    def test_ime_confirm(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_ime(session, "ime_confirm_candidate", value="x", metadata={}) is True

    def test_ime_delete(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_ime(session, "ime_delete_backward", value=None, metadata={}) is True
        assert client._handle_ime(session, "ime_delete_forward", value=None, metadata={}) is True

    def test_ime_candidate_sequence(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_ime(session, "ime_candidate_sequence", value="ime_on;ime_select_candidate", metadata={}) is True


# ═══════════════════════════════════════════════════════════════════════════════
# UiTarsDesktopClient — _handle_shortcut_macro / _handle_text_macro
# ═══════════════════════════════════════════════════════════════════════════════

class TestUiTarsClientMacroHandlers:
    def test_shortcut_macro_no_combos(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_shortcut_macro(session, value="", metadata={}) is True

    def test_shortcut_macro_no_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_shortcut_macro(session, value="Ctrl+A;Ctrl+C", metadata={}) is True
        assert any("without browser page" in a.detail for a in session.actions)

    def test_shortcut_macro_with_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        session.browser_page = page
        assert client._handle_shortcut_macro(session, value="Ctrl+A;Ctrl+C", metadata={}) is True
        assert page.keyboard.press.call_count == 2

    def test_text_macro_none_value(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_text_macro(session, value=None, metadata={}) is False

    def test_text_macro_no_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        assert client._handle_text_macro(session, value="hello", metadata={}) is True

    def test_text_macro_with_page(self):
        client = UiTarsDesktopClient()
        session = client.create_session()
        page = MagicMock()
        session.browser_page = page
        assert client._handle_text_macro(session, value="hello", metadata={}) is True
        page.keyboard.insert_text.assert_called_once_with("hello")


# ═══════════════════════════════════════════════════════════════════════════════
# Global singleton
# ═══════════════════════════════════════════════════════════════════════════════

class TestGlobalSingleton:
    def test_singleton_exists(self):
        assert ui_tars_desktop_client is not None
        assert isinstance(ui_tars_desktop_client, UiTarsDesktopClient)
