# Auto-generated pure-payload readiness packet specs.
from __future__ import annotations

SPECS = {
    "artifact_evidence_index": {
        "actions": [
            "provide_codex_artifact_evidence_index_inventory",
            "share_artifact_evidence_index_readiness_with_mainline"
        ],
        "aliases": [
            "artifacts",
            "findings"
        ],
        "build_function": "build_codex_artifact_evidence_index_readiness_packet",
        "codes": [
            "codex_artifact_evidence_index_live_operation_blocked",
            "codex_artifact_evidence_index_packet_missing_evidence",
            "codex_artifact_evidence_index_readiness_packet",
            "codex_artifact_evidence_index_status_failed"
        ],
        "collection_key": "artifacts",
        "item_id_field": "artifact_id",
        "module": "codex_artifact_evidence_index_readiness_packet",
        "packet_missing_refs": [
            "artifact_policy_ref",
            "evidence_index_policy_ref",
            "provenance_policy_ref",
            "retention_policy_ref",
            "artifact_evidence_manifest_ref",
            "work_product_governance_ref"
        ],
        "packet_policy_keys": [
            "artifact_policy",
            "evidence_index_policy",
            "provenance_policy",
            "retention_policy",
            "artifact_evidence_manifest_ref",
            "work_product_governance_ref"
        ],
        "required_fields": [
            "artifact_id",
            "status",
            "artifact_ref",
            "evidence_index_refs",
            "provenance_refs",
            "retention_refs",
            "validation_receipt_refs",
            "handoff_refs",
            "source_refs",
            "owner_refs",
            "integrity_refs"
        ],
        "summarize_function": "summarize_codex_artifact_evidence_index",
        "summary_keys": [
            "artifact_count",
            "evidence_index_ref_count"
        ]
    },
    "background_task": {
        "actions": [
            "provide_codex_background_task_inventory",
            "refresh_background_task_readiness",
            "resolve_background_task_blockers",
            "share_background_task_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "tasks"
        ],
        "build_function": "build_codex_background_task_readiness_packet",
        "codes": [
            "codex_background_task_missing_evidence",
            "codex_background_task_packet_missing_evidence",
            "codex_background_task_readiness_packet",
            "codex_background_task_terminal_failure"
        ],
        "collection_key": "tasks",
        "item_id_field": "task_id",
        "module": "codex_background_task_readiness_packet",
        "packet_missing_refs": [
            "retry_policy_ref",
            "resumability_policy_ref",
            "artifact_policy_ref",
            "task_queue_ref",
            "handoff_policy_ref",
            "notification_policy_ref"
        ],
        "packet_policy_keys": [
            "retry_policy",
            "resumability_policy",
            "artifact_policy",
            "queue_ref",
            "handoff_policy_ref",
            "notification_policy_ref"
        ],
        "required_fields": [
            "task_id",
            "task_type",
            "state",
            "queue_state",
            "resumable",
            "retry_policy",
            "branch_ref",
            "worktree_ref",
            "handoff_ref",
            "notification_ref",
            "artifact_refs",
            "validation_refs",
            "diff_refs"
        ],
        "summarize_function": "summarize_codex_background_task",
        "summary_keys": [
            "remote_task_count",
            "task_count"
        ]
    },
    "ci_gate": {
        "actions": [
            "provide_codex_ci_gate_inventory",
            "review_posting_policy",
            "review_posting_policy_ref",
            "review_posting_ref_count",
            "review_result_posting_refs",
            "share_ci_gate_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "gates"
        ],
        "build_function": "build_codex_ci_gate_readiness_packet",
        "codes": [
            "codex_ci_gate_check_failed",
            "codex_ci_gate_packet_missing_evidence",
            "codex_ci_gate_readiness_packet"
        ],
        "collection_key": "gates",
        "item_id_field": "gate_id",
        "module": "codex_ci_gate_readiness_packet",
        "packet_missing_refs": [
            "required_check_policy_ref",
            "workflow_policy_ref",
            "artifact_policy_ref",
            "review_posting_policy_ref",
            "ci_manifest_ref"
        ],
        "packet_policy_keys": [
            "required_check_policy",
            "workflow_policy",
            "artifact_policy",
            "review_posting_policy",
            "ci_manifest_ref"
        ],
        "required_fields": [
            "gate_id",
            "provider",
            "gate_status",
            "workflow_refs",
            "check_run_refs",
            "status_contexts",
            "check_states",
            "artifact_refs",
            "required_check_refs",
            "review_result_posting_refs",
            "validation_refs"
        ],
        "summarize_function": "summarize_codex_ci_gate",
        "summary_keys": [
            "gate_count",
            "review_posting_ref_count"
        ]
    },
    "code_review_findings": {
        "actions": [
            "provide_codex_code_review_findings_inventory",
            "refresh_code_review_findings_readiness",
            "resolve_code_review_finding_blockers",
            "review_findings",
            "review_findings_manifest_ref",
            "review_output_governance_ref",
            "review_policy",
            "review_policy_ref",
            "share_code_review_findings_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "review_findings"
        ],
        "build_function": "build_codex_code_review_findings_readiness_packet",
        "codes": [
            "codex_code_review_finding_status_failed",
            "codex_code_review_findings_live_output_blocked",
            "codex_code_review_findings_packet_missing_evidence",
            "codex_code_review_findings_readiness_packet"
        ],
        "collection_key": "findings",
        "item_id_field": "finding_id",
        "module": "codex_code_review_findings_readiness_packet",
        "packet_missing_refs": [
            "review_policy_ref",
            "severity_policy_ref",
            "evidence_policy_ref",
            "suppression_policy_ref",
            "review_findings_manifest_ref",
            "review_output_governance_ref"
        ],
        "packet_policy_keys": [
            "review_policy",
            "severity_policy",
            "evidence_policy",
            "suppression_policy",
            "review_findings_manifest_ref",
            "review_output_governance_ref"
        ],
        "required_fields": [
            "finding_id",
            "status",
            "severity",
            "finding_ref",
            "file_line_refs",
            "evidence_refs",
            "suggested_fix_refs",
            "validation_receipt_refs",
            "suppression_refs",
            "owner_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_code_review_finding",
        "summary_keys": [
            "file_line_ref_count",
            "finding_count"
        ]
    },
    "collaboration_subagent": {
        "actions": [
            "provide_codex_collaboration_subagent_inventory",
            "refresh_collaboration_subagent_readiness",
            "resolve_collaboration_subagent_blockers",
            "share_collaboration_subagent_readiness_with_mainline"
        ],
        "aliases": [
            "collaborations",
            "findings"
        ],
        "build_function": "build_codex_collaboration_subagent_readiness_packet",
        "codes": [
            "codex_collaboration_subagent_live_execution_blocked",
            "codex_collaboration_subagent_packet_missing_evidence",
            "codex_collaboration_subagent_readiness_packet",
            "codex_collaboration_subagent_status_failed"
        ],
        "collection_key": "collaborations",
        "item_id_field": "collaboration_id",
        "module": "codex_collaboration_subagent_readiness_packet",
        "packet_missing_refs": [
            "collaboration_policy_ref",
            "assignment_policy_ref",
            "handoff_policy_ref",
            "aggregation_policy_ref",
            "collaboration_manifest_ref",
            "coordination_governance_ref"
        ],
        "packet_policy_keys": [
            "collaboration_policy",
            "assignment_policy",
            "handoff_policy",
            "aggregation_policy",
            "collaboration_manifest_ref",
            "coordination_governance_ref"
        ],
        "required_fields": [
            "collaboration_id",
            "status",
            "subagent_request_ref",
            "assignment_refs",
            "worker_thread_refs",
            "handoff_refs",
            "partial_result_refs",
            "aggregation_refs",
            "timeout_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_collaboration_subagent",
        "summary_keys": [
            "aggregation_ref_count",
            "collaboration_count"
        ]
    },
    "conversation_state_transition_audit": {
        "actions": [
            "provide_codex_conversation_state_transition_audit_inventory",
            "refresh_conversation_state_transition_audit_readiness",
            "resolve_conversation_state_transition_audit_blockers",
            "share_conversation_state_transition_audit_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "transitions"
        ],
        "build_function": "build_codex_conversation_state_transition_audit_readiness_packet",
        "codes": [
            "codex_conversation_state_transition_audit_live_operation_blocked",
            "codex_conversation_state_transition_audit_packet_missing_evidence",
            "codex_conversation_state_transition_audit_readiness_packet",
            "codex_conversation_state_transition_audit_status_failed"
        ],
        "collection_key": "transitions",
        "item_id_field": "transition_id",
        "module": "codex_conversation_state_transition_audit_readiness_packet",
        "packet_missing_refs": [
            "state_transition_policy_ref",
            "resume_policy_ref",
            "compaction_policy_ref",
            "audit_policy_ref",
            "conversation_state_manifest_ref",
            "state_transition_governance_ref"
        ],
        "packet_policy_keys": [
            "state_transition_policy",
            "resume_policy",
            "compaction_policy",
            "audit_policy",
            "conversation_state_manifest_ref",
            "state_transition_governance_ref"
        ],
        "required_fields": [
            "transition_id",
            "status",
            "thread_ref",
            "previous_state_refs",
            "current_state_refs",
            "transition_reason_refs",
            "resume_refs",
            "compaction_refs",
            "interruption_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_conversation_state_transition_audit",
        "summary_keys": [
            "resume_ref_count",
            "transition_count"
        ]
    },
    "cross_thread_handoff_digest": {
        "actions": [
            "attach_current_handoff_receipts",
            "provide_codex_cross_thread_handoff_digest_inventory",
            "refresh_cross_thread_handoff_digest",
            "refresh_cross_thread_handoff_digest_readiness",
            "resolve_cross_thread_handoff_digest_blockers",
            "share_cross_thread_handoff_digest_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "handoffs"
        ],
        "build_function": "build_codex_cross_thread_handoff_digest_readiness_packet",
        "codes": [
            "codex_cross_thread_handoff_digest_live_operation_blocked",
            "codex_cross_thread_handoff_digest_packet_missing_evidence",
            "codex_cross_thread_handoff_digest_readiness_packet",
            "codex_cross_thread_handoff_digest_stale",
            "codex_cross_thread_handoff_digest_status_failed"
        ],
        "collection_key": "handoffs",
        "item_id_field": "handoff_id",
        "module": "codex_cross_thread_handoff_digest_readiness_packet",
        "packet_missing_refs": [
            "handoff_digest_policy_ref",
            "source_of_truth_policy_ref",
            "read_receipt_policy_ref",
            "stale_handoff_policy_ref",
            "cross_thread_handoff_manifest_ref",
            "multi_thread_continuity_governance_ref"
        ],
        "packet_policy_keys": [
            "handoff_digest_policy",
            "source_of_truth_policy",
            "read_receipt_policy",
            "stale_handoff_policy",
            "cross_thread_handoff_manifest_ref",
            "multi_thread_continuity_governance_ref"
        ],
        "required_fields": [
            "handoff_id",
            "status",
            "source_thread_ref",
            "target_thread_refs",
            "handoff_digest_refs",
            "source_of_truth_refs",
            "candidate_refs",
            "validation_receipt_refs",
            "read_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_cross_thread_handoff_digest",
        "summary_keys": [
            "handoff_count",
            "read_receipt_ref_count"
        ]
    },
    "enterprise_usage_log": {
        "actions": [
            "provide_codex_enterprise_usage_log_inventory",
            "refresh_enterprise_usage_log_readiness",
            "resolve_enterprise_usage_log_blockers",
            "share_enterprise_usage_log_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "usage_logs"
        ],
        "build_function": "build_codex_enterprise_usage_log_readiness_packet",
        "codes": [
            "codex_enterprise_usage_log_live_admin_mutation_blocked",
            "codex_enterprise_usage_log_packet_missing_evidence",
            "codex_enterprise_usage_log_readiness_packet",
            "codex_enterprise_usage_log_status_failed"
        ],
        "collection_key": "usage_logs",
        "item_id_field": "usage_id",
        "module": "codex_enterprise_usage_log_readiness_packet",
        "packet_missing_refs": [
            "usage_log_policy_ref",
            "admin_access_policy_ref",
            "privacy_policy_ref",
            "retention_policy_ref",
            "usage_manifest_ref",
            "audit_export_policy_ref"
        ],
        "packet_policy_keys": [
            "usage_log_policy",
            "admin_access_policy",
            "privacy_policy",
            "retention_policy",
            "usage_manifest_ref",
            "audit_export_policy"
        ],
        "required_fields": [
            "usage_id",
            "status",
            "tenant_ref",
            "user_ref",
            "account_ref",
            "source",
            "task_refs",
            "run_refs",
            "usage_log_export_refs",
            "audit_log_refs",
            "privacy_redaction_refs",
            "retention_policy_refs",
            "admin_access_policy_refs",
            "billing_quota_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_enterprise_usage_log",
        "summary_keys": [
            "billing_quota_ref_count",
            "usage_log_count"
        ]
    },
    "environment_repro": {
        "actions": [
            "provide_codex_environment_repro_inventory",
            "refresh_environment_repro_readiness",
            "resolve_environment_repro_blockers",
            "share_environment_repro_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "reproducibility"
        ],
        "build_function": "build_codex_environment_repro_readiness_packet",
        "codes": [
            "codex_environment_repro_live_mutation_blocked",
            "codex_environment_repro_packet_missing_evidence",
            "codex_environment_repro_readiness_packet",
            "codex_environment_repro_status_failed"
        ],
        "collection_key": "reproducibility",
        "item_id_field": "repro_id",
        "module": "codex_environment_repro_readiness_packet",
        "packet_missing_refs": [
            "environment_policy_ref",
            "sandbox_policy_ref",
            "redaction_policy_ref",
            "reproducibility_policy_ref",
            "environment_manifest_ref",
            "validation_matrix_ref"
        ],
        "packet_policy_keys": [
            "environment_policy",
            "sandbox_policy",
            "redaction_policy",
            "reproducibility_policy",
            "environment_manifest_ref",
            "validation_matrix_ref"
        ],
        "required_fields": [
            "repro_id",
            "status",
            "workspace_ref",
            "runtime_profile",
            "source",
            "workspace_snapshot_refs",
            "dependency_lock_refs",
            "runtime_version_refs",
            "command_transcript_refs",
            "sandbox_profile_refs",
            "env_var_redaction_refs",
            "test_command_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_environment_repro",
        "summary_keys": [
            "dependency_lock_ref_count",
            "repro_count"
        ]
    },
    "eval_repair": {
        "actions": [
            "provide_codex_eval_repair_inventory",
            "refresh_eval_repair_readiness",
            "resolve_eval_repair_blockers",
            "share_eval_repair_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "repairs"
        ],
        "build_function": "build_codex_eval_repair_readiness_packet",
        "codes": [
            "codex_eval_repair_missing_evidence",
            "codex_eval_repair_packet_missing_evidence",
            "codex_eval_repair_readiness_packet",
            "codex_eval_repair_state_blocked"
        ],
        "collection_key": "repairs",
        "item_id_field": "repair_id",
        "module": "codex_eval_repair_readiness_packet",
        "packet_missing_refs": [
            "eval_policy_ref",
            "repair_policy_ref",
            "validation_policy_ref",
            "rollback_policy_ref",
            "eval_manifest_ref"
        ],
        "packet_policy_keys": [
            "eval_policy",
            "repair_policy",
            "validation_policy",
            "rollback_policy",
            "eval_manifest_ref"
        ],
        "required_fields": [
            "repair_id",
            "state",
            "confidence",
            "failure_classification_refs",
            "repro_command_refs",
            "repair_plan_refs",
            "patch_attempt_refs",
            "validation_rerun_refs",
            "regression_evidence_refs",
            "confidence_scoring_refs",
            "closure_receipts",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_eval_repair",
        "summary_keys": [
            "high_confidence_count",
            "repair_count"
        ]
    },
    "external_source_freshness": {
        "actions": [
            "provide_codex_external_source_freshness_inventory",
            "refresh_external_source_freshness_readiness",
            "resolve_external_source_freshness_blockers",
            "share_external_source_freshness_readiness_with_mainline"
        ],
        "aliases": [
            "external_sources",
            "findings"
        ],
        "build_function": "build_codex_external_source_freshness_readiness_packet",
        "codes": [
            "codex_external_source_freshness_live_operation_blocked",
            "codex_external_source_freshness_packet_missing_evidence",
            "codex_external_source_freshness_readiness_packet",
            "codex_external_source_freshness_status_failed"
        ],
        "collection_key": "external_sources",
        "item_id_field": "source_id",
        "module": "codex_external_source_freshness_readiness_packet",
        "packet_missing_refs": [
            "external_source_policy_ref",
            "freshness_policy_ref",
            "attribution_policy_ref",
            "stale_context_policy_ref",
            "external_source_manifest_ref",
            "current_information_governance_ref"
        ],
        "packet_policy_keys": [
            "external_source_policy",
            "freshness_policy",
            "attribution_policy",
            "stale_context_policy",
            "external_source_manifest_ref",
            "current_information_governance_ref"
        ],
        "required_fields": [
            "source_id",
            "status",
            "source_ref",
            "official_source_refs",
            "retrieval_timestamp_refs",
            "freshness_refs",
            "source_attribution_refs",
            "stale_context_warning_refs",
            "citation_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_external_source_freshness",
        "summary_keys": [
            "official_source_ref_count",
            "source_count"
        ]
    },
    "file_edit_session": {
        "actions": [
            "provide_codex_file_edit_session_inventory",
            "refresh_file_edit_session_readiness",
            "resolve_file_edit_session_blockers",
            "share_file_edit_session_readiness_with_mainline"
        ],
        "aliases": [
            "edit_sessions",
            "findings"
        ],
        "build_function": "build_codex_file_edit_session_readiness_packet",
        "codes": [
            "codex_file_edit_session_live_mutation_blocked",
            "codex_file_edit_session_packet_missing_evidence",
            "codex_file_edit_session_readiness_packet",
            "codex_file_edit_session_status_failed"
        ],
        "collection_key": "edit_sessions",
        "item_id_field": "edit_session_id",
        "module": "codex_file_edit_session_readiness_packet",
        "packet_missing_refs": [
            "edit_policy_ref",
            "preservation_policy_ref",
            "formatting_policy_ref",
            "validation_policy_ref",
            "edit_session_manifest_ref",
            "edit_governance_ref"
        ],
        "packet_policy_keys": [
            "edit_policy",
            "preservation_policy",
            "formatting_policy",
            "validation_policy",
            "edit_session_manifest_ref",
            "edit_governance_ref"
        ],
        "required_fields": [
            "edit_session_id",
            "status",
            "edit_intent_ref",
            "target_file_refs",
            "read_before_write_refs",
            "user_change_preservation_refs",
            "patch_refs",
            "formatting_refs",
            "conflict_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_file_edit_session",
        "summary_keys": [
            "edit_session_count",
            "read_before_write_ref_count"
        ]
    },
    "gap_matrix_traceability": {
        "actions": [
            "decide_next_gap_candidate",
            "provide_codex_gap_matrix_traceability_inventory",
            "review_codex_gap_matrix_residual_gaps",
            "share_codex_gap_matrix_traceability_readiness_with_mainline"
        ],
        "aliases": [
            "capabilities",
            "findings"
        ],
        "build_function": "build_codex_gap_matrix_traceability_readiness_packet",
        "codes": [
            "codex_gap_matrix_manifest_ref",
            "codex_gap_matrix_traceability_live_operation_blocked",
            "codex_gap_matrix_traceability_packet_missing_evidence",
            "codex_gap_matrix_traceability_readiness_packet",
            "codex_gap_matrix_traceability_residual_gap",
            "codex_gap_matrix_traceability_status_failed",
            "codex_parity_governance_ref"
        ],
        "collection_key": "capabilities",
        "item_id_field": "capability_id",
        "module": "codex_gap_matrix_traceability_readiness_packet",
        "packet_missing_refs": [
            "gap_matrix_policy_ref",
            "traceability_policy_ref",
            "adoption_status_policy_ref",
            "residual_gap_policy_ref",
            "codex_gap_matrix_manifest_ref",
            "codex_parity_governance_ref"
        ],
        "packet_policy_keys": [
            "gap_matrix_policy",
            "traceability_policy",
            "adoption_status_policy",
            "residual_gap_policy",
            "codex_gap_matrix_manifest_ref",
            "codex_parity_governance_ref"
        ],
        "required_fields": [
            "capability_id",
            "status",
            "capability_ref",
            "competitor_source_refs",
            "candidate_refs",
            "implemented_module_refs",
            "validation_receipt_refs",
            "handoff_refs",
            "adoption_status_refs",
            "owner_refs",
            "residual_gap_refs"
        ],
        "summarize_function": "summarize_codex_gap_matrix_traceability",
        "summary_keys": [
            "capability_count",
            "implemented_module_ref_count"
        ]
    },
    "human_approval_escalation": {
        "actions": [
            "provide_codex_human_approval_inventory",
            "refresh_human_approval_readiness",
            "resolve_human_approval_blockers",
            "share_human_approval_readiness_with_mainline"
        ],
        "aliases": [
            "approvals",
            "findings"
        ],
        "build_function": "build_codex_human_approval_escalation_readiness_packet",
        "codes": [
            "codex_human_approval_escalation_readiness_packet",
            "codex_human_approval_live_dispatch_blocked",
            "codex_human_approval_packet_missing_evidence",
            "codex_human_approval_status_failed"
        ],
        "collection_key": "approvals",
        "item_id_field": "approval_id",
        "module": "codex_human_approval_escalation_readiness_packet",
        "packet_missing_refs": [
            "approval_policy_ref",
            "escalation_policy_ref",
            "timeout_policy_ref",
            "decision_policy_ref",
            "approval_manifest_ref",
            "approval_governance_ref"
        ],
        "packet_policy_keys": [
            "approval_policy",
            "escalation_policy",
            "timeout_policy",
            "decision_policy",
            "approval_manifest_ref",
            "approval_governance_ref"
        ],
        "required_fields": [
            "approval_id",
            "status",
            "risk_level",
            "approval_request_ref",
            "approver_refs",
            "risk_refs",
            "timeout_refs",
            "escalation_refs",
            "decision_receipt_refs",
            "denial_refs",
            "notification_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_human_approval_escalation",
        "summary_keys": [
            "approval_count",
            "decision_receipt_ref_count"
        ]
    },
    "interruption_recovery": {
        "actions": [
            "provide_codex_interruption_recovery_inventory",
            "share_interruption_recovery_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "recoveries"
        ],
        "build_function": "build_codex_interruption_recovery_readiness_packet",
        "codes": [
            "codex_interruption_recovery_live_operation_blocked",
            "codex_interruption_recovery_packet_missing_evidence",
            "codex_interruption_recovery_readiness_packet",
            "codex_interruption_recovery_status_failed"
        ],
        "collection_key": "recoveries",
        "item_id_field": "recovery_id",
        "module": "codex_interruption_recovery_readiness_packet",
        "packet_missing_refs": [
            "interruption_policy_ref",
            "recovery_policy_ref",
            "resume_policy_ref",
            "partial_progress_policy_ref",
            "interruption_recovery_manifest_ref",
            "failure_recovery_governance_ref"
        ],
        "packet_policy_keys": [
            "interruption_policy",
            "recovery_policy",
            "resume_policy",
            "partial_progress_policy",
            "interruption_recovery_manifest_ref",
            "failure_recovery_governance_ref"
        ],
        "required_fields": [
            "recovery_id",
            "status",
            "task_ref",
            "interruption_refs",
            "resumability_refs",
            "failure_recovery_refs",
            "partial_progress_refs",
            "recovery_validation_refs",
            "resume_token_refs",
            "recovery_plan_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_interruption_recovery",
        "summary_keys": [
            "interruption_ref_count",
            "recovery_count"
        ]
    },
    "local_runtime_dependency": {
        "actions": [
            "provide_codex_local_runtime_dependency_inventory",
            "share_local_runtime_dependency_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "runtimes"
        ],
        "build_function": "build_codex_local_runtime_dependency_readiness_packet",
        "codes": [
            "codex_local_runtime_dependency_live_operation_blocked",
            "codex_local_runtime_dependency_packet_missing_evidence",
            "codex_local_runtime_dependency_readiness_packet",
            "codex_local_runtime_dependency_status_failed",
            "codex_local_runtime_dependency_version_mismatch"
        ],
        "collection_key": "runtimes",
        "item_id_field": "runtime_id",
        "module": "codex_local_runtime_dependency_readiness_packet",
        "packet_missing_refs": [
            "runtime_policy_ref",
            "dependency_policy_ref",
            "lockfile_policy_ref",
            "environment_template_policy_ref",
            "runtime_dependency_manifest_ref",
            "reproducibility_governance_ref"
        ],
        "packet_policy_keys": [
            "runtime_policy",
            "dependency_policy",
            "lockfile_policy",
            "environment_template_policy",
            "runtime_dependency_manifest_ref",
            "reproducibility_governance_ref"
        ],
        "required_fields": [
            "runtime_id",
            "status",
            "runtime_ref",
            "python_runtime_refs",
            "node_runtime_refs",
            "package_manager_refs",
            "lockfile_refs",
            "environment_template_refs",
            "install_verification_refs",
            "version_mismatch_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_local_runtime_dependency",
        "summary_keys": [
            "package_manager_ref_count",
            "runtime_count"
        ]
    },
    "long_running_task_supervision": {
        "actions": [
            "provide_codex_long_running_task_supervision_inventory",
            "share_long_running_task_supervision_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "tasks"
        ],
        "build_function": "build_codex_long_running_task_supervision_readiness_packet",
        "codes": [
            "codex_long_running_task_supervision_live_operation_blocked",
            "codex_long_running_task_supervision_packet_missing_evidence",
            "codex_long_running_task_supervision_readiness_packet",
            "codex_long_running_task_supervision_status_failed"
        ],
        "collection_key": "tasks",
        "item_id_field": "task_id",
        "module": "codex_long_running_task_supervision_readiness_packet",
        "packet_missing_refs": [
            "heartbeat_policy_ref",
            "progress_policy_ref",
            "timeout_policy_ref",
            "escalation_policy_ref",
            "task_supervision_manifest_ref",
            "durable_task_governance_ref"
        ],
        "packet_policy_keys": [
            "heartbeat_policy",
            "progress_policy",
            "timeout_policy",
            "escalation_policy",
            "task_supervision_manifest_ref",
            "durable_task_governance_ref"
        ],
        "required_fields": [
            "task_id",
            "status",
            "task_ref",
            "heartbeat_refs",
            "progress_refs",
            "supervision_refs",
            "timeout_refs",
            "escalation_refs",
            "checkpoint_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_long_running_task_supervision",
        "summary_keys": [
            "heartbeat_ref_count",
            "task_count"
        ]
    },
    "mcp_tool_contract": {
        "actions": [
            "provide_codex_mcp_tool_contract_inventory",
            "refresh_mcp_tool_contract_readiness",
            "resolve_mcp_tool_contract_blockers",
            "share_mcp_tool_contract_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "tools"
        ],
        "build_function": "build_codex_mcp_tool_contract_readiness_packet",
        "codes": [
            "codex_mcp_tool_contract_live_mutation_blocked",
            "codex_mcp_tool_contract_packet_missing_evidence",
            "codex_mcp_tool_contract_readiness_packet",
            "codex_mcp_tool_contract_status_failed"
        ],
        "collection_key": "tools",
        "item_id_field": "tool_id",
        "module": "codex_mcp_tool_contract_readiness_packet",
        "packet_missing_refs": [
            "tool_contract_policy_ref",
            "mcp_server_policy_ref",
            "permission_policy_ref",
            "schema_policy_ref",
            "tool_manifest_ref",
            "tool_contract_matrix_ref"
        ],
        "packet_policy_keys": [
            "tool_contract_policy",
            "mcp_server_policy",
            "permission_policy",
            "schema_policy",
            "tool_manifest_ref",
            "tool_contract_matrix_ref"
        ],
        "required_fields": [
            "tool_id",
            "status",
            "tool_ref",
            "mcp_server_ref",
            "tool_schema_refs",
            "tool_permission_refs",
            "argument_schema_refs",
            "result_schema_refs",
            "failure_taxonomy_refs",
            "discovery_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_mcp_tool_contract",
        "summary_keys": [
            "argument_schema_ref_count",
            "tool_count"
        ]
    },
    "memory_context": {
        "actions": [
            "attach_packet_level_context_policies",
            "provide_codex_memory_context_inventory",
            "refresh_memory_context_readiness",
            "restore_required_context_sources",
            "review_memory_context_scope",
            "share_memory_context_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "sources"
        ],
        "build_function": "build_codex_memory_context_readiness_packet",
        "codes": [
            "codex_memory_context_packet_missing_evidence",
            "codex_memory_context_readiness_packet",
            "codex_memory_context_source_disabled"
        ],
        "collection_key": "",
        "item_id_field": "name",
        "module": "codex_memory_context_readiness_packet",
        "packet_missing_refs": [
            "context_budget_policy",
            "stale_context_policy",
            "redaction_policy"
        ],
        "packet_policy_keys": [],
        "required_fields": [
            "name",
            "source_type",
            "status",
            "scope",
            "token_budget",
            "instruction_refs",
            "redaction_refs",
            "validation_refs",
            "boundaries"
        ],
        "summarize_function": "summarize_codex_memory_context_source",
        "summary_keys": [
            "source_count",
            "total_token_budget"
        ]
    },
    "model_router": {
        "actions": [
            "provide_codex_model_router_inventory",
            "refresh_model_router_readiness",
            "resolve_model_router_blockers",
            "share_model_router_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "routes"
        ],
        "build_function": "build_codex_model_router_readiness_packet",
        "codes": [
            "codex_model_router_live_call_blocked",
            "codex_model_router_packet_missing_evidence",
            "codex_model_router_readiness_packet",
            "codex_model_router_status_failed"
        ],
        "collection_key": "routes",
        "item_id_field": "route_id",
        "module": "codex_model_router_readiness_packet",
        "packet_missing_refs": [
            "routing_policy_ref",
            "fallback_policy_ref",
            "cost_policy_ref",
            "safety_policy_ref",
            "model_manifest_ref",
            "provider_matrix_ref"
        ],
        "packet_policy_keys": [
            "routing_policy",
            "fallback_policy",
            "cost_policy",
            "safety_policy",
            "model_manifest_ref",
            "provider_matrix_ref"
        ],
        "required_fields": [
            "route_id",
            "status",
            "model_ref",
            "provider_ref",
            "reasoning_profile",
            "model_capability_refs",
            "provider_health_refs",
            "reasoning_profile_refs",
            "fallback_policy_refs",
            "context_window_refs",
            "tool_call_compatibility_refs",
            "rate_limit_quota_refs",
            "cost_policy_refs",
            "safety_policy_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_model_router",
        "summary_keys": [
            "route_count",
            "tool_call_compatibility_ref_count"
        ]
    },
    "multi_agent_delegation_receipt": {
        "actions": [
            "attach_multi_agent_delegation_receipts",
            "provide_codex_multi_agent_delegation_receipt_inventory",
            "refresh_multi_agent_delegation_receipt_readiness",
            "resolve_multi_agent_delegation_receipt_blockers",
            "share_multi_agent_delegation_receipt_readiness_with_mainline"
        ],
        "aliases": [
            "delegations",
            "findings"
        ],
        "build_function": "build_codex_multi_agent_delegation_receipt_readiness_packet",
        "codes": [
            "codex_multi_agent_delegation_receipt_live_operation_blocked",
            "codex_multi_agent_delegation_receipt_packet_missing_evidence",
            "codex_multi_agent_delegation_receipt_readiness_packet",
            "codex_multi_agent_delegation_receipt_status_failed",
            "codex_multi_agent_delegation_receipt_still_open"
        ],
        "collection_key": "delegations",
        "item_id_field": "delegation_id",
        "module": "codex_multi_agent_delegation_receipt_readiness_packet",
        "packet_missing_refs": [
            "delegation_policy_ref",
            "scope_policy_ref",
            "handoff_policy_ref",
            "completion_policy_ref",
            "delegation_manifest_ref",
            "multi_agent_governance_ref"
        ],
        "packet_policy_keys": [
            "delegation_policy",
            "scope_policy",
            "handoff_policy",
            "completion_policy",
            "delegation_manifest_ref",
            "multi_agent_governance_ref"
        ],
        "required_fields": [
            "delegation_id",
            "status",
            "delegation_ref",
            "source_thread_ref",
            "target_thread_refs",
            "scope_refs",
            "handoff_refs",
            "completion_receipt_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_multi_agent_delegation_receipt",
        "summary_keys": [
            "completion_receipt_ref_count",
            "delegation_count"
        ]
    },
    "multimodal_browser_desktop": {
        "actions": [
            "provide_codex_multimodal_browser_desktop_inventory",
            "refresh_multimodal_browser_desktop_readiness",
            "resolve_multimodal_browser_desktop_blockers",
            "share_multimodal_browser_desktop_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "interactions"
        ],
        "build_function": "build_codex_multimodal_browser_desktop_readiness_packet",
        "codes": [
            "codex_multimodal_browser_desktop_live_execution_blocked",
            "codex_multimodal_browser_desktop_packet_missing_evidence",
            "codex_multimodal_browser_desktop_readiness_packet",
            "codex_multimodal_browser_desktop_status_failed"
        ],
        "collection_key": "interactions",
        "item_id_field": "interaction_id",
        "module": "codex_multimodal_browser_desktop_readiness_packet",
        "packet_missing_refs": [
            "browser_policy_ref",
            "desktop_policy_ref",
            "visual_observation_policy_ref",
            "gesture_policy_ref",
            "interaction_manifest_ref",
            "multimodal_governance_ref"
        ],
        "packet_policy_keys": [
            "browser_policy",
            "desktop_policy",
            "visual_observation_policy",
            "gesture_policy",
            "interaction_manifest_ref",
            "multimodal_governance_ref"
        ],
        "required_fields": [
            "interaction_id",
            "status",
            "interaction_ref",
            "focus",
            "browser_session_refs",
            "screenshot_refs",
            "dom_snapshot_refs",
            "ui_snapshot_refs",
            "visual_observation_refs",
            "user_gesture_refs",
            "desktop_target_refs",
            "permission_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_multimodal_browser_desktop",
        "summary_keys": [
            "interaction_count",
            "screenshot_ref_count"
        ]
    },
    "observability_trace": {
        "actions": [
            "provide_codex_observability_trace_inventory",
            "refresh_observability_trace_readiness",
            "resolve_observability_trace_blockers",
            "share_observability_trace_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "traces"
        ],
        "build_function": "build_codex_observability_trace_readiness_packet",
        "codes": [
            "codex_observability_live_export_blocked",
            "codex_observability_trace_packet_missing_evidence",
            "codex_observability_trace_readiness_packet",
            "codex_observability_trace_status_failed"
        ],
        "collection_key": "traces",
        "item_id_field": "trace_id",
        "module": "codex_observability_trace_readiness_packet",
        "packet_missing_refs": [
            "trace_schema_policy_ref",
            "redaction_policy_ref",
            "retention_policy_ref",
            "export_policy_ref",
            "trace_manifest_ref",
            "audit_access_policy_ref"
        ],
        "packet_policy_keys": [
            "trace_schema_policy",
            "redaction_policy",
            "retention_policy",
            "export_policy",
            "trace_manifest_ref",
            "audit_access_policy"
        ],
        "required_fields": [
            "trace_id",
            "run_ref",
            "status",
            "source",
            "provider",
            "run_trace_refs",
            "tool_call_trace_refs",
            "model_decision_refs",
            "permission_prompt_refs",
            "sandbox_event_refs",
            "validation_receipt_refs",
            "redaction_refs",
            "error_taxonomy_refs",
            "retention_policy_refs",
            "export_policy_refs",
            "audit_log_refs",
            "replay_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_observability_trace",
        "summary_keys": [
            "tool_call_trace_ref_count",
            "trace_count"
        ]
    },
    "open_source_candidate_evaluation": {
        "actions": [
            "decide_adoption_guardrail",
            "provide_codex_open_source_candidate_evaluation_inventory",
            "review_open_source_candidate_maintenance_risk",
            "share_open_source_candidate_evaluation_readiness_with_mainline"
        ],
        "aliases": [
            "candidates",
            "findings"
        ],
        "build_function": "build_codex_open_source_candidate_evaluation_readiness_packet",
        "codes": [
            "codex_open_source_candidate_evaluation_license_blocked",
            "codex_open_source_candidate_evaluation_live_operation_blocked",
            "codex_open_source_candidate_evaluation_maintenance_risk",
            "codex_open_source_candidate_evaluation_packet_missing_evidence",
            "codex_open_source_candidate_evaluation_readiness_packet"
        ],
        "collection_key": "candidates",
        "item_id_field": "candidate_id",
        "module": "codex_open_source_candidate_evaluation_readiness_packet",
        "packet_missing_refs": [
            "open_source_policy_ref",
            "license_policy_ref",
            "security_policy_ref",
            "adoption_policy_ref",
            "open_source_evaluation_manifest_ref",
            "capability_gap_governance_ref"
        ],
        "packet_policy_keys": [
            "open_source_policy",
            "license_policy",
            "security_policy",
            "adoption_policy",
            "open_source_evaluation_manifest_ref",
            "capability_gap_governance_ref"
        ],
        "required_fields": [
            "candidate_id",
            "status",
            "repository_ref",
            "license_refs",
            "maintenance_refs",
            "security_refs",
            "capability_gap_refs",
            "competitor_comparison_refs",
            "adoption_decision_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_open_source_candidate_evaluation",
        "summary_keys": [
            "candidate_count",
            "capability_gap_ref_count"
        ]
    },
    "output_contract": {
        "actions": [
            "provide_codex_output_contract_inventory",
            "share_output_contract_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "outputs"
        ],
        "build_function": "build_codex_output_contract_readiness_packet",
        "codes": [
            "codex_output_contract_live_operation_blocked",
            "codex_output_contract_packet_missing_evidence",
            "codex_output_contract_readiness_packet",
            "codex_output_contract_status_failed"
        ],
        "collection_key": "outputs",
        "item_id_field": "output_id",
        "module": "codex_output_contract_readiness_packet",
        "packet_missing_refs": [
            "final_answer_policy_ref",
            "command_output_policy_ref",
            "file_reference_policy_ref",
            "verification_policy_ref",
            "output_contract_manifest_ref",
            "response_governance_ref"
        ],
        "packet_policy_keys": [
            "final_answer_policy",
            "command_output_policy",
            "file_reference_policy",
            "verification_policy",
            "output_contract_manifest_ref",
            "response_governance_ref"
        ],
        "required_fields": [
            "output_id",
            "status",
            "final_answer_ref",
            "command_output_summary_refs",
            "file_reference_refs",
            "failure_disclosure_refs",
            "verification_evidence_refs",
            "next_step_refs",
            "handoff_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_output_contract",
        "summary_keys": [
            "command_output_summary_ref_count",
            "output_count"
        ]
    },
    "owner_visibility_status": {
        "actions": [
            "provide_codex_owner_visibility_status_inventory",
            "share_owner_visibility_status_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "visibility_items"
        ],
        "build_function": "build_codex_owner_visibility_status_readiness_packet",
        "codes": [
            "codex_owner_visibility_status_failed",
            "codex_owner_visibility_status_live_operation_blocked",
            "codex_owner_visibility_status_packet_missing_evidence",
            "codex_owner_visibility_status_readiness_packet"
        ],
        "collection_key": "visibility_items",
        "item_id_field": "visibility_id",
        "module": "codex_owner_visibility_status_readiness_packet",
        "packet_missing_refs": [
            "candidate_status_policy_ref",
            "handoff_digest_policy_ref",
            "owner_decision_policy_ref",
            "stage_classification_policy_ref",
            "owner_visibility_manifest_ref",
            "multi_thread_visibility_governance_ref"
        ],
        "packet_policy_keys": [
            "candidate_status_policy",
            "handoff_digest_policy",
            "owner_decision_policy",
            "stage_classification_policy",
            "owner_visibility_manifest_ref",
            "multi_thread_visibility_governance_ref"
        ],
        "required_fields": [
            "visibility_id",
            "status",
            "candidate_ref",
            "candidate_status_refs",
            "handoff_digest_refs",
            "notification_refs",
            "owner_decision_refs",
            "stage_classification_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs",
            "mainline_thread_refs"
        ],
        "summarize_function": "summarize_codex_owner_visibility_status",
        "summary_keys": [
            "candidate_status_ref_count",
            "visibility_count"
        ]
    },
    "patch_apply": {
        "actions": [
            "provide_codex_patch_apply_inventory",
            "refresh_patch_apply_readiness",
            "resolve_patch_apply_blockers",
            "share_patch_apply_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "patches"
        ],
        "build_function": "build_codex_patch_apply_readiness_packet",
        "codes": [
            "codex_patch_apply_live_mutation_blocked",
            "codex_patch_apply_packet_missing_evidence",
            "codex_patch_apply_readiness_packet",
            "codex_patch_apply_status_failed"
        ],
        "collection_key": "patches",
        "item_id_field": "patch_id",
        "module": "codex_patch_apply_readiness_packet",
        "packet_missing_refs": [
            "patch_policy_ref",
            "apply_policy_ref",
            "conflict_policy_ref",
            "rollback_policy_ref",
            "patch_manifest_ref",
            "apply_governance_ref"
        ],
        "packet_policy_keys": [
            "patch_policy",
            "apply_policy",
            "conflict_policy",
            "rollback_policy",
            "patch_manifest_ref",
            "apply_governance_ref"
        ],
        "required_fields": [
            "patch_id",
            "status",
            "patch_ref",
            "target_file_refs",
            "preimage_refs",
            "postimage_refs",
            "conflict_refs",
            "dry_run_refs",
            "backup_refs",
            "rollback_refs",
            "apply_transcript_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_patch_apply",
        "summary_keys": [
            "dry_run_ref_count",
            "patch_count"
        ]
    },
    "permission_escalation_audit": {
        "actions": [
            "provide_codex_permission_escalation_audit_inventory",
            "refresh_permission_escalation_audit_readiness",
            "resolve_permission_escalation_audit_blockers",
            "share_permission_escalation_audit_readiness_with_mainline"
        ],
        "aliases": [
            "audits",
            "findings"
        ],
        "build_function": "build_codex_permission_escalation_audit_readiness_packet",
        "codes": [
            "codex_permission_escalation_audit_live_operation_blocked",
            "codex_permission_escalation_audit_packet_missing_evidence",
            "codex_permission_escalation_audit_readiness_packet",
            "codex_permission_escalation_audit_status_failed"
        ],
        "collection_key": "audits",
        "item_id_field": "audit_id",
        "module": "codex_permission_escalation_audit_readiness_packet",
        "packet_missing_refs": [
            "approval_policy_ref",
            "sandbox_policy_ref",
            "command_prefix_policy_ref",
            "escalation_policy_ref",
            "permission_escalation_manifest_ref",
            "controlled_escalation_governance_ref"
        ],
        "packet_policy_keys": [
            "approval_policy",
            "sandbox_policy",
            "command_prefix_policy",
            "escalation_policy",
            "permission_escalation_manifest_ref",
            "controlled_escalation_governance_ref"
        ],
        "required_fields": [
            "audit_id",
            "status",
            "risk_level",
            "approval_request_refs",
            "sandbox_profile_refs",
            "command_prefix_refs",
            "escalation_justification_refs",
            "approval_decision_refs",
            "denial_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_permission_escalation_audit",
        "summary_keys": [
            "audit_count",
            "command_prefix_ref_count"
        ]
    },
    "permission_sandbox": {
        "actions": [
            "attach_permission_sandbox_evidence",
            "provide_codex_permission_sandbox_policy",
            "refresh_permission_sandbox_readiness",
            "remove_dangerous_runtime_bypass",
            "share_permission_sandbox_readiness_with_mainline",
            "tighten_approval_and_sandbox_policy"
        ],
        "aliases": [
            "findings",
            "policies"
        ],
        "build_function": "build_codex_permission_sandbox_readiness_packet",
        "codes": [
            "codex_permission_sandbox_autonomous_approval",
            "codex_permission_sandbox_hook_trust_bypass",
            "codex_permission_sandbox_missing_evidence",
            "codex_permission_sandbox_readiness_packet"
        ],
        "collection_key": "",
        "item_id_field": "name",
        "module": "codex_permission_sandbox_readiness_packet",
        "packet_missing_refs": [],
        "packet_policy_keys": [],
        "required_fields": [
            "name",
            "approval_policy",
            "sandbox_policy",
            "filesystem_scope",
            "network_scope",
            "destructive_command_policy",
            "shell_policy",
            "patch_policy",
            "hook_policy",
            "operator_prompt_policy",
            "allowed_write_roots",
            "blocked_commands",
            "trusted_hook_refs",
            "audit_refs",
            "validation_refs"
        ],
        "summarize_function": "summarize_codex_permission_sandbox_policy",
        "summary_keys": [
            "ready_count"
        ]
    },
    "planning_goal": {
        "actions": [
            "provide_codex_planning_goal_inventory",
            "refresh_planning_goal_readiness",
            "resolve_planning_goal_blockers",
            "share_planning_goal_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "goals"
        ],
        "build_function": "build_codex_planning_goal_readiness_packet",
        "codes": [
            "codex_planning_goal_live_mutation_blocked",
            "codex_planning_goal_packet_missing_evidence",
            "codex_planning_goal_readiness_packet",
            "codex_planning_goal_status_failed"
        ],
        "collection_key": "goals",
        "item_id_field": "goal_id",
        "module": "codex_planning_goal_readiness_packet",
        "packet_missing_refs": [
            "planning_policy_ref",
            "goal_policy_ref",
            "approval_policy_ref",
            "completion_policy_ref",
            "planning_manifest_ref",
            "goal_matrix_ref"
        ],
        "packet_policy_keys": [
            "planning_policy",
            "goal_policy",
            "approval_policy",
            "completion_policy",
            "planning_manifest_ref",
            "goal_matrix_ref"
        ],
        "required_fields": [
            "goal_id",
            "status",
            "owner_ref",
            "plan_refs",
            "goal_refs",
            "task_decomposition_refs",
            "progress_checkpoint_refs",
            "user_approval_refs",
            "interruption_resume_refs",
            "completion_criteria_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_planning_goal",
        "summary_keys": [
            "approval_ref_count",
            "goal_count"
        ]
    },
    "pr_delivery": {
        "actions": [
            "provide_codex_pr_delivery_inventory",
            "refresh_pr_delivery_readiness",
            "resolve_pr_delivery_blockers",
            "review_policy",
            "review_policy_ref",
            "review_status",
            "share_pr_delivery_readiness_with_mainline"
        ],
        "aliases": [
            "deliveries",
            "findings"
        ],
        "build_function": "build_codex_pr_delivery_readiness_packet",
        "codes": [
            "codex_pr_delivery_ci_failed",
            "codex_pr_delivery_non_dry_run_blocked",
            "codex_pr_delivery_packet_missing_evidence",
            "codex_pr_delivery_readiness_packet"
        ],
        "collection_key": "deliveries",
        "item_id_field": "delivery_id",
        "module": "codex_pr_delivery_readiness_packet",
        "packet_missing_refs": [
            "delivery_policy_ref",
            "review_policy_ref",
            "ci_policy_ref",
            "redaction_policy_ref",
            "reviewer_policy_ref",
            "delivery_manifest_ref"
        ],
        "packet_policy_keys": [
            "delivery_policy",
            "review_policy",
            "ci_policy",
            "redaction_policy",
            "reviewer_policy_ref",
            "delivery_manifest_ref"
        ],
        "required_fields": [
            "delivery_id",
            "provider",
            "review_status",
            "dry_run",
            "diff_refs",
            "branch_refs",
            "commit_refs",
            "pr_refs",
            "ci_check_refs",
            "ci_states",
            "file_change_refs",
            "reviewer_handoff_refs",
            "artifact_refs",
            "validation_refs",
            "redaction_refs"
        ],
        "summarize_function": "summarize_codex_pr_delivery",
        "summary_keys": [
            "delivery_count",
            "pr_ref_count"
        ]
    },
    "repo_worktree_drift_reconciliation": {
        "actions": [
            "attach_repo_worktree_drift_receipts",
            "provide_codex_repo_worktree_drift_reconciliation_inventory",
            "share_repo_worktree_drift_reconciliation_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "reconciliations"
        ],
        "build_function": "build_codex_repo_worktree_drift_reconciliation_readiness_packet",
        "codes": [
            "codex_repo_worktree_drift_live_operation_blocked",
            "codex_repo_worktree_drift_packet_missing_evidence",
            "codex_repo_worktree_drift_reconciliation_readiness_packet",
            "codex_repo_worktree_drift_status_failed",
            "codex_repo_worktree_drift_still_open"
        ],
        "collection_key": "reconciliations",
        "item_id_field": "reconciliation_id",
        "module": "codex_repo_worktree_drift_reconciliation_readiness_packet",
        "packet_missing_refs": [
            "worktree_policy_ref",
            "branch_policy_ref",
            "drift_policy_ref",
            "reconciliation_policy_ref",
            "worktree_drift_manifest_ref",
            "repo_worktree_governance_ref"
        ],
        "packet_policy_keys": [
            "worktree_policy",
            "branch_policy",
            "drift_policy",
            "reconciliation_policy",
            "worktree_drift_manifest_ref",
            "repo_worktree_governance_ref"
        ],
        "required_fields": [
            "reconciliation_id",
            "status",
            "worktree_ref",
            "branch_refs",
            "base_refs",
            "head_refs",
            "dirty_worktree_refs",
            "conflict_refs",
            "preservation_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_repo_worktree_drift_reconciliation",
        "summary_keys": [
            "branch_ref_count",
            "reconciliation_count"
        ]
    },
    "result_quality_acceptance": {
        "actions": [
            "provide_codex_result_quality_acceptance_inventory",
            "share_result_quality_acceptance_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "results"
        ],
        "build_function": "build_codex_result_quality_acceptance_readiness_packet",
        "codes": [
            "codex_result_quality_acceptance_live_operation_blocked",
            "codex_result_quality_acceptance_packet_missing_evidence",
            "codex_result_quality_acceptance_readiness_packet",
            "codex_result_quality_acceptance_status_failed"
        ],
        "collection_key": "results",
        "item_id_field": "result_id",
        "module": "codex_result_quality_acceptance_readiness_packet",
        "packet_missing_refs": [
            "result_quality_policy_ref",
            "acceptance_policy_ref",
            "evidence_policy_ref",
            "regression_policy_ref",
            "result_quality_manifest_ref",
            "acceptance_governance_ref"
        ],
        "packet_policy_keys": [
            "result_quality_policy",
            "acceptance_policy",
            "evidence_policy",
            "regression_policy",
            "result_quality_manifest_ref",
            "acceptance_governance_ref"
        ],
        "required_fields": [
            "result_id",
            "status",
            "expected_result_ref",
            "acceptance_criteria_refs",
            "result_quality_refs",
            "mismatch_refs",
            "regression_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "evidence_refs"
        ],
        "summarize_function": "summarize_codex_result_quality_acceptance",
        "summary_keys": [
            "acceptance_criteria_ref_count",
            "result_count"
        ]
    },
    "review_comment": {
        "actions": [
            "provide_codex_review_comment_inventory",
            "refresh_review_comment_readiness",
            "resolve_review_comment_blockers",
            "review_count",
            "review_feedback_open",
            "review_id",
            "review_policy",
            "review_policy_ref",
            "review_thread_ref",
            "share_review_comment_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "reviews"
        ],
        "build_function": "build_codex_review_comment_readiness_packet",
        "codes": [
            "codex_review_comment_missing_evidence",
            "codex_review_comment_packet_missing_evidence",
            "codex_review_comment_readiness_packet",
            "codex_review_comment_response_blocked"
        ],
        "collection_key": "reviews",
        "item_id_field": "review_id",
        "module": "codex_review_comment_readiness_packet",
        "packet_missing_refs": [
            "review_policy_ref",
            "comment_fetch_policy_ref",
            "response_policy_ref",
            "closure_policy_ref",
            "provider_auth_ref",
            "feedback_manifest_ref"
        ],
        "packet_policy_keys": [
            "review_policy",
            "comment_fetch_policy",
            "response_policy",
            "closure_policy",
            "provider_auth_ref",
            "feedback_manifest_ref"
        ],
        "required_fields": [
            "review_id",
            "provider",
            "response_status",
            "pr_ref",
            "review_thread_ref",
            "comment_refs",
            "changed_file_refs",
            "closure_receipts",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_review_comment",
        "summary_keys": [
            "closure_receipt_count",
            "review_count"
        ]
    },
    "safety_policy_boundary": {
        "actions": [
            "provide_codex_safety_policy_boundary_inventory",
            "share_safety_policy_boundary_readiness_with_mainline"
        ],
        "aliases": [
            "boundaries",
            "findings"
        ],
        "build_function": "build_codex_safety_policy_boundary_readiness_packet",
        "codes": [
            "codex_safety_policy_boundary_live_operation_blocked",
            "codex_safety_policy_boundary_packet_missing_evidence",
            "codex_safety_policy_boundary_readiness_packet",
            "codex_safety_policy_boundary_status_failed"
        ],
        "collection_key": "boundaries",
        "item_id_field": "boundary_id",
        "module": "codex_safety_policy_boundary_readiness_packet",
        "packet_missing_refs": [
            "safety_policy_ref",
            "refusal_policy_ref",
            "risky_operation_policy_ref",
            "escalation_policy_ref",
            "safety_boundary_manifest_ref",
            "policy_governance_ref"
        ],
        "packet_policy_keys": [
            "safety_policy",
            "refusal_policy",
            "risky_operation_policy",
            "escalation_policy",
            "safety_boundary_manifest_ref",
            "policy_governance_ref"
        ],
        "required_fields": [
            "boundary_id",
            "status",
            "subject_ref",
            "refusal_refs",
            "risky_operation_refs",
            "policy_decision_refs",
            "escalation_refs",
            "user_approval_refs",
            "sandbox_policy_refs",
            "audit_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_safety_policy_boundary",
        "summary_keys": [
            "boundary_count",
            "policy_decision_ref_count"
        ]
    },
    "search_context": {
        "actions": [
            "provide_codex_search_context_inventory",
            "refresh_search_context_readiness",
            "resolve_search_context_blockers",
            "share_search_context_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "search_contexts"
        ],
        "build_function": "build_codex_search_context_readiness_packet",
        "codes": [
            "codex_search_context_live_execution_blocked",
            "codex_search_context_packet_missing_evidence",
            "codex_search_context_readiness_packet",
            "codex_search_context_status_failed"
        ],
        "collection_key": "search_contexts",
        "item_id_field": "search_context_id",
        "module": "codex_search_context_readiness_packet",
        "packet_missing_refs": [
            "search_policy_ref",
            "source_policy_ref",
            "freshness_policy_ref",
            "scope_policy_ref",
            "search_manifest_ref",
            "context_governance_ref"
        ],
        "packet_policy_keys": [
            "search_policy",
            "source_policy",
            "freshness_policy",
            "scope_policy",
            "search_manifest_ref",
            "context_governance_ref"
        ],
        "required_fields": [
            "search_context_id",
            "status",
            "search_query_ref",
            "result_set_refs",
            "source_attribution_refs",
            "freshness_refs",
            "scope_refs",
            "relevance_refs",
            "ranking_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_search_context",
        "summary_keys": [
            "search_context_count",
            "source_attribution_ref_count"
        ]
    },
    "secondary_integration_adoption_decision_archive_followup_closure": {
        "actions": [
            "attach_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_evidence",
            "provide_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_inventory",
            "refresh_archive_followup_closure_readiness_packet",
            "refresh_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
            "review_archive_followup_owner_signoffs",
            "share_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_with_mainline"
        ],
        "aliases": [
            "closures",
            "findings"
        ],
        "build_function": "build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
        "codes": [
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_live_operation_blocked",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_missing_evidence",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_owner_signoff_review_required",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet_missing_evidence",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_status_failed",
            "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_still_open"
        ],
        "collection_key": "closures",
        "item_id_field": "closure_id",
        "module": "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
        "packet_missing_refs": [
            "followup_closure_readiness_policy_ref",
            "closure_criteria_policy_ref",
            "owner_signoff_policy_ref",
            "blocker_resolution_policy_ref",
            "secondary_integration_adoption_decision_archive_followup_closure_readiness_manifest_ref",
            "secondary_integration_adoption_decision_archive_followup_closure_governance_ref"
        ],
        "packet_policy_keys": [
            "followup_closure_readiness_policy",
            "closure_criteria_policy",
            "owner_signoff_policy",
            "blocker_resolution_policy",
            "secondary_integration_adoption_decision_archive_followup_closure_readiness_manifest_ref",
            "secondary_integration_adoption_decision_archive_followup_closure_governance_ref"
        ],
        "required_fields": [
            "closure_id",
            "status",
            "archive_followup_closure_readiness_ref",
            "disposition_preview_refs",
            "notification_readiness_refs",
            "owner_handoff_refs",
            "followup_status_rollup_refs",
            "unresolved_blocker_refs",
            "validation_refs",
            "evidence_refs",
            "owner_signoff_refs",
            "closure_criteria_refs",
            "next_action_refs"
        ],
        "summarize_function": "summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness",
        "summary_keys": [
            "closure_count",
            "owner_signoff_ref_count"
        ]
    },
    "secondary_integration_adoption_decision_archive_followup_notification": {
        "actions": [
            "provide_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_inventory",
            "refresh_archive_followup_notification_readiness_packet",
            "review_archive_followup_notification_recipients",
            "review_archive_followup_notification_suppressions",
            "share_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "notifications"
        ],
        "build_function": "build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet",
        "codes": [
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_live_operation_blocked",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet_missing_evidence",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_recipient_review_required",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_status_failed",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_still_open",
            "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_suppression_review_required"
        ],
        "collection_key": "notifications",
        "item_id_field": "notification_id",
        "module": "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet",
        "packet_missing_refs": [
            "followup_notification_readiness_policy_ref",
            "recipient_policy_ref",
            "channel_policy_ref",
            "suppression_policy_ref",
            "secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref",
            "secondary_integration_adoption_decision_archive_followup_notification_governance_ref"
        ],
        "packet_policy_keys": [
            "followup_notification_readiness_policy",
            "recipient_policy",
            "channel_policy",
            "suppression_policy",
            "secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref",
            "secondary_integration_adoption_decision_archive_followup_notification_governance_ref"
        ],
        "required_fields": [
            "notification_id",
            "status",
            "archive_followup_notification_readiness_ref",
            "owner_handoff_refs",
            "followup_status_rollup_refs",
            "recipient_refs",
            "channel_policy_refs",
            "message_preview_refs",
            "validation_refs",
            "evidence_refs",
            "suppression_refs",
            "next_action_refs"
        ],
        "summarize_function": "summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness",
        "summary_keys": [
            "message_preview_ref_count",
            "notification_count"
        ]
    },
    "secrets_redaction": {
        "actions": [
            "provide_codex_secrets_redaction_inventory",
            "refresh_secrets_redaction_readiness",
            "resolve_secrets_redaction_blockers",
            "share_secrets_redaction_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "secret_reviews"
        ],
        "build_function": "build_codex_secrets_redaction_readiness_packet",
        "codes": [
            "codex_secrets_redaction_packet_missing_evidence",
            "codex_secrets_redaction_raw_secret_blocked",
            "codex_secrets_redaction_readiness_packet",
            "codex_secrets_redaction_status_failed"
        ],
        "collection_key": "secret_reviews",
        "item_id_field": "secret_review_id",
        "module": "codex_secrets_redaction_readiness_packet",
        "packet_missing_refs": [
            "secret_scan_policy_ref",
            "redaction_policy_ref",
            "transcript_policy_ref",
            "exposure_policy_ref",
            "secrets_manifest_ref",
            "sensitive_data_governance_ref"
        ],
        "packet_policy_keys": [
            "secret_scan_policy",
            "redaction_policy",
            "transcript_policy",
            "exposure_policy",
            "secrets_manifest_ref",
            "sensitive_data_governance_ref"
        ],
        "required_fields": [
            "secret_review_id",
            "status",
            "secret_review_ref",
            "secret_scan_refs",
            "redaction_policy_refs",
            "transcript_refs",
            "artifact_refs",
            "exposure_refs",
            "validation_receipt_refs",
            "denylist_refs",
            "allowlist_refs",
            "owner_escalation_refs"
        ],
        "summarize_function": "summarize_codex_secrets_redaction",
        "summary_keys": [
            "redaction_policy_ref_count",
            "secret_review_count"
        ]
    },
    "session_budget_guard": {
        "actions": [
            "provide_codex_session_budget_guard_inventory",
            "share_session_budget_guard_readiness_with_mainline"
        ],
        "aliases": [
            "budgets",
            "findings"
        ],
        "build_function": "build_codex_session_budget_guard_readiness_packet",
        "codes": [
            "codex_session_budget_guard_exhausted",
            "codex_session_budget_guard_live_operation_blocked",
            "codex_session_budget_guard_packet_missing_evidence",
            "codex_session_budget_guard_readiness_packet",
            "codex_session_budget_guard_status_failed"
        ],
        "collection_key": "budgets",
        "item_id_field": "budget_id",
        "module": "codex_session_budget_guard_readiness_packet",
        "packet_missing_refs": [
            "token_budget_policy_ref",
            "elapsed_time_policy_ref",
            "retry_budget_policy_ref",
            "tool_call_budget_policy_ref",
            "session_budget_manifest_ref",
            "bounded_execution_governance_ref"
        ],
        "packet_policy_keys": [
            "token_budget_policy",
            "elapsed_time_policy",
            "retry_budget_policy",
            "tool_call_budget_policy",
            "session_budget_manifest_ref",
            "bounded_execution_governance_ref"
        ],
        "required_fields": [
            "budget_id",
            "status",
            "session_ref",
            "token_budget_refs",
            "elapsed_time_refs",
            "retry_budget_refs",
            "tool_call_budget_refs",
            "context_compaction_threshold_refs",
            "interruption_refs",
            "cancellation_policy_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_session_budget_guard",
        "summary_keys": [
            "budget_count",
            "tool_call_budget_ref_count"
        ]
    },
    "session_thread": {
        "actions": [
            "provide_codex_session_thread_inventory",
            "refresh_session_thread_readiness",
            "resolve_session_thread_blockers",
            "share_session_thread_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "sessions"
        ],
        "build_function": "build_codex_session_thread_readiness_packet",
        "codes": [
            "codex_session_thread_live_mutation_blocked",
            "codex_session_thread_packet_missing_evidence",
            "codex_session_thread_readiness_packet",
            "codex_session_thread_status_failed"
        ],
        "collection_key": "sessions",
        "item_id_field": "session_id",
        "module": "codex_session_thread_readiness_packet",
        "packet_missing_refs": [
            "session_policy_ref",
            "resume_policy_ref",
            "handoff_policy_ref",
            "compaction_policy_ref",
            "session_manifest_ref",
            "continuity_matrix_ref"
        ],
        "packet_policy_keys": [
            "session_policy",
            "resume_policy",
            "handoff_policy",
            "compaction_policy",
            "session_manifest_ref",
            "continuity_matrix_ref"
        ],
        "required_fields": [
            "session_id",
            "status",
            "thread_ref",
            "task_ref",
            "conversation_state_refs",
            "resume_token_refs",
            "task_continuation_refs",
            "handoff_refs",
            "branch_worktree_refs",
            "interruption_refs",
            "compaction_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_session_thread",
        "summary_keys": [
            "resume_token_ref_count",
            "session_count"
        ]
    },
    "task_intake_clarification": {
        "actions": [
            "provide_codex_task_intake_clarification_inventory",
            "share_task_intake_clarification_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "intakes"
        ],
        "build_function": "build_codex_task_intake_clarification_readiness_packet",
        "codes": [
            "codex_task_intake_clarification_live_operation_blocked",
            "codex_task_intake_clarification_packet_missing_evidence",
            "codex_task_intake_clarification_readiness_packet",
            "codex_task_intake_clarification_status_failed"
        ],
        "collection_key": "intakes",
        "item_id_field": "intake_id",
        "module": "codex_task_intake_clarification_readiness_packet",
        "packet_missing_refs": [
            "intake_policy_ref",
            "clarification_policy_ref",
            "scope_policy_ref",
            "acceptance_policy_ref",
            "task_intake_manifest_ref",
            "request_understanding_governance_ref"
        ],
        "packet_policy_keys": [
            "intake_policy",
            "clarification_policy",
            "scope_policy",
            "acceptance_policy",
            "task_intake_manifest_ref",
            "request_understanding_governance_ref"
        ],
        "required_fields": [
            "intake_id",
            "status",
            "user_request_ref",
            "ambiguity_refs",
            "assumption_refs",
            "clarification_refs",
            "scope_refs",
            "acceptance_criteria_refs",
            "constraint_refs",
            "risk_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_task_intake_clarification",
        "summary_keys": [
            "clarification_ref_count",
            "intake_count"
        ]
    },
    "task_progress_event_timeline": {
        "actions": [
            "attach_task_timeline_receipts",
            "provide_codex_task_progress_event_timeline_inventory",
            "refresh_task_progress_event_timeline_readiness",
            "resolve_task_progress_event_timeline_blockers",
            "share_task_progress_event_timeline_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "timelines"
        ],
        "build_function": "build_codex_task_progress_event_timeline_readiness_packet",
        "codes": [
            "codex_task_progress_event_timeline_live_operation_blocked",
            "codex_task_progress_event_timeline_packet_missing_evidence",
            "codex_task_progress_event_timeline_readiness_packet",
            "codex_task_progress_event_timeline_status_failed",
            "codex_task_progress_event_timeline_still_open"
        ],
        "collection_key": "timelines",
        "item_id_field": "timeline_id",
        "module": "codex_task_progress_event_timeline_readiness_packet",
        "packet_missing_refs": [
            "timeline_policy_ref",
            "progress_event_policy_ref",
            "phase_transition_policy_ref",
            "budget_policy_ref",
            "task_timeline_manifest_ref",
            "task_timeline_governance_ref"
        ],
        "packet_policy_keys": [
            "timeline_policy",
            "progress_event_policy",
            "phase_transition_policy",
            "budget_policy",
            "task_timeline_manifest_ref",
            "task_timeline_governance_ref"
        ],
        "required_fields": [
            "timeline_id",
            "status",
            "task_ref",
            "progress_event_refs",
            "phase_transition_refs",
            "tool_event_refs",
            "validation_event_refs",
            "elapsed_time_refs",
            "budget_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_task_progress_event_timeline",
        "summary_keys": [
            "progress_event_ref_count",
            "timeline_count"
        ]
    },
    "terminal_command": {
        "actions": [
            "provide_codex_terminal_command_inventory",
            "refresh_terminal_command_readiness",
            "resolve_terminal_command_blockers",
            "share_terminal_command_readiness_with_mainline"
        ],
        "aliases": [
            "commands",
            "findings"
        ],
        "build_function": "build_codex_terminal_command_readiness_packet",
        "codes": [
            "codex_terminal_command_live_execution_blocked",
            "codex_terminal_command_packet_missing_evidence",
            "codex_terminal_command_readiness_packet",
            "codex_terminal_command_status_failed"
        ],
        "collection_key": "commands",
        "item_id_field": "command_id",
        "module": "codex_terminal_command_readiness_packet",
        "packet_missing_refs": [
            "command_policy_ref",
            "permission_policy_ref",
            "sandbox_policy_ref",
            "redaction_policy_ref",
            "command_manifest_ref",
            "execution_governance_ref"
        ],
        "packet_policy_keys": [
            "command_policy",
            "permission_policy",
            "sandbox_policy",
            "redaction_policy",
            "command_manifest_ref",
            "execution_governance_ref"
        ],
        "required_fields": [
            "command_id",
            "status",
            "command_ref",
            "working_directory_ref",
            "permission_refs",
            "sandbox_refs",
            "timeout_refs",
            "stdout_transcript_refs",
            "stderr_transcript_refs",
            "exit_code_refs",
            "redaction_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_terminal_command",
        "summary_keys": [
            "command_count",
            "exit_code_ref_count"
        ]
    },
    "thread_resume_compaction": {
        "actions": [
            "provide_codex_thread_resume_compaction_inventory",
            "refresh_thread_resume_compaction_readiness",
            "resolve_thread_resume_compaction_blockers",
            "share_thread_resume_compaction_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "resumes"
        ],
        "build_function": "build_codex_thread_resume_compaction_readiness_packet",
        "codes": [
            "codex_thread_resume_compaction_live_operation_blocked",
            "codex_thread_resume_compaction_packet_missing_evidence",
            "codex_thread_resume_compaction_readiness_packet",
            "codex_thread_resume_compaction_status_failed"
        ],
        "collection_key": "resumes",
        "item_id_field": "resume_id",
        "module": "codex_thread_resume_compaction_readiness_packet",
        "packet_missing_refs": [
            "resume_policy_ref",
            "compaction_policy_ref",
            "handoff_policy_ref",
            "context_budget_policy_ref",
            "thread_continuity_manifest_ref",
            "resume_governance_ref"
        ],
        "packet_policy_keys": [
            "resume_policy",
            "compaction_policy",
            "handoff_policy",
            "context_budget_policy",
            "thread_continuity_manifest_ref",
            "resume_governance_ref"
        ],
        "required_fields": [
            "resume_id",
            "status",
            "thread_ref",
            "compaction_summary_refs",
            "continuation_refs",
            "resume_token_refs",
            "handoff_refs",
            "context_budget_refs",
            "source_thread_refs",
            "resume_receipt_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_thread_resume_compaction",
        "summary_keys": [
            "resume_count",
            "resume_token_ref_count"
        ]
    },
    "tool_result_provenance_receipt": {
        "actions": [
            "attach_tool_result_provenance_receipts",
            "provide_codex_tool_result_provenance_receipt_inventory",
            "share_tool_result_provenance_receipt_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "receipts"
        ],
        "build_function": "build_codex_tool_result_provenance_receipt_readiness_packet",
        "codes": [
            "codex_tool_result_provenance_receipt_live_operation_blocked",
            "codex_tool_result_provenance_receipt_packet_missing_evidence",
            "codex_tool_result_provenance_receipt_readiness_packet",
            "codex_tool_result_provenance_receipt_status_failed",
            "codex_tool_result_provenance_receipt_still_open"
        ],
        "collection_key": "receipts",
        "item_id_field": "receipt_id",
        "module": "codex_tool_result_provenance_receipt_readiness_packet",
        "packet_missing_refs": [
            "tool_result_policy_ref",
            "provenance_policy_ref",
            "receipt_policy_ref",
            "redaction_policy_ref",
            "tool_result_manifest_ref",
            "tool_result_governance_ref"
        ],
        "packet_policy_keys": [
            "tool_result_policy",
            "provenance_policy",
            "receipt_policy",
            "redaction_policy",
            "tool_result_manifest_ref",
            "tool_result_governance_ref"
        ],
        "required_fields": [
            "receipt_id",
            "status",
            "tool_call_ref",
            "result_refs",
            "source_refs",
            "provenance_refs",
            "stdout_receipt_refs",
            "stderr_receipt_refs",
            "exit_status_refs",
            "redaction_refs",
            "validation_receipt_refs",
            "artifact_refs",
            "owner_refs"
        ],
        "summarize_function": "summarize_codex_tool_result_provenance_receipt",
        "summary_keys": [
            "provenance_ref_count",
            "receipt_count"
        ]
    },
    "tool_runtime": {
        "actions": [
            "block_unsafe_runtime_surfaces",
            "provide_codex_tool_runtime_inventory",
            "review_permission_and_sandbox_policy",
            "share_codex_tool_runtime_readiness_with_mainline"
        ],
        "aliases": [
            "components",
            "findings"
        ],
        "build_function": "build_codex_tool_runtime_readiness_packet",
        "codes": [
            "codex_tool_runtime_high_risk_without_manual_approval",
            "codex_tool_runtime_missing_evidence",
            "codex_tool_runtime_readiness_packet"
        ],
        "collection_key": "mcp_tools",
        "item_id_field": "name",
        "module": "codex_tool_runtime_readiness_packet",
        "packet_missing_refs": [],
        "packet_policy_keys": [],
        "required_fields": [
            "name",
            "component_type",
            "status",
            "approval_profile",
            "sandbox_profile",
            "validation_refs"
        ],
        "summarize_function": "summarize_codex_tool_runtime_component",
        "summary_keys": [
            "by_component_type",
            "component_count",
            "missing_ref_count",
            "needs_review_count",
            "ready_count"
        ]
    },
    "workspace_diff": {
        "actions": [
            "provide_codex_workspace_diff_inventory",
            "refresh_workspace_diff_readiness",
            "resolve_workspace_diff_blockers",
            "review_matrix_ref",
            "share_workspace_diff_readiness_with_mainline"
        ],
        "aliases": [
            "diffs",
            "findings"
        ],
        "build_function": "build_codex_workspace_diff_readiness_packet",
        "codes": [
            "codex_workspace_diff_live_mutation_blocked",
            "codex_workspace_diff_packet_missing_evidence",
            "codex_workspace_diff_readiness_packet",
            "codex_workspace_diff_status_failed"
        ],
        "collection_key": "diffs",
        "item_id_field": "diff_id",
        "module": "codex_workspace_diff_readiness_packet",
        "packet_missing_refs": [
            "diff_policy_ref",
            "patch_policy_ref",
            "conflict_policy_ref",
            "artifact_policy_ref",
            "workspace_manifest_ref",
            "review_matrix_ref"
        ],
        "packet_policy_keys": [
            "diff_policy",
            "patch_policy",
            "conflict_policy",
            "artifact_policy",
            "workspace_manifest_ref",
            "review_matrix_ref"
        ],
        "required_fields": [
            "diff_id",
            "status",
            "workspace_ref",
            "changed_file_refs",
            "diff_summary_refs",
            "patch_refs",
            "conflict_refs",
            "staged_state_refs",
            "unstaged_state_refs",
            "generated_artifact_refs",
            "file_risk_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_workspace_diff",
        "summary_keys": [
            "changed_file_ref_count",
            "diff_count"
        ]
    },
    "worktree_git_state": {
        "actions": [
            "provide_codex_worktree_git_state_inventory",
            "refresh_worktree_git_state_readiness",
            "resolve_worktree_git_state_blockers",
            "share_worktree_git_state_readiness_with_mainline"
        ],
        "aliases": [
            "findings",
            "states"
        ],
        "build_function": "build_codex_worktree_git_state_readiness_packet",
        "codes": [
            "codex_worktree_git_state_failed",
            "codex_worktree_git_state_live_operation_blocked",
            "codex_worktree_git_state_packet_missing_evidence",
            "codex_worktree_git_state_readiness_packet"
        ],
        "collection_key": "states",
        "item_id_field": "state_id",
        "module": "codex_worktree_git_state_readiness_packet",
        "packet_missing_refs": [
            "worktree_policy_ref",
            "git_state_policy_ref",
            "staging_policy_ref",
            "commit_policy_ref",
            "worktree_manifest_ref",
            "git_state_governance_ref"
        ],
        "packet_policy_keys": [
            "worktree_policy",
            "git_state_policy",
            "staging_policy",
            "commit_policy",
            "worktree_manifest_ref",
            "git_state_governance_ref"
        ],
        "required_fields": [
            "state_id",
            "status",
            "worktree_ref",
            "branch_refs",
            "base_refs",
            "head_refs",
            "staged_state_refs",
            "unstaged_state_refs",
            "user_change_preservation_refs",
            "validation_receipt_refs",
            "artifact_refs"
        ],
        "summarize_function": "summarize_codex_worktree_git_state",
        "summary_keys": [
            "branch_ref_count",
            "state_count"
        ]
    }
}
