const pandaCoreRuntimeFields = [
  'status',
  'risk_level',
  'progress',
  'owner_agent',
  'updated_at',
  'evidence_refs',
]

function quotedItems(source) {
  return [...source.matchAll(/'([^']+)'/g)].map((item) => item[1])
}

export function extractPandaPageResourceContracts(source) {
  const contracts = new Map()
  const contractPattern = /(\w+):\s*\{([\s\S]*?)\n\s*\}/g
  for (const match of source.matchAll(contractPattern)) {
    const [, objectKey, body] = match
    const page = body.match(/page:\s*'([^']+)'/)?.[1]
    const resourceKeysSource = body.match(/resourceKeys:\s*\[([^\]]*)\]/)?.[1] ?? ''
    const bffEndpoint = body.match(/bffEndpoint:\s*'([^']+)'/)?.[1]
    const readiness = body.match(/readiness:\s*'([^']+)'/)?.[1]
    const runtimeFieldsSource = body.match(/runtimeFields:\s*pandaCoreRuntimeFields/)?.[0]
      ? 'pandaCoreRuntimeFields'
      : (body.match(/runtimeFields:\s*\[([^\]]*)\]/)?.[1] ?? '')
    const apiNeedsSource = body.match(/apiNeeds:\s*\[([^\]]*)\]/)?.[1] ?? ''
    if (!page || !bffEndpoint || !readiness) {
      continue
    }
    contracts.set(page, {
      objectKey,
      page,
      resourceKeys: quotedItems(resourceKeysSource),
      bffEndpoint,
      readiness,
      runtimeFields:
        runtimeFieldsSource === 'pandaCoreRuntimeFields'
          ? pandaCoreRuntimeFields
          : quotedItems(runtimeFieldsSource),
      apiNeeds: quotedItems(apiNeedsSource),
    })
  }
  return contracts
}
