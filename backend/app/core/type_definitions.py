"""
类型定义模块 - 集中管理所有复杂数据结构的类型定义。

这个模块使用TypedDict和Pydantic模型定义所有复杂数据结构，
提升代码的类型安全性和IDE支持。
"""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


# ============================================================================
# 执行相关的类型定义
# ============================================================================


class ExecutionSummary(TypedDict, total=False):
    """执行摘要的类型定义。"""
    iterations: int
    subtasks: list[str]
    observations: list[str]
    tool_results: list[dict[str, Any]]
    reflections: list[str]
    subtask_status: dict[str, str]
    current_subtask_index: int
    branch: str
    branch_note: str
    reason: str
    next_action: str
    next_actions: list[str]
    recovery_plan: dict[str, Any]
    status: str
    retryable_failures: int
    repair_summary: dict[str, Any]
    verification: dict[str, Any]
    suggested_test_commands: list[str]
    code_index: dict[str, Any]
    test_mapping: dict[str, Any]
    execution_plan: dict[str, Any]
    workflow_state: dict[str, Any]
    approval_state: dict[str, Any]
    browser_state: dict[str, Any]
    desktop_state: dict[str, Any]
    orchestrator_plan: dict[str, Any]
    orchestrator_tool_decision: dict[str, Any]
    orchestrator_recovery_hint: dict[str, Any]
    repair_retries: list[dict[str, Any]]
    repair_failures: list[dict[str, Any]]
    repair_retry_count: int
    session_id: str | None
    run_view: dict[str, Any]


class CodeIndexContext(TypedDict, total=False):
    """代码索引上下文的类型定义。"""
    count: int
    related_files: list[str]
    impact_hints: list[str]
    test_files: list[str]


class TestMappingContext(TypedDict, total=False):
    """测试映射上下文的类型定义。"""
    related_files: list[str]
    test_files: list[str]
    impact_hints: list[str]
    dependency_hints: list[str]
    recommended_commands: list[str]


class ToolDecisionInfo(TypedDict, total=False):
    """工具决策信息的类型定义。"""
    tool_name: str
    confidence: float
    input_preview: dict[str, Any]
    reason: str


class RecoveryHintInfo(TypedDict, total=False):
    """恢复提示信息的类型定义。"""
    branch: str
    reason: str
    confidence: float
    follow_up: list[str]


# ============================================================================
# 工具执行相关的类型定义
# ============================================================================


class ToolExecutionResult(TypedDict, total=False):
    """工具执行结果的类型定义。"""
    tool_name: str
    success: bool
    output: Any
    error: str | None
    latency_ms: int
    risk_level: str


class ToolCallInfo(TypedDict, total=False):
    """工具调用信息的类型定义。"""
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    error: str | None
    success: bool


# ============================================================================
# 工作流相关的类型定义
# ============================================================================


class WorkflowState(TypedDict, total=False):
    """工作流状态的类型定义。"""
    workflow_id: str
    workflow_name: str
    workflow_status: str
    workflow_node_type: str
    active_count: int
    pending_count: int


class ApprovalState(TypedDict, total=False):
    """审批状态的类型定义。"""
    pending_count: int
    approval_status: str
    pending_approvals: list[dict[str, Any]]


class BrowserState(TypedDict, total=False):
    """浏览器状态的类型定义。"""
    active_count: int
    sessions: list[dict[str, Any]]


class DesktopState(TypedDict, total=False):
    """桌面状态的类型定义。"""
    active_count: int
    sessions: list[dict[str, Any]]


# ============================================================================
# Pydantic模型定义
# ============================================================================


class PlanStepModel(BaseModel):
    """计划步骤模型。"""
    kind: str
    instruction: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class TrajectoryModel(BaseModel):
    """轨迹模型。"""
    task: str
    goal: str
    stage: str = "planning"
    subtasks: list[str] = Field(default_factory=list)
    subtask_status: dict[str, str] = Field(default_factory=dict)
    current_subtask_index: int = 0
    observations: list[str] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    steps: list[PlanStepModel] = Field(default_factory=list)


class PlatformContextModel(BaseModel):
    """平台上下文模型。"""
    trace_id: str
    agent_id: str
    task: str
    goal: str
    stage: str
    memory: dict[str, Any] = Field(default_factory=dict)
    runs: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, Any] = Field(default_factory=dict)
    workflow: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    browser: dict[str, Any] = Field(default_factory=dict)
    desktop: dict[str, Any] = Field(default_factory=dict)
    extra_context: dict[str, Any] = Field(default_factory=dict)


class RepairSuggestionModel(BaseModel):
    """修复建议模型。"""
    should_retry: bool
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str
    error_type: str
    confidence: float
    follow_up: list[str] = Field(default_factory=list)


class VerificationResultModel(BaseModel):
    """验证结果模型。"""
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ============================================================================
# 辅助类型定义
# ============================================================================


class CompactContext(TypedDict, total=False):
    """压缩上下文的类型定义。"""
    root: str
    path: str
    target_path: str
    file: str
    pattern: str
    limit: int
    read_limit: int
    replace_all: bool
    old_text: str
    new_text: str
    replacement: str
    content: str
    goal: str
    objective: str
    patches: list[dict[str, Any]]
    resume_trace_id: str
    skip_observe_on_resume: bool
    task_focus: str
    patch_preview: list[dict[str, Any]]
    patch_count: int
    code_index: CodeIndexContext
    test_mapping: TestMappingContext
    capability_decision: dict[str, Any]
    orchestration_recovery_hint: dict[str, Any]
    orchestration_context: dict[str, Any]
    draft_plan: dict[str, Any]
    tool_decision: dict[str, Any]
    verification: dict[str, Any]
    execution_plan: dict[str, Any]
    session_id: str


class ResumePayload(TypedDict, total=False):
    """恢复负载的类型定义。"""
    completed_kinds: list[str]
    completed_step_labels: list[str]
    last_tool_call: dict[str, Any]
    previous_execution_summary: dict[str, Any]
    previous_status: str
