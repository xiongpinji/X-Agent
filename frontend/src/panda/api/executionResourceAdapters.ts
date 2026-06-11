import type { TaskSummary, ThreadItem, WorkflowNode } from '../types'
import type { ApiTaskSummary, ApiThreadItem, ApiWorkflowNode } from './apiContracts'
import { clampProgress, mapRuntimeMetadata, stringValue, toStatusTone } from './runtimeMapping'

export function mapTaskSummary(item: ApiTaskSummary): TaskSummary {
  const status = stringValue(item.status, '未知')
  const ownerAgent = stringValue(item.owner_agent, '未分配')
  return {
    id: stringValue(item.id, 'task-local'),
    title: stringValue(item.title, '未命名任务'),
    ownerAgent,
    project: stringValue(item.project, '默认项目'),
    status,
    priority: stringValue(item.priority, 'P2'),
    progress: clampProgress(item.progress),
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status, owner_agent: ownerAgent }),
  }
}

export function mapThreadItem(item: ApiThreadItem): ThreadItem {
  const status = stringValue(item.status, '未知')
  const ownerAgent = stringValue(item.owner_agent, '未分配')
  return {
    id: stringValue(item.id, 'thread-local'),
    title: stringValue(item.title, '未命名线程'),
    project: stringValue(item.project, '默认项目'),
    status,
    ownerAgent,
    progress: clampProgress(item.progress),
    runtime: mapRuntimeMetadata({ ...item, status, owner_agent: ownerAgent }),
  }
}

export function mapWorkflowNode(item: ApiWorkflowNode): WorkflowNode {
  const status = stringValue(item.status, '未知')
  return {
    id: stringValue(item.id, 'node-local'),
    title: stringValue(item.title, '未命名节点'),
    role: stringValue(item.role, '未分配'),
    status,
    tone: toStatusTone(item.tone ?? item.risk_level),
    x: typeof item.x === 'number' ? item.x : 50,
    y: typeof item.y === 'number' ? item.y : 50,
    runtime: mapRuntimeMetadata({ ...item, status }),
  }
}
