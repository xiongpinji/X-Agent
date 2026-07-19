package xagent

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

const Version = "0.2.0-alpha" // 单一事实源: pyproject.toml

// ============================================================================
// TYPES
// ============================================================================

// PartnerClientConfig holds configuration for PartnerClient
type PartnerClientConfig struct {
	APIKey    string
	BaseURL   string
	Timeout   time.Duration
	MaxRetries int
}

// PartnerRegistrationRequest is the request to register a new partner
type PartnerRegistrationRequest struct {
	CompanyName     string   `json:"company_name"`
	ContactEmail    string   `json:"contact_email"`
	ContactName     string   `json:"contact_name"`
	CompanyWebsite  string   `json:"company_website,omitempty"`
	Description     string   `json:"description,omitempty"`
	IntegrationType string   `json:"integration_type,omitempty"`
	UseCases        []string `json:"use_cases,omitempty"`
	ExpectedVolume  string   `json:"expected_volume,omitempty"`
}

// PartnerResponse is the response containing partner information
type PartnerResponse struct {
	PartnerID       string    `json:"partner_id"`
	CompanyName     string    `json:"company_name"`
	ContactEmail    string    `json:"contact_email"`
	ContactName     string    `json:"contact_name"`
	CompanyWebsite  string    `json:"company_website,omitempty"`
	Description     string    `json:"description,omitempty"`
	IntegrationType string    `json:"integration_type"`
	UseCases        []string  `json:"use_cases"`
	Status          string    `json:"status"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
	APIKeyPrefix    string    `json:"api_key_prefix,omitempty"`
	WebhookURL      string    `json:"webhook_url,omitempty"`
	MonthlyRequests int       `json:"monthly_requests"`
	MonthlyLimit    int       `json:"monthly_limit"`
}

// APIKeyRequest is the request to create an API key
type APIKeyRequest struct {
	Name           string   `json:"name"`
	ExpiresInDays  int      `json:"expires_in_days,omitempty"`
	RateLimitRPM   int      `json:"rate_limit_rpm,omitempty"`
	RateLimitRPH   int      `json:"rate_limit_rph,omitempty"`
	IPWhitelist    []string `json:"ip_whitelist,omitempty"`
	Scopes         []string `json:"scopes,omitempty"`
}

// APIKeyResponse is the response containing API key information
type APIKeyResponse struct {
	KeyID          string    `json:"key_id"`
	Key            string    `json:"key,omitempty"`
	KeyPrefix      string    `json:"key_prefix"`
	Name           string    `json:"name"`
	PartnerID      string    `json:"partner_id"`
	CreatedAt      time.Time `json:"created_at"`
	ExpiresAt      time.Time `json:"expires_at,omitempty"`
	RateLimitRPM   int       `json:"rate_limit_rpm"`
	RateLimitRPH   int       `json:"rate_limit_rph"`
	IPWhitelist    []string  `json:"ip_whitelist,omitempty"`
	Scopes         []string  `json:"scopes"`
	Status         string    `json:"status"`
}

// WebhookRequest is the request to register a webhook
type WebhookRequest struct {
	EventType   string                 `json:"event_type"`
	URL         string                 `json:"url"`
	Active      bool                   `json:"active,omitempty"`
	RetryPolicy map[string]interface{} `json:"retry_policy,omitempty"`
}

// WebhookResponse is the response containing webhook information
type WebhookResponse struct {
	WebhookID       string                 `json:"webhook_id"`
	PartnerID       string                 `json:"partner_id"`
	EventType       string                 `json:"event_type"`
	URL             string                 `json:"url"`
	Active          bool                   `json:"active"`
	CreatedAt       time.Time              `json:"created_at"`
	LastTriggeredAt time.Time              `json:"last_triggered_at,omitempty"`
	RetryPolicy     map[string]interface{} `json:"retry_policy,omitempty"`
	DeliveryCount   int                    `json:"delivery_count"`
	FailureCount    int                    `json:"failure_count"`
}

// UsageResponse is the response containing usage statistics
type UsageResponse struct {
	PartnerID              string            `json:"partner_id"`
	PeriodStart            time.Time         `json:"period_start"`
	PeriodEnd              time.Time         `json:"period_end"`
	TotalRequests          int               `json:"total_requests"`
	SuccessfulRequests     int               `json:"successful_requests"`
	FailedRequests         int               `json:"failed_requests"`
	AverageResponseTimeMs  float64           `json:"average_response_time_ms"`
	APICallsByEndpoint     map[string]int    `json:"api_calls_by_endpoint"`
	ErrorsByType           map[string]int    `json:"errors_by_type"`
	BandwidthUsedMB        float64           `json:"bandwidth_used_mb"`
}

// QuotaResponse is the response containing quota information
type QuotaResponse struct {
	PartnerID       string    `json:"partner_id"`
	MonthlyLimit    int       `json:"monthly_limit"`
	MonthlyUsed     int       `json:"monthly_used"`
	MonthlyRemaining int      `json:"monthly_remaining"`
	ResetDate       time.Time `json:"reset_date"`
	QuotaExceeded   bool      `json:"quota_exceeded"`
}

// SupportTicketRequest is the request to create a support ticket
type SupportTicketRequest struct {
	Subject     string   `json:"subject"`
	Description string   `json:"description"`
	Priority    string   `json:"priority,omitempty"`
	Category    string   `json:"category,omitempty"`
	Attachments []string `json:"attachments,omitempty"`
}

// SupportTicketResponse is the response containing support ticket information
type SupportTicketResponse struct {
	TicketID        string    `json:"ticket_id"`
	PartnerID       string    `json:"partner_id"`
	Subject         string    `json:"subject"`
	Description     string    `json:"description"`
	Priority        string    `json:"priority"`
	Category        string    `json:"category"`
	Status          string    `json:"status"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
	AssignedTo      string    `json:"assigned_to,omitempty"`
	ResolutionNotes string    `json:"resolution_notes,omitempty"`
}

// ============================================================================
// ERRORS
// ============================================================================

// PartnerAPIError is the base error type for Partner API errors
type PartnerAPIError struct {
	Message    string
	StatusCode int
	Response   map[string]interface{}
}

func (e *PartnerAPIError) Error() string {
	return fmt.Sprintf("PartnerAPIError: %s (status: %d)", e.Message, e.StatusCode)
}

// PartnerAuthError is returned when authentication fails
type PartnerAuthError struct {
	*PartnerAPIError
}

// PartnerNotFoundError is returned when a resource is not found
type PartnerNotFoundError struct {
	*PartnerAPIError
}

// PartnerRateLimitError is returned when rate limit is exceeded
type PartnerRateLimitError struct {
	*PartnerAPIError
}

// ============================================================================
// CLIENT
// ============================================================================

// PartnerClient is the main client for interacting with Partner API
type PartnerClient struct {
	apiKey    string
	baseURL   string
	timeout   time.Duration
	maxRetries int
	httpClient *http.Client
}

// NewPartnerClient creates a new PartnerClient
func NewPartnerClient(config PartnerClientConfig) *PartnerClient {
	if config.BaseURL == "" {
		config.BaseURL = "https://api.x-agent.io"
	}
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}
	if config.MaxRetries == 0 {
		config.MaxRetries = 3
	}

	return &PartnerClient{
		apiKey:    config.APIKey,
		baseURL:   config.BaseURL,
		timeout:   config.Timeout,
		maxRetries: config.MaxRetries,
		httpClient: &http.Client{
			Timeout: config.Timeout,
		},
	}
}

func (c *PartnerClient) getHeaders() map[string]string {
	return map[string]string{
		"Authorization": fmt.Sprintf("Bearer %s", c.apiKey),
		"Content-Type":  "application/json",
		"User-Agent":    fmt.Sprintf("xagent-partner-sdk/%s", Version),
	}
}

func (c *PartnerClient) makeRequest(method, endpoint string, body interface{}, params map[string]string) ([]byte, error) {
	fullURL := c.baseURL + endpoint

	// Add query parameters
	if len(params) > 0 {
		q := url.Values{}
		for k, v := range params {
			if v != "" {
				q.Add(k, v)
			}
		}
		if len(q) > 0 {
			fullURL += "?" + q.Encode()
		}
	}

	var bodyReader io.Reader
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		bodyReader = bytes.NewReader(bodyBytes)
	}

	for attempt := 0; attempt < c.maxRetries; attempt++ {
		req, err := http.NewRequest(method, fullURL, bodyReader)
		if err != nil {
			return nil, err
		}

		// Set headers
		for k, v := range c.getHeaders() {
			req.Header.Set(k, v)
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			if attempt == c.maxRetries-1 {
				return nil, &PartnerAPIError{
					Message:    fmt.Sprintf("Request failed: %v", err),
					StatusCode: 0,
				}
			}
			time.Sleep(time.Duration(1<<uint(attempt)) * time.Second)
			continue
		}

		defer resp.Body.Close()
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, err
		}

		// Handle rate limiting
		if resp.StatusCode == 429 {
			retryAfter := resp.Header.Get("Retry-After")
			if retryAfter != "" {
				if seconds, err := strconv.Atoi(retryAfter); err == nil {
					if attempt < c.maxRetries-1 {
						time.Sleep(time.Duration(seconds) * time.Second)
						continue
					}
				}
			}
			var respData map[string]interface{}
			json.Unmarshal(respBody, &respData)
			return nil, &PartnerRateLimitError{
				PartnerAPIError: &PartnerAPIError{
					Message:    "Rate limit exceeded",
					StatusCode: 429,
					Response:   respData,
				},
			}
		}

		// Handle server errors
		if resp.StatusCode >= 500 {
			if attempt < c.maxRetries-1 {
				time.Sleep(time.Duration(1<<uint(attempt)) * time.Second)
				continue
			}
		}

		// Handle client errors
		if resp.StatusCode == 401 {
			var respData map[string]interface{}
			json.Unmarshal(respBody, &respData)
			return nil, &PartnerAuthError{
				PartnerAPIError: &PartnerAPIError{
					Message:    "Unauthorized",
					StatusCode: 401,
					Response:   respData,
				},
			}
		}

		if resp.StatusCode == 404 {
			var respData map[string]interface{}
			json.Unmarshal(respBody, &respData)
			return nil, &PartnerNotFoundError{
				PartnerAPIError: &PartnerAPIError{
					Message:    "Resource not found",
					StatusCode: 404,
					Response:   respData,
				},
			}
		}

		if resp.StatusCode >= 400 {
			var respData map[string]interface{}
			json.Unmarshal(respBody, &respData)
			return nil, &PartnerAPIError{
				Message:    fmt.Sprintf("API error: %v", respData),
				StatusCode: resp.StatusCode,
				Response:   respData,
			}
		}

		return respBody, nil
	}

	return nil, &PartnerAPIError{
		Message:    "Max retries exceeded",
		StatusCode: 0,
	}
}

// ========================================================================
// PARTNER MANAGEMENT
// ========================================================================

// RegisterPartner registers a new partner
func (c *PartnerClient) RegisterPartner(req PartnerRegistrationRequest) (*PartnerResponse, error) {
	body, err := c.makeRequest("POST", "/api/v1/partners/register", req, nil)
	if err != nil {
		return nil, err
	}

	var resp PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// GetPartner retrieves partner information
func (c *PartnerClient) GetPartner(partnerID string) (*PartnerResponse, error) {
	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s", partnerID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ListPartners lists all partners
func (c *PartnerClient) ListPartners(statusFilter, integrationType string, skip, limit int) ([]PartnerResponse, error) {
	params := map[string]string{
		"skip":  strconv.Itoa(skip),
		"limit": strconv.Itoa(limit),
	}
	if statusFilter != "" {
		params["status_filter"] = statusFilter
	}
	if integrationType != "" {
		params["integration_type"] = integrationType
	}

	body, err := c.makeRequest("GET", "/api/v1/partners", nil, params)
	if err != nil {
		return nil, err
	}

	var resp []PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return resp, nil
}

// UpdatePartner updates partner information
func (c *PartnerClient) UpdatePartner(partnerID string, updates map[string]interface{}) (*PartnerResponse, error) {
	body, err := c.makeRequest("PATCH", fmt.Sprintf("/api/v1/partners/%s", partnerID), updates, nil)
	if err != nil {
		return nil, err
	}

	var resp PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ApprovePartner approves a pending partner
func (c *PartnerClient) ApprovePartner(partnerID string) (*PartnerResponse, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/approve", partnerID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// SuspendPartner suspends a partner
func (c *PartnerClient) SuspendPartner(partnerID, reason string) (*PartnerResponse, error) {
	params := map[string]string{"reason": reason}
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/suspend", partnerID), nil, params)
	if err != nil {
		return nil, err
	}

	var resp PartnerResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ========================================================================
// API KEY MANAGEMENT
// ========================================================================

// CreateAPIKey creates a new API key
func (c *PartnerClient) CreateAPIKey(partnerID string, req APIKeyRequest) (*APIKeyResponse, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/api-keys", partnerID), req, nil)
	if err != nil {
		return nil, err
	}

	var resp APIKeyResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ListAPIKeys lists API keys for a partner
func (c *PartnerClient) ListAPIKeys(partnerID, statusFilter string) ([]APIKeyResponse, error) {
	params := map[string]string{}
	if statusFilter != "" {
		params["status_filter"] = statusFilter
	}

	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s/api-keys", partnerID), nil, params)
	if err != nil {
		return nil, err
	}

	var resp []APIKeyResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return resp, nil
}

// RotateAPIKey rotates an API key
func (c *PartnerClient) RotateAPIKey(partnerID, keyID string) (*APIKeyResponse, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/api-keys/%s/rotate", partnerID, keyID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp APIKeyResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// RevokeAPIKey revokes an API key
func (c *PartnerClient) RevokeAPIKey(partnerID, keyID string) error {
	_, err := c.makeRequest("DELETE", fmt.Sprintf("/api/v1/partners/%s/api-keys/%s", partnerID, keyID), nil, nil)
	return err
}

// ========================================================================
// WEBHOOK MANAGEMENT
// ========================================================================

// RegisterWebhook registers a webhook
func (c *PartnerClient) RegisterWebhook(partnerID string, req WebhookRequest) (*WebhookResponse, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/webhooks", partnerID), req, nil)
	if err != nil {
		return nil, err
	}

	var resp WebhookResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ListWebhooks lists webhooks for a partner
func (c *PartnerClient) ListWebhooks(partnerID string) ([]WebhookResponse, error) {
	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s/webhooks", partnerID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp []WebhookResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return resp, nil
}

// DeleteWebhook deletes a webhook
func (c *PartnerClient) DeleteWebhook(partnerID, webhookID string) error {
	_, err := c.makeRequest("DELETE", fmt.Sprintf("/api/v1/partners/%s/webhooks/%s", partnerID, webhookID), nil, nil)
	return err
}

// TestWebhook sends a test event to a webhook
func (c *PartnerClient) TestWebhook(partnerID, webhookID string) (map[string]interface{}, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/webhooks/%s/test", partnerID, webhookID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return resp, nil
}

// ========================================================================
// USAGE & ANALYTICS
// ========================================================================

// GetUsage retrieves usage statistics
func (c *PartnerClient) GetUsage(partnerID, period, startDate, endDate string) (*UsageResponse, error) {
	params := map[string]string{"period": period}
	if startDate != "" {
		params["start_date"] = startDate
	}
	if endDate != "" {
		params["end_date"] = endDate
	}

	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s/usage", partnerID), nil, params)
	if err != nil {
		return nil, err
	}

	var resp UsageResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// GetQuota retrieves quota information
func (c *PartnerClient) GetQuota(partnerID string) (*QuotaResponse, error) {
	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s/quota", partnerID), nil, nil)
	if err != nil {
		return nil, err
	}

	var resp QuotaResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ========================================================================
// SUPPORT TICKETS
// ========================================================================

// CreateSupportTicket creates a support ticket
func (c *PartnerClient) CreateSupportTicket(partnerID string, req SupportTicketRequest) (*SupportTicketResponse, error) {
	body, err := c.makeRequest("POST", fmt.Sprintf("/api/v1/partners/%s/support/tickets", partnerID), req, nil)
	if err != nil {
		return nil, err
	}

	var resp SupportTicketResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// ListSupportTickets lists support tickets
func (c *PartnerClient) ListSupportTickets(partnerID, statusFilter, priorityFilter string, skip, limit int) ([]SupportTicketResponse, error) {
	params := map[string]string{
		"skip":  strconv.Itoa(skip),
		"limit": strconv.Itoa(limit),
	}
	if statusFilter != "" {
		params["status_filter"] = statusFilter
	}
	if priorityFilter != "" {
		params["priority_filter"] = priorityFilter
	}

	body, err := c.makeRequest("GET", fmt.Sprintf("/api/v1/partners/%s/support/tickets", partnerID), nil, params)
	if err != nil {
		return nil, err
	}

	var resp []SupportTicketResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	return resp, nil
}

// ========================================================================
// WEBHOOK VERIFICATION
// ========================================================================

// VerifyWebhookSignature verifies webhook signature
func VerifyWebhookSignature(requestBody []byte, signature, secret string) bool {
	expectedSignature := hmac.New(sha256.New, []byte(secret))
	expectedSignature.Write(requestBody)
	expected := hex.EncodeToString(expectedSignature.Sum(nil))
	return hmac.Equal([]byte(signature), []byte(expected))
}
