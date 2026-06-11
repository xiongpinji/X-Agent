import type { AuditEvent, AutomationRule, SettingsSection } from '../types'
import type { ApiAuditEvent, ApiAutomationRule, ApiSettingsSection } from './apiContracts'
import { mapRuntimeMetadata, stringValue, toStatusTone } from './runtimeMapping'

export function mapAuditEvent(item: ApiAuditEvent): AuditEvent {
  const riskLevel = toStatusTone(item.risk_level)
  const time = stringValue(item.time, '刚刚')
  return {
    id: stringValue(item.id, 'audit-local'),
    title: stringValue(item.title, '未命名审计事件'),
    actor: stringValue(item.actor, '系统'),
    riskLevel,
    evidenceRefs: Array.isArray(item.evidence_refs) ? [...item.evidence_refs] : [],
    time,
    summary: stringValue(item.summary, '暂无摘要'),
    runtime: mapRuntimeMetadata({ ...item, status: item.status ?? '审计记录', updated_at: item.updated_at ?? time }),
  }
}

export function mapAutomationRule(item: ApiAutomationRule): AutomationRule {
  const status = stringValue(item.status, '未知')
  const lastRun = stringValue(item.last_run, '从未运行')
  return {
    id: stringValue(item.id, 'automation-local'),
    name: stringValue(item.name, '未命名自动化'),
    trigger: stringValue(item.trigger, '未配置'),
    destination: stringValue(item.destination, '未分配'),
    status,
    lastRun,
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status, updated_at: item.updated_at ?? lastRun }),
  }
}

export function mapSettingsSection(item: ApiSettingsSection): SettingsSection {
  const status = stringValue(item.status, '未知')
  return {
    id: stringValue(item.id, 'settings-local'),
    title: stringValue(item.title, '未命名设置'),
    description: stringValue(item.description, '暂无说明'),
    status,
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status }),
  }
}
