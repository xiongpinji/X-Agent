import React, { useMemo, useState } from "react";

import { sendFailure } from "../../sendOutcome";

export type CreateAgentPageProps = {
  roleCatalog: RoleCatalog;
  organizationGraph: OrganizationGraphView;
  avatars: RoleAvatar[];
  initialOrgId?: string;
  initialDepartmentId?: string;
  /**
   * 当前组织名（只读展示）。
   *
   * 表单里此前**连「所属组织」这一栏都没有** —— orgId 隐式取自组织图，用户看不见
   * 自己正往哪个组织里建人。有了组织切换之后这件事更必须显式化。
   */
  organizationName?: string;
  onCreateAgent: (payload: AgentCreatePayload) => Promise<AgentCreateResult>;
  onPreviewWorkflow?: (roleTemplateId: string) => void;
  onPreviewTools?: (roleTemplateId: string) => void;
  onCancel?: () => void;
};

/**
 * 创建结果。
 *
 * `warnings` 承载后端的「部分成功」——目前唯一来源是上级智能体编制已满：
 * 智能体本身建成了，但汇报关系没挂上。这件事必须回到用户眼前，否则就是把
 * 一次静默的部分成功藏在 201 里。
 */
export type AgentCreateResult = { agentId: string; warnings: string[] };

export type AgentCreateFormState = {
  orgId: string;
  departmentId: string;
  name: string;
  title: string;
  managerAgentId: string;
  roleTemplateId: string;
};

/**
 * 创建组织岗位智能体的请求体（POST /api/v1/organization/agents）。
 *
 * 刻意窄：岗位画像（capabilities / plugins / apps / persona / tone /
 * decision_style / communication_style / risk_appetite）与 room_id **全部删掉**了。
 * 旧契约带着它们，但表单里根本没有对应输入框 —— capabilities / plugins / apps
 * 恒被发成空数组，persona / tone / decision_style 发的是与模板默认值逐字相同的
 * 常量，后端也一个都没读。这正是本仓反复出现的「前端以为设置了、后端没读」。
 *
 * 画像统一从所选 RoleTemplate 继承；实例层是否允许覆盖模板是**未拍板**的产品
 * 口径，未拍板前不预留字段。后端对该请求模型开了 extra="forbid"，
 * 多传一个字段即 422，不会静默丢弃。
 */
export type AgentCreatePayload = {
  org_id: string;
  department_id: string;
  name: string;
  role_template_id: string;
  title?: string;
  manager_agent_id?: string | null;
};

const defaultFormState = (props: CreateAgentPageProps): AgentCreateFormState => ({
  orgId: props.initialOrgId ?? props.organizationGraph.organization?.org_id ?? "",
  departmentId: props.initialDepartmentId ?? props.organizationGraph.departments[0]?.department_id ?? "",
  name: "",
  title: "",
  managerAgentId: "",
  roleTemplateId: props.roleCatalog.templates[0]?.role_id ?? "",
});

export function CreateAgentPage(props: CreateAgentPageProps) {
  const [form, setForm] = useState<AgentCreateFormState>(() => defaultFormState(props));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submitNotice, setSubmitNotice] = useState("");

  const selectedTemplate = useMemo(
    () => props.roleCatalog.templates.find((item) => item.role_id === form.roleTemplateId) ?? null,
    [props.roleCatalog.templates, form.roleTemplateId],
  );

  const selectedAvatar = useMemo(
    () => selectedTemplate ? props.avatars.find((avatar) => avatar.role_name === selectedTemplate.role_name) ?? null : null,
    [props.avatars, selectedTemplate],
  );

  const workflow = useMemo(
    () => selectedTemplate ? props.roleCatalog.workflows.find((item) => item.role_template_id === selectedTemplate.role_id) ?? null : null,
    [props.roleCatalog.workflows, selectedTemplate],
  );

  const update = <K extends keyof AgentCreateFormState>(key: K, value: AgentCreateFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    const missing: string[] = [];
    if (!form.orgId) missing.push("所属组织");
    if (!form.departmentId) missing.push("所属部门");
    if (!form.name.trim()) missing.push("智能体名称");
    if (!form.roleTemplateId) missing.push("岗位模板");
    if (missing.length) {
      setSubmitError(`请先填写：${missing.join("、")}`);
      return;
    }
    setSubmitError("");
    setSubmitNotice("");
    setSubmitting(true);
    try {
      const result = await props.onCreateAgent({
        org_id: form.orgId,
        department_id: form.departmentId,
        name: form.name.trim(),
        role_template_id: form.roleTemplateId,
        // 留空即「继承模板的 title」；后端按 falsy 处理，不发空串。
        title: form.title.trim() || undefined,
        manager_agent_id: form.managerAgentId || null,
      });
      setSubmitNotice(
        result.warnings.length
          ? `智能体已创建，但有 ${result.warnings.length} 项未完成：${result.warnings.join("；")}`
          : "",
      );
    } catch (cause) {
      setSubmitError(sendFailure("创建智能体", cause).error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)_320px]">
      <section className="console-section">
        <header className="mb-4">
          <h2 className="text-lg font-semibold">选择岗位模板</h2>
          <p className="text-sm text-gray-500">先选角色，再创建组织里的岗位智能体。</p>
        </header>
        <div className="space-y-3">
          {props.roleCatalog.templates.map((template) => (
            <button key={template.role_id} className={`w-full border-b p-3 text-left transition ${form.roleTemplateId === template.role_id ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"}`} onClick={() => { update("roleTemplateId", template.role_id); props.onPreviewWorkflow?.(template.role_id); }}>
              <div className="flex items-center gap-3"><div className="h-10 w-10 rounded-full bg-gray-200" /><div className="min-w-0"><div className="font-medium">{template.role_name}</div><div className="truncate text-xs text-gray-500">{template.title}</div></div></div>
              <div className="mt-2 line-clamp-2 text-sm text-gray-600">{template.description}</div>
            </button>
          ))}
        </div>
      </section>

      <section className="console-section">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">创建智能体</h2>
            <p className="text-sm text-gray-500">填写岗位实例信息，并设置组织挂载关系。</p>
          </div>
          <button className="border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onCancel}>返回组织图</button>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="智能体名称"><input className="w-full border px-3 py-2" value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="例如：短剧导演智能体" /></Field>
          <Field label="岗位标题"><input className="w-full border px-3 py-2" value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="例如：内容总监" /></Field>
          {/* 「所属组织」是只读的：组织切换统一在组织图页做，这里只如实显示建到哪去。
              此前表单里根本没有这一栏，orgId 隐式取自组织图，用户看不见目标组织。 */}
          <Field label="所属组织">
            <div className="w-full border bg-gray-50 px-3 py-2 text-sm text-gray-700">
              {props.organizationName ?? props.organizationGraph.organization?.name ?? "未选择组织（请先到「组织图」新建或切换组织）"}
            </div>
          </Field>
          <Field label="所属部门"><select className="w-full border px-3 py-2" value={form.departmentId} onChange={(e) => update("departmentId", e.target.value)}>{props.organizationGraph.departments.map((department) => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}</select></Field>
          <Field label="上级智能体"><select className="w-full border px-3 py-2" value={form.managerAgentId} onChange={(e) => update("managerAgentId", e.target.value)}><option value="">无</option>{props.organizationGraph.agent_instances.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}</select></Field>
        </div>
        {/* 会议室 / 人格风格 / 语气 / 决策风格四处输入框已删除：
            前三者的值后端一个都没读（rooms 是每次现造的假实体，AgentNode 没有
            会议室字段），人格三项发的是与模板默认值逐字相同的常量。岗位画像改为
            从所选模板继承，因此不再在表单里假装可编辑。 */}
        <p className="mt-4 text-sm text-gray-500">
          岗位画像（能力、工具、人格风格、语气、决策风格）由所选岗位模板继承，此处不单独设置。
        </p>
        <div className="mt-4 border bg-gray-50 p-4"><h3 className="font-medium">角色预览</h3><div className="mt-2 flex items-center gap-3"><div className="h-14 w-14 rounded-full bg-gray-200" /><div><div className="font-semibold">{selectedTemplate?.role_name ?? "未选择角色"}</div><div className="text-sm text-gray-500">{selectedTemplate?.title ?? "-"}</div></div></div><div className="mt-3 text-sm text-gray-600">{selectedTemplate?.description ?? ""}</div></div>
        {submitError ? <p role="alert" className="mt-4 text-sm text-red-600">{submitError}</p> : null}
        {submitNotice ? (
          <p role="status" className="mt-4 border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
            {submitNotice}
          </p>
        ) : null}
        <div className="mt-4 flex justify-end gap-3"><button className="border px-4 py-2" onClick={props.onCancel}>取消</button><button className="bg-blue-600 px-4 py-2 text-white disabled:opacity-50" disabled={submitting} onClick={handleSubmit}>{submitting ? "创建中..." : "创建智能体"}</button></div>
      </section>

      <aside className="console-section space-y-4">
        <section><h3 className="font-semibold">角色形象</h3><div className="mt-3 flex items-center gap-3"><div className="h-16 w-16 rounded-full bg-gradient-to-br from-gray-200 to-gray-300" /><div><div className="font-medium">{selectedAvatar?.display_name ?? "默认形象"}</div><div className="text-xs text-gray-500">{selectedAvatar?.style ?? "business"}</div></div></div></section>
        <section><h3 className="font-semibold">工作流预览</h3><ul className="mt-3 space-y-2 text-sm text-gray-600">{workflow?.steps?.map((step) => <li key={step} className="border-b px-3 py-2">{step}</li>) ?? <li className="text-gray-400">暂无工作流</li>}</ul><button className="mt-3 border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onPreviewWorkflow?.(form.roleTemplateId)}>预览工作流</button></section>
        <section><h3 className="font-semibold">岗位能力</h3><div className="mt-3 flex flex-wrap gap-2">{selectedTemplate?.core_skills?.map((skill) => <span key={skill} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{skill}</span>) ?? <span className="text-sm text-gray-400">暂无技能</span>}</div><button className="mt-3 border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onPreviewTools?.(form.roleTemplateId)}>查看工具映射</button></section>
      </aside>
    </div>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return <label className="block"><div className="mb-1 text-sm font-medium text-gray-700">{props.label}</div>{props.children}</label>;
}
