# Gateway Mode

Gateway mode packages existing workflow scheduling and channel adapters into an always-available local entrypoint.

Commands:

- `xagent gateway status`
- `xagent gateway start --once --dry-run`
- `xagent gateway start --once --execute`

Default behavior is dry-run. It reports the scheduler and configured channels without requiring Telegram or other channel credentials.

`--execute` triggers due workflow schedules once through the existing `WorkflowScheduler.run_due` boundary and then exits. Production daemon management is intentionally left to process supervisors such as systemd, Windows Task Scheduler, Docker Compose, or Kubernetes.
