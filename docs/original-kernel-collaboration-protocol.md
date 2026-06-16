# Original Kernel Collaboration Protocol

Updated: 2026-06-09

## Thread Roles

- Mainline integration thread owns final review, staging, commits, and any owner-gated wiring.
- Secondary migration thread: `019ea5d4-c646-7340-9f11-e2681230470c`.
- Secondary thread is a capability-source thread only. Its handoff does not interrupt mainline atomic work.

## Shared Inbox

The shared source of truth is:

```text
D:\AI编程库\项目库\进行中的项目\X-Agent\docs\original-kernel-secondary-handoff.md
```

Secondary thread must update this file after each standalone module is completed.
Mainline thread must read this file before refreshing the original-kernel delivery manifest or staging.

## Secondary Thread Rules

1. Add only standalone modules, tests, reports, and handoff documentation.
2. Do not modify API routers, agent loop, control plane, frontend, or `backend/app/core/__init__.py`.
3. Each handoff entry must include:
   - file list
   - capability purpose
   - explicit non-wiring statement
   - validation command and result
   - suggested mainline integration point
   - skipped candidates and reasons, when applicable
4. Thread reminders are allowed, but they mean "new candidate waiting for review" only.
5. Skip and document any candidate that would introduce broken imports, real execution, database/API/worker entrypoints, agent loop coupling, or a large runtime dependency surface.

## Mainline Thread Rules

1. Do not let secondary reminders interrupt current atomic work unless the owner explicitly prioritizes the handoff.
2. Classify new secondary files as `secondary_integration_candidate` first.
3. Do not add secondary candidates to `stage_include_paths` until a separate mainline review gate or integration report accepts them.
4. Keep `.xagent_runtime/reports/*.json` as local evidence unless a release process explicitly asks for an archive artifact.
5. Real mainline wiring requires a separate owner-gated design task and must not be mixed with module migration.

## Candidate States

- `secondary_integration_candidate`: completed by secondary, verified, awaiting mainline review.
- `secondary_handoff`: shared inbox documentation.
- `secondary_pending_candidate`: mentioned but not yet completed or verified.
- `accepted_to_stage`: reviewed by mainline and allowed into explicit staging scope.
- `owner_gated_wiring_design`: approved for adapter or entrypoint design, still not wired by default.
