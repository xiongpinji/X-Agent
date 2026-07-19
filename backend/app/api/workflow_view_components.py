from __future__ import annotations


def build_workflow_components() -> dict[str, dict[str, object]]:
    return {
        "workflow_shell": {"component": "AppShell", "source": "slots", "props": ["navbar", "main", "aside"]},
        "workflow_page": {"component": "Container", "source": "layout", "props": ["framework", "ui_kit", "primary", "secondary", "tertiary"]},
        "page_header": {"component": "Stack", "source": "header", "props": ["gap", "children"]},
        "section_title": {"component": "Group", "source": "header", "props": ["children", "align", "gap"]},
        "stat_card": {"component": "Card", "source": "metrics.items[]", "props": ["label", "value", "description", "icon"]},
        "overview_card": {"component": "Card", "source": "panels.overview", "props": ["title", "status", "subtitle", "trace_count", "node_count", "badges", "recovery_branch"]},
        "recovery_card": {"component": "Card", "source": "panels.recovery", "props": ["plan", "next_actions", "latest_branch"]},
        "timeline_panel": {"component": "Timeline", "source": "panels.timeline", "props": ["active", "bulletSize", "lineWidth", "children"]},
        "timeline_item": {"component": "Timeline.Item", "source": "panels.timeline.items[]", "props": ["title", "bullet", "children"]},
        "timeline_event_row": {"component": "Group", "source": "panels.timeline.items[].events[]", "props": ["children", "position", "spacing"]},
        "node_list": {"component": "List", "source": "panels.nodes", "props": ["spacing", "size", "center", "children"]},
        "node_list_item": {"component": "List.Item", "source": "panels.nodes.items[]", "props": ["icon", "title", "description", "rightSection"]},
        "node_badge": {"component": "Badge", "source": "panels.nodes.items[]", "props": ["children", "variant", "color"]},
        "node_meta": {"component": "Group", "source": "panels.nodes.items[]", "props": ["children", "spacing"]},
        "failure_panel": {"component": "Stack", "source": "panels.failures", "props": ["gap", "children"]},
        "compensation_panel": {"component": "Stack", "source": "panels.compensations", "props": ["gap", "children"]},
        "trace_chips": {"component": "Group", "source": "panels.traces", "props": ["gap", "children"]},
        "Alert": {"component": "Alert", "source": "panels.failures.items[]|panels.compensations.items[]", "props": ["title", "color", "children", "icon"]},
        "Button": {"component": "Button", "source": "panels.failures.items[].ui|panels.compensations.items[].ui", "props": ["children", "variant", "size"]},
        "Badge": {"component": "Badge", "source": "panels.traces.items[]|panels.nodes.items[]", "props": ["children", "variant", "radius"]},
        "Group": {"component": "Group", "source": "slots.topbar|components.page_header|components.section_title|components.timeline_event_row|components.node_meta|components.trace_chips", "props": ["children", "gap", "justify"]},
        "Text": {"component": "Text", "source": "components.page_header|components.timeline_panel|components.node_list", "props": ["children", "size", "c"]},
        "ThemeIcon": {"component": "ThemeIcon", "source": "components.timeline_panel", "props": ["size", "variant", "children"]},
        "Stack": {"component": "Stack", "source": "components.page_header|components.failure_panel|components.compensation_panel", "props": ["gap", "children"]},
        "Card": {"component": "Card", "source": "components.stat_card|components.overview_card", "props": ["shadow", "radius", "p", "children"]},
        "SimpleGrid": {"component": "SimpleGrid", "source": "slots.content", "props": ["cols", "spacing", "children"]},
        "Drawer": {"component": "Drawer", "source": "slots.inspector", "props": ["opened", "title", "children"]},
    }
