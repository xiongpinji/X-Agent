import type { DataSource, KnowledgeSource, ToolCapability } from '../types'
import type { ApiDataSource, ApiKnowledgeSource, ApiToolCapability } from './apiContracts'
import { mapRuntimeMetadata, stringValue, toStatusTone } from './runtimeMapping'

export function mapKnowledgeSource(item: ApiKnowledgeSource): KnowledgeSource {
  const status = stringValue(item.status, '未知')
  const lastSync = stringValue(item.last_sync, '未知')
  return {
    id: stringValue(item.id, 'knowledge-local'),
    name: stringValue(item.name, '未命名知识源'),
    kind: stringValue(item.kind, 'Knowledge'),
    status,
    documents: stringValue(item.documents, '0'),
    lastSync,
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status, updated_at: item.updated_at ?? lastSync }),
  }
}

export function mapDataSource(item: ApiDataSource): DataSource {
  const status = stringValue(item.status, '未知')
  return {
    id: stringValue(item.id, 'data-local'),
    name: stringValue(item.name, '未命名数据源'),
    source: stringValue(item.source, 'Unknown'),
    status,
    records: stringValue(item.records, '0'),
    syncState: stringValue(item.sync_state, '未知'),
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status }),
  }
}

export function mapToolCapability(item: ApiToolCapability): ToolCapability {
  const status = stringValue(item.status, '未知')
  return {
    id: stringValue(item.id, 'tool-local'),
    name: stringValue(item.name, '未命名工具'),
    provider: stringValue(item.provider, 'Unknown'),
    status,
    permission: stringValue(item.permission, '未配置'),
    invocations: stringValue(item.invocations, '0'),
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status }),
  }
}
