from __future__ import annotations

from backend.app.services.desktop.ui_tars_client import UiTarsDesktopClient


def test_run_macro_dispatches_shortcuts_clipboard_and_ime() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    results = client.run_macro(
        session.session_id,
        "shortcut:ControlOrMeta+a;ControlOrMeta+c|clipboard:clipboard_write;clipboard_clear|ime:ime_next_candidate;ime_confirm_candidate|text:hello",
    )

    assert len(results) >= 4
    assert all(item.action == "macro.step" for item in results)
    assert session.actions[-1].action == "text_macro"


def test_shortcut_macro_records_without_browser_page() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    result = client.send_action(session.session_id, "shortcut_macro", value="ControlOrMeta+a;ControlOrMeta+c")

    assert result.ok is True
    assert any(item.action == "shortcut_macro" for item in session.actions)


def test_clipboard_sequence_records_actions() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    result = client.send_action(session.session_id, "clipboard_sequence", value="clipboard_write;clipboard_clear")

    assert result.ok is True
    assert any(item.action == "clipboard_sequence" for item in session.actions)


def test_ime_candidate_sequence_records_actions() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    result = client.send_action(session.session_id, "ime_candidate_sequence", value="ime_next_candidate;ime_confirm_candidate")

    assert result.ok is True
    assert any(item.action == "ime_candidate_sequence" for item in session.actions)
