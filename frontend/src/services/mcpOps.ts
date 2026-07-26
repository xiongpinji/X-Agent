import axios, { AxiosInstance } from 'axios'

/**
 * MCP operations client — aligned 1:1 with backend/app/api/mcp.py
 * (re-verified on 2026-07-26). All 17 real endpoints are wrapped:
 *
 *  POST   /api/v1/mcp/request                          (legacy)
 *  POST   /api/v1/mcp/tools/execute
 *  GET    /api/v1/mcp/tools
 *  GET    /api/v1/mcp/health
 *  GET    /api/v1/mcp/audit-logs
 *  GET    /api/v1/mcp/permissions/{tool_category}
 *  PUT    /api/v1/mcp/permissions/{tool_category}
 *  GET    /api/v1/mcp/status
 *  GET    /api/v1/mcp/servers
 *  GET    /api/v1/mcp/discovered-tools
 *  POST   /api/v1/mcp/tools/{server_name}/{tool_name}/invoke
 *  POST   /api/v1/mcp/client-manager/connect
 *  POST   /api/v1/mcp/client-manager/{server_id}/disconnect
 *  GET    /api/v1/mcp/client-manager/servers
 *  GET    /api/v1/mcp/client-manager/tools
 *  POST   /api/v1/mcp/client-manager/{server_id}/call-tool
 *  GET    /api/v1/mcp/client-manager/health
 *
 * The backend exposes NO per-tool risk level / approval flag for MCP tools —
 * pages must render those columns as disabled "coming soon" affordances.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface McpLegacyTool {
  name: string
  description?: string
  input_schema?: Record<string, any>
  [key: string]: any
}

export interface McpToolListResponse {
  tools: McpLegacyTool[]
  count: number
}

export interface McpHealthResponse {
  status: string
  timestamp: string
  components: Record<string, string>
}

export interface McpAuditLogResponse {
  tool_category: string
  entries: Array<Record<string, any>>
  count: number
  timestamp: string
}

export interface McpServerInfo {
  name: string
  connected: boolean
  transport: string
  server_info?: Record<string, any>
}

export interface McpServersResponse {
  servers: McpServerInfo[]
  count: number
  mcp_enabled: boolean
  initialized?: boolean
  message?: string
  timestamp: string
}

export interface McpDiscoveredTool {
  name: string
  description?: string
  input_schema?: Record<string, any>
  server: string
  registered_name: string
}

export interface McpDiscoveredToolsResponse {
  tools: McpDiscoveredTool[]
  count: number
  servers: Record<string, McpDiscoveredTool[]>
  message?: string
  timestamp: string
}

export interface McpStatusResponse {
  status: string
  host: string
  port: number
  tools_count: number
  tools: string[]
  timestamp: string
}

export interface ConnectServerRequest {
  name?: string
  url?: string
  transport?: string // 'http' | 'stdio'
  command?: string | null
  args?: string[]
  env?: Record<string, string> | null
  cwd?: string | null
  headers?: Record<string, string> | null
  timeout?: number
  max_retries?: number
  enable_cache?: boolean
}

export interface ConnectServerResponse {
  success: boolean
  server_id: string
  message: string
  timestamp: string
}

export interface CmServerInfo {
  server_id?: string
  name?: string
  connected?: boolean
  transport?: string
  [key: string]: any
}

export interface CmServersResponse {
  servers: CmServerInfo[]
  count: number
  sdk_available: boolean
  timestamp: string
}

export interface CmToolsResponse {
  tools: Array<Record<string, any>>
  count: number
  timestamp: string
}

export interface ToolInvokeResponse {
  success: boolean
  server: string
  tool: string
  result: any
  timestamp: string
}

export interface ToolExecutionResponse {
  tool_name: string
  success: boolean
  result?: Record<string, any> | null
  error?: string | null
  error_code?: string | null
  timestamp: string
}

// ─── Client ──────────────────────────────────────────────────────────────────

class McpOpsClient {
  private client: AxiosInstance

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })
    // Same auth convention as services/api.ts: Bearer token from localStorage.
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  private async unwrap<T>(promise: Promise<{ data: T }>): Promise<T> {
    const resp = await promise
    return resp.data
  }

  // ── Legacy server endpoints ──

  sendMcpRequest(request: Record<string, any>): Promise<Record<string, any>> {
    return this.unwrap(this.client.post('/mcp/request', request))
  }

  executeTool(toolName: string, args?: Record<string, any>): Promise<ToolExecutionResponse> {
    return this.unwrap(
      this.client.post('/mcp/tools/execute', { tool_name: toolName, arguments: args ?? {} })
    )
  }

  listTools(): Promise<McpToolListResponse> {
    return this.unwrap(this.client.get('/mcp/tools'))
  }

  healthCheck(): Promise<McpHealthResponse> {
    return this.unwrap(this.client.get('/mcp/health'))
  }

  getAuditLogs(toolCategory?: string): Promise<McpAuditLogResponse> {
    const params = toolCategory ? { tool_category: toolCategory } : {}
    return this.unwrap(this.client.get('/mcp/audit-logs', { params }))
  }

  getPermissions(toolCategory: string): Promise<Record<string, boolean>> {
    return this.unwrap(
      this.client.get(`/mcp/permissions/${encodeURIComponent(toolCategory)}`)
    )
  }

  updatePermissions(
    toolCategory: string,
    permissions: Record<string, boolean>
  ): Promise<{ success: boolean; tool_category: string; permissions: Record<string, boolean>; timestamp: string }> {
    return this.unwrap(
      this.client.put(`/mcp/permissions/${encodeURIComponent(toolCategory)}`, {
        tool_category: toolCategory,
        permissions,
      })
    )
  }

  getStatus(): Promise<McpStatusResponse> {
    return this.unwrap(this.client.get('/mcp/status'))
  }

  // ── P1-01: MCP Manager (official SDK discovery) ──

  listServers(): Promise<McpServersResponse> {
    return this.unwrap(this.client.get('/mcp/servers'))
  }

  listDiscoveredTools(): Promise<McpDiscoveredToolsResponse> {
    return this.unwrap(this.client.get('/mcp/discovered-tools'))
  }

  invokeTool(
    serverName: string,
    toolName: string,
    args: Record<string, any> = {}
  ): Promise<ToolInvokeResponse> {
    return this.unwrap(
      this.client.post(
        `/mcp/tools/${encodeURIComponent(serverName)}/${encodeURIComponent(toolName)}/invoke`,
        { arguments: args }
      )
    )
  }

  // ── P1-01: MCPClientManager (connection management) ──

  connectServer(config: ConnectServerRequest): Promise<ConnectServerResponse> {
    return this.unwrap(this.client.post('/mcp/client-manager/connect', config))
  }

  disconnectServer(
    serverId: string
  ): Promise<{ success: boolean; server_id: string; message: string; timestamp: string }> {
    return this.unwrap(
      this.client.post(`/mcp/client-manager/${encodeURIComponent(serverId)}/disconnect`)
    )
  }

  cmListServers(): Promise<CmServersResponse> {
    return this.unwrap(this.client.get('/mcp/client-manager/servers'))
  }

  cmListTools(serverId?: string): Promise<CmToolsResponse> {
    const params = serverId ? { server_id: serverId } : {}
    return this.unwrap(this.client.get('/mcp/client-manager/tools', { params }))
  }

  cmCallTool(
    serverId: string,
    toolName: string,
    args: Record<string, any> = {}
  ): Promise<any> {
    return this.unwrap(
      this.client.post(`/mcp/client-manager/${encodeURIComponent(serverId)}/call-tool`, {
        tool_name: toolName,
        arguments: args,
      })
    )
  }

  cmHealthCheck(): Promise<Record<string, any>> {
    return this.unwrap(this.client.get('/mcp/client-manager/health'))
  }
}

export const mcpOps = new McpOpsClient()
export default mcpOps
