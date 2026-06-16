import type { RuntimeMetadata, StatusTone } from '../types'
import { buildRuntimeMetaStripItems } from './runtimeMetaViewModel'
import { MiniTagList } from './tagListPrimitives'

export function RuntimeMetaStrip({
  runtime,
  owner,
  updatedAt,
  risk,
}: {
  runtime?: RuntimeMetadata
  owner?: string
  updatedAt?: string
  risk?: StatusTone
}) {
  const items = buildRuntimeMetaStripItems({ runtime, owner, updatedAt, risk })

  return <MiniTagList items={items} />
}
