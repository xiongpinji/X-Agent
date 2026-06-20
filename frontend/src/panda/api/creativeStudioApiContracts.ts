export type ApiCreativeStudioVideoProviderStatus = {
  provider: string
  model: string
  configured: boolean
  api_url_configured: boolean
  api_key_configured: boolean
  api_key_fingerprint: string
  requires_human_review: true
  provider_api_call_attempted: false
  endpoints: {
    shot_video: '/api/v1/creative-studio/shot-video'
    video_workflow: '/api/v1/creative-studio/video-workflow'
  }
}

export type ApiCreativeStudioShotVideoRequest = {
  video_prompt: string
  output_path?: string
  duration_seconds?: number
  aspect_ratio?: string
  human_review_approved: boolean
}

export type ApiCreativeStudioShotVideoResult = {
  success: boolean
  output_path: string
  provider: string
  error: string | null
  metadata: {
    provider_api_call_attempted: boolean
    job_id?: string | null
    response_keys?: string[]
  }
}

export type ApiCreativeStudioVideoWorkflowRequest = {
  storyboard_json: Record<string, unknown>
  execute: boolean
  human_review_approved: boolean
  max_shots?: number
}

export type ApiCreativeStudioVideoWorkflowNode = {
  id: string
  type: 'preflight' | 'approval' | 'shot_video' | 'compose_handoff'
  title: string
  status: string
  requires_human_review: boolean
  provider_api_call_attempted: false
  risk_level?: 'high'
  shot_id?: string
  duration_seconds?: number
  aspect_ratio?: string
}

export type ApiCreativeStudioVideoWorkflowResult = {
  success: boolean
  workflow_id: string
  workflow_name: string
  workflow_status: 'dry_run' | 'needs_approval' | 'ready' | 'completed' | 'failed' | 'invalid'
  dry_run: boolean
  approval_required: boolean
  risk_level: 'high'
  provider_api_call_attempted: boolean
  provider_status: ApiCreativeStudioVideoProviderStatus
  selected_shot_count: number
  nodes: readonly ApiCreativeStudioVideoWorkflowNode[]
  edges: readonly { source: string; target: string }[]
  approval: {
    required: boolean
    subject_type: 'network_request'
    risk_level: 'high'
    reason: 'external_video_provider_call_requires_human_review'
  }
  results: readonly ({ shot_id: string } & ApiCreativeStudioShotVideoResult)[]
  error?: string
}

export const creativeStudioApiEndpoints = {
  videoProviderStatus: '/api/v1/creative-studio/video-provider-status',
  shotVideo: '/api/v1/creative-studio/shot-video',
  videoWorkflow: '/api/v1/creative-studio/video-workflow',
} as const
