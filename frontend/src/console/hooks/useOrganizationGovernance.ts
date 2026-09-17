/**
 * 组织治理数据 —— 岗位模板目录（含**真实**在用数）+ 组织审计流水。
 *
 * 数据源是 (d) 批次新增的真实端点：
 *   GET /api/v1/organization/roles?org_id=xx  → 角色目录 + 各模板在用智能体数
 *   GET /api/v1/organization/audit?limit=nn   → 本租户审计流水（created_at 倒序）
 *
 * ★ 刻意**不**用 `/api/v1/organization-control/*`：那个模块的 4 个 GET 全是硬编码
 * 字面量（24 个角色 / 13 条审核事件），且未挂载 ⇒ 此前两页的 fetch 恒 404，被
 * `if (!response.ok) return` 静默吞掉，页面显示的其实是 props 里的假数字。
 *
 * ★ 必须走 `consoleFetch`：这两个端点依赖 `get_current_principal`，它**没有** dev
 * 匿名放行（只有 `/api/v1/workbench` 有），裸请求会 401。
 */
import { useCallback, useEffect, useState } from "react";

import { apiFailureMessage, sendFailure } from "../sendOutcome";
import { consoleFetch } from "../consoleFetch";

export type OrganizationRoleTemplate = {
  role_id: string;
  role_name: string;
  category: string;
  level: string;
  title: string;
  description: string;
  core_skills: string[];
  /** 该模板在当前组织下**真实在用**的智能体数量（后端 list_agents 数出来的）。 */
  in_use: number;
};

export type OrganizationRolesPayload = {
  total_templates: number;
  in_use_total: number;
  templates: OrganizationRoleTemplate[];
  role_groups: Record<string, string[]>;
};

export type OrganizationAuditRecord = {
  id: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  created_at: string;
  details: Record<string, unknown>;
};

export type OrganizationAuditSummary = {
  success: number;
  failure: number;
  latest_outcome: string | null;
};

export type OrganizationAuditPayload = {
  total: number;
  limit: number;
  offset: number;
  /** 后端扫描上界被撑满时为 true —— 让截断可见，而不是让 total 静默失真。 */
  truncated: boolean;
  summary: OrganizationAuditSummary;
  records: OrganizationAuditRecord[];
};

export type OrganizationGovernance = {
  roles: OrganizationRolesPayload | null;
  audit: OrganizationAuditPayload | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
};

const AUDIT_PAGE_SIZE = 50;

export function useOrganizationGovernance(
  orgId: string | null,
): OrganizationGovernance {
  const [roles, setRoles] = useState<OrganizationRolesPayload | null>(null);
  const [audit, setAudit] = useState<OrganizationAuditPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const rolesUrl = orgId
        ? `/api/v1/organization/roles?org_id=${encodeURIComponent(orgId)}`
        : "/api/v1/organization/roles";
      const rolesResponse = await consoleFetch(rolesUrl);
      if (!rolesResponse.ok) {
        throw new Error(await apiFailureMessage(rolesResponse));
      }
      setRoles((await rolesResponse.json()) as OrganizationRolesPayload);

      const auditResponse = await consoleFetch(
        `/api/v1/organization/audit?limit=${AUDIT_PAGE_SIZE}`,
      );
      if (!auditResponse.ok) {
        throw new Error(await apiFailureMessage(auditResponse));
      }
      setAudit((await auditResponse.json()) as OrganizationAuditPayload);
      setError("");
    } catch (cause) {
      setError(sendFailure("加载组织治理数据", cause).error);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { roles, audit, loading, error, reload };
}
