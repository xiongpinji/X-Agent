from __future__ import annotations

from backend.app.core.integration_adoption_readme import (
    build_integration_adoption_readme,
    render_adoption_readme_markdown,
)


def test_adoption_readme_payload_is_ready_with_brief_closure_files_and_validation() -> None:
    readme = build_integration_adoption_readme(
        {
            "readme_id": "adopt-1",
            "title": "Secondary Candidate Adoption",
            "final_review_brief": {
                "kind": "integration_final_review_brief",
                "status": "ready",
                "ok": True,
                "verdict": "ready_for_mainline_review",
                "highlights": ["5 signals ready"],
                "next_actions": ["submit_final_review_brief_to_mainline"],
            },
            "closure_checklist": {
                "kind": "integration_closure_checklist",
                "status": "ready",
                "ok": True,
                "next_actions": ["submit_closure_checklist_for_mainline_review"],
            },
            "traceability_index": {
                "kind": "integration_traceability_index",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 2},
                "files": [
                    "backend/app/core/integration_final_review_brief.py",
                    "tests/test_integration_final_review_brief.py",
                ],
            },
            "validation": {
                "commands": ["python -m pytest tests/test_integration_final_review_brief.py -q"],
                "results": ["6 passed"],
            },
        }
    )

    assert readme["kind"] == "integration_adoption_readme"
    assert readme["ok"] is True
    assert readme["status"] == "ready"
    assert readme["summary"]["section_count"] == 5
    assert readme["summary"]["candidate_file_count"] == 2
    assert readme["validation"]["results"] == ["6 passed"]
    assert readme["next_actions"] == ["review_adoption_readme_payload_with_mainline"]
    assert "# Secondary Candidate Adoption" in readme["markdown_preview"]
    assert "## Boundaries" in readme["markdown_preview"]


def test_missing_validation_and_files_keep_readme_in_review() -> None:
    readme = build_integration_adoption_readme(
        {
            "final_review_brief": {"kind": "integration_final_review_brief", "status": "ready", "ok": True},
            "closure_checklist": {"kind": "integration_closure_checklist", "status": "ready", "ok": True},
        }
    )

    assert readme["status"] == "needs_review"
    assert readme["issues"] == [
        {"code": "adoption_readme_validation_missing", "severity": "medium"},
        {"code": "adoption_readme_files_missing", "severity": "medium"},
    ]
    assert readme["next_actions"] == [
        "attach_adoption_validation_commands",
        "attach_adoption_candidate_files",
        "rebuild_integration_adoption_readme",
    ]


def test_blocked_brief_blocks_adoption_readme() -> None:
    readme = build_integration_adoption_readme(
        {
            "final_review_brief": {
                "kind": "integration_final_review_brief",
                "status": "blocked",
                "ok": False,
            },
            "closure_checklist": {"kind": "integration_closure_checklist", "status": "ready", "ok": True},
            "candidate_files": ["backend/app/core/integration_final_review_brief.py"],
            "validation_commands": ["python -m pytest tests/test_integration_final_review_brief.py -q"],
        }
    )

    assert readme["status"] == "blocked"
    assert readme["ok"] is False
    assert readme["issues"][0] == {
        "code": "adoption_readme_component_blocked",
        "severity": "high",
        "component": "final_review_brief",
    }
    assert readme["next_actions"] == [
        "resolve_adoption_readme_blockers",
        "rebuild_integration_adoption_readme",
    ]


def test_components_aliases_and_traceability_entries_are_accepted() -> None:
    readme = build_integration_adoption_readme(
        {
            "components": [
                {"kind": "integration_final_review_brief", "status": "ready", "ok": True},
                {"kind": "integration_closure_checklist", "status": "ready", "ok": True},
                {
                    "kind": "integration_traceability_index",
                    "status": "ready",
                    "ok": True,
                    "entries": [
                        {
                            "candidate_id": "brief",
                            "files": ["backend/app/core/integration_final_review_brief.py"],
                        }
                    ],
                },
            ],
            "validation_results": ["281 passed"],
            "validation_commands": ["python -m pytest tests/test_integration_final_review_brief.py -q"],
        }
    )

    assert readme["status"] == "ready"
    assert readme["candidate_files"] == ["backend/app/core/integration_final_review_brief.py"]
    assert readme["validation"]["commands"] == [
        "python -m pytest tests/test_integration_final_review_brief.py -q"
    ]


def test_render_adoption_readme_markdown_from_sections() -> None:
    markdown = render_adoption_readme_markdown(
        [
            {
                "section_id": "overview",
                "title": "Overview",
                "bullets": ["Ready for review."],
                "status": "ready",
            }
        ]
    )

    assert markdown == "# Integration Adoption Notes\n\n## Overview\n- Ready for review.\n"


def test_custom_boundaries_are_preserved() -> None:
    readme = build_integration_adoption_readme(
        {
            "final_review_brief": {"kind": "integration_final_review_brief", "status": "ready", "ok": True},
            "closure_checklist": {"kind": "integration_closure_checklist", "status": "ready", "ok": True},
            "candidate_files": ["backend/app/core/integration_adoption_readme.py"],
            "validation_commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
            "boundaries": ["Detached only.", "Mainline owns writes."],
        }
    )

    boundaries = next(section for section in readme["sections"] if section["section_id"] == "boundaries")
    assert boundaries["bullets"] == ["Detached only.", "Mainline owns writes."]
