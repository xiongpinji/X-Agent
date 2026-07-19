import type { ConsoleState } from "./consoleReducer";

export function selectMemoryCenterOverviewData(state: ConsoleState) {
  const api = state.memoryCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      totalMemories: api.primary.total_memories,
      activeMemories: api.primary.active_memories,
      archivedMemories: api.primary.archived_memories,
      referencedMemories: api.primary.referenced_memories,
      riskLevel: api.primary.risk_level,
      linkedMemoriesSummary: api.linked_summaries.memories,
      linkedExperiencesSummary: api.linked_summaries.experiences,
      linkedReferencesSummary: api.linked_summaries.references,
      linkedHistorySummary: api.linked_summaries.history,
    };
  }

  return {
    resourceType: "memory_center_overview",
    resourceId: state.console.session_id || state.console.user_id,
    totalMemories: 0,
    activeMemories: 0,
    archivedMemories: 0,
    referencedMemories: 0,
    riskLevel: "低",
    linkedMemoriesSummary: { summary: { title: "memories" }, data: {} },
    linkedExperiencesSummary: { summary: { title: "experiences" }, data: {} },
    linkedReferencesSummary: { summary: { title: "references" }, data: {} },
    linkedHistorySummary: { summary: { title: "history" }, data: {} },
  };
}
