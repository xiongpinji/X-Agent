/**
 * console 子应用共享领域类型（全局环境声明）。
 *
 * 这些类型对应后端契约：
 * - /api/v1/workbench        → backend.app.core.org.ConsoleBootstrapResponse
 * - /api/v1/dispatch         → backend.app.core.dispatch.DispatchResult
 * - /api/v1/collaboration    → 会议室 / 消息负载
 * - /api/v1/*-control        → 各中心 Overview 响应（在 consoleReducer.ts 中定义）
 *
 * 历史上 console 各文件以裸类型名引用这些契约（未 import），
 * 这里以全局声明方式补齐，避免逐文件改造。
 */

/** 链接摘要段落：{ summary, data } 结构，后端各中心 / 信封通用 */
type LinkedSummary = {
  summary?: ({ title?: string } & Record<string, any>);
  data?: Record<string, any>;
  [key: string]: any;
};

/** 统一信封：primary + linked_summaries 结构 */
type LinkedSummaryEnvelope = {
  resource_type?: string;
  resource_id?: string;
  primary?: Record<string, any>;
  linked_summaries?: Record<string, LinkedSummary>;
  snapshot?: Record<string, any>;
  [key: string]: any;
};

/** 实时消息（messages/stream、collaboration rooms messages） */
type RealtimeMessage = {
  message_id: string;
  room_id?: string | null;
  conversation_id?: string | null;
  sender_id?: string;
  sender_type?: string;
  sender_name: string;
  sender_avatar_id?: string | null;
  content: string;
  message_type: string;
  created_at: string;
  references?: string[];
  [key: string]: unknown;
};

/** 会话摘要 */
type ConversationSummary = {
  conversation_id: string;
  title: string;
  room_id?: string | null;
  unread_count: number;
  participant_ids: string[];
  last_message_at?: string | null;
  messages?: RealtimeMessage[];
  [key: string]: unknown;
};

/** 在线状态条目与映射 */
type PresenceEntry = {
  online?: boolean;
  status?: string;
  last_seen?: string | null;
  [key: string]: unknown;
};
type PresenceMap = Record<string, PresenceEntry>;

/** 会议室摘要 */
type MeetingRoomSummary = {
  room_id: string;
  name: string;
  topic: string;
  status?: string;
  department_id?: string;
  member_count?: number;
  member_agent_ids: string[];
  messages?: RealtimeMessage[];
  [key: string]: unknown;
};

/** 记忆快照（workbench.memory） */
type MemorySnapshot = {
  session_summary?: Record<string, unknown> | null;
  agent_summary?: Record<string, unknown> | null;
  department_summary?: Record<string, unknown> | null;
  layer_totals: Record<string, number>;
  memory_refs: string[];
  items?: unknown[];
  summary?: unknown;
  [key: string]: unknown;
};

/** 调度动作（后端 DispatchAction 的前端超集，status 为前端跟踪字段） */
type DispatchAction = {
  action: string;
  target?: string | null;
  reason?: string;
  priority?: number;
  status?: string;
  required_scope?: string[];
  parameters?: Record<string, unknown>;
  [key: string]: unknown;
};

/** 决策路径步骤 */
type DispatchDecisionStep = {
  step: string | number;
  name: string;
  reason?: string;
  confidence?: number | string;
  [key: string]: unknown;
};

/** 调度结果（后端 DispatchResult 的前端超集） */
type DispatchResult = {
  request?: Record<string, unknown>;
  suggestion: {
    confidence: number;
    reason: { summary: string } & Record<string, any>;
    next_actions: DispatchAction[];
    decision_path?: DispatchDecisionStep[];
    [key: string]: any;
  };
  status: string;
  trace_id?: string | null;
  generated_at?: string;
  actions: DispatchAction[];
  pending: DispatchAction[];
  queue_size: number;
  last_result: ({ task_id: string } & Record<string, any>) | null;
  [key: string]: any;
};

/** 角色形象（backend.app.core.org.RoleAvatar） */
type RoleAvatar = {
  avatar_id: string;
  role_name: string;
  display_name: string;
  category?: string;
  style?: string;
  icon_type?: string;
  expression?: string;
  outfit?: string;
  palette?: string[];
  badge?: string;
  status_variants?: Record<string, string>;
  graph_variant?: string;
  chat_variant?: string;
  meeting_variant?: string;
  thumbnail_url?: string | null;
  full_image_url?: string | null;
  alt_text?: string;
  usage?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

/** 岗位模板（backend.app.core.org.RoleTemplate 的页面使用子集） */
type RoleTemplate = {
  role_id: string;
  role_name: string;
  category?: string;
  level?: string;
  title: string;
  description: string;
  core_skills: string[];
  tools: string[];
  plugins?: string[];
  apps?: string[];
  persona?: string;
  tone?: string;
  decision_style?: string;
  communication_style?: string;
  risk_appetite?: string;
  [key: string]: unknown;
};

/** 兼容旧名：角色目录条目即岗位模板 */
type RoleCatalogItem = RoleTemplate;

/** 角色工作流模板（backend.app.core.org.RoleWorkflowTemplate） */
type RoleWorkflowTemplate = {
  role_template_id: string;
  workflow_name: string;
  steps: string[];
  review_steps: string[];
  approval_steps: string[];
  input_contract: string[];
  output_contract: string[];
  example_prompts?: string[];
  validation_rules: string[];
  handoff_rules: string[];
  escalation_rules: string[];
  required_tools?: string[];
  checkpoints?: string[];
  artifacts: string[];
  estimated_steps?: number;
  [key: string]: unknown;
};

/** 角色目录（backend.app.core.org.RoleCatalog） */
type RoleCatalog = {
  templates: RoleTemplate[];
  workflows: RoleWorkflowTemplate[];
  role_groups: Record<string, string[]>;
  role_index?: Record<string, string>;
  avatar_map?: Record<string, string>;
  [key: string]: unknown;
};

/** 组织图节点 */
type OrganizationGraphNode = {
  node_id: string;
  name: string;
  node_type?: string;
  [key: string]: unknown;
};

/** 智能体实例（组织图内） */
type AgentInstance = {
  agent_id: string;
  name: string;
  title: string;
  status?: string;
  online_status?: string;
  department_id?: string;
  role_template_id?: string;
  capabilities: string[];
  [key: string]: unknown;
};

/** 组织摘要 */
type OrganizationSummary = {
  org_id?: string;
  organization_id?: string;
  name?: string;
  [key: string]: unknown;
};

/** 部门摘要 */
type DepartmentSummary = {
  department_id: string;
  name: string;
  mission?: string;
  [key: string]: unknown;
};

/** 组织架构图视图（organization_store.build_organization_graph） */
type OrganizationGraphView = {
  organization: OrganizationSummary | null;
  departments: DepartmentSummary[];
  role_templates: RoleTemplate[];
  agent_instances: AgentInstance[];
  meeting_rooms: MeetingRoomSummary[];
  nodes: OrganizationGraphNode[];
  edges: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

/** 会议室发消息负载（MeetingRoomsPage 内部使用） */
type SendMessagePayload = {
  roomId: string;
  content: string;
  references: string[];
};
