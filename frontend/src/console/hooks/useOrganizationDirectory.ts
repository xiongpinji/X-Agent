/**
 * 当前租户的「组织目录」——组织列表 + 所选组织下的部门列表。
 *
 * 数据源是 (a) 批次落地的真实端点（不是 `organization_control` 那套 fixture）：
 *   GET /api/v1/organization/organizations          → 本租户全部组织
 *   GET /api/v1/organization/departments?org_id=xx  → 该组织下的部门
 *
 * ★ 必须走 `consoleFetch` 而不是裸 fetch：这两个端点依赖 `get_current_principal`，
 * 它是**没有** dev 匿名放行的（只有 `/api/v1/workbench` 有），裸请求会 401。
 */
import { useCallback, useEffect, useState } from "react";

import { apiFailureMessage, sendFailure } from "../sendOutcome";
import { consoleFetch } from "../consoleFetch";

export type OrganizationRecord = {
  org_id: string;
  tenant_id: string;
  name: string;
  description: string;
  owner_user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DepartmentRecord = {
  department_id: string;
  org_id: string;
  name: string;
  mission: string;
  leader_agent_id: string | null;
  parent_department_id: string | null;
  created_at: string;
  updated_at: string;
};

export type OrganizationDirectory = {
  organizations: OrganizationRecord[];
  departments: DepartmentRecord[];
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
};

export function useOrganizationDirectory(
  orgId: string | null,
): OrganizationDirectory {
  const [organizations, setOrganizations] = useState<OrganizationRecord[]>([]);
  const [departments, setDepartments] = useState<DepartmentRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const orgsResponse = await consoleFetch("/api/v1/organization/organizations");
      if (!orgsResponse.ok) {
        throw new Error(await apiFailureMessage(orgsResponse));
      }
      setOrganizations((await orgsResponse.json()) as OrganizationRecord[]);

      if (orgId) {
        const deptResponse = await consoleFetch(
          `/api/v1/organization/departments?org_id=${encodeURIComponent(orgId)}`,
        );
        if (!deptResponse.ok) {
          throw new Error(await apiFailureMessage(deptResponse));
        }
        setDepartments((await deptResponse.json()) as DepartmentRecord[]);
      } else {
        // 没有当前组织 ⇒ 留空。不去拉「全部部门」，那是另一个组织的目录，
        // 显示出来会让用户以为它属于当前组织。
        setDepartments([]);
      }
      setError("");
    } catch (cause) {
      setError(sendFailure("加载组织目录", cause).error);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { organizations, departments, loading, error, reload };
}
