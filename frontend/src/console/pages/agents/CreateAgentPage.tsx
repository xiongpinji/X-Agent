import React, { useMemo, useState } from "react";

export type CreateAgentPageProps = {
  roleCatalog: RoleCatalog;
  organizationGraph: OrganizationGraphView;
  avatars: RoleAvatar[];
  initialOrgId?: string;
  initialDepartmentId?: string;
  initialRoomId?: string;
  onCreateAgent: (payload: AgentCreatePayload) => Promise<void>;
  onPreviewWorkflow?: (roleTemplateId: string) => void;
  onPreviewTools?: (roleTemplateId: string) => void;
  onCancel?: () => void;
};

export type AgentCreateFormState = {
  orgId: string;
  departmentId: string;
  roomId: string;
  name: string;
  title: string;
  managerAgentId: string;
  roleTemplateId: string;
  capabilities: string[];
  plugins: string[];
  apps: string[];
  persona: string;
  tone: string;
  decisionStyle: string;
  communicationStyle: string;
  riskAppetite: string;
};

export type AgentCreatePayload = {
  org_id: string;
  department_id: string;
  room_id?: string | null;
  name: string;
  title: string;
  manager_agent_id?: string | null;
  role_template_id: string;
  capabilities: string[];
  plugins: string[];
  apps: string[];
  persona: string;
  tone: string;
  decision_style: string;
  communication_style: string;
  risk_appetite: string;
};

const defaultFormState = (props: CreateAgentPageProps): AgentCreateFormState => ({
  orgId: props.initialOrgId ?? props.organizationGraph.organization?.org_id ?? "",
  departmentId: props.initialDepartmentId ?? props.organizationGraph.departments[0]?.department_id ?? "",
  roomId: props.initialRoomId ?? props.organizationGraph.meeting_rooms[0]?.room_id ?? "",
  name: "",
  title: "",
  managerAgentId: "",
  roleTemplateId: props.roleCatalog.templates[0]?.role_id ?? "",
  capabilities: [],
  plugins: [],
  apps: [],
  persona: "professional",
  tone: "clear",
  decisionStyle: "balanced",
  communicationStyle: "direct",
  riskAppetite: "medium",
});

export function CreateAgentPage(props: CreateAgentPageProps) {
  const [form, setForm] = useState<AgentCreateFormState>(() => defaultFormState(props));
  const [submitting, setSubmitting] = useState(false);

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
    if (!form.orgId || !form.departmentId || !form.name || !form.roleTemplateId) return;
    setSubmitting(true);
    try {
      await props.onCreateAgent({
        org_id: form.orgId,
        department_id: form.departmentId,
        room_id: form.roomId || null,
        name: form.name,
        title: form.title,
        manager_agent_id: form.managerAgentId || null,
        role_template_id: form.roleTemplateId,
        capabilities: form.capabilities,
        plugins: form.plugins,
        apps: form.apps,
        persona: form.persona,
        tone: form.tone,
        decision_style: form.decisionStyle,
        communication_style: form.communicationStyle,
        risk_appetite: form.riskAppetite,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)_320px]">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="mb-4">
          <h2 className="text-lg font-semibold">选择岗位模板</h2>
          <p className="text-sm text-gray-500">先选角色，再创建组织里的岗位智能体。</p>
        </header>
        <div className="space-y-3">
          {props.roleCatalog.templates.map((template) => (
            <button key={template.role_id} className={`w-full rounded-xl border p-3 text-left transition ${form.roleTemplateId === template.role_id ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:bg-gray-50"}`} onClick={() => { update("roleTemplateId", template.role_id); props.onPreviewWorkflow?.(template.role_id); }}>
              <div className="flex items-center gap-3"><div className="h-10 w-10 rounded-full bg-gray-200" /><div className="min-w-0"><div className="font-medium">{template.role_name}</div><div className="truncate text-xs text-gray-500">{template.title}</div></div></div>
              <div className="mt-2 line-clamp-2 text-sm text-gray-600">{template.description}</div>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">创建智能体</h2>
            <p className="text-sm text-gray-500">填写岗位实例信息，并设置组织挂载关系。</p>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onCancel}>返回组织图</button>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="智能体名称"><input className="w-full rounded-lg border px-3 py-2" value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="例如：短剧导演智能体" /></Field>
          <Field label="岗位标题"><input className="w-full rounded-lg border px-3 py-2" value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="例如：内容总监" /></Field>
          <Field label="所属部门"><select className="w-full rounded-lg border px-3 py-2" value={form.departmentId} onChange={(e) => update("departmentId", e.target.value)}>{props.organizationGraph.departments.map((department) => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}</select></Field>
          <Field label="上级智能体"><select className="w-full rounded-lg border px-3 py-2" value={form.managerAgentId} onChange={(e) => update("managerAgentId", e.target.value)}><option value="">无</option>{props.organizationGraph.agent_instances.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}</select></Field>
          <Field label="会议室"><select className="w-full rounded-lg border px-3 py-2" value={form.roomId} onChange={(e) => update("roomId", e.target.value)}><option value="">不绑定</option>{props.organizationGraph.meeting_rooms.map((room) => <option key={room.room_id} value={room.room_id}>{room.name}</option>)}</select></Field>
          <Field label="人格风格"><input className="w-full rounded-lg border px-3 py-2" value={form.persona} onChange={(e) => update("persona", e.target.value)} /></Field>
          <Field label="语气"><input className="w-full rounded-lg border px-3 py-2" value={form.tone} onChange={(e) => update("tone", e.target.value)} /></Field>
          <Field label="决策风格"><input className="w-full rounded-lg border px-3 py-2" value={form.decisionStyle} onChange={(e) => update("decisionStyle", e.target.value)} /></Field>
        </div>
        <div className="mt-4 rounded-xl border bg-gray-50 p-4"><h3 className="font-medium">角色预览</h3><div className="mt-2 flex items-center gap-3"><div className="h-14 w-14 rounded-full bg-gray-200" /><div><div className="font-semibold">{selectedTemplate?.role_name ?? "未选择角色"}</div><div className="text-sm text-gray-500">{selectedTemplate?.title ?? "-"}</div></div></div><div className="mt-3 text-sm text-gray-600">{selectedTemplate?.description ?? ""}</div></div>
        <div className="mt-4 flex justify-end gap-3"><button className="rounded-lg border px-4 py-2" onClick={props.onCancel}>取消</button><button className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50" disabled={submitting} onClick={handleSubmit}>{submitting ? "创建中..." : "创建智能体"}</button></div>
      </section>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        <section><h3 className="font-semibold">角色形象</h3><div className="mt-3 flex items-center gap-3"><div className="h-16 w-16 rounded-full bg-gradient-to-br from-gray-200 to-gray-300" /><div><div className="font-medium">{selectedAvatar?.display_name ?? "默认形象"}</div><div className="text-xs text-gray-500">{selectedAvatar?.style ?? "business"}</div></div></div></section>
        <section><h3 className="font-semibold">工作流预览</h3><ul className="mt-3 space-y-2 text-sm text-gray-600">{workflow?.steps?.map((step) => <li key={step} className="rounded-lg border px-3 py-2">{step}</li>) ?? <li className="text-gray-400">暂无工作流</li>}</ul><button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onPreviewWorkflow?.(form.roleTemplateId)}>预览工作流</button></section>
        <section><h3 className="font-semibold">岗位能力</h3><div className="mt-3 flex flex-wrap gap-2">{selectedTemplate?.core_skills?.map((skill) => <span key={skill} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{skill}</span>) ?? <span className="text-sm text-gray-400">暂无技能</span>}</div><button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onPreviewTools?.(form.roleTemplateId)}>查看工具映射</button></section>
      </aside>
    </div>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return <label className="block"><div className="mb-1 text-sm font-medium text-gray-700">{props.label}</div>{props.children}</label>;
}
