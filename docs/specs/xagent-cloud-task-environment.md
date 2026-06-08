# X-Agent Cloud Task Environment Contract

## Purpose

This document defines the first X-Agent contract for Codex-style cloud task
environments. It is a product and safety contract, not a claim that X-Agent has
full Codex cloud parity.

The contract lets future hosted runners, worktrees, automations, CLI wrappers,
and enterprise schedulers describe the same execution boundary before any real
container, network, repository, or file mutation adapter is enabled.

## Design Rules

- Checkout identity must be explicit: repository, branch or commit SHA, and
  workspace ID are required before task execution.
- Setup and maintenance run before the agent task loop.
- Setup may use dependency network access; the agent phase has internet access
  off by default.
- Agent internet access must be constrained by allowlisted domains and HTTP
  methods when enabled.
- Production secrets are only available to setup or owner-approved phases.
- The agent loop records commands, file edits, checks, and validation evidence.
- Artifact diffs are exported as review evidence before PR or delivery actions.
- All mutating execution remains owner-gated until a concrete hosted runner
  adapter is implemented.

## Contract Object

```json
{
  "schema_version": "2026-06-08",
  "status": "cloud_task_environment_contract_ready",
  "full_codex_parity_claimed": false,
  "mutation_performed_by_contract": false,
  "checkout_identity": {
    "required": ["provider", "repository", "workspace_id"],
    "one_of_required": ["branch", "commit_sha"],
    "detached_head_supported": true,
    "dirty_local_changes_supported": false,
    "worktree_mode": "metadata_only_until_adapter"
  },
  "environment_phases": [
    {
      "name": "checkout",
      "network": "off",
      "secrets_available": false,
      "owner_approval_required": false,
      "evidence": ["repo_url", "branch_or_commit_sha", "workspace_id"]
    },
    {
      "name": "setup",
      "network": "dependency_allowlist",
      "secrets_available": true,
      "owner_approval_required": false,
      "evidence": ["setup_script_sha256", "install_log_ref"]
    },
    {
      "name": "maintenance",
      "network": "dependency_allowlist",
      "secrets_available": true,
      "owner_approval_required": false,
      "evidence": ["maintenance_script_sha256", "cache_key"]
    },
    {
      "name": "agent",
      "network": "off_by_default",
      "secrets_available": false,
      "owner_approval_required": false,
      "evidence": ["command_log_ref", "tool_events_ref", "validation_ref"]
    },
    {
      "name": "package_evidence",
      "network": "off",
      "secrets_available": false,
      "owner_approval_required": false,
      "evidence": ["artifact_manifest", "diff_summary", "validation_summary"]
    },
    {
      "name": "publish_or_pr",
      "network": "owner_approved_only",
      "secrets_available": "owner_approved_only",
      "owner_approval_required": true,
      "evidence": ["approval_id", "audit_id", "delivery_ref"]
    }
  ],
  "network_policy": {
    "setup_default": "dependency_allowlist",
    "agent_default": "off",
    "allowed_http_methods_default": ["GET", "HEAD", "OPTIONS"],
    "domain_allowlist_presets": ["none", "common_dependencies"],
    "unrestricted_network_requires_owner_approval": true,
    "blocked_without_approval": ["POST", "PUT", "PATCH", "DELETE"]
  },
  "secret_policy": {
    "raw_secret_payloads_allowed": false,
    "setup_phase_secret_refs_allowed": true,
    "agent_phase_secrets_available": false,
    "owner_approved_secret_phases": ["publish_or_pr"],
    "secret_evidence_redacted": true
  },
  "task_loop": {
    "status_vocabulary": [
      "queued",
      "running",
      "waiting_for_approval",
      "waiting_for_user",
      "completed",
      "failed",
      "cancelled",
      "blocked"
    ],
    "events_required": [
      "task.created",
      "environment.checkout",
      "environment.setup",
      "agent.command",
      "agent.validation",
      "artifact.diff",
      "task.completed"
    ],
    "uses_agents_md": true,
    "validation_commands_required": true
  },
  "artifact_diff": {
    "required": true,
    "includes": ["changed_files", "patch_summary", "created_artifacts", "validation_results"],
    "binary_artifacts_manifest_required": true,
    "diff_before_publish_required": true
  },
  "evidence_export": {
    "required": true,
    "format": "json",
    "report_status": "cloud_task_environment_contract_ready",
    "fields": [
      "task_id",
      "trace_id",
      "workspace_id",
      "checkout_identity",
      "phase_results",
      "network_policy",
      "secret_policy",
      "artifact_diff",
      "approval_summary",
      "audit_ids",
      "full_codex_parity_claimed"
    ]
  },
  "adapter_boundary": {
    "hosted_container_adapter": "not_implemented",
    "real_checkout_mutation": false,
    "real_network_mutation": false,
    "real_pr_mutation": false,
    "owner_gate_required_before_execution": true
  }
}
```

## Lifecycle

1. Register a cloud task environment with checkout identity, setup script,
   optional maintenance script, runtime versions, and network policy.
2. Prepare checkout evidence and cache metadata without exposing secrets to the
   agent phase.
3. Run setup and maintenance in pre-agent phases.
4. Run the agent task loop with the default network policy set to off.
5. Capture command, tool, validation, and artifact diff evidence.
6. Require owner approval before publish, PR creation, channel send, or any
   external mutation.

## Acceptance Gate

The minimum source gate for this contract is:

```powershell
python -m pytest tests/test_cloud_task_environment_contract.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

The generated latest Codex alignment report may reference this contract only
when the test above passes and `full_codex_parity_claimed` remains `false`.

## Known Limits

- This contract does not start a hosted container.
- This contract does not create a Git worktree or mutate repository files.
- This contract does not enable unrestricted network access.
- This contract does not expose production secrets to the agent phase.
- This contract does not claim full Codex cloud parity.
