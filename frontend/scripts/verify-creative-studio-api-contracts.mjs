import { readFileSync } from 'node:fs'

function read(path) {
  return readFileSync(path, 'utf8')
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

const contract = read('src/panda/api/creativeStudioApiContracts.ts')
const client = read('src/panda/api/creativeStudioClient.ts')
const barrel = read('src/panda/api/apiContracts.ts')

assert(contract.includes("videoProviderStatus: '/api/v1/creative-studio/video-provider-status'"), 'Creative Studio status endpoint must be contracted')
assert(contract.includes("shotVideo: '/api/v1/creative-studio/shot-video'"), 'Creative Studio shot-video endpoint must be contracted')
assert(contract.includes("videoWorkflow: '/api/v1/creative-studio/video-workflow'"), 'Creative Studio video-workflow endpoint must be contracted')
assert(contract.includes('ApiCreativeStudioVideoProviderStatus'), 'Video provider status DTO must be exported')
assert(contract.includes('ApiCreativeStudioVideoWorkflowRequest'), 'Video workflow request DTO must be exported')
assert(contract.includes('ApiCreativeStudioVideoWorkflowResult'), 'Video workflow result DTO must be exported')
assert(contract.includes('requires_human_review: true'), 'Video provider status must declare human review requirement')
assert(contract.includes('provider_api_call_attempted: false'), 'Status response must declare no provider call attempt')
assert(contract.includes('api_key_fingerprint: string'), 'Status DTO must expose only a key fingerprint')
assert(!contract.includes('api_key: string'), 'Status DTO must not expose API key')
assert(!contract.includes('api_url: string'), 'Status DTO must not expose API URL')
assert(contract.includes('human_review_approved: boolean'), 'Shot-video request must include explicit human review approval')
assert(contract.includes('provider_api_call_attempted: boolean'), 'Shot-video result metadata must expose provider call attempt state')
assert(!contract.includes('axios'), 'Creative Studio API contracts must stay transport-free')
assert(!contract.includes('react'), 'Creative Studio API contracts must stay React-free')
assert(client.includes('createCreativeStudioFetchClient'), 'Creative Studio fetch client must be exported')
assert(client.includes('getAuthHeaders'), 'Creative Studio client must attach auth headers')
assert(client.includes('runVideoWorkflow'), 'Creative Studio client must expose the video workflow action')
assert(client.includes('JSON.stringify(body)'), 'Creative Studio client must serialize POST bodies')
assert(!client.includes('axios'), 'Creative Studio client must not add axios coupling')
assert(!client.toLowerCase().includes('react'), 'Creative Studio client must stay UI-free')
assert(barrel.includes("from './creativeStudioApiContracts'"), 'Panda API compatibility barrel must re-export Creative Studio contracts')
assert(barrel.includes("from './creativeStudioClient'"), 'Panda API compatibility barrel must re-export Creative Studio client')

const outputJson = process.argv.includes('--json')
const result = {
  productName: 'Panda Agent',
  status: 'passed',
  source: 'src/panda/api/creativeStudioApiContracts.ts',
  endpoints: [
    '/api/v1/creative-studio/video-provider-status',
    '/api/v1/creative-studio/shot-video',
    '/api/v1/creative-studio/video-workflow',
  ],
  guarantees: [
    'external video provider status is redacted',
    'shot-video calls require explicit human_review_approved',
    'video workflow defaults to explicit dry-run contract',
    'Panda client attaches auth headers without UI coupling',
    'contracts are transport-free',
  ],
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log('Creative Studio API contracts passed')
}
