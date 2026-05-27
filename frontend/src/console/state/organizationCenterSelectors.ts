import type { ConsoleState } from "./consoleReducer";

export function selectOrganizationCenterOverviewData(state: ConsoleState) {
  const api = state.organizationCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      totalDepartments: api.primary.total_departments,
      totalRoles: api.primary.total_roles,
      totalMembers: api.primary.total_members,
      pendingReviews: api.primary.pending_reviews,
      riskLevel: api.primary.risk_level,
      linkedOrganizationSummary: api.linked_summaries.organization,
      linkedDepartmentsSummary: api.linked_summaries.departments,
      linkedRolesSummary: api.linked_summaries.roles,
      linkedAuditsSummary: api.linked_summaries.audits,
    };
  }

  return {
    resourceType: "organization_center_overview",
    resourceId: state.console.session_id || state.console.user_id,
    totalDepartments: 0,
    totalRoles: 0,
    totalMembers: 0,
    pendingReviews: 0,
    riskLevel: "低",
    linkedOrganizationSummary: { summary: { title: "organization" }, data: {} },
    linkedDepartmentsSummary: { summary: { title: "departments" }, data: {} },
    linkedRolesSummary: { summary: { title: "roles" }, data: {} },
    linkedAuditsSummary: { summary: { title: "audits" }, data: {} },
  };
}
