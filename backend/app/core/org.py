from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field


class RoleAvatar(BaseModel):
    avatar_id: str = Field(default_factory=lambda: str(uuid4()))
    role_name: str
    display_name: str = ""
    category: str
    style: str = "business"
    icon_type: str = "portrait"
    expression: str = "neutral"
    outfit: str = "default"
    palette: list[str] = Field(default_factory=list)
    badge: str = ""
    status_variants: dict[str, str] = Field(default_factory=dict)
    graph_variant: str = ""
    chat_variant: str = ""
    meeting_variant: str = ""
    thumbnail_url: str | None = None
    full_image_url: str | None = None
    alt_text: str = ""
    usage: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ConsoleContext(BaseModel):
    mode: str = "full"
    tenant_id: str = "default"
    org_id: str | None = None
    department_id: str | None = None
    agent_id: str | None = None
    room_id: str | None = None
    session_id: str | None = None
    user_id: str = "anonymous"
    workspace_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    server_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConsoleBootstrapResponse(BaseModel):
    console: ConsoleContext
    dispatch: dict[str, object] = Field(default_factory=dict)
    role_catalog: RoleCatalog = Field(default_factory=RoleCatalog)
    organization_graph: dict[str, object] = Field(default_factory=dict)
    meeting_rooms: dict[str, object] = Field(default_factory=dict)
    realtime: dict[str, object] = Field(default_factory=dict)
    ui: dict[str, object] = Field(default_factory=dict)
    avatars: list[RoleAvatar] = Field(default_factory=list)
    workflows: dict[str, object] = Field(default_factory=dict)
    memory: dict[str, object] = Field(default_factory=dict)
    permissions: dict[str, object] = Field(default_factory=dict)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    server_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoleCategory(StrEnum):
    LEADERSHIP = "leadership"
    FINANCE = "finance"
    LEGAL = "legal"
    ENGINEERING = "engineering"
    DESIGN = "design"
    CONTENT = "content"
    OPERATIONS = "operations"
    SECURITY = "security"
    ADMINISTRATION = "administration"
    ANALYTICS = "analytics"
    SALES = "sales"
    CUSTOMER_SUCCESS = "customer_success"
    HR = "hr"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AgentRole(StrEnum):
    DIRECTOR = "director"
    MANAGER = "manager"
    LEAD = "lead"
    SPECIALIST = "specialist"
    ASSISTANT = "assistant"


class RoleTemplate(BaseModel):
    role_id: str = Field(default_factory=lambda: str(uuid4()))
    role_name: str
    category: RoleCategory
    level: str = "specialist"
    title: str = ""
    description: str = ""
    core_skills: list[str] = Field(default_factory=list)
    sub_skills: list[str] = Field(default_factory=list)
    industry_knowledge: list[str] = Field(default_factory=list)
    typical_tasks: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    quality_standards: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    review_steps: list[str] = Field(default_factory=list)
    approval_steps: list[str] = Field(default_factory=list)
    handoff_rules: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)
    model_mode: str = "balanced"
    persona: str = "professional"
    tone: str = "clear"
    decision_style: str = "balanced"
    communication_style: str = "direct"
    risk_appetite: str = "medium"
    can_manage_roles: list[str] = Field(default_factory=list)
    reports_to: str | None = None
    can_create_sub_agents: bool = True
    can_join_meetings: bool = True
    can_approve: bool = False
    can_delegate: bool = True
    can_view_sensitive_data: bool = False
    can_access_finance: bool = False
    can_access_contracts: bool = False
    can_access_source_code: bool = False
    can_access_customer_data: bool = False
    can_trigger_execution: bool = False
    extra: dict[str, object] = Field(default_factory=dict)


class RoleWorkflowTemplate(BaseModel):
    role_template_id: str
    workflow_name: str
    steps: list[str] = Field(default_factory=list)
    review_steps: list[str] = Field(default_factory=list)
    approval_steps: list[str] = Field(default_factory=list)
    input_contract: list[str] = Field(default_factory=list)
    output_contract: list[str] = Field(default_factory=list)
    example_prompts: list[str] = Field(default_factory=list)
    example_outputs: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    handoff_rules: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_plugins: list[str] = Field(default_factory=list)
    required_apps: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    estimated_steps: int = 0


class RoleCatalog(BaseModel):
    templates: list[RoleTemplate] = Field(default_factory=list)
    workflows: list[RoleWorkflowTemplate] = Field(default_factory=list)
    role_groups: dict[str, list[str]] = Field(default_factory=dict)
    role_index: dict[str, str] = Field(default_factory=dict)
    avatar_map: dict[str, str] = Field(default_factory=dict)


class Organization(BaseModel):
    org_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    name: str
    description: str = ""
    owner_user_id: str = "anonymous"
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Department(BaseModel):
    department_id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str
    name: str
    mission: str = ""
    leader_agent_id: str | None = None
    parent_department_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MeetingRoom(BaseModel):
    room_id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str
    department_id: str | None = None
    name: str
    topic: str = ""
    created_by: str = "anonymous"
    parent_room_id: str | None = None
    member_agent_ids: list[str] = Field(default_factory=list)
    member_user_ids: list[str] = Field(default_factory=list)
    invited_role_template_ids: list[str] = Field(default_factory=list)
    status: str = "active"
    visibility: str = "org"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrganizationGraphNode(BaseModel):
    node_id: str
    node_type: str
    name: str
    parent_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class OrganizationGraphEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    target_id: str
    relation: str
    metadata: dict[str, object] = Field(default_factory=dict)


class OrganizationGraphView(BaseModel):
    organization: Organization | None = None
    departments: list[Department] = Field(default_factory=list)
    role_templates: list[RoleTemplate] = Field(default_factory=list)
    agent_instances: list[AgentInstance] = Field(default_factory=list)
    meeting_rooms: list[MeetingRoom] = Field(default_factory=list)
    nodes: list[OrganizationGraphNode] = Field(default_factory=list)
    edges: list[OrganizationGraphEdge] = Field(default_factory=list)


class AgentInstance(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str
    department_id: str
    role_template_id: str
    name: str
    title: str = ""
    manager_agent_id: str | None = None
    meeting_room_id: str | None = None
    status: AgentStatus = AgentStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    child_agent_ids: list[str] = Field(default_factory=list)
    team_size_limit: int = Field(default=5, ge=0, le=100)
    memory_scope: dict[str, str] = Field(default_factory=dict)
    online_status: str = "offline"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentNode(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str
    department_id: str
    name: str
    role: AgentRole = AgentRole.ASSISTANT
    title: str = ""
    manager_agent_id: str | None = None
    status: AgentStatus = AgentStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    child_agent_ids: list[str] = Field(default_factory=list)
    team_size_limit: int = Field(default=5, ge=0, le=100)
    memory_scope: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


from backend.app.core.memory import memory_system


def build_default_role_catalog() -> RoleCatalog:
    templates = [
        RoleTemplate(
            role_name="总经理",
            category=RoleCategory.LEADERSHIP,
            level="executive",
            title="总经理 / CEO",
            description="负责组织级决策、资源协调、审批和跨部门统筹。",
            core_skills=["战略决策", "资源协调", "组织管理", "跨部门沟通"],
            industry_knowledge=["企业治理", "流程管理", "业务规划"],
            typical_tasks=["审批重大事项", "协调部门资源", "推进关键项目"],
            output_artifacts=["决策意见", "会议纪要", "行动计划"],
            quality_standards=["目标清晰", "责任明确", "结果可追踪"],
            workflow_steps=["接收议题", "评估风险", "召集会议", "决策下发", "跟踪结果"],
            review_steps=["风险复核", "预算复核", "资源复核"],
            approval_steps=["重大事项审批", "跨部门调度审批"],
            handoff_rules=["按部门负责人分发执行"],
            escalation_rules=["高风险事项升级董事会/老板"],
            tools=["overview", "dispatch", "audit"],
            plugins=["approval", "workflow", "memory"],
            apps=["workbench", "meeting_room"],
            persona="decisive",
            tone="firm",
            decision_style="high_level",
            communication_style="clear and concise",
            risk_appetite="low",
            can_manage_roles=["manager", "lead", "specialist", "assistant"],
            can_approve=True,
            can_delegate=True,
            can_view_sensitive_data=True,
            can_access_finance=True,
            can_access_contracts=True,
            can_access_source_code=False,
            can_access_customer_data=True,
            can_trigger_execution=True,
        ),
        RoleTemplate(
            role_name="短剧导演",
            category=RoleCategory.CONTENT,
            level="lead",
            title="短剧导演 / 内容总监",
            description="负责故事党纲、剧本、分镜、故事板、短视频制作与发布链路。",
            core_skills=["故事结构", "剧本创作", "分镜设计", "节奏控制", "短视频制作"],
            industry_knowledge=["短剧行业", "平台规则", "受众心理", "内容爆款逻辑"],
            typical_tasks=["根据故事党纲生成剧本", "制作分镜脚本", "输出故事板", "组织短视频制作"],
            output_artifacts=["剧本", "分镜脚本", "故事板", "拍摄清单", "剪辑建议"],
            quality_standards=["故事完整", "节奏强", "冲突明确", "可拍可剪"],
            workflow_steps=["接收故事党纲", "生成剧本", "用户审核", "生成分镜", "生成故事板", "生成制作清单", "输出发布建议"],
            review_steps=["剧本审核", "分镜审核", "故事板审核"],
            approval_steps=["剧本确认", "分镜确认", "成片发布确认"],
            handoff_rules=["剧本通过后进入分镜", "分镜通过后进入故事板"],
            escalation_rules=["重大改稿提交总经理或项目经理审批"],
            tools=["browser", "desktop", "memory", "workflow"],
            plugins=["script_writing", "storyboard", "video_planning"],
            apps=["workbench", "meeting_room", "video_pipeline"],
            persona="creative_director",
            tone="vivid",
            decision_style="creative_and_structured",
            communication_style="fast and visual",
            risk_appetite="medium",
            can_manage_roles=["writer", "editor", "producer"],
            can_join_meetings=True,
            can_approve=True,
            can_delegate=True,
            can_trigger_execution=True,
        ),
        RoleTemplate(
            role_name="财务会计",
            category=RoleCategory.FINANCE,
            level="specialist",
            title="财务会计",
            description="负责票据、报销、预算、成本和财务报表辅助。",
            core_skills=["票据整理", "账务分类", "预算跟踪", "成本分析"],
            industry_knowledge=["会计准则", "税务常识", "财务流程"],
            typical_tasks=["审核报销", "整理发票", "生成财务摘要"],
            output_artifacts=["报销清单", "财务摘要", "预算差异分析"],
            workflow_steps=["接收单据", "检查合规", "分类入账", "生成摘要", "提交审核"],
            review_steps=["票据复核", "预算复核"],
            approval_steps=["超预算审批", "异常支出审批"],
            handoff_rules=["异常单据升级法务/总经理"],
            escalation_rules=["发现风险立即上报"],
            tools=["table", "ocr", "document"],
            plugins=["invoice", "budget", "expense_review"],
            apps=["workbench", "finance_board"],
            persona="careful",
            tone="strict",
            decision_style="rule_based",
            communication_style="clear and formal",
            risk_appetite="low",
            can_access_finance=True,
            can_view_sensitive_data=True,
            can_approve=False,
        ),
        RoleTemplate(
            role_name="法律顾问",
            category=RoleCategory.LEGAL,
            level="specialist",
            title="法律顾问",
            description="负责合同审阅、风险提示、条款比对与合规建议。",
            core_skills=["合同审阅", "风险识别", "条款比对", "合规分析"],
            industry_knowledge=["合同法", "劳动法", "商业合规"],
            typical_tasks=["审阅合同", "标记风险条款", "给出修改建议"],
            output_artifacts=["合同审查意见", "风险提示", "修改建议清单"],
            workflow_steps=["接收合同", "提取关键条款", "识别风险", "给出建议", "提交审核"],
            review_steps=["法条比对", "风险复核"],
            approval_steps=["高风险条款审批"],
            handoff_rules=["风险过高转总经理/法务主管"],
            escalation_rules=["诉讼/重大纠纷立即升级"],
            tools=["document", "search", "memory"],
            plugins=["contract_review", "risk_scan"],
            apps=["workbench", "legal_board"],
            persona="formal",
            tone="precise",
            decision_style="risk_averse",
            communication_style="structured and cautious",
            risk_appetite="low",
            can_access_contracts=True,
            can_view_sensitive_data=True,
            can_approve=False,
        ),
        RoleTemplate(
            role_name="编程大牛",
            category=RoleCategory.ENGINEERING,
            level="lead",
            title="技术负责人 / 编程大牛",
            description="负责需求拆解、架构设计、代码生成、重构、测试与性能优化。",
            core_skills=["架构设计", "代码实现", "调试排错", "测试策略", "性能优化"],
            industry_knowledge=["软件工程", "工程实践", "CI/CD", "安全"],
            typical_tasks=["拆解需求", "设计方案", "生成代码", "修复 Bug"],
            output_artifacts=["技术方案", "代码补丁", "测试计划", "重构建议"],
            workflow_steps=["理解需求", "拆分任务", "设计方案", "实现编码", "自测验证", "交付代码"],
            review_steps=["代码审查", "测试复核", "安全检查"],
            approval_steps=["上线审批"],
            handoff_rules=["代码完成后交测试/发布"],
            escalation_rules=["架构风险升级总经理/技术负责人"],
            tools=["code", "test", "git", "browser"],
            plugins=["code_review", "test_generation", "bug_analysis"],
            apps=["workbench", "ide", "git_board"],
            persona="expert",
            tone="direct",
            decision_style="technical",
            communication_style="concise and practical",
            risk_appetite="medium",
            can_access_source_code=True,
            can_trigger_execution=True,
        ),
        RoleTemplate(
            role_name="前端设计",
            category=RoleCategory.DESIGN,
            level="specialist",
            title="前端设计 / UI 设计师",
            description="负责信息架构、交互设计、界面布局、组件拆分与设计系统。",
            core_skills=["信息架构", "交互设计", "UI 布局", "设计系统"],
            industry_knowledge=["前端工程", "UX", "可访问性", "响应式设计"],
            typical_tasks=["设计页面结构", "输出组件规范", "优化交互"],
            output_artifacts=["页面草图", "组件规范", "交互说明", "视觉稿"],
            workflow_steps=["理解需求", "设计结构", "制定布局", "定义组件", "输出规范", "交付设计"],
            review_steps=["可用性复核", "视觉复核"],
            approval_steps=["设计确认"],
            handoff_rules=["设计稿交付前端实现"],
            escalation_rules=["需求冲突升级产品/总经理"],
            tools=["browser", "design", "image"],
            plugins=["layout", "component_map", "design_system"],
            apps=["workbench", "design_board"],
            persona="detail_oriented",
            tone="clear",
            decision_style="user_centered",
            communication_style="visual and structured",
            risk_appetite="medium",
            can_join_meetings=True,
        ),
    ]
    workflows = [
        RoleWorkflowTemplate(role_template_id=templates[1].role_id, workflow_name="短剧导演工作流", steps=["故事党纲输入", "剧本生成", "用户审核", "分镜脚本生成", "故事板生成", "制作清单", "短视频制作建议", "发布建议"], review_steps=["剧本审核", "分镜审核", "故事板审核"], approval_steps=["剧本确认", "分镜确认", "成片确认"], input_contract=["故事党纲", "故事方向", "受众", "平台要求", "时长要求"], output_contract=["剧本", "分镜脚本", "故事板", "短视频制作清单"], example_prompts=["根据这个故事党纲生成短剧剧本"], example_outputs=["输出三幕式剧本、人物关系和冲突点"], validation_rules=["必须包含冲突点", "必须可拍摄", "必须能剪辑成短视频"], handoff_rules=["剧本确认后进入分镜", "分镜确认后进入故事板"], escalation_rules=["重大改稿升级总经理"], required_tools=["browser", "desktop", "memory"], required_plugins=["script_writing", "storyboard", "video_planning"], required_apps=["meeting_room", "video_pipeline"], checkpoints=["剧本确认", "分镜确认", "故事板确认", "制作清单确认"], artifacts=["剧本", "分镜脚本", "故事板", "拍摄清单"], estimated_steps=8),
        RoleWorkflowTemplate(role_template_id=templates[2].role_id, workflow_name="财务会计工作流", steps=["单据接收", "合规检查", "费用分类", "预算核对", "生成财务摘要", "提交审核"], review_steps=["票据复核", "预算复核"], approval_steps=["超预算审批", "异常支出审批"], input_contract=["发票", "报销单", "预算表"], output_contract=["财务摘要", "报销清单", "预算差异分析"], validation_rules=["金额必须匹配", "类别必须正确", "必须保留票据编号"], required_tools=["table", "ocr", "document"], required_plugins=["invoice", "budget", "expense_review"], required_apps=["finance_board"], checkpoints=["合规通过", "预算通过", "摘要确认"], artifacts=["报销清单", "预算差异分析"], estimated_steps=6),
        RoleWorkflowTemplate(role_template_id=templates[3].role_id, workflow_name="法律顾问工作流", steps=["合同接收", "条款提取", "风险识别", "法条比对", "给出修改建议", "提交审核"], review_steps=["法条复核", "风险复核"], approval_steps=["高风险条款审批"], input_contract=["合同正文", "附件", "业务背景"], output_contract=["风险提示", "修改建议清单", "审查意见"], validation_rules=["必须标记高风险条款", "必须给出可执行建议"], required_tools=["document", "search", "memory"], required_plugins=["contract_review", "risk_scan"], required_apps=["legal_board"], checkpoints=["条款提取", "风险标记", "建议确认"], artifacts=["审查意见", "风险提示"], estimated_steps=6),
        RoleWorkflowTemplate(role_template_id=templates[4].role_id, workflow_name="编程大牛工作流", steps=["需求理解", "任务拆分", "方案设计", "代码实现", "自测验证", "交付"], review_steps=["代码审查", "测试复核", "安全检查"], approval_steps=["上线审批"], input_contract=["需求描述", "约束条件", "验收标准"], output_contract=["技术方案", "代码补丁", "测试计划"], validation_rules=["必须可执行", "必须可测试", "必须符合安全要求"], required_tools=["code", "test", "git"], required_plugins=["code_review", "test_generation"], required_apps=["ide", "git_board"], checkpoints=["方案确认", "代码完成", "测试通过"], artifacts=["技术方案", "测试计划"], estimated_steps=6),
        RoleWorkflowTemplate(role_template_id=templates[5].role_id, workflow_name="前端设计工作流", steps=["需求理解", "信息架构", "布局设计", "组件拆分", "视觉稿输出", "交付开发"], review_steps=["可用性复核", "视觉复核"], approval_steps=["设计确认"], input_contract=["产品需求", "品牌规范", "目标用户"], output_contract=["页面草图", "组件规范", "视觉稿"], validation_rules=["必须可实现", "必须可访问", "必须符合设计系统"], required_tools=["browser", "design"], required_plugins=["layout", "component_map"], required_apps=["design_board"], checkpoints=["结构确认", "布局确认", "视觉确认"], artifacts=["视觉稿", "组件规范"], estimated_steps=6),
        RoleWorkflowTemplate(role_template_id=role_index.get("运营经理", templates[0].role_id), workflow_name="运营经理工作流", steps=["目标拆解", "活动策划", "执行排期", "数据监控", "复盘优化"], review_steps=["活动复核", "数据复核"], approval_steps=["预算审批", "活动上线审批"], input_contract=["业务目标", "活动预算", "目标用户"], output_contract=["活动方案", "执行排期", "复盘报告"], validation_rules=["目标必须可量化", "活动必须可执行"], required_tools=["memory", "table", "workflow"], required_plugins=["campaign_planning", "analytics_report"], required_apps=["ops_board"], checkpoints=["方案确认", "执行确认", "复盘确认"], artifacts=["活动方案", "复盘报告"], estimated_steps=5),
        RoleWorkflowTemplate(role_template_id=role_index.get("销售经理", templates[0].role_id), workflow_name="销售经理工作流", steps=["线索分配", "需求确认", "方案报价", "谈判推进", "签约跟进"], review_steps=["商机复核", "报价复核"], approval_steps=["折扣审批", "合同审批"], input_contract=["客户需求", "销售目标", "报价策略"], output_contract=["客户方案", "报价单", "签约跟进记录"], validation_rules=["方案必须可成交", "报价必须有依据"], required_tools=["crm", "memory", "document"], required_plugins=["lead_tracking", "deal_pipeline"], required_apps=["sales_board"], checkpoints=["需求确认", "报价确认", "签约确认"], artifacts=["报价单", "跟进记录"], estimated_steps=5),
        RoleWorkflowTemplate(role_template_id=role_index.get("HR", templates[0].role_id), workflow_name="HR 工作流", steps=["岗位需求", "简历筛选", "面试安排", "面试反馈", "录用办理"], review_steps=["岗位复核", "面试复核"], approval_steps=["录用审批"], input_contract=["岗位说明", "候选人简历", "面试反馈"], output_contract=["面试安排", "录用建议", "入职清单"], validation_rules=["岗位必须明确", "候选人必须匹配"], required_tools=["document", "calendar", "memory"], required_plugins=["resume_screening", "interview_scheduler"], required_apps=["hr_board"], checkpoints=["筛选确认", "面试确认", "录用确认"], artifacts=["面试安排", "录用建议"], estimated_steps=5),
    ]
    role_index = {template.role_name: template.role_id for template in templates}
    role_groups = {
        "leadership": [templates[0].role_id],
        "content": [templates[1].role_id],
        "finance": [templates[2].role_id],
        "legal": [templates[3].role_id],
        "engineering": [templates[4].role_id],
        "design": [templates[5].role_id],
    }
    avatar_map = {
        "总经理": "avatar-ceo",
        "短剧导演": "avatar-content-director",
        "财务会计": "avatar-finance",
        "法律顾问": "avatar-legal",
        "编程大牛": "avatar-engineering",
        "前端设计": "avatar-design",
    }
    return RoleCatalog(templates=templates, workflows=workflows, role_groups=role_groups, role_index=role_index, avatar_map=avatar_map)


class OrganizationStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._orgs: dict[str, Organization] = {}
        self._departments: dict[str, Department] = {}
        self._agents: dict[str, AgentNode] = {}
        self._role_catalog: RoleCatalog = build_default_role_catalog()

    def get_role_catalog(self) -> RoleCatalog:
        return self._role_catalog

    def create_organization(self, *, tenant_id: str, name: str, description: str = "", owner_user_id: str = "anonymous") -> Organization:
        org = Organization(tenant_id=tenant_id, name=name, description=description, owner_user_id=owner_user_id)
        with self._lock:
            self._orgs[org.org_id] = org
        return org

    def list_organizations(self, tenant_id: str | None = None) -> list[Organization]:
        items = list(self._orgs.values())
        if tenant_id is not None:
            items = [item for item in items if item.tenant_id == tenant_id]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def create_department(self, *, org_id: str, name: str, mission: str = "", leader_agent_id: str | None = None, parent_department_id: str | None = None) -> Department:
        if org_id not in self._orgs:
            raise KeyError(org_id)
        department = Department(org_id=org_id, name=name, mission=mission, leader_agent_id=leader_agent_id, parent_department_id=parent_department_id)
        with self._lock:
            self._departments[department.department_id] = department
            self._orgs[org_id].updated_at = datetime.now(UTC)
        return department

    def list_departments(self, org_id: str | None = None) -> list[Department]:
        items = list(self._departments.values())
        if org_id is not None:
            items = [item for item in items if item.org_id == org_id]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def create_agent(self, *, org_id: str, department_id: str, name: str, role: AgentRole = AgentRole.ASSISTANT, title: str = "", manager_agent_id: str | None = None, capabilities: list[str] | None = None, team_size_limit: int = 5, memory_scope: dict[str, str] | None = None) -> AgentNode:
        if org_id not in self._orgs:
            raise KeyError(org_id)
        if department_id not in self._departments:
            raise KeyError(department_id)
        agent = AgentNode(
            org_id=org_id,
            department_id=department_id,
            name=name,
            role=role,
            title=title,
            manager_agent_id=manager_agent_id,
            capabilities=capabilities or [],
            team_size_limit=team_size_limit,
            memory_scope=memory_scope or {},
        )
        with self._lock:
            self._agents[agent.agent_id] = agent
            if manager_agent_id and manager_agent_id in self._agents:
                manager = self._agents[manager_agent_id]
                if agent.agent_id not in manager.child_agent_ids and len(manager.child_agent_ids) < manager.team_size_limit:
                    manager.child_agent_ids.append(agent.agent_id)
                    manager.updated_at = datetime.now(UTC)
            self._departments[department_id].updated_at = datetime.now(UTC)
            self._orgs[org_id].updated_at = datetime.now(UTC)
        return agent

    def list_agents(self, org_id: str | None = None, department_id: str | None = None, manager_agent_id: str | None = None) -> list[AgentNode]:
        items = list(self._agents.values())
        if org_id is not None:
            items = [item for item in items if item.org_id == org_id]
        if department_id is not None:
            items = [item for item in items if item.department_id == department_id]
        if manager_agent_id is not None:
            items = [item for item in items if item.manager_agent_id == manager_agent_id]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def get_organization(self, org_id: str) -> Organization | None:
        return self._orgs.get(org_id)

    def get_department(self, department_id: str) -> Department | None:
        return self._departments.get(department_id)

    def get_agent(self, agent_id: str) -> AgentNode | None:
        return self._agents.get(agent_id)

    def get_agent_tree(self, root_agent_id: str) -> dict[str, object] | None:
        root = self.get_agent(root_agent_id)
        if root is None:
            return None
        return {
            "agent": root,
            "children": [self.get_agent_tree(child_id) for child_id in root.child_agent_ids if self.get_agent(child_id) is not None],
        }

    def build_organization_graph(self, org_id: str) -> OrganizationGraphView | None:
        org = self.get_organization(org_id)
        if org is None:
            return None
        departments = self.list_departments(org_id=org_id)
        agents = self.list_agents(org_id=org_id)
        rooms = [
            MeetingRoom(
                org_id=org_id,
                department_id=department.department_id,
                name=f"{department.name}会议室",
                topic=department.mission,
                invited_role_template_ids=[],
            )
            for department in departments
        ]
        role_catalog = build_default_role_catalog()
        nodes: list[OrganizationGraphNode] = [
            OrganizationGraphNode(node_id=org.org_id, node_type="organization", name=org.name, metadata={"status": org.status, "tenant_id": org.tenant_id}),
        ]
        edges: list[OrganizationGraphEdge] = []
        for department in departments:
            nodes.append(OrganizationGraphNode(node_id=department.department_id, node_type="department", name=department.name, parent_id=org.org_id, metadata={"mission": department.mission, "leader_agent_id": department.leader_agent_id}))
            edges.append(OrganizationGraphEdge(source_id=org.org_id, target_id=department.department_id, relation="contains_department"))
        for agent in agents:
            nodes.append(OrganizationGraphNode(node_id=agent.agent_id, node_type="agent", name=agent.name, parent_id=agent.manager_agent_id or agent.department_id, metadata={"department_id": agent.department_id, "role": agent.role, "title": agent.title, "status": agent.status, "online_status": getattr(agent, "online_status", "offline")}))
            edges.append(OrganizationGraphEdge(source_id=agent.department_id, target_id=agent.agent_id, relation="belongs_to_department"))
            if agent.manager_agent_id:
                edges.append(OrganizationGraphEdge(source_id=agent.manager_agent_id, target_id=agent.agent_id, relation="manages"))
        for template in role_catalog.templates:
            nodes.append(OrganizationGraphNode(node_id=template.role_id, node_type="role_template", name=template.role_name, metadata={"category": template.category, "level": template.level, "title": template.title}))
        for room in rooms:
            nodes.append(OrganizationGraphNode(node_id=room.room_id, node_type="meeting_room", name=room.name, parent_id=room.department_id or org.org_id, metadata={"topic": room.topic, "visibility": room.visibility}))
            if room.department_id:
                edges.append(OrganizationGraphEdge(source_id=room.department_id, target_id=room.room_id, relation="has_meeting_room"))
        return OrganizationGraphView(organization=org, departments=departments, role_templates=role_catalog.templates, agent_instances=[
            AgentInstance(
                agent_id=agent.agent_id,
                org_id=agent.org_id,
                department_id=agent.department_id,
                role_template_id=role_catalog.role_index.get(agent.role.value if hasattr(agent.role, "value") else str(agent.role), ""),
                name=agent.name,
                title=agent.title,
                manager_agent_id=agent.manager_agent_id,
                capabilities=agent.capabilities,
                child_agent_ids=agent.child_agent_ids,
                team_size_limit=agent.team_size_limit,
                memory_scope=agent.memory_scope,
                online_status=getattr(agent, "online_status", "offline"),
            ) for agent in agents
        ], meeting_rooms=rooms, nodes=nodes, edges=edges)

    def department_agent_tree(self, department_id: str) -> dict[str, object] | None:
        department = self.get_department(department_id)
        if department is None:
            return None
        agents = self.list_agents(department_id=department_id)
        leaders = [agent for agent in agents if agent.manager_agent_id is None]
        trees = [self.get_agent_tree(agent.agent_id) for agent in leaders]
        return {
            "department": department.model_dump(mode="json"),
            "agents": [agent.model_dump(mode="json") for agent in agents],
            "trees": [tree for tree in trees if tree is not None],
        }

    def department_memory_summary(self, department_id: str) -> dict[str, object]:
        department = self.get_department(department_id)
        if department is None:
            return {}
        agents = self.list_agents(department_id=department_id)
        leaders = [agent for agent in agents if agent.manager_agent_id is None]
        agent_summaries = [self.agent_memory_summary(agent.agent_id) for agent in leaders]
        layer_totals: dict[int, int] = {}
        for summary in agent_summaries:
            memory = summary.get("memory") or {}
            for layer, count in (memory.get("layer_breakdown") or {}).items():
                layer_totals[int(layer)] = layer_totals.get(int(layer), 0) + int(count)
        return {
            "department": department.model_dump(mode="json"),
            "leader_count": len(leaders),
            "agent_count": len(agents),
            "leaders": agent_summaries,
            "layer_totals": dict(sorted(layer_totals.items())),
        }

    def agent_memory_summary(self, agent_id: str) -> dict[str, object]:
        agent = self.get_agent(agent_id)
        if agent is None:
            return {}
        summary = memory_system.agent_summary(agent_id) if hasattr(memory_system, "agent_summary") else None
        children = [self.agent_memory_summary(child_id) for child_id in agent.child_agent_ids if self.get_agent(child_id) is not None]
        return {
            "agent": agent.model_dump(mode="json"),
            "memory": summary,
            "children": children,
        }

    def agent_context(self, agent_id: str) -> dict[str, object]:
        agent = self.get_agent(agent_id)
        if agent is None:
            return {}
        department = self.get_department(agent.department_id)
        org = self.get_organization(agent.org_id)
        return {
            "organization": org.model_dump(mode="json") if org else {},
            "department": department.model_dump(mode="json") if department else {},
            "agent": agent.model_dump(mode="json"),
            "children": [self.get_agent(child_id).model_dump(mode="json") for child_id in agent.child_agent_ids if self.get_agent(child_id) is not None],
            "feishu": {
                "feishu_user_id": agent.memory_scope.get("feishu_user_id", ""),
                "feishu_open_id": agent.memory_scope.get("feishu_open_id", ""),
                "feishu_union_id": agent.memory_scope.get("feishu_union_id", ""),
                "feishu_email": agent.memory_scope.get("feishu_email", ""),
                "feishu_enabled": agent.memory_scope.get("feishu_enabled", "false"),
            },
        }


organization_store = OrganizationStore()
