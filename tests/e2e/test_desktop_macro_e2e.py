from __future__ import annotations

from backend.app.services.desktop.ui_tars_client import UiTarsDesktopClient


def test_desktop_end_to_end_macro_chain() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()
    results = client.run_macro(
        session.session_id,
        "shortcut:ControlOrMeta+a;ControlOrMeta+c|clipboard:clipboard_write;clipboard_clear|ime:ime_next_candidate;ime_confirm_candidate|text:hello world",
    )

    assert len(results) >= 4
    assert any(item.action == "shortcut_macro" for item in session.actions)
    assert any(item.action == "text_macro" for item in session.actions)
