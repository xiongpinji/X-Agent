import type { ConsoleState } from "./consoleReducer";

export function selectToolsCenterOverviewData(state: ConsoleState) {
  const api = state.toolsCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      totalTools: api.primary.total_tools,
      enabledTools: api.primary.enabled_tools,
      disabledTools: api.primary.disabled_tools,
      pluginCount: api.primary.plugin_count,
      resourceCount: api.primary.resource_count,
      riskLevel: api.primary.risk_level,
      linkedToolsSummary: api.linked_summaries.tools,
      linkedPluginsSummary: api.linked_summaries.plugins,
      linkedResourcesSummary: api.linked_summaries.resources,
      linkedHistorySummary: api.linked_summaries.history,
    };
  }

  return {
    resourceType: "tools_center_overview",
    resourceId: state.console.session_id || state.console.user_id,
    totalTools: 0,
    enabledTools: 0,
    disabledTools: 0,
    pluginCount: 0,
    resourceCount: 0,
    riskLevel: "低",
    linkedToolsSummary: { summary: { title: "tools" }, data: {} },
    linkedPluginsSummary: { summary: { title: "plugins" }, data: {} },
    linkedResourcesSummary: { summary: { title: "resources" }, data: {} },
    linkedHistorySummary: { summary: { title: "history" }, data: {} },
  };
}
