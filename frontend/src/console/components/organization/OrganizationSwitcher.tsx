/**
 * 组织切换器 —— 控制台里唯一的「组织 / 部门」写入口。
 *
 * 为什么需要它
 * ============
 * (c) 之前控制台**完全没有**建组织、建部门的入口（前端零引用 `/organizations`、
 * `/departments`），而 `/api/v1/workbench` 又恒取「最近更新的组织」⇒ 用户建了
 * 第二个组织后，「我建的组织不见了」：组织图只会展示那一个，表单里的「所属组织」
 * 也不可切换。这个组件同时解决两件事：
 *   1. 下拉切换当前组织（切完组织图与「创建智能体」的目标组织一起跟着变）
 *   2. 就地把组织和部门建出来
 *
 * 写失败一律**抛异常**并渲染进 `role="alert"`（与 `CreateAgentPage` 同一约定），
 * 不静默吞掉，也不假装成功。
 */
import React from "react";

import type {
  DepartmentRecord,
  OrganizationRecord,
} from "../../hooks/useOrganizationDirectory";
import { sendFailure } from "../../sendOutcome";

export type NewOrganizationPayload = { name: string; description: string };
export type NewDepartmentPayload = { name: string; mission: string };

export type OrganizationSwitcherProps = {
  organizations: OrganizationRecord[];
  departments: DepartmentRecord[];
  activeOrgId: string | null;
  loading: boolean;
  error: string;
  onSelectOrg: (orgId: string) => void;
  /** 创建成功即视为「已切换过去」由调用方负责；失败必须抛异常。 */
  onCreateOrganization: (payload: NewOrganizationPayload) => Promise<void>;
  onCreateDepartment: (payload: NewDepartmentPayload) => Promise<void>;
};

type PanelKind = "none" | "organization" | "department";

export function OrganizationSwitcher(props: OrganizationSwitcherProps) {
  const [panel, setPanel] = React.useState<PanelKind>("none");
  const [orgName, setOrgName] = React.useState("");
  const [orgDescription, setOrgDescription] = React.useState("");
  const [deptName, setDeptName] = React.useState("");
  const [deptMission, setDeptMission] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState("");
  const [notice, setNotice] = React.useState("");

  const activeOrg =
    props.organizations.find((item) => item.org_id === props.activeOrgId) ?? null;

  const openPanel = (next: PanelKind) => {
    setPanel((current) => (current === next ? "none" : next));
    setSubmitError("");
    setNotice("");
  };

  const submitOrganization = async () => {
    if (!orgName.trim()) {
      setSubmitError("请先填写组织名称");
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    setNotice("");
    try {
      await props.onCreateOrganization({
        name: orgName.trim(),
        description: orgDescription.trim(),
      });
      setOrgName("");
      setOrgDescription("");
      setPanel("none");
      setNotice("组织已创建，并已切换为当前组织。");
    } catch (cause) {
      setSubmitError(sendFailure("创建组织", cause).error);
    } finally {
      setSubmitting(false);
    }
  };

  const submitDepartment = async () => {
    if (!props.activeOrgId) {
      setSubmitError("请先选择一个组织");
      return;
    }
    if (!deptName.trim()) {
      setSubmitError("请先填写部门名称");
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    setNotice("");
    try {
      await props.onCreateDepartment({
        name: deptName.trim(),
        mission: deptMission.trim(),
      });
      setDeptName("");
      setDeptMission("");
      setPanel("none");
      setNotice("部门已创建。");
    } catch (cause) {
      setSubmitError(sendFailure("创建部门", cause).error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="console-section">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[240px] flex-1">
          <div className="mb-1 text-sm font-medium text-gray-700">
            当前组织
            {props.loading ? <span className="ml-2 text-xs text-gray-400">加载中…</span> : null}
          </div>
          <select
            className="w-full border px-3 py-2"
            value={props.activeOrgId ?? ""}
            disabled={props.loading || props.organizations.length === 0}
            onChange={(event) => props.onSelectOrg(event.target.value)}
          >
            {/* activeOrgId 可能来自本地记忆（组织已被删除等）⇒ 此时列表里找不到它。
                给一个显式占位，而不是让 select 静默跳到第一个选项 —— 那会让 UI 显示的
                组织和实际请求的组织不是同一个。 */}
            {props.activeOrgId && !activeOrg ? (
              <option value={props.activeOrgId}>未知组织（{props.activeOrgId}）</option>
            ) : null}
            {props.organizations.map((organization) => (
              <option key={organization.org_id} value={organization.org_id}>
                {organization.org_id === props.activeOrgId
                  ? `${organization.name}（${props.departments.length} 个部门）`
                  : organization.name}
              </option>
            ))}
          </select>
        </label>

        <button
          className="border px-3 py-2 text-sm hover:bg-gray-50"
          onClick={() => openPanel("organization")}
        >
          新建组织
        </button>
        <button
          className="border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          disabled={!props.activeOrgId}
          title={props.activeOrgId ? undefined : "请先选择一个组织"}
          onClick={() => openPanel("department")}
        >
          新建部门
        </button>
        <div className="text-xs text-gray-500">
          当前组织下共 {props.departments.length} 个部门
        </div>
      </div>

      {panel === "organization" ? (
        <div className="mt-4 border bg-gray-50 p-4">
          <h3 className="font-medium">新建组织</h3>
          <p className="mt-1 text-xs text-gray-500">
            归属取当前登录租户，创建者记为所有者；创建后会立即切换过去。
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Field label="组织名称">
              <input
                className="w-full border px-3 py-2"
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
                placeholder="例如：内容事业部"
              />
            </Field>
            <Field label="组织说明">
              <input
                className="w-full border px-3 py-2"
                value={orgDescription}
                onChange={(event) => setOrgDescription(event.target.value)}
                placeholder="可选"
              />
            </Field>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button className="border px-3 py-2 text-sm" onClick={() => openPanel("none")}>
              取消
            </button>
            <button
              className="bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50"
              disabled={submitting}
              onClick={submitOrganization}
            >
              {submitting ? "创建中…" : "创建组织"}
            </button>
          </div>
        </div>
      ) : null}

      {panel === "department" ? (
        <div className="mt-4 border bg-gray-50 p-4">
          <h3 className="font-medium">新建部门</h3>
          <p className="mt-1 text-xs text-gray-500">
            将建在「{activeOrg?.name ?? props.activeOrgId}」下。
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Field label="部门名称">
              <input
                className="w-full border px-3 py-2"
                value={deptName}
                onChange={(event) => setDeptName(event.target.value)}
                placeholder="例如：前端设计部"
              />
            </Field>
            <Field label="部门职责">
              <input
                className="w-full border px-3 py-2"
                value={deptMission}
                onChange={(event) => setDeptMission(event.target.value)}
                placeholder="可选"
              />
            </Field>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button className="border px-3 py-2 text-sm" onClick={() => openPanel("none")}>
              取消
            </button>
            <button
              className="bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50"
              disabled={submitting}
              onClick={submitDepartment}
            >
              {submitting ? "创建中…" : "创建部门"}
            </button>
          </div>
        </div>
      ) : null}

      {props.error ? (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {props.error}
        </p>
      ) : null}
      {submitError ? (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {submitError}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-3 border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
          {notice}
        </p>
      ) : null}
    </section>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 text-sm font-medium text-gray-700">{props.label}</div>
      {props.children}
    </label>
  );
}
