/**
 * X-Agent Partner SDK for JavaScript/TypeScript
 *
 * A comprehensive SDK for integrating with X-Agent Partner API.
 *
 * Installation:
 *   npm install xagent-partner-sdk
 *
 * Usage:
 *   import { PartnerClient } from 'xagent-partner-sdk';
 *
 *   const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });
 *   const partner = await client.getPartner('partner_id');
 */

import crypto from 'crypto';

export const VERSION = '1.0.0';

// ============================================================================
// TYPES
// ============================================================================

export interface PartnerClientConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}

export interface PartnerRegistrationRequest {
  company_name: string;
  contact_email: string;
  contact_name: string;
  company_website?: string;
  description?: string;
  integration_type?: string;
  use_cases?: string[];
  expected_volume?: string;
}

export interface PartnerResponse {
  partner_id: string;
  company_name: string;
  contact_email: string;
  contact_name: string;
  company_website?: string;
  description?: string;
  integration_type: string;
  use_cases: string[];
  status: string;
  created_at: string;
  updated_at: string;
  api_key_prefix?: string;
  webhook_url?: string;
  monthly_requests: number;
  monthly_limit: number;
}

export interface APIKeyRequest {
  name: string;
  expires_in_days?: number;
  rate_limit_rpm?: number;
  rate_limit_rph?: number;
  ip_whitelist?: string[];
  scopes?: string[];
}

export interface APIKeyResponse {
  key_id: string;
  key?: string;
  key_prefix: string;
  name: string;
  partner_id: string;
  created_at: string;
  expires_at?: string;
  rate_limit_rpm: number;
  rate_limit_rph: number;
  ip_whitelist?: string[];
  scopes: string[];
  status: string;
}

export interface WebhookRequest {
  event_type: string;
  url: string;
  active?: boolean;
  retry_policy?: Record<string, any>;
}

export interface WebhookResponse {
  webhook_id: string;
  partner_id: string;
  event_type: string;
  url: string;
  active: boolean;
  created_at: string;
  last_triggered_at?: string;
  retry_policy?: Record<string, any>;
  delivery_count: number;
  failure_count: number;
}

export interface UsageResponse {
  partner_id: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  average_response_time_ms: number;
  api_calls_by_endpoint: Record<string, number>;
  errors_by_type: Record<string, number>;
  bandwidth_used_mb: number;
}

export interface QuotaResponse {
  partner_id: string;
  monthly_limit: number;
  monthly_used: number;
  monthly_remaining: number;
  reset_date: string;
  quota_exceeded: boolean;
}

export interface SupportTicketRequest {
  subject: string;
  description: string;
  priority?: string;
  category?: string;
  attachments?: string[];
}

export interface SupportTicketResponse {
  ticket_id: string;
  partner_id: string;
  subject: string;
  description: string;
  priority: string;
  category: string;
  status: string;
  created_at: string;
  updated_at: string;
  assigned_to?: string;
  resolution_notes?: string;
}

// ============================================================================
// ERRORS
// ============================================================================

export class PartnerAPIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: Record<string, any>,
  ) {
    super(message);
    this.name = 'PartnerAPIError';
  }
}

export class PartnerAuthError extends PartnerAPIError {
  constructor(message: string, response?: Record<string, any>) {
    super(message, 401, response);
    this.name = 'PartnerAuthError';
  }
}

export class PartnerNotFoundError extends PartnerAPIError {
  constructor(message: string, response?: Record<string, any>) {
    super(message, 404, response);
    this.name = 'PartnerNotFoundError';
  }
}

export class PartnerRateLimitError extends PartnerAPIError {
  constructor(message: string, response?: Record<string, any>) {
    super(message, 429, response);
    this.name = 'PartnerRateLimitError';
  }
}

// ============================================================================
// CLIENT
// ============================================================================

export class PartnerClient {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;
  private maxRetries: number;

  constructor(config: PartnerClientConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || 'https://api.x-agent.io').replace(/\/$/, '');
    this.timeout = config.timeout || 30000;
    this.maxRetries = config.maxRetries || 3;
  }

  private getHeaders(): Record<string, string> {
    return {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'User-Agent': `xagent-partner-sdk/${VERSION}`,
    };
  }

  private async makeRequest<T>(
    method: string,
    endpoint: string,
    options?: {
      body?: Record<string, any>;
      params?: Record<string, any>;
    },
  ): Promise<T> {
    let url = `${this.baseUrl}${endpoint}`;

    if (options?.params) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(options.params)) {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      }
      const queryString = searchParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          method,
          headers: this.getHeaders(),
          body: options?.body ? JSON.stringify(options.body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Handle rate limiting
        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get('Retry-After') || '60', 10);
          if (attempt < this.maxRetries - 1) {
            await this.sleep(retryAfter * 1000);
            continue;
          }
          const data = await response.json();
          throw new PartnerRateLimitError('Rate limit exceeded', data);
        }

        // Handle server errors
        if (response.status >= 500) {
          if (attempt < this.maxRetries - 1) {
            const waitTime = Math.pow(2, attempt) * 1000;
            await this.sleep(waitTime);
            continue;
          }
        }

        // Handle client errors
        if (response.status === 401) {
          const data = await response.json();
          throw new PartnerAuthError('Unauthorized', data);
        }

        if (response.status === 404) {
          const data = await response.json();
          throw new PartnerNotFoundError('Resource not found', data);
        }

        if (response.status >= 400) {
          const data = await response.json();
          throw new PartnerAPIError(
            data.error?.message || 'API error',
            response.status,
            data,
          );
        }

        return await response.json();
      } catch (error) {
        if (error instanceof PartnerAPIError) {
          throw error;
        }

        if (attempt === this.maxRetries - 1) {
          throw new PartnerAPIError(`Request failed: ${error}`);
        }

        const waitTime = Math.pow(2, attempt) * 1000;
        await this.sleep(waitTime);
      }
    }

    throw new PartnerAPIError('Max retries exceeded');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // ========================================================================
  // PARTNER MANAGEMENT
  // ========================================================================

  async registerPartner(request: PartnerRegistrationRequest): Promise<PartnerResponse> {
    return this.makeRequest<PartnerResponse>('POST', '/api/v1/partners/register', {
      body: request,
    });
  }

  async getPartner(partnerId: string): Promise<PartnerResponse> {
    return this.makeRequest<PartnerResponse>('GET', `/api/v1/partners/${partnerId}`);
  }

  async listPartners(options?: {
    statusFilter?: string;
    integrationType?: string;
    skip?: number;
    limit?: number;
  }): Promise<PartnerResponse[]> {
    const response = await this.makeRequest<PartnerResponse[] | { partners: PartnerResponse[] }>(
      'GET',
      '/api/v1/partners',
      {
        params: {
          status_filter: options?.statusFilter,
          integration_type: options?.integrationType,
          skip: options?.skip,
          limit: options?.limit,
        },
      },
    );
    return Array.isArray(response) ? response : response.partners || [];
  }

  async updatePartner(partnerId: string, updates: Record<string, any>): Promise<PartnerResponse> {
    return this.makeRequest<PartnerResponse>('PATCH', `/api/v1/partners/${partnerId}`, {
      body: updates,
    });
  }

  async approvePartner(partnerId: string): Promise<PartnerResponse> {
    return this.makeRequest<PartnerResponse>('POST', `/api/v1/partners/${partnerId}/approve`);
  }

  async suspendPartner(partnerId: string, reason: string): Promise<PartnerResponse> {
    return this.makeRequest<PartnerResponse>('POST', `/api/v1/partners/${partnerId}/suspend`, {
      params: { reason },
    });
  }

  // ========================================================================
  // API KEY MANAGEMENT
  // ========================================================================

  async createAPIKey(partnerId: string, request: APIKeyRequest): Promise<APIKeyResponse> {
    return this.makeRequest<APIKeyResponse>('POST', `/api/v1/partners/${partnerId}/api-keys`, {
      body: request,
    });
  }

  async listAPIKeys(
    partnerId: string,
    statusFilter?: string,
  ): Promise<APIKeyResponse[]> {
    const response = await this.makeRequest<APIKeyResponse[] | { keys: APIKeyResponse[] }>(
      'GET',
      `/api/v1/partners/${partnerId}/api-keys`,
      {
        params: { status_filter: statusFilter },
      },
    );
    return Array.isArray(response) ? response : response.keys || [];
  }

  async rotateAPIKey(partnerId: string, keyId: string): Promise<APIKeyResponse> {
    return this.makeRequest<APIKeyResponse>(
      'POST',
      `/api/v1/partners/${partnerId}/api-keys/${keyId}/rotate`,
    );
  }

  async revokeAPIKey(partnerId: string, keyId: string): Promise<void> {
    await this.makeRequest<void>('DELETE', `/api/v1/partners/${partnerId}/api-keys/${keyId}`);
  }

  // ========================================================================
  // WEBHOOK MANAGEMENT
  // ========================================================================

  async registerWebhook(partnerId: string, request: WebhookRequest): Promise<WebhookResponse> {
    return this.makeRequest<WebhookResponse>('POST', `/api/v1/partners/${partnerId}/webhooks`, {
      body: request,
    });
  }

  async listWebhooks(partnerId: string): Promise<WebhookResponse[]> {
    const response = await this.makeRequest<WebhookResponse[] | { webhooks: WebhookResponse[] }>(
      'GET',
      `/api/v1/partners/${partnerId}/webhooks`,
    );
    return Array.isArray(response) ? response : response.webhooks || [];
  }

  async updateWebhook(
    partnerId: string,
    webhookId: string,
    updates: Record<string, any>,
  ): Promise<WebhookResponse> {
    return this.makeRequest<WebhookResponse>(
      'PATCH',
      `/api/v1/partners/${partnerId}/webhooks/${webhookId}`,
      { body: updates },
    );
  }

  async deleteWebhook(partnerId: string, webhookId: string): Promise<void> {
    await this.makeRequest<void>('DELETE', `/api/v1/partners/${partnerId}/webhooks/${webhookId}`);
  }

  async testWebhook(partnerId: string, webhookId: string): Promise<Record<string, any>> {
    return this.makeRequest<Record<string, any>>(
      'POST',
      `/api/v1/partners/${partnerId}/webhooks/${webhookId}/test`,
    );
  }

  // ========================================================================
  // USAGE & ANALYTICS
  // ========================================================================

  async getUsage(
    partnerId: string,
    options?: {
      period?: string;
      startDate?: string;
      endDate?: string;
    },
  ): Promise<UsageResponse> {
    return this.makeRequest<UsageResponse>('GET', `/api/v1/partners/${partnerId}/usage`, {
      params: {
        period: options?.period,
        start_date: options?.startDate,
        end_date: options?.endDate,
      },
    });
  }

  async getDailyUsage(
    partnerId: string,
    days?: number,
  ): Promise<Record<string, any>[]> {
    const response = await this.makeRequest<
      Record<string, any>[] | { daily_usage: Record<string, any>[] }
    >('GET', `/api/v1/partners/${partnerId}/usage/daily`, {
      params: { days },
    });
    return Array.isArray(response) ? response : response.daily_usage || [];
  }

  async getQuota(partnerId: string): Promise<QuotaResponse> {
    return this.makeRequest<QuotaResponse>('GET', `/api/v1/partners/${partnerId}/quota`);
  }

  // ========================================================================
  // SUPPORT TICKETS
  // ========================================================================

  async createSupportTicket(
    partnerId: string,
    request: SupportTicketRequest,
  ): Promise<SupportTicketResponse> {
    return this.makeRequest<SupportTicketResponse>(
      'POST',
      `/api/v1/partners/${partnerId}/support/tickets`,
      { body: request },
    );
  }

  async listSupportTickets(
    partnerId: string,
    options?: {
      statusFilter?: string;
      priorityFilter?: string;
      skip?: number;
      limit?: number;
    },
  ): Promise<SupportTicketResponse[]> {
    const response = await this.makeRequest<
      SupportTicketResponse[] | { tickets: SupportTicketResponse[] }
    >('GET', `/api/v1/partners/${partnerId}/support/tickets`, {
      params: {
        status_filter: options?.statusFilter,
        priority_filter: options?.priorityFilter,
        skip: options?.skip,
        limit: options?.limit,
      },
    });
    return Array.isArray(response) ? response : response.tickets || [];
  }

  async getSupportTicket(partnerId: string, ticketId: string): Promise<SupportTicketResponse> {
    return this.makeRequest<SupportTicketResponse>(
      'GET',
      `/api/v1/partners/${partnerId}/support/tickets/${ticketId}`,
    );
  }

  async updateSupportTicket(
    partnerId: string,
    ticketId: string,
    updates: Record<string, any>,
  ): Promise<SupportTicketResponse> {
    return this.makeRequest<SupportTicketResponse>(
      'PATCH',
      `/api/v1/partners/${partnerId}/support/tickets/${ticketId}`,
      { body: updates },
    );
  }

  // ========================================================================
  // DASHBOARD & HEALTH
  // ========================================================================

  async getDashboard(partnerId: string): Promise<Record<string, any>> {
    return this.makeRequest<Record<string, any>>('GET', `/api/v1/partners/${partnerId}/dashboard`);
  }

  async getHealth(partnerId: string): Promise<Record<string, any>> {
    return this.makeRequest<Record<string, any>>('GET', `/api/v1/partners/${partnerId}/health`);
  }

  // ========================================================================
  // WEBHOOK VERIFICATION
  // ========================================================================

  static verifyWebhookSignature(
    requestBody: string | Buffer,
    signature: string,
    secret: string,
  ): boolean {
    const body = typeof requestBody === 'string' ? requestBody : requestBody.toString();
    const expectedSignature = crypto
      .createHmac('sha256', secret)
      .update(body)
      .digest('hex');
    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSignature));
  }
}

// ============================================================================
// EXAMPLE USAGE
// ============================================================================

/*
async function example() {
  const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });

  try {
    // Register partner
    const partner = await client.registerPartner({
      company_name: 'Acme Corp',
      contact_email: 'contact@acme.com',
      contact_name: 'John Doe',
      integration_type: 'standard',
    });
    console.log('Partner registered:', partner.partner_id);

    // Create API key
    const apiKey = await client.createAPIKey(partner.partner_id, {
      name: 'Production Key',
      expires_in_days: 365,
    });
    console.log('API key created:', apiKey.key_prefix);

    // Register webhook
    const webhook = await client.registerWebhook(partner.partner_id, {
      event_type: 'partner.api_key.created',
      url: 'https://acme.com/webhooks/xagent',
    });
    console.log('Webhook registered:', webhook.webhook_id);

    // Get usage
    const usage = await client.getUsage(partner.partner_id);
    console.log('Usage:', usage.total_requests, 'requests');
  } catch (error) {
    console.error('Error:', error);
  }
}
*/

export default PartnerClient;
