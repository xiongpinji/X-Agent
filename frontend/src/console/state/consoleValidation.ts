import type { ConsoleBootstrapResponse } from "./consoleReducer";

export type ConsoleValidationIssue = {
  path: string;
  message: string;
};

export type ConsoleValidationResult = {
  ok: boolean;
  issues: ConsoleValidationIssue[];
};

export type SelectorValidationResult = ConsoleValidationResult;

const REQUIRED_BOOTSTRAP_FIELDS = [
  "envelope.resource_type",
  "envelope.resource_id",
  "envelope.linked_summaries.primary.data",
  "envelope.linked_summaries.trace.data",
  "envelope.linked_summaries.workflow.data",
  "envelope.linked_summaries.audit.data",
  "envelope.linked_summaries.run.data",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateSection(issues: ConsoleValidationIssue[], path: string, value: unknown) {
  if (value == null) return;
  if (!isRecord(value)) {
    issues.push({ path, message: "section must be an object" });
    return;
  }

  if ("count" in value && typeof value.count !== "number") {
    issues.push({ path: `${path}.count`, message: "count must be a number" });
  }
  if ("items" in value && !Array.isArray(value.items)) {
    issues.push({ path: `${path}.items`, message: "items must be an array" });
  }
  if ("summary" in value && !isRecord(value.summary)) {
    issues.push({ path: `${path}.summary`, message: "summary must be an object" });
  }
  if ("data" in value && !isRecord(value.data)) {
    issues.push({ path: `${path}.data`, message: "data must be an object" });
  }
}

function validateRequiredField(issues: ConsoleValidationIssue[], payload: ConsoleBootstrapResponse, path: string) {
  const parts = path.split(".");
  let current: unknown = payload as unknown;
  for (const part of parts) {
    if (!isRecord(current) || !(part in current)) {
      issues.push({ path, message: "required bootstrap field is missing" });
      return;
    }
    current = current[part];
  }
  if (current == null || (typeof current === "string" && !current.trim())) {
    issues.push({ path, message: "required bootstrap field is empty" });
  }
}

function normalizeSection(section: unknown): Record<string, unknown> | null {
  return isRecord(section) ? section : null;
}

function validateSelectorPayload(issues: ConsoleValidationIssue[], path: string, value: unknown) {
  if (value == null) {
    issues.push({ path, message: "selector payload is missing" });
    return;
  }
  if (!isRecord(value)) {
    issues.push({ path, message: "selector payload must be an object" });
  }
}

export function validateConsoleBootstrapResponse(payload: ConsoleBootstrapResponse | null | undefined): ConsoleValidationResult {
  const issues: ConsoleValidationIssue[] = [];

  if (!payload) {
    return { ok: false, issues: [{ path: "root", message: "bootstrap payload is missing" }] };
  }

  if (payload.envelope && !isRecord(payload.envelope)) {
    issues.push({ path: "envelope", message: "envelope must be an object" });
  }

  const envelope = payload.envelope;
  const primary = envelope?.primary;
  const linked = envelope?.linked_summaries;

  if (envelope) {
    if (typeof envelope.resource_type !== "string" || !envelope.resource_type.trim()) {
      issues.push({ path: "envelope.resource_type", message: "resource_type is required" });
    }
    if (typeof envelope.resource_id !== "string" || !envelope.resource_id.trim()) {
      issues.push({ path: "envelope.resource_id", message: "resource_id is required" });
    }
  }

  if (primary && !isRecord(primary)) {
    issues.push({ path: "envelope.primary", message: "primary must be an object" });
  }

  if (linked && !isRecord(linked)) {
    issues.push({ path: "envelope.linked_summaries", message: "linked_summaries must be an object" });
  }

  if (primary && isRecord(primary)) {
    const primaryLinked = primary.linked_summaries;
    if (primaryLinked && !isRecord(primaryLinked)) {
      issues.push({ path: "envelope.primary.linked_summaries", message: "linked_summaries must be an object" });
    }
    validateSection(issues, "envelope.primary", primary);
  }

  if (linked && isRecord(linked)) {
    for (const key of ["primary", "trace", "run", "workflow", "audit", "approvals", "memory", "tools"] as const) {
      validateSection(issues, `envelope.linked_summaries.${key}`, linked[key]);
    }
  }

  for (const field of REQUIRED_BOOTSTRAP_FIELDS) {
    validateRequiredField(issues, payload, field);
  }

  return { ok: issues.length === 0, issues };
}

export function warnConsoleBootstrapIssues(result: ConsoleValidationResult) {
  if (result.ok) return;

  const groups = {
    missing: [] as ConsoleValidationIssue[],
    structure: [] as ConsoleValidationIssue[],
    empty: [] as ConsoleValidationIssue[],
    other: [] as ConsoleValidationIssue[],
  };

  for (const issue of result.issues) {
    if (issue.message.includes("missing")) {
      groups.missing.push(issue);
    } else if (issue.message.includes("empty")) {
      groups.empty.push(issue);
    } else if (issue.message.includes("object") || issue.message.includes("array") || issue.message.includes("number")) {
      groups.structure.push(issue);
    } else {
      groups.other.push(issue);
    }
  }

  const orderedGroups: Array<[string, ConsoleValidationIssue[]]> = [
    ["missing", groups.missing],
    ["structure", groups.structure],
    ["empty", groups.empty],
    ["other", groups.other],
  ];

  for (const [groupName, issues] of orderedGroups) {
    if (!issues.length) continue;
    console.warn(`[console-bootstrap] ${groupName} issues (${issues.length})`);
    for (const issue of issues) {
      console.warn(`  - ${issue.path}: ${issue.message}`);
    }
  }
}

export function validateConsoleSelectors(overviewData: unknown, workflowData: unknown, traceData: unknown, auditData: unknown, contextData: unknown) {
  const issues: ConsoleValidationIssue[] = [];
  validateSelectorPayload(issues, "selector.overviewData", overviewData);
  validateSelectorPayload(issues, "selector.workflowData", workflowData);
  validateSelectorPayload(issues, "selector.traceData", traceData);
  validateSelectorPayload(issues, "selector.auditData", auditData);
  validateSelectorPayload(issues, "selector.contextData", contextData);
  return { ok: issues.length === 0, issues };
}
