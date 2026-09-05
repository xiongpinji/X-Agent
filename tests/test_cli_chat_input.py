"""CLI chat input enhancement tests (pure-function level, no TUI).

Covers:
- @path file reference parsing (cli.streaming.parse_file_references)
- extra_context building from attachments (build_extra_context)
- slash command parsing (parse_slash_command)
- SSE event normalization for the new fine-grained backend events
- LocalClient mode dispatch in the chat command
"""

from __future__ import annotations

import json

from cli.streaming import (
    MAX_FILE_REFS,
    SSEStreamClient,
    build_extra_context,
    parse_file_references,
    parse_slash_command,
)


# ============================================================================
# @path file references
# ============================================================================


class TestParseFileReferences:
    def test_reads_existing_file(self, tmp_path):
        target = tmp_path / "notes.md"
        target.write_text("hello world", encoding="utf-8")

        parsed = parse_file_references("summarize @notes.md please", cwd=tmp_path)

        assert parsed.message == "summarize @notes.md please"  # message unchanged
        assert len(parsed.files) == 1
        ref = parsed.files[0]
        assert ref.raw == "notes.md"
        assert ref.content == "hello world"
        assert ref.error is None
        assert parsed.notices == []

    def test_missing_file_notice_no_crash(self, tmp_path):
        parsed = parse_file_references("check @does_not_exist.txt", cwd=tmp_path)
        assert len(parsed.files) == 1
        assert parsed.files[0].error == "file not found"
        assert parsed.files[0].content is None
        assert any("not found" in n for n in parsed.notices)

    def test_directory_is_skipped_with_notice(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        parsed = parse_file_references("look at @subdir", cwd=tmp_path)
        assert parsed.files[0].error == "is a directory"
        assert any("directory" in n for n in parsed.notices)

    def test_size_cap_truncates(self, tmp_path):
        big = tmp_path / "big.txt"
        big.write_text("x" * (128 * 1024), encoding="utf-8")
        parsed = parse_file_references("@big.txt", cwd=tmp_path)
        ref = parsed.files[0]
        assert ref.truncated is True
        assert len(ref.content) == 100 * 1024
        assert any("truncated" in n for n in parsed.notices)

    def test_max_five_files(self, tmp_path):
        for i in range(8):
            (tmp_path / f"f{i}.txt").write_text(f"content-{i}", encoding="utf-8")
        parsed = parse_file_references(
            " ".join(f"@f{i}.txt" for i in range(8)), cwd=tmp_path
        )
        attached = [f for f in parsed.files if f.content is not None]
        assert len(attached) == MAX_FILE_REFS
        assert len(parsed.notices) == 8 - MAX_FILE_REFS
        assert all("max" in n for n in parsed.notices)

    def test_email_is_not_a_file_reference(self, tmp_path):
        parsed = parse_file_references("mail me at bob@example.com thanks", cwd=tmp_path)
        assert parsed.files == []
        assert parsed.notices == []

    def test_duplicate_refs_attached_once(self, tmp_path):
        (tmp_path / "a.txt").write_text("A", encoding="utf-8")
        parsed = parse_file_references("@a.txt and again @a.txt", cwd=tmp_path)
        assert len(parsed.files) == 1

    def test_subdirectory_path(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
        parsed = parse_file_references("review @src/main.py", cwd=tmp_path)
        assert parsed.files[0].content == "print('hi')"

    def test_trailing_punctuation_stripped_from_ref(self, tmp_path):
        (tmp_path / "doc.md").write_text("d", encoding="utf-8")
        parsed = parse_file_references("see @doc.md.", cwd=tmp_path)
        assert parsed.files[0].raw == "doc.md"
        assert parsed.files[0].content == "d"


class TestBuildExtraContext:
    def test_attaches_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("AAA", encoding="utf-8")
        (tmp_path / "b.txt").write_text("BBB", encoding="utf-8")
        parsed = parse_file_references("@a.txt @b.txt", cwd=tmp_path)

        extra = build_extra_context(parsed, base={"conversation_history": []})

        assert len(extra["attached_files"]) == 2
        assert extra["file_count"] == 2
        assert extra["attached_files"][0]["content"] == "AAA"
        assert "conversation_history" in extra  # base preserved

    def test_no_files_no_attachment_keys(self):
        extra = build_extra_context(parse_file_references("plain text"))
        assert "attached_files" not in extra
        assert build_extra_context(None) == {}


# ============================================================================
# Slash commands
# ============================================================================


class TestParseSlashCommand:
    def test_known_commands(self):
        for name in ("/help", "/clear", "/sessions", "/approvals", "/model"):
            cmd = parse_slash_command(name)
            assert cmd is not None, name
            assert cmd.name == name
            assert cmd.args == []

    def test_command_with_args(self):
        cmd = parse_slash_command("/resume trace-abc-123")
        assert cmd.name == "/resume"
        assert cmd.args == ["trace-abc-123"]

        cmd = parse_slash_command("/approve appr-9")
        assert cmd.name == "/approve"
        assert cmd.args == ["appr-9"]

    def test_unknown_command_returns_none(self):
        assert parse_slash_command("/frobnicate") is None

    def test_plain_text_returns_none(self):
        assert parse_slash_command("hello world") is None
        assert parse_slash_command("") is None
        assert parse_slash_command("email at bob@example.com") is None

    def test_mixed_slash_prefix_in_sentence(self):
        # A slash only counts at the start of the line
        assert parse_slash_command("use /help here") is None


# ============================================================================
# SSE event normalization (backend fine-grained events -> CLI events)
# ============================================================================


def _sse_frame(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


class TestSSSEEventNormalization:
    def setup_method(self):
        self.client = SSEStreamClient("http://localhost:8000")

    def test_backend_envelope_unwraps_nested_data(self):
        raw = _sse_frame(
            "iteration",
            {
                "event_type": "iteration",
                "run_id": "r1",
                "sequence": 5,
                "data": {"iteration": 3, "step_kind": "tool", "instruction": "do it"},
            },
        )
        event = self.client._parse_sse_event(raw)
        assert event is not None
        assert event.event_type == "iteration"
        assert event.data["step_kind"] == "tool"
        assert event.data["run_id"] == "r1"
        assert event.data["sequence"] == 5

    def test_completion_normalizes_to_done(self):
        raw = _sse_frame("completion", {"event_type": "completion", "data": {"status": "completed", "result": "answer!"}})
        event = self.client._parse_sse_event(raw)
        assert event.event_type == "done"
        assert event.data["result"] == "answer!"

    def test_system_message_normalizes_to_status(self):
        raw = _sse_frame("message", {"event_type": "message", "data": {"content": "Starting...", "role": "system"}})
        event = self.client._parse_sse_event(raw)
        assert event.event_type == "status"
        assert event.data["text"] == "Starting..."

    def test_assistant_message_normalizes_to_token(self):
        raw = _sse_frame("message", {"event_type": "message", "data": {"content": "partial answer", "role": "assistant"}})
        event = self.client._parse_sse_event(raw)
        assert event.event_type == "token"
        assert event.data["text"] == "partial answer"

    def test_heartbeat_skipped(self):
        raw = _sse_frame("heartbeat", {"event_type": "heartbeat"})
        assert self.client._parse_sse_event(raw) is None

    def test_tool_and_approval_events_passthrough(self):
        for etype in ("tool_call", "tool_result", "plan", "approval_required", "error"):
            raw = _sse_frame(etype, {"event_type": etype, "data": {"tool_name": "echo"}})
            event = self.client._parse_sse_event(raw)
            assert event is not None
            assert event.event_type == etype

    def test_plain_text_chunk_falls_back_to_token(self):
        event = self.client._parse_sse_event("just some text\n")
        assert event is not None
        assert event.event_type == "token"
        assert event.data["text"] == "just some text"


# ============================================================================
# LocalClient mode dispatch
# ============================================================================


class TestLocalModeChat:
    def test_send_message_local_uses_local_client(self, monkeypatch, capsys, tmp_path):
        import cli.client as client_module
        from cli.commands import chat_cmd
        from cli.config import CLIConfig

        class FakeLocalClient:
            async def chat(self, message, session_id=None, stream=False):
                return {"status": "completed", "answer": f"local-reply:{message}"}

            async def close(self):
                pass

        fake = FakeLocalClient()
        monkeypatch.setattr(client_module, "create_client", lambda config: fake)

        config = CLIConfig(mode="local")
        chat_cmd._send_message_local("hi there", config)

        out = capsys.readouterr().out
        assert "local-reply:hi there" in out

    def test_http_mode_uses_streaming(self, monkeypatch, tmp_path):
        """http mode must go through the streaming path, not LocalClient."""
        import cli.commands.chat_cmd as chat_cmd
        from cli.config import CLIConfig

        called = {"streaming": False}

        def fake_streaming(message, config, session_id=None):
            called["streaming"] = True

        monkeypatch.setattr(chat_cmd, "_send_message_streaming", fake_streaming)
        config = CLIConfig(mode="http")
        chat_cmd._send_message_streaming("hi", config)
        assert called["streaming"] is True
