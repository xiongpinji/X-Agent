import React, { useMemo } from "react";

export type RoleCatalogPageProps = {
  roleCatalog: RoleCatalog;
  avatars: RoleAvatar[];
  selectedRoleTemplateId?: string | null;
  onSelectRoleTemplate: (roleTemplateId: string) => void;
  onOpenWorkflow?: (roleTemplateId: string) => void;
  onOpenTools?: (roleTemplateId: string) => void;
};

export function RoleCatalogPage(props: RoleCatalogPageProps) {
  const selectedTemplate = useMemo(() => props.roleCatalog.templates.find((item) => item.role_id === props.selectedRoleTemplateId) ?? null, [props.roleCatalog.templates, props.selectedRoleTemplateId]);
  const selectedAvatar = useMemo(() => selectedTemplate ? props.avatars.find((avatar) => avatar.role_name === selectedTemplate.role_name) ?? null : null, [props.avatars, selectedTemplate]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="mb-4 flex items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">角色模板库</h2><p className="text-sm text-gray-500">浏览岗位模板、工作流和角色形象。</p></div><button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectRoleTemplate(selectedTemplate?.role_id ?? props.roleCatalog.templates[0]?.role_id ?? "")}>返回当前</button></header>
        <div className="mb-4 flex flex-wrap gap-2">{Object.keys(props.roleCatalog.role_groups).map((group) => <button key={group} className="rounded-full border px-3 py-1 text-sm hover:bg-gray-50">{group}</button>)}</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {props.roleCatalog.templates.map((template) => (
            <button key={template.role_id} className={`rounded-2xl border p-4 text-left transition hover:bg-gray-50 ${props.selectedRoleTemplateId === template.role_id ? "border-blue-500 bg-blue-50" : ""}`} onClick={() => props.onSelectRoleTemplate(template.role_id)}>
              <div className="flex items-center gap-3"><div className="h-12 w-12 rounded-full bg-gray-200" /><div className="min-w-0"><div className="font-semibold">{template.role_name}</div><div className="truncate text-xs text-gray-500">{template.title}</div></div></div>
              <div className="mt-3 line-clamp-3 text-sm text-gray-600">{template.description}</div>
              <div className="mt-3 flex flex-wrap gap-2">{template.core_skills.slice(0, 3).map((skill) => <span key={skill} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{skill}</span>)}</div>
            </button>
          ))}
        </div>
      </section>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        {selectedTemplate ? <>
          <section><h3 className="text-lg font-semibold">{selectedTemplate.role_name}</h3><div className="mt-2 text-sm text-gray-500">{selectedTemplate.title}</div><div className="mt-3 text-sm text-gray-700">{selectedTemplate.description}</div></section>
          <section><h4 className="font-medium">角色形象</h4><div className="mt-3 flex items-center gap-3"><div className="h-16 w-16 rounded-full bg-gray-200" /><div><div className="font-medium">{selectedAvatar?.display_name ?? "默认形象"}</div><div className="text-xs text-gray-500">{selectedAvatar?.style ?? "-"}</div></div></div></section>
          <section><h4 className="font-medium">工作流预览</h4><ul className="mt-3 space-y-2">{props.roleCatalog.workflows.filter((workflow) => workflow.role_template_id === selectedTemplate.role_id).flatMap((workflow) => workflow.steps).map((step) => <li key={step} className="rounded-xl border px-3 py-2 text-sm">{step}</li>)}</ul><button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenWorkflow?.(selectedTemplate.role_id)}>打开工作流</button></section>
          <section><h4 className="font-medium">能力与工具</h4><div className="mt-3 flex flex-wrap gap-2">{selectedTemplate.core_skills.map((skill) => <span key={skill} className="rounded-full bg-gray-100 px-3 py-1 text-xs">{skill}</span>)}</div><div className="mt-3 flex flex-wrap gap-2">{selectedTemplate.tools.map((tool) => <span key={tool} className="rounded-full bg-gray-100 px-3 py-1 text-xs">{tool}</span>)}</div><button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenTools?.(selectedTemplate.role_id)}>查看工具映射</button></section>
        </> : <div className="text-sm text-gray-500">请选择一个角色模板查看详情。</div>}
      </aside>
    </div>
  );
}
