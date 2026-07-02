from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.instruction_source_audit import audit_instruction_sources


def test_instruction_source_audit_ready_with_matching_agents_md_and_skill() -> None:
    report = audit_instruction_sources(
        {
            "task": "Fix backend API auth bug and run pytest",
            "paths": ["backend/app/api/auth.py", "tests/test_auth.py"],
            "instruction_sources": [
                {
                    "path": "AGENTS.md",
                    "kind": "agents_md",
                    "priority": 10,
                    "summary": "Repo rules",
                }
            ],
            "skills": [
                {
                    "name": "python-api-maintainer",
                    "description": "Python backend API testing and auth fixes",
                    "tags": ["development", "security"],
                    "source": ".agents/skills/python-api-maintainer",
                }
            ],
        }
    )

    assert report["kind"] == "instruction_source_audit"
    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["domains"] == ["development", "security"]
    assert report["applicable_instruction_sources"][0]["path"] == "AGENTS.md"
    assert report["suggested_skills"][0]["name"] == "python-api-maintainer"
    assert report["next_actions"] == ["review_suggested_skills"]


def test_missing_instruction_sources_needs_review() -> None:
    report = audit_instruction_sources({"task": "Update docs report", "paths": ["docs/report.md"]})

    assert report["ok"] is True
    assert report["status"] == "needs_review"
    assert [issue["code"] for issue in report["issues"]] == [
        "instruction_sources_missing",
        "instruction_skill_suggestion_missing",
    ]
    assert report["next_actions"] == ["provide_instruction_sources", "review_skill_catalog"]


def test_instruction_sources_scoped_to_other_paths_are_not_applicable() -> None:
    report = audit_instruction_sources(
        {
            "task": "Change frontend component",
            "paths": ["frontend/src/App.tsx"],
            "instruction_sources": [
                {"path": "backend/AGENTS.md", "priority": 5, "scopes": ["backend/"]},
            ],
            "skills": [{"name": "react-ui", "tags": ["development", "design"]}],
        }
    )

    assert report["status"] == "needs_review"
    assert [issue["code"] for issue in report["issues"]] == ["instruction_sources_not_applicable"]
    assert report["next_actions"] == ["review_instruction_scopes", "review_suggested_skills"]


def test_equal_priority_applicable_sources_report_conflict() -> None:
    report = audit_instruction_sources(
        {
            "task": "Deploy docker workflow",
            "paths": [".github/workflows/ci.yml"],
            "instruction_sources": [
                {"path": "AGENTS.md", "priority": 10},
                {"path": ".codex/AGENTS.md", "priority": 10},
            ],
            "skills": [{"name": "ci-cd-pipeline-builder", "tags": ["deployment"]}],
        }
    )

    assert report["status"] == "needs_review"
    assert [issue["code"] for issue in report["issues"]] == [
        "instruction_sources_priority_conflict"
    ]
    assert report["issues"][0]["details"]["conflicts"] == [
        {"priority": 10, "sources": [".codex/AGENTS.md", "AGENTS.md"]}
    ]


def test_skill_suggestion_missing_for_specific_domain() -> None:
    report = audit_instruction_sources(
        {
            "task": "Analyze browser console errors",
            "paths": ["frontend/src/App.tsx"],
            "instruction_sources": [{"path": "AGENTS.md", "priority": 1}],
            "skills": [{"name": "docs-writer", "tags": ["docs"]}],
        }
    )

    assert report["domains"] == ["development", "browser"]
    assert report["suggested_skills"] == []
    assert [issue["code"] for issue in report["issues"]] == [
        "instruction_skill_suggestion_missing"
    ]


def test_general_task_without_skill_match_is_ready_if_instructions_apply() -> None:
    report = audit_instruction_sources(
        {
            "task": "Think about next milestone",
            "instruction_sources": [{"path": "AGENTS.md", "priority": 1}],
            "skills": [],
        }
    )

    assert report["domains"] == ["general"]
    assert report["status"] == "ready"
    assert report["issues"] == []
    assert report["next_actions"] == ["proceed_with_applicable_instructions"]


def test_accepts_dataclass_like_instruction_source() -> None:
    @dataclass
    class InstructionSource:
        path: str
        priority: int

    report = audit_instruction_sources(
        {
            "task": "Write README docs",
            "paths": ["README.md"],
            "instruction_sources": [InstructionSource(path="AGENTS.md", priority=3)],
            "skills": [{"name": "docs-writer", "tags": ["docs"]}],
        }
    )

    assert report["applicable_instruction_sources"][0]["path"] == "AGENTS.md"
    assert report["suggested_skills"][0]["name"] == "docs-writer"
