# X-Agent 原创内核能力包接入评估

生成日期：2026-06-10

## 范围

本评估只覆盖已迁移到主线仓库的独立模块、脚本和测试，不接入主线入口。

明确未修改：
- `backend/app/main.py`
- API router / control-plane
- agent loop
- frontend
- `backend/app/core/__init__.py`

## 当前状态

主线中的迁移文件目前仍是独立能力包，入口层未引用这些模块。模块级测试已存在，适合作为下一步集成前的安全边界。

2026-06-10 追加收口结论：

- 模块级集成报告已闭环：`.xagent_runtime/reports/original-kernel-module-integration-summary.json`
  - `status`: `original_kernel_module_integration_summary_ready`
  - `ready_report_count`: `7/7`
  - `entrypoints_modified`: `false`
  - `api_router_modified`: `false`
  - `control_plane_modified`: `false`
  - `frontend_modified`: `false`
  - `agent_loop_modified`: `false`
  - `backend_core_init_modified`: `false`
  - `real_execution_or_mutation_enabled`: `false`
  - `full_codex_parity_claimed`: `false`
- 选择性交付清单已闭环：`.xagent_runtime/reports/original-kernel-delivery-manifest.json`
  - `status`: `original_kernel_delivery_manifest_ready`
  - `stage_include_count`: `86`
  - `excluded_dirty_count`: `147`
  - `runtime_reports_stage_excluded`: `true`
  - `git_stage_performed`: `false`
  - `git_commit_performed`: `false`
  - `git_push_performed`: `false`
- 商用交付 owner-gated 门禁脚本已纳入选择性交付清单；`.xagent_runtime/reports/commercial-delivery-owner-commit-packet.json` 在当前未 staging 状态下为 `owner_commit_packet_blocked` / `commit_allowed=false`，这是空缓存区下的 post-stage 预期状态，不阻塞 pre-stage owner review。
- `.xagent_runtime/reports/commercial-delivery-owner-delivery-packet.json` 已作为单一 owner-facing pre-stage handoff，汇总 manifest、staging packet、runbook、pre-stage gate、owner stage approval request/gate、post-stage gate、commit packet、refresh chain 和 task board；当前为 `owner_delivery_packet_ready`，`stage_ready=true`，`commit_ready=false`。
- `.xagent_runtime/reports/commercial-delivery-owner-stage-approval-request.json` 当前为 `owner_stage_approval_request_ready`，并生成 `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json` 作为 owner approval payload 模板；该模板不是正式 approval，不会让 `stage_allowed` 变成 `true`。
- `.xagent_runtime/reports/commercial-delivery-owner-stage-execution-plan.json` 当前为 `owner_stage_execution_blocked` / `stage_allowed=false`，仅因 approval gate 尚未 ready；该计划会在 approval gate ready 后提供精确 stage command 顺序，但当前不会执行任何 `git add`。
- `.xagent_runtime/reports/commercial-delivery-owner-stage-approval-gate.json` 当前为 `owner_stage_approval_blocked` / `stage_allowed=false`，原因是 owner 尚未提供 `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.json`；这会阻止实际 staging，但不阻止 owner 先审阅 delivery packet。
- `excluded_dirty_paths` 已按 scope 区分 UI/API/配置/无关改动、二线共享收件箱和二线待主线评估候选；二线候选不是 UI 或 accidental dirty state。
- 二线 Codex gap/open-source fill report 已归类为 `secondary_handoff`；`integration_followup_queue.py`、`integration_owner_digest.py`、`integration_closure_checklist.py`、`integration_final_review_brief.py`、`integration_adoption_readme.py`、`integration_rollout_guardrails.py`、`integration_post_adoption_monitor.py`、`integration_sunset_review.py`、`integration_secondary_index.py`、`integration_conflict_risk_register.py`、`integration_review_readiness_gate.py`、`integration_review_packet_manifest.py`、`integration_stage_label_policy.py`、`integration_manifest_diff_summary.py`、`integration_manifest_review_digest.py`、`integration_reviewer_assignment_matrix.py`、`integration_review_calendar.py`、`integration_review_minutes.py`、`integration_review_archive_manifest.py`、`integration_review_retention_policy.py`、`integration_review_evidence_index.py`、`integration_review_query_plan.py`、`integration_review_query_result_digest.py`、`integration_review_answer_brief.py`、`integration_review_answer_action_matrix.py` 及对应测试已根据二线验证升级为 `secondary_integration_candidate`；`integration_review_action_status_board.py` 和对应测试已按 handoff 的 `next` 状态归类为 `secondary_pending_candidate`，等待二线完成验证交接后再评估升级。
- 二线固定线程 ID：`019ea5d4-c646-7340-9f11-e2681230470c`。主线协作协议已记录在 `docs/original-kernel-collaboration-protocol.md`，二线提醒只表示“新增候选待评估”，不会自动打断主线原子任务。
- 结论：原创内核能力包已经达到“模块级可选择性提交”状态，但仍未接入主线 API、agent loop、control plane、frontend 或 `backend/app/core/__init__.py`。

已做验证：

```powershell
python -m py_compile backend\app\core\structured_logging.py backend\app\core\permission_profiles.py backend\app\core\repo_context.py backend\app\core\context_pack.py backend\app\core\agent_run_closure.py backend\app\core\long_task_models.py backend\app\core\long_task_state_machine.py backend\app\core\long_task_merge_gates.py backend\app\core\long_tasks_helpers.py backend\app\core\shell_job_runner.py backend\app\core\pull_request_delivery.py backend\app\core\storage.py backend\app\core\audit_signing.py scripts\run_pytest_evidence.py scripts\check_report_hygiene.py scripts\normalize_report_count_aliases.py tests\test_structured_logging.py tests\test_permission_profiles.py tests\test_repo_context.py tests\test_context_pack.py tests\test_agent_run_closure.py tests\test_long_task_models.py tests\test_long_task_state_machine.py tests\test_long_task_merge_gates.py tests\test_long_tasks_helpers.py tests\test_shell_job_runner.py tests\test_pull_request_delivery.py tests\test_storage.py tests\test_audit_signing.py tests\test_run_pytest_evidence.py tests\test_report_hygiene.py tests\test_normalize_report_count_aliases.py
```

```powershell
python -m pytest tests/test_structured_logging.py tests/test_permission_profiles.py tests/test_repo_context.py tests/test_context_pack.py tests/test_agent_run_closure.py tests/test_long_task_models.py tests/test_long_task_state_machine.py tests/test_long_task_merge_gates.py tests/test_long_tasks_helpers.py tests/test_shell_job_runner.py tests/test_pull_request_delivery.py tests/test_storage.py tests/test_audit_signing.py tests/test_run_pytest_evidence.py tests/test_report_hygiene.py tests/test_normalize_report_count_aliases.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short
```

结果：`115 passed, 1 skipped`

新增收口验证：

```powershell
python -m py_compile scripts\original_kernel_module_integration_summary.py tests\test_original_kernel_module_integration_summary.py scripts\original_kernel_delivery_manifest.py tests\test_original_kernel_delivery_manifest.py
```

```powershell
python scripts\original_kernel_module_integration_summary.py
python scripts\original_kernel_delivery_manifest.py
```

```powershell
python -m pytest tests/test_original_kernel_minimal_integration_report.py tests/test_original_kernel_context_integration_report.py tests/test_original_kernel_agent_run_closure_report.py tests/test_original_kernel_long_task_integration_report.py tests/test_original_kernel_shell_job_runner_integration_report.py tests/test_original_kernel_pull_request_delivery_integration_report.py tests/test_original_kernel_report_evidence_integration_report.py tests/test_original_kernel_module_integration_summary.py tests/test_original_kernel_delivery_manifest.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short
```

结果：`25 passed`

## 来源一致性

已对主线与原创内核来源执行 SHA256 对比。

完全一致：
- `backend/app/core/storage.py`
- `backend/app/core/audit_signing.py`
- `backend/app/core/repo_context.py`
- `backend/app/core/coding_loop.py`
- `backend/app/core/permission_profiles.py`
- `backend/app/core/long_task_state_machine.py`
- `backend/app/core/structured_logging.py`
- `tests/test_storage.py`
- `tests/test_repo_context.py`
- `tests/test_context_pack.py`
- `tests/test_permission_profiles.py`
- `tests/test_pull_request_delivery.py`
- `tests/test_long_task_state_machine.py`
- `tests/test_run_pytest_evidence.py`

主线副本与来源已有差异，需要在接入前保留主线版本并审查差异来源：
- `backend/app/core/context_pack.py`
- `backend/app/core/pull_request_delivery.py`
- `backend/app/core/long_task_models.py`
- `backend/app/core/long_task_merge_gates.py`
- `backend/app/core/long_tasks_helpers.py`
- `backend/app/core/shell_job_runner.py`
- `backend/app/core/agent_run_closure.py`
- `scripts/run_pytest_evidence.py`
- `scripts/check_report_hygiene.py`
- `scripts/normalize_report_count_aliases.py`
- `tests/test_coding_loop.py`
- `tests/test_long_task_models.py`
- `tests/test_long_task_merge_gates.py`
- `tests/test_shell_job_runner.py`
- `tests/test_report_hygiene.py`
- `tests/test_normalize_report_count_aliases.py`

主线存在但来源同名文件未找到：
- `tests/test_audit_signing.py`
- `tests/test_long_tasks_helpers.py`
- `tests/test_agent_run_closure.py`
- `tests/test_structured_logging.py`

## 依赖与风险分层

低风险纯库：
- `structured_logging.py`
- `permission_profiles.py`
- `long_task_models.py`
- `long_task_state_machine.py`
- `long_tasks_helpers.py`
- `long_task_merge_gates.py`
- `agent_run_closure.py`

中风险本地只读/上下文扫描：
- `repo_context.py`：调用 `git` subprocess，当前用于构建仓库上下文。
- `context_pack.py`：依赖 `repo_context.py` 和主线 `RunContext`，适合作为报告/证据包入口，暂不接 agent loop。

高风险执行/写入/外部系统边界：
- `shell_job_runner.py`：可创建 shell 子进程并写运行结果，必须 owner-gated。
- `pull_request_delivery.py`：可调用 provider API，必须保持 dry-run-first，真实执行需要 `dry_run=False` 且 `execute=True`。
- `audit_signing.py`：支持外部命令签名，必须限制命令来源。
- `run_pytest_evidence.py`：会执行 pytest，适合作为显式 operator 脚本，不自动挂到主线流程。
- `check_report_hygiene.py` / `normalize_report_count_aliases.py`：会读写 `.xagent_runtime/reports`，适合放在交付验证链，不接在线请求路径。

## 最小接入点设计

### Step 1: structured_logging

接入目标：统一新增能力包自己的结构化日志格式，不改全局 logging 配置。

最小接入点：
- 只允许新模块直接 `from backend.app.core.structured_logging import ...`
- 不改 `backend/app/core/__init__.py`
- 不改 FastAPI startup 或全局 logger 初始化
- 先在后续新报告脚本或 runner 里按需使用

验收：
- `tests/test_structured_logging.py`
- 不新增入口依赖

### Step 2: permission_profiles

接入目标：把权限 profile 作为 approval/sandbox/admin contract 的离线判定库。

最小接入点：
- 新增适配层时应独立成文件，例如 `backend/app/core/permission_profile_adapter.py`
- 不直接改 approval router/control-plane
- 不替换现有审批主体，只做 profile -> decision metadata 的转换

验收：
- `tests/test_permission_profiles.py`
- 新增 adapter 测试时只验证 contract，不触发真实执行

### Step 3: repo_context + context_pack

接入目标：生成仓库上下文包，先服务于报告和 owner review，不接 agent loop。

最小接入点：
- 先做独立 report/script，例如 `scripts/repo_context_pack_report.py`
- 输出 `.xagent_runtime/reports/repo-context-pack.json`
- 不修改 `/sdk/invoke`、agent loop 或 control-plane

验收：
- `tests/test_repo_context.py`
- `tests/test_context_pack.py`
- 新增 report 测试确保不写源码、不执行 agent

### Step 4: agent_run_closure

接入目标：作为 trace/run 结果的离线收尾判定，不控制 agent loop。

最小接入点：
- 先只用于报告脚本或测试证据摘要
- 不接入 `AgentCoordinator` 或运行循环

验收：
- `tests/test_agent_run_closure.py`

### Step 5: long task state group

接入目标：先作为新长任务 contract 的模型和状态机，不替换主线长任务 API。

范围：
- `long_task_models.py`
- `long_task_state_machine.py`
- `long_task_merge_gates.py`
- `long_tasks_helpers.py`

最小接入点：
- 新增离线/owner-gated report 或 adapter
- 保持现有 API 和 workbench 不变
- 后续再评估是否映射到主线 long task 存储

验收：
- `tests/test_long_task_models.py`
- `tests/test_long_task_state_machine.py`
- `tests/test_long_task_merge_gates.py`
- `tests/test_long_tasks_helpers.py`

### Step 6: shell_job_runner

接入目标：只作为 owner-gated shell job contract，不自动执行。

最小接入点：
- 先新增 dry-run plan/report
- 默认不调用 `asyncio.create_subprocess_shell`
- 真实执行必须经过统一 approval/sandbox/admin contract

验收：
- `tests/test_shell_job_runner.py`
- 新增安全 grep，确认无默认执行路径

### Step 7: pull_request_delivery

接入目标：只接 dry-run delivery envelope，不自动创建 PR。

最小接入点：
- 保持 provider execution disabled
- 若进入主线流程，先只暴露计划、目标 remote、diff 摘要和执行前置条件
- 真实 API 调用必须保持 `dry_run=False` 且 `execute=True`

验收：
- `tests/test_pull_request_delivery.py`

### Step 8: report hygiene / pytest evidence

接入目标：作为交付验证脚本，不挂在线请求。

最小接入点：
- `check_report_hygiene.py` 可加入 RC/交付 gate
- `normalize_report_count_aliases.py` 默认先用 `--dry-run`
- `run_pytest_evidence.py` 只由 operator/CI 显式调用

验收：
- `tests/test_report_hygiene.py`
- `tests/test_normalize_report_count_aliases.py`
- `tests/test_run_pytest_evidence.py`

## 本轮建议

本轮已经完成 Step 1 到 Step 8 的模块级接入验证与交付清单收口。下一步不应继续自动接线，而应进入 owner-gated 的主线接入设计。

建议下一步：

1. 使用 `.xagent_runtime/reports/original-kernel-delivery-manifest.json` 的 `stage_include_paths` 做显式 staging，仍然不要使用 `git add .`。
2. 保持 `.xagent_runtime/reports/*.json` 作为本地证据，不默认提交运行时报告。
3. 明确排除 UI、API router、配置和无关工作树改动，包括：
   - `backend/app/api/workbench.py`
   - `frontend/`
   - `.agents/`
   - `.codex/`
   - `AGENTS.md`
   - `COMPETITIVE_ANALYSIS_2026.md`
   - `docs/01-项目规划/05-Creative-Studio短剧成片工作流.md`
4. 二线迁移会话已通过 `docs/original-kernel-secondary-handoff.md` 交接以下候选，它们不是 UI 或无关 dirty 文件，但本轮仍不纳入 `stage_include_paths`，需要主线单独评估后再整合：
   - `backend/app/core/workflow_events.py`
   - `tests/test_workflow_events.py`
   - `backend/app/core/long_tasks_recovery_audit.py`
   - `tests/test_long_tasks_recovery_audit.py`
   - `backend/app/core/skill_bundles.py`
   - `tests/test_skill_bundles.py`
   - `backend/app/core/trace_analysis.py`
   - `tests/test_trace_analysis.py`
   - `backend/app/core/agent_orchestration_runtime.py`
   - `tests/test_agent_orchestration_runtime.py`
   - `backend/app/core/agent_registry.py`
   - `tests/test_agent_registry.py`
   - `backend/app/core/policy_risk_analysis.py`
   - `tests/test_policy_risk_analysis.py`
   - `backend/app/core/acceptance_matrix.py`
   - `tests/test_acceptance_matrix.py`
   - `backend/app/core/model_provider_contracts.py`
   - `tests/test_model_provider_contracts.py`
   - `backend/app/core/deployment_security_contracts.py`
   - `tests/test_deployment_security_contracts.py`
   - `backend/app/core/url_safety.py`
   - `tests/test_url_safety.py`
   - `backend/app/core/output_redaction.py`
   - `tests/test_output_redaction.py`
   - `backend/app/core/patch_risk_analysis.py`
   - `tests/test_patch_risk_analysis.py`
   - `backend/app/core/open_source_report_audit.py`
   - `tests/test_open_source_report_audit.py`
   - `backend/app/core/task_environment_contracts.py`
   - `tests/test_task_environment_contracts.py`
   - `backend/app/core/pr_review_readiness.py`
   - `tests/test_pr_review_readiness.py`
   - `backend/app/core/instruction_source_audit.py`
   - `tests/test_instruction_source_audit.py`
   - `backend/app/core/browser_task_readiness.py`
   - `tests/test_browser_task_readiness.py`
   - `backend/app/core/open_source_adoption_matrix.py`
   - `tests/test_open_source_adoption_matrix.py`
   - `backend/app/core/agent_eval_matrix.py`
   - `tests/test_agent_eval_matrix.py`
   - `backend/app/core/subagent_handoff_matrix.py`
   - `tests/test_subagent_handoff_matrix.py`
   - `backend/app/core/mcp_tool_readiness.py`
   - `tests/test_mcp_tool_readiness.py`
   - `backend/app/core/channel_integration_readiness.py`
   - `tests/test_channel_integration_readiness.py`
   - `backend/app/core/release_evidence_pack.py`
   - `tests/test_release_evidence_pack.py`
   - `backend/app/core/runtime_capability_manifest.py`
   - `tests/test_runtime_capability_manifest.py`
   - `backend/app/core/integration_candidate_scorecard.py`
   - `tests/test_integration_candidate_scorecard.py`
   - `backend/app/core/integration_decision_audit.py`
   - `tests/test_integration_decision_audit.py`
   - `backend/app/core/integration_readiness_snapshot.py`
   - `tests/test_integration_readiness_snapshot.py`
   - `backend/app/core/candidate_dependency_map.py`
   - `tests/test_candidate_dependency_map.py`
   - `backend/app/core/integration_sequence_plan.py`
   - `tests/test_integration_sequence_plan.py`
   - `backend/app/core/integration_traceability_index.py`
   - `tests/test_integration_traceability_index.py`
   - `backend/app/core/integration_review_packet.py`
   - `tests/test_integration_review_packet.py`
   - `backend/app/core/integration_governance_summary.py`
   - `tests/test_integration_governance_summary.py`
   - `backend/app/core/integration_followup_queue.py`
   - `tests/test_integration_followup_queue.py`
   - `backend/app/core/integration_owner_digest.py`
   - `tests/test_integration_owner_digest.py`
   - `backend/app/core/integration_closure_checklist.py`
   - `tests/test_integration_closure_checklist.py`
   - `backend/app/core/integration_final_review_brief.py`
   - `tests/test_integration_final_review_brief.py`
   - `backend/app/core/integration_adoption_readme.py`
   - `tests/test_integration_adoption_readme.py`
   - `backend/app/core/integration_rollout_guardrails.py`
   - `tests/test_integration_rollout_guardrails.py`
   - `backend/app/core/integration_post_adoption_monitor.py`
   - `tests/test_integration_post_adoption_monitor.py`
   - `backend/app/core/integration_sunset_review.py`
   - `tests/test_integration_sunset_review.py`
   - `backend/app/core/integration_secondary_index.py`
   - `tests/test_integration_secondary_index.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_conflict_risk_register.py`
   - `tests/test_integration_conflict_risk_register.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_review_readiness_gate.py`
   - `tests/test_integration_review_readiness_gate.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_review_packet_manifest.py`
   - `tests/test_integration_review_packet_manifest.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_stage_label_policy.py`
   - `tests/test_integration_stage_label_policy.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_manifest_diff_summary.py`
   - `tests/test_integration_manifest_diff_summary.py`
   - 二线 focused 验证：`6 passed`
   - `backend/app/core/integration_manifest_review_digest.py`
   - `tests/test_integration_manifest_review_digest.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - `backend/app/core/integration_reviewer_assignment_matrix.py`
   - `tests/test_integration_reviewer_assignment_matrix.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_reviewer_assignment_matrix.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_calendar.py`
   - `tests/test_integration_review_calendar.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`18 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_calendar.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_minutes.py`
   - `tests/test_integration_review_minutes.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_minutes.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_archive_manifest.py`
   - `tests/test_integration_review_archive_manifest.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_archive_manifest.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_retention_policy.py`
   - `tests/test_integration_review_retention_policy.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`25 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_retention_policy.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_evidence_index.py`
   - `tests/test_integration_review_evidence_index.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_evidence_index.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_query_plan.py`
   - `tests/test_integration_review_query_plan.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_query_plan.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_query_result_digest.py`
   - `tests/test_integration_review_query_result_digest.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`18 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_query_result_digest.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_answer_brief.py`
   - `tests/test_integration_review_answer_brief.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`24 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_answer_brief.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - `backend/app/core/integration_review_answer_action_matrix.py`
   - `tests/test_integration_review_answer_action_matrix.py`
   - 二线 focused 验证：`6 passed`
   - 二线相邻组合验证：`30 passed`
   - 主线复核：`python -m pytest tests/test_integration_review_answer_action_matrix.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short` -> `6 passed`
   - 二线明确跳过：`long_task_workbench.py`，原因是依赖主线不存在的 `backend/app/core/long_tasks.py` 及多个底层工作台构造函数，直接迁移会造成断 import 或拉入大运行时/API 面。
   - 二线明确不覆盖：`tracing.py` / `tracing_postgres.py`，因为主线已有实现并被依赖注入和 agent trace endpoints 使用；本轮只新增旁路纯分析层 `trace_analysis.py`。
   - 二线明确不迁移：`agent_registry.py` 的 `PostgresAgentRegistryStore`、`AGENT_REGISTRY_SCHEMA_SQL`、dependency factory/API 测试，因为这些会引入数据库后端和入口集成预期；当前仅保留 JSON/in-memory registry contract。
   - 二线明确不替换：`policy.py` / `ToolPolicyEngine.evaluate()` / `ToolPolicyVerdict`，因为这会影响现役工具策略、审批和 registry 行为；当前仅保留 detached advisory helper `policy_risk_analysis.py`。
   - 二线明确不迁移：原 `scripts/run_acceptance_matrix.py`、历史报告 supersede mutation 和原 `scripts/acceptance_matrix.py` 依赖的 provider policy 脚本；当前仅保留纯内存 `build_p0_acceptance_matrix()` builder。
   - 二线明确不接入：`backend/app/core/llm_providers/*`、provider router、provider API、模型调用、运行时 provider selection 或 release gate；当前仅保留离线 provider/env contract helper。
   - 二线明确不替换：`backend/app/core/security.py`，也不迁移原 `scripts/check_deployment_security_mode.py` 文件扫描 CLI；当前仅保留纯文本映射输入的 deployment security analyzer。
   - 二线明确不替换：`backend/app/core/log_sanitizer.py`，也不接入 logging filters、request handlers、tool execution、upload/handoff APIs 或 secret storage；当前仅保留离线 URL safety/redaction helper。
   - 二线明确不接入：logging filters、tool execution、request handlers、command-result persistence 或 secret storage；当前仅保留离线 command-output/report-payload redaction helper。
   - 二线明确不接入：engineering runtime、patch application、approval policy、file access enforcement、API router、agent loop、control plane 或 frontend；当前仅保留路径级 patch risk advisory helper。
   - 二线明确不替换或接入：`open_source_base.py`、`open_source_store.py`、`open_source_wiring.py`、provider、API routes、agent-loop discovery usage 或 public `open_source_api` exports；当前仅保留离线 open-source discovery report/candidate quality analyzer。
   - 二线明确不接入：worktree creation、git operations、sandbox allocation、issue-to-PR execution、API router、agent loop、control plane、database、workers、frontend 或 approval policy；当前仅保留纯 payload task/worktree/sandbox/PR lifecycle contract。
   - 二线明确不接入：GitHub API、PR 创建/更新、PR comment、live git diff、test execution、merge gates、API router、agent loop、control plane、database、workers、frontend 或 approval policy；当前仅保留纯离线 PR/code-review readiness matrix。
   - 二线明确不接入：真实 `AGENTS.md` 读写、`.agents` / `.codex` mutation、skill loading/execution、config mutation、API router、agent loop、control plane、database、workers、frontend 或 skill runtime；当前仅保留纯 payload instruction-source audit helper。
   - 二线明确不接入：Playwright/browser execution、screenshot capture、live session reads、browser API calls、browser state mutation、API router、agent loop、control plane、database、workers、frontend 或 browser runtime；当前仅保留纯离线 browser task readiness matrix。
   - 二线明确不接入：open-source provider calls、network access、dependency install、external project imports、store mutation、API router、agent loop、control plane、database、workers、frontend、provider runtime 或 skill-market ingestion；当前仅保留纯离线 open-source adoption scoring matrix。
   - 二线明确不接入：model calls、benchmark execution、test execution、runtime report reads/writes、release gates、evaluation dataset mutation、API router、agent loop、control plane、database、workers、frontend、model provider routing 或 benchmark runtime；当前仅保留纯 payload agent task acceptance/regression matrix。
   - 二线明确不接入：subagent spawning、Codex thread inspect/control、worktree reads、git merge、validation execution、parent task/staging manifest mutation、API router、agent loop、control plane、database、workers、frontend、orchestration runtime 或 merge gates；当前仅保留纯 payload subagent handoff/readiness matrix。
   - 二线明确不接入：MCP server calls、OAuth、tool execution、server install、config/tool registry/hooks/approval/execution store mutation、API router、agent loop、control plane、database、workers、frontend、tool runtime 或 plugin ingestion；当前仅保留纯 payload MCP/tool metadata readiness matrix。
   - 二线明确不接入：webhook send、channel API calls、message posting、live credential reads、callback registration、channel config mutation、API router、agent loop、control plane、database、workers、frontend、commercial pilot scripts、notification runtime、issue-to-PR endpoints 或 external connector wiring；当前仅保留纯 payload collaboration-channel readiness matrix。
   - 二线明确不接入：filesystem report read/write、`.xagent_runtime` mutation、verification execution、provider calls、release gates、API router、agent loop、control plane、database、workers、frontend、report writers、PR delivery 或 acceptance matrix wiring；当前仅保留纯 payload release/integration evidence pack aggregator。
   - 二线明确不接入：live runtime probing、optional dependency import、installed package inspection、config read/write、manifest mutation、API router、agent loop、control plane、database、workers、frontend、capability discovery、release reports、provider/tool/browser/channel runtimes 或 runtime config；当前仅保留纯 payload runtime capability manifest builder。
   - 二线明确不接入：staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration candidate prioritization scorecard。
   - 二线明确不接入：decision log mutation、staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration decision audit helper。
   - 二线明确不接入：filesystem snapshot writes、dashboard mutation、decision log mutation、staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration readiness snapshot summarizer。
   - 二线明确不接入：dependency manifest 写入、staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload candidate dependency/blocker map。
   - 二线明确不接入：staging manifest 写入、include/exclude path mutation、dependency manifest mutation、integration queues、decision logs、release reports、filesystem snapshots、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration sequence plan。
   - 二线明确不接入：filesystem 扫描、git state 读取、report 写入、validation manifest mutation、staging manifest mutation、include/exclude path mutation、dependency manifest mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration traceability index。
   - 二线明确不接入：report 写入、dashboard 渲染、filesystem 扫描、git state 读取、validation manifest mutation、staging manifest mutation、include/exclude path mutation、decision log mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration review packet。
   - 二线明确不接入：report 写入、dashboard 渲染、filesystem 扫描、git state 读取、validation manifest mutation、staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration governance summary。
   - 二线明确不接入：GitHub/Linear/ClickUp issue 创建、notification/message 发送、file 写入、filesystem 扫描、git state 读取、validation manifest mutation、staging manifest mutation、include/exclude path mutation、integration queues、release reports、PR delivery、acceptance gates、API router、agent loop、control plane、database、workers、frontend 或 mainline integration workflow；当前仅保留纯 payload integration follow-up queue。
5. 若要继续推进主线接入，先单独设计 owner-gated adapter，不直接改 API router、agent loop、control plane、frontend 或 `backend/app/core/__init__.py`。
6. 推荐第一个主线接入设计点仍是只读/无执行的 `repo_context + context_pack` report 或 approval metadata adapter；`shell_job_runner`、`pull_request_delivery`、`run_pytest_evidence` 继续保持显式 operator/owner-gated。
