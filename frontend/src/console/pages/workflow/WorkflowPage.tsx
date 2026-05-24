import React, { useMemo, useState } from "react";

export type WorkflowPageProps = {
  envelope?: LinkedSummaryEnvelope | null;
  workflowSummary?: { data?: Record<string, unknown>; summary?: Record<string, unknown> } | null;
  roleCatalog: RoleCatalog;
  selectedRoleTemplateId?: string | null;
  activeWorkflowId?: string | null;
  onSelectRoleTemplate: (roleTemplateId: string) => void;
  onSelectWorkflow?: (workflowId: string) => void;
};

export function WorkflowPage(props: WorkflowPageProps) {
  const selectedTemplate = useMemo(() => props.roleCatalog.templates.find((item) => item.role_id === props.selectedRoleTemplateId) ?? null, [props.roleCatalog.templates, props.selectedRoleTemplateId]);
  const workflows = useMemo(() => selectedTemplate ? props.roleCatalog.workflows.filter((workflow) => workflow.role_template_id === selectedTemplate.role_id) : [], [props.roleCatalog.workflows, selectedTemplate]);
  const [selectedStepIndex, setSelectedStepIndex] = useState(0);
  const envelopeWorkflowId = props.workflowSummary?.data?.workflow_id ?? props.workflowSummary?.summary?.workflow_id ?? props.envelope?.linked_summaries?.workflow?.workflow_id ?? props.envelope?.snapshot?.workflow_id ?? null;
  const activeWorkflow = useMemo(() => workflows.find((item) => item.workflow_name === props.activeWorkflowId) ?? workflows.find((item) => item.workflow_name === envelopeWorkflowId) ?? workflows[0] ?? null, [envelopeWorkflowId, workflows, props.activeWorkflowId]);
  const selectedStep = activeWorkflow?.steps[selectedStepIndex] ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px]">
      <aside className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">工作流库</h2>
            <p className="text-sm text-gray-500">先选岗位模板，再看对应工作流。</p>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectWorkflow?.(activeWorkflow?.workflow_name ?? workflows[0]?.workflow_name ?? "")}>返回当前</button>
        </header>
        <div className="mt-4 space-y-2">
          {props.roleCatalog.templates.map((template) => (
            <button
              key={template.role_id}
              className={`w-full rounded-xl border px-3 py-3 text-left transition ${selectedTemplate?.role_id === template.role_id ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"}`}
              onClick={() => {
                props.onSelectRoleTemplate(template.role_id);
                setSelectedStepIndex(0);
              }}
            >
              <div className="font-medium">{template.role_name}</div>
              <div className="mt-1 text-xs text-gray-500">{template.title}</div>
            </button>
          ))}
        </div>
      </aside>

      <main className="rounded-2xl border bg-white p-4 shadow-sm">
        {activeWorkflow ? (
          <>
            <header className="border-b pb-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{activeWorkflow.workflow_name}</h2>
                  <p className="mt-1 text-sm text-gray-500">角色：{selectedTemplate?.role_name ?? "-"}</p>
                </div>
                <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectWorkflow?.(activeWorkflow.workflow_name)}>
                  设为当前工作流
                </button>
              </div>
            </header>

            <section className="mt-4 grid gap-4 md:grid-cols-2">
              <WorkflowStepTimeline workflow={activeWorkflow} selectedStepIndex={selectedStepIndex} onSelectStep={setSelectedStepIndex} />
              <WorkflowExecutionPanel workflow={activeWorkflow} selectedStep={selectedStep} />
            </section>
            <section className="mt-4 grid gap-4 md:grid-cols-2">
              <WorkflowApprovalPanel workflow={activeWorkflow} />
              <WorkflowArtifactPanel workflow={activeWorkflow} />
            </section>
            <section className="mt-4">
              <WorkflowTracePanel workflow={activeWorkflow} />
            </section>
          </>
        ) : (
          <div className="flex min-h-[360px] items-center justify-center text-sm text-gray-500">暂无可展示工作流</div>
        )}
      </main>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        <section>
          <h3 className="font-semibold">工作流摘要</h3>
          <div className="mt-3 rounded-xl border p-3 text-sm text-gray-600">{selectedTemplate ? selectedTemplate.description : "请选择一个岗位模板"}</div>
        </section>
        <section>
          <h3 className="font-semibold">输入 / 输出</h3>
          <div className="mt-3 space-y-2 text-sm">
            <InfoList title="输入契约" items={activeWorkflow?.input_contract ?? []} />
            <InfoList title="输出契约" items={activeWorkflow?.output_contract ?? []} />
          </div>
        </section>
        <section>
          <h3 className="font-semibold">当前步骤</h3>
          <div className="mt-3 rounded-xl border p-3 text-sm text-gray-600">
            {selectedStep ?? "请选择步骤查看"}
          </div>
        </section>
      </aside>
    </div>
  );
}

function WorkflowStepTimeline({ workflow, selectedStepIndex, onSelectStep }: { workflow: RoleWorkflowTemplate; selectedStepIndex: number; onSelectStep: (index: number) => void; }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">步骤时间线</h3>
      <div className="mt-3 space-y-2">
        {workflow.steps.map((step, index) => (
          <button
            key={step}
            className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left hover:bg-gray-50 ${selectedStepIndex === index ? "border-blue-500 bg-blue-50" : ""}`}
            onClick={() => onSelectStep(index)}
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">{index + 1}</div>
            <div className="flex-1 text-sm">{step}</div>
          </button>
        ))}
      </div>
    </section>
  );
}

function WorkflowExecutionPanel({ workflow, selectedStep }: { workflow: RoleWorkflowTemplate; selectedStep: string | null; }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">执行节点</h3>
      <div className="mt-3 space-y-2 text-sm text-gray-600">
        <InfoList title="复核节点" items={workflow.review_steps} />
        <InfoList title="交接节点" items={workflow.handoff_rules} />
        <InfoList title="升级规则" items={workflow.escalation_rules} />
      </div>
      <div className="mt-4 rounded-xl border bg-gray-50 p-3 text-sm text-gray-700">
        {selectedStep ? `当前步骤：${selectedStep}` : "暂无选中步骤"}
      </div>
    </section>
  );
}

function WorkflowApprovalPanel({ workflow }: { workflow: RoleWorkflowTemplate }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">审批节点</h3>
      <div className="mt-3 space-y-2">
        {workflow.approval_steps.length ? workflow.approval_steps.map((step) => <div key={step} className="rounded-xl border px-3 py-2 text-sm">{step}</div>) : <div className="text-sm text-gray-500">无审批节点</div>}
      </div>
    </section>
  );
}

function WorkflowArtifactPanel({ workflow }: { workflow: RoleWorkflowTemplate }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">产出物</h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {workflow.artifacts.length ? workflow.artifacts.map((artifact) => <span key={artifact} className="rounded-full bg-gray-100 px-3 py-1 text-xs">{artifact}</span>) : <span className="text-sm text-gray-500">暂无产出物</span>}
      </div>
    </section>
  );
}

function WorkflowTracePanel({ workflow }: { workflow: RoleWorkflowTemplate }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">Trace / 审计路径</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {workflow.validation_rules.map((rule) => <div key={rule} className="rounded-xl border px-3 py-2 text-sm">{rule}</div>)}
      </div>
    </section>
  );
}

function InfoList({ title, items }: { title: string; items: string[] }) {
  return <div><div className="text-xs font-medium uppercase text-gray-400">{title}</div><div className="mt-2 flex flex-wrap gap-2">{items.length ? items.map((item) => <span key={item} className="rounded-full bg-gray-100 px-2 py-1 text-xs">{item}</span>) : <span className="text-xs text-gray-400">无</span>}</div></div>;
}
