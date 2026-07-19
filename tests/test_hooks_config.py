"""Unit tests for hooks configuration (backend/app/core/hooks/config.py)."""

from __future__ import annotations

import json

import pytest

from backend.app.core.hooks.config import HookDefinition, HooksConfig
from backend.app.core.hooks.types import HookEvent


class TestHookDefinition:
    def test_event_enums_resolves_known(self):
        d = HookDefinition(
            name="h",
            type="python",
            events=["pre_tool_use", "post_tool_use"],
            target="m:H",
        )
        assert d.event_enums() == [HookEvent.PRE_TOOL_USE, HookEvent.POST_TOOL_USE]

    def test_event_enums_skips_unknown(self):
        d = HookDefinition(name="h", type="python", events=["bogus"], target="m:H")
        assert d.event_enums() == []

    def test_validate_command_ok(self):
        d = HookDefinition(
            name="guard",
            type="command",
            events=["pre_tool_use"],
            command=["python", "guard.py"],
        )
        assert d.validate() == []

    def test_validate_python_ok(self):
        d = HookDefinition(
            name="audit",
            type="python",
            events=["post_tool_use"],
            target="pkg.hooks:Audit",
        )
        assert d.validate() == []

    def test_validate_missing_name(self):
        d = HookDefinition(name="", type="python", events=["pre_tool_use"], target="m:H")
        assert any("name" in e for e in d.validate())

    def test_validate_bad_type(self):
        d = HookDefinition(name="x", type="weird", events=["pre_tool_use"])
        assert any("invalid type" in e for e in d.validate())

    def test_validate_command_requires_command(self):
        d = HookDefinition(name="x", type="command", events=["pre_tool_use"])
        assert any("requires 'command'" in e for e in d.validate())

    def test_validate_command_must_be_list(self):
        d = HookDefinition(
            name="x",
            type="command",
            events=["pre_tool_use"],
            command="python guard.py",  # type: ignore[arg-type]
        )
        assert any("must be a list" in e for e in d.validate())

    def test_validate_python_requires_target(self):
        d = HookDefinition(name="x", type="python", events=["pre_tool_use"])
        assert any("requires 'target'" in e for e in d.validate())

    def test_validate_no_events(self):
        d = HookDefinition(name="x", type="python", events=[], target="m:H")
        assert any("no events" in e for e in d.validate())

    def test_validate_bad_timeout(self):
        d = HookDefinition(
            name="x",
            type="command",
            events=["pre_tool_use"],
            command=["a"],
            timeout_seconds=0,
        )
        assert any("timeout_seconds" in e for e in d.validate())


class TestHooksConfigIO:
    def test_load_from_file(self, tmp_path):
        cfg_path = tmp_path / "hooks.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "hooks": [
                        {
                            "name": "block-writes",
                            "type": "command",
                            "events": ["pre_tool_use"],
                            "command": ["python", "guard.py"],
                            "tool_matcher": "write_file",
                            "priority": 10,
                            "timeout_seconds": 3.0,
                            "enabled": True,
                        },
                        {
                            "name": "audit",
                            "type": "python",
                            "events": ["post_tool_use"],
                            "target": "pkg:Audit",
                            "enabled": False,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        cfg = HooksConfig(cfg_path)
        assert len(cfg.hooks) == 2
        assert cfg.hooks[0].name == "block-writes"
        assert cfg.hooks[0].command == ["python", "guard.py"]
        assert cfg.hooks[0].priority == 10
        assert cfg.hooks[1].enabled is False

    def test_enabled_hooks_filters(self, tmp_path):
        cfg_path = tmp_path / "hooks.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "hooks": [
                        {
                            "name": "on",
                            "type": "python",
                            "events": ["pre_tool_use"],
                            "target": "m:A",
                            "enabled": True,
                        },
                        {
                            "name": "off",
                            "type": "python",
                            "events": ["pre_tool_use"],
                            "target": "m:B",
                            "enabled": False,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        cfg = HooksConfig(cfg_path)
        enabled = cfg.enabled_hooks()
        assert [h.name for h in enabled] == ["on"]

    def test_missing_file_is_empty(self, tmp_path):
        cfg = HooksConfig(tmp_path / "does_not_exist.json")
        assert cfg.hooks == []

    def test_malformed_json_is_empty(self, tmp_path):
        cfg_path = tmp_path / "hooks.json"
        cfg_path.write_text("{not valid json", encoding="utf-8")
        cfg = HooksConfig(cfg_path)
        assert cfg.hooks == []

    def test_save_roundtrip(self, tmp_path):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="audit",
                type="python",
                events=["post_tool_use"],
                target="pkg:Audit",
            )
        ]
        out = tmp_path / "out.json"
        cfg.save_to_file(out)
        reloaded = HooksConfig(out)
        assert len(reloaded.hooks) == 1
        assert reloaded.hooks[0].name == "audit"


class TestHooksConfigValidate:
    def test_valid_config(self, tmp_path):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="audit",
                type="python",
                events=["post_tool_use"],
                target="pkg:Audit",
            )
        ]
        valid, errors = cfg.validate()
        assert valid is True
        assert errors == []

    def test_duplicate_names_flagged(self):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(name="dup", type="python", events=["pre_tool_use"], target="m:A"),
            HookDefinition(name="dup", type="python", events=["pre_tool_use"], target="m:B"),
        ]
        valid, errors = cfg.validate()
        assert valid is False
        assert any("duplicate" in e for e in errors)
