from __future__ import annotations

from backend.app.services.desktop.ui_tars_client import UiTarsDesktopClient


def test_desktop_runtime_macro_chain_records_final_actions() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()
    client.run_macro(session.session_id, "shortcut:ControlOrMeta+a;ControlOrMeta+c|clipboard:clipboard_write;clipboard_clear|ime:ime_next_candidate;ime_confirm_candidate|text:hello")

    assert session.actions
    assert any(action.action == "text_macro" for action in session.actions)
