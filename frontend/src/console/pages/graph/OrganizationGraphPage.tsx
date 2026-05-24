import React, { useMemo } from "react";

export type OrganizationGraphPageProps = {
  graph: OrganizationGraphView;
  avatars: RoleAvatar[];
  selectedNodeId?: string | null;
  onSelectNode: (nodeId: string) => void;
  onCreateAgentFromNode?: (nodeId: string) => void;
  onCreateRoomFromNode?: (roomId: string) => void;
};

export function OrganizationGraphPage(props: OrganizationGraphPageProps) {
  const selectedNode = useMemo(() => props.graph.nodes.find((node) => node.node_id === props.selectedNodeId) ?? null, [props.graph.nodes, props.selectedNodeId]);
  const selectedAgent = useMemo(() => props.graph.agent_instances.find((agent) => agent.agent_id === props.selectedNodeId) ?? null, [props.graph.agent_instances, props.selectedNodeId]);
  const selectedRoleTemplate = useMemo(() => selectedAgent ? props.graph.role_templates.find((role) => role.role_id === selectedAgent.role_template_id) ?? null : null, [props.graph.role_templates, selectedAgent]);
  const selectedAvatar = useMemo(() => selectedRoleTemplate ? props.avatars.find((avatar) => avatar.role_name === selectedRoleTemplate.role_name) ?? null : null, [props.avatars, selectedRoleTemplate]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">组织架构图</h2>
            <p className="text-sm text-gray-500">企业、部门、岗位、智能体、会议室关系图。</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectNode(props.graph.organization?.organization_id ?? "")}>
              返回组织
            </button>
          </div>
        </header>

        <div className="space-y-4">
          {props.graph.departments.map((department) => {
            const departmentAgents = props.graph.agent_instances.filter((agent) => agent.department_id === department.department_id);
            const departmentRooms = props.graph.meeting_rooms.filter((room) => room.department_id === department.department_id);
            return (
              <div key={department.department_id} className="rounded-xl border bg-white p-4">
                <button className="mb-3 flex w-full items-center justify-between text-left" onClick={() => props.onSelectNode(department.department_id)}>
                  <div>
                    <div className="font-semibold">{department.name}</div>
                    <div className="text-sm text-gray-500">{department.mission}</div>
                  </div>
                  <span className="text-xs text-gray-400">部门</span>
                </button>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {departmentAgents.map((agent) => {
                    const role = props.graph.role_templates.find((r) => r.role_id === agent.role_template_id);
                    const avatar = role ? props.avatars.find((a) => a.role_name === role.role_name) : null;
                    return (
                      <button key={agent.agent_id} className={`rounded-xl border p-3 text-left hover:bg-gray-50 ${props.selectedNodeId === agent.agent_id ? "border-blue-500 bg-blue-50" : ""}`} onClick={() => props.onSelectNode(agent.agent_id)}>
                        <div className="flex items-center gap-3"><div className="h-10 w-10 rounded-full bg-gray-200" /><div className="min-w-0"><div className="font-medium">{agent.name}</div><div className="truncate text-xs text-gray-500">{role?.title ?? agent.title}</div></div></div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-blue-50 px-2 py-1 text-blue-700">{agent.online_status}</span>{avatar ? <span className="rounded-full bg-gray-100 px-2 py-1 text-gray-600">{avatar.display_name}</span> : null}</div>
                      </button>
                    );
                  })}
                  {departmentRooms.map((room) => (
                    <button key={room.room_id} className={`rounded-xl border p-3 text-left hover:bg-gray-50 ${props.selectedNodeId === room.room_id ? "border-blue-500 bg-blue-50" : ""}`} onClick={() => props.onSelectNode(room.room_id)}>
                      <div className="font-medium">{room.name}</div>
                      <div className="text-sm text-gray-500">{room.topic}</div>
                      <div className="mt-2 text-xs text-gray-400">{room.member_count ?? room.member_agent_ids.length} 成员</div>
                      <div className="mt-3 flex gap-2">
                        <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={(e) => { e.stopPropagation(); props.onCreateRoomFromNode?.(room.room_id); }}>打开房间</button>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <aside className="rounded-2xl border bg-white p-4 shadow-sm">
        <h3 className="text-lg font-semibold">节点详情</h3>
        {selectedNode ? (
          <div className="mt-4 space-y-4">
            <div className="flex items-center gap-3"><div className="h-14 w-14 rounded-full bg-gray-200" /><div><div className="font-medium">{selectedNode.name}</div><div className="text-sm text-gray-500">{selectedNode.node_type}</div></div></div>
            {selectedAgent ? <section className="rounded-xl border p-3"><div className="text-sm font-medium">智能体信息</div><div className="mt-2 text-sm text-gray-600">岗位：{selectedAgent.title}</div><div className="text-sm text-gray-600">在线：{selectedAgent.online_status}</div><div className="mt-3 flex flex-wrap gap-2">{selectedAgent.capabilities.map((cap) => <span key={cap} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{cap}</span>)}</div><div className="mt-3 flex gap-2"><button className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white" onClick={() => props.onCreateAgentFromNode?.(selectedAgent.agent_id)}>从节点创建智能体</button></div></section> : null}
            {selectedRoleTemplate ? <section className="rounded-xl border p-3"><div className="text-sm font-medium">岗位模板</div><div className="mt-1 text-sm text-gray-600">{selectedRoleTemplate.description}</div><div className="mt-3 flex flex-wrap gap-2">{selectedRoleTemplate.core_skills.map((skill) => <span key={skill} className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700">{skill}</span>)}</div></section> : null}
            {selectedAvatar ? <section className="rounded-xl border p-3"><div className="text-sm font-medium">角色形象</div><div className="mt-2 flex items-center gap-3"><div className="h-12 w-12 rounded-full bg-gray-200" /><div><div className="text-sm font-medium">{selectedAvatar.display_name}</div><div className="text-xs text-gray-500">{selectedAvatar.style}</div></div></div></section> : null}
            <div className="flex gap-2"><button className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white" onClick={() => props.onCreateAgentFromNode?.(selectedNode.node_id)}>从节点创建智能体</button><button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onCreateRoomFromNode?.(selectedNode.node_id)}>打开关联房间</button></div>
          </div>
        ) : <p className="mt-4 text-sm text-gray-500">请选择一个节点查看详情。</p>}
      </aside>
    </div>
  );
}
