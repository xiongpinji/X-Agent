package io.xagent.partner;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * X-Agent Partner SDK for Java
 *
 * A comprehensive SDK for integrating with X-Agent Partner API.
 *
 * Usage:
 *   PartnerClient client = new PartnerClient("xag_partner_xxx");
 *   PartnerResponse partner = client.getPartner("partner_id");
 */
public class PartnerClient {
    public static final String VERSION = "0.2.0-alpha"; // 单一事实源: pyproject.toml

    private final String apiKey;
    private final String baseUrl;
    private final Duration timeout;
    private final int maxRetries;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    // ========================================================================
    // CONSTRUCTORS
    // ========================================================================

    public PartnerClient(String apiKey) {
        this(apiKey, "https://api.x-agent.io", Duration.ofSeconds(30), 3);
    }

    public PartnerClient(String apiKey, String baseUrl, Duration timeout, int maxRetries) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl.replaceAll("/$", "");
        this.timeout = timeout;
        this.maxRetries = maxRetries;
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(timeout)
            .build();
        this.objectMapper = new ObjectMapper();
    }

    // ========================================================================
    // PRIVATE METHODS
    // ========================================================================

    private Map<String, String> getHeaders() {
        Map<String, String> headers = new HashMap<>();
        headers.put("Authorization", "Bearer " + apiKey);
        headers.put("Content-Type", "application/json");
        headers.put("User-Agent", "xagent-partner-sdk/" + VERSION);
        return headers;
    }

    private <T> T makeRequest(String method, String endpoint, Object body, Map<String, String> params, Class<T> responseType) throws PartnerAPIException {
        String url = baseUrl + endpoint;

        if (params != null && !params.isEmpty()) {
            StringBuilder queryString = new StringBuilder();
            for (Map.Entry<String, String> entry : params.entrySet()) {
                if (entry.getValue() != null && !entry.getValue().isEmpty()) {
                    if (queryString.length() > 0) {
                        queryString.append("&");
                    }
                    queryString.append(URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8))
                        .append("=")
                        .append(URLEncoder.encode(entry.getValue(), StandardCharsets.UTF_8));
                }
            }
            if (queryString.length() > 0) {
                url += "?" + queryString;
            }
        }

        for (int attempt = 0; attempt < maxRetries; attempt++) {
            try {
                HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(timeout);

                // Add headers
                for (Map.Entry<String, String> header : getHeaders().entrySet()) {
                    requestBuilder.header(header.getKey(), header.getValue());
                }

                // Add body
                if (body != null) {
                    String bodyJson = objectMapper.writeValueAsString(body);
                    requestBuilder.method(method, HttpRequest.BodyPublishers.ofString(bodyJson));
                } else {
                    requestBuilder.method(method, HttpRequest.BodyPublishers.noBody());
                }

                HttpRequest request = requestBuilder.build();
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

                // Handle rate limiting
                if (response.statusCode() == 429) {
                    String retryAfter = response.headers().firstValue("Retry-After").orElse("60");
                    if (attempt < maxRetries - 1) {
                        Thread.sleep(Long.parseLong(retryAfter) * 1000L);
                        continue;
                    }
                    Map<String, Object> errorResponse = objectMapper.readValue(response.body(), Map.class);
                    throw new PartnerRateLimitException("Rate limit exceeded", errorResponse);
                }

                // Handle server errors
                if (response.statusCode() >= 500) {
                    if (attempt < maxRetries - 1) {
                        long waitTime = (long) Math.pow(2, attempt) * 1000;
                        Thread.sleep(waitTime);
                        continue;
                    }
                }

                // Handle client errors
                if (response.statusCode() == 401) {
                    Map<String, Object> errorResponse = objectMapper.readValue(response.body(), Map.class);
                    throw new PartnerAuthException("Unauthorized", errorResponse);
                }

                if (response.statusCode() == 404) {
                    Map<String, Object> errorResponse = objectMapper.readValue(response.body(), Map.class);
                    throw new PartnerNotFoundException("Resource not found", errorResponse);
                }

                if (response.statusCode() >= 400) {
                    Map<String, Object> errorResponse = objectMapper.readValue(response.body(), Map.class);
                    throw new PartnerAPIException("API error", response.statusCode(), errorResponse);
                }

                return objectMapper.readValue(response.body(), responseType);

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new PartnerAPIException("Request interrupted: " + e.getMessage());
            } catch (IOException e) {
                if (attempt == maxRetries - 1) {
                    throw new PartnerAPIException("Request failed: " + e.getMessage());
                }
                try {
                    long waitTime = (long) Math.pow(2, attempt) * 1000;
                    Thread.sleep(waitTime);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new PartnerAPIException("Request interrupted");
                }
            }
        }

        throw new PartnerAPIException("Max retries exceeded");
    }

    // ========================================================================
    // PARTNER MANAGEMENT
    // ========================================================================

    public PartnerResponse registerPartner(PartnerRegistrationRequest request) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/register", request, null, PartnerResponse.class);
    }

    public PartnerResponse getPartner(String partnerId) throws PartnerAPIException {
        return makeRequest("GET", "/api/v1/partners/" + partnerId, null, null, PartnerResponse.class);
    }

    public List<PartnerResponse> listPartners(String statusFilter, String integrationType, int skip, int limit) throws PartnerAPIException {
        Map<String, String> params = new HashMap<>();
        params.put("skip", String.valueOf(skip));
        params.put("limit", String.valueOf(limit));
        if (statusFilter != null) {
            params.put("status_filter", statusFilter);
        }
        if (integrationType != null) {
            params.put("integration_type", integrationType);
        }

        PartnerListResponse response = makeRequest("GET", "/api/v1/partners", null, params, PartnerListResponse.class);
        return response.partners != null ? response.partners : new ArrayList<>();
    }

    public PartnerResponse updatePartner(String partnerId, Map<String, Object> updates) throws PartnerAPIException {
        return makeRequest("PATCH", "/api/v1/partners/" + partnerId, updates, null, PartnerResponse.class);
    }

    public PartnerResponse approvePartner(String partnerId) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/approve", null, null, PartnerResponse.class);
    }

    public PartnerResponse suspendPartner(String partnerId, String reason) throws PartnerAPIException {
        Map<String, String> params = new HashMap<>();
        params.put("reason", reason);
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/suspend", null, params, PartnerResponse.class);
    }

    // ========================================================================
    // API KEY MANAGEMENT
    // ========================================================================

    public APIKeyResponse createAPIKey(String partnerId, APIKeyRequest request) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/api-keys", request, null, APIKeyResponse.class);
    }

    public List<APIKeyResponse> listAPIKeys(String partnerId, String statusFilter) throws PartnerAPIException {
        Map<String, String> params = new HashMap<>();
        if (statusFilter != null) {
            params.put("status_filter", statusFilter);
        }

        APIKeyListResponse response = makeRequest("GET", "/api/v1/partners/" + partnerId + "/api-keys", null, params, APIKeyListResponse.class);
        return response.keys != null ? response.keys : new ArrayList<>();
    }

    public APIKeyResponse rotateAPIKey(String partnerId, String keyId) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/api-keys/" + keyId + "/rotate", null, null, APIKeyResponse.class);
    }

    public void revokeAPIKey(String partnerId, String keyId) throws PartnerAPIException {
        makeRequest("DELETE", "/api/v1/partners/" + partnerId + "/api-keys/" + keyId, null, null, Void.class);
    }

    // ========================================================================
    // WEBHOOK MANAGEMENT
    // ========================================================================

    public WebhookResponse registerWebhook(String partnerId, WebhookRequest request) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/webhooks", request, null, WebhookResponse.class);
    }

    public List<WebhookResponse> listWebhooks(String partnerId) throws PartnerAPIException {
        WebhookListResponse response = makeRequest("GET", "/api/v1/partners/" + partnerId + "/webhooks", null, null, WebhookListResponse.class);
        return response.webhooks != null ? response.webhooks : new ArrayList<>();
    }

    public WebhookResponse updateWebhook(String partnerId, String webhookId, Map<String, Object> updates) throws PartnerAPIException {
        return makeRequest("PATCH", "/api/v1/partners/" + partnerId + "/webhooks/" + webhookId, updates, null, WebhookResponse.class);
    }

    public void deleteWebhook(String partnerId, String webhookId) throws PartnerAPIException {
        makeRequest("DELETE", "/api/v1/partners/" + partnerId + "/webhooks/" + webhookId, null, null, Void.class);
    }

    public Map<String, Object> testWebhook(String partnerId, String webhookId) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/webhooks/" + webhookId + "/test", null, null, Map.class);
    }

    // ========================================================================
    // USAGE & ANALYTICS
    // ========================================================================

    public UsageResponse getUsage(String partnerId, String period, String startDate, String endDate) throws PartnerAPIException {
        Map<String, String> params = new HashMap<>();
        params.put("period", period);
        if (startDate != null) {
            params.put("start_date", startDate);
        }
        if (endDate != null) {
            params.put("end_date", endDate);
        }

        return makeRequest("GET", "/api/v1/partners/" + partnerId + "/usage", null, params, UsageResponse.class);
    }

    public QuotaResponse getQuota(String partnerId) throws PartnerAPIException {
        return makeRequest("GET", "/api/v1/partners/" + partnerId + "/quota", null, null, QuotaResponse.class);
    }

    // ========================================================================
    // SUPPORT TICKETS
    // ========================================================================

    public SupportTicketResponse createSupportTicket(String partnerId, SupportTicketRequest request) throws PartnerAPIException {
        return makeRequest("POST", "/api/v1/partners/" + partnerId + "/support/tickets", request, null, SupportTicketResponse.class);
    }

    public List<SupportTicketResponse> listSupportTickets(String partnerId, String statusFilter, String priorityFilter, int skip, int limit) throws PartnerAPIException {
        Map<String, String> params = new HashMap<>();
        params.put("skip", String.valueOf(skip));
        params.put("limit", String.valueOf(limit));
        if (statusFilter != null) {
            params.put("status_filter", statusFilter);
        }
        if (priorityFilter != null) {
            params.put("priority_filter", priorityFilter);
        }

        SupportTicketListResponse response = makeRequest("GET", "/api/v1/partners/" + partnerId + "/support/tickets", null, params, SupportTicketListResponse.class);
        return response.tickets != null ? response.tickets : new ArrayList<>();
    }

    public SupportTicketResponse getSupportTicket(String partnerId, String ticketId) throws PartnerAPIException {
        return makeRequest("GET", "/api/v1/partners/" + partnerId + "/support/tickets/" + ticketId, null, null, SupportTicketResponse.class);
    }

    public SupportTicketResponse updateSupportTicket(String partnerId, String ticketId, Map<String, Object> updates) throws PartnerAPIException {
        return makeRequest("PATCH", "/api/v1/partners/" + partnerId + "/support/tickets/" + ticketId, updates, null, SupportTicketResponse.class);
    }

    // ========================================================================
    // DASHBOARD & HEALTH
    // ========================================================================

    public Map<String, Object> getDashboard(String partnerId) throws PartnerAPIException {
        return makeRequest("GET", "/api/v1/partners/" + partnerId + "/dashboard", null, null, Map.class);
    }

    public Map<String, Object> getHealth(String partnerId) throws PartnerAPIException {
        return makeRequest("GET", "/api/v1/partners/" + partnerId + "/health", null, null, Map.class);
    }

    // ========================================================================
    // WEBHOOK VERIFICATION
    // ========================================================================

    public static boolean verifyWebhookSignature(byte[] requestBody, String signature, String secret) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] expectedSignatureBytes = mac.doFinal(requestBody);
            String expectedSignature = bytesToHex(expectedSignatureBytes);
            return expectedSignature.equals(signature);
        } catch (Exception e) {
            return false;
        }
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    // ========================================================================
    // DATA CLASSES
    // ========================================================================

    public static class PartnerRegistrationRequest {
        @JsonProperty("company_name")
        public String companyName;

        @JsonProperty("contact_email")
        public String contactEmail;

        @JsonProperty("contact_name")
        public String contactName;

        @JsonProperty("company_website")
        public String companyWebsite;

        @JsonProperty("description")
        public String description;

        @JsonProperty("integration_type")
        public String integrationType;

        @JsonProperty("use_cases")
        public List<String> useCases;

        @JsonProperty("expected_volume")
        public String expectedVolume;
    }

    public static class PartnerResponse {
        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("company_name")
        public String companyName;

        @JsonProperty("contact_email")
        public String contactEmail;

        @JsonProperty("contact_name")
        public String contactName;

        @JsonProperty("company_website")
        public String companyWebsite;

        @JsonProperty("description")
        public String description;

        @JsonProperty("integration_type")
        public String integrationType;

        @JsonProperty("use_cases")
        public List<String> useCases;

        @JsonProperty("status")
        public String status;

        @JsonProperty("created_at")
        public Instant createdAt;

        @JsonProperty("updated_at")
        public Instant updatedAt;

        @JsonProperty("api_key_prefix")
        public String apiKeyPrefix;

        @JsonProperty("webhook_url")
        public String webhookUrl;

        @JsonProperty("monthly_requests")
        public int monthlyRequests;

        @JsonProperty("monthly_limit")
        public int monthlyLimit;
    }

    public static class PartnerListResponse {
        @JsonProperty("partners")
        public List<PartnerResponse> partners;
    }

    public static class APIKeyRequest {
        @JsonProperty("name")
        public String name;

        @JsonProperty("expires_in_days")
        public int expiresInDays;

        @JsonProperty("rate_limit_rpm")
        public int rateLimitRpm;

        @JsonProperty("rate_limit_rph")
        public int rateLimitRph;

        @JsonProperty("ip_whitelist")
        public List<String> ipWhitelist;

        @JsonProperty("scopes")
        public List<String> scopes;
    }

    public static class APIKeyResponse {
        @JsonProperty("key_id")
        public String keyId;

        @JsonProperty("key")
        public String key;

        @JsonProperty("key_prefix")
        public String keyPrefix;

        @JsonProperty("name")
        public String name;

        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("created_at")
        public Instant createdAt;

        @JsonProperty("expires_at")
        public Instant expiresAt;

        @JsonProperty("rate_limit_rpm")
        public int rateLimitRpm;

        @JsonProperty("rate_limit_rph")
        public int rateLimitRph;

        @JsonProperty("ip_whitelist")
        public List<String> ipWhitelist;

        @JsonProperty("scopes")
        public List<String> scopes;

        @JsonProperty("status")
        public String status;
    }

    public static class APIKeyListResponse {
        @JsonProperty("keys")
        public List<APIKeyResponse> keys;
    }

    public static class WebhookRequest {
        @JsonProperty("event_type")
        public String eventType;

        @JsonProperty("url")
        public String url;

        @JsonProperty("active")
        public boolean active;

        @JsonProperty("retry_policy")
        public Map<String, Object> retryPolicy;
    }

    public static class WebhookResponse {
        @JsonProperty("webhook_id")
        public String webhookId;

        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("event_type")
        public String eventType;

        @JsonProperty("url")
        public String url;

        @JsonProperty("active")
        public boolean active;

        @JsonProperty("created_at")
        public Instant createdAt;

        @JsonProperty("last_triggered_at")
        public Instant lastTriggeredAt;

        @JsonProperty("retry_policy")
        public Map<String, Object> retryPolicy;

        @JsonProperty("delivery_count")
        public int deliveryCount;

        @JsonProperty("failure_count")
        public int failureCount;
    }

    public static class WebhookListResponse {
        @JsonProperty("webhooks")
        public List<WebhookResponse> webhooks;
    }

    public static class UsageResponse {
        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("period_start")
        public Instant periodStart;

        @JsonProperty("period_end")
        public Instant periodEnd;

        @JsonProperty("total_requests")
        public int totalRequests;

        @JsonProperty("successful_requests")
        public int successfulRequests;

        @JsonProperty("failed_requests")
        public int failedRequests;

        @JsonProperty("average_response_time_ms")
        public double averageResponseTimeMs;

        @JsonProperty("api_calls_by_endpoint")
        public Map<String, Integer> apiCallsByEndpoint;

        @JsonProperty("errors_by_type")
        public Map<String, Integer> errorsByType;

        @JsonProperty("bandwidth_used_mb")
        public double bandwidthUsedMb;
    }

    public static class QuotaResponse {
        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("monthly_limit")
        public int monthlyLimit;

        @JsonProperty("monthly_used")
        public int monthlyUsed;

        @JsonProperty("monthly_remaining")
        public int monthlyRemaining;

        @JsonProperty("reset_date")
        public Instant resetDate;

        @JsonProperty("quota_exceeded")
        public boolean quotaExceeded;
    }

    public static class SupportTicketRequest {
        @JsonProperty("subject")
        public String subject;

        @JsonProperty("description")
        public String description;

        @JsonProperty("priority")
        public String priority;

        @JsonProperty("category")
        public String category;

        @JsonProperty("attachments")
        public List<String> attachments;
    }

    public static class SupportTicketResponse {
        @JsonProperty("ticket_id")
        public String ticketId;

        @JsonProperty("partner_id")
        public String partnerId;

        @JsonProperty("subject")
        public String subject;

        @JsonProperty("description")
        public String description;

        @JsonProperty("priority")
        public String priority;

        @JsonProperty("category")
        public String category;

        @JsonProperty("status")
        public String status;

        @JsonProperty("created_at")
        public Instant createdAt;

        @JsonProperty("updated_at")
        public Instant updatedAt;

        @JsonProperty("assigned_to")
        public String assignedTo;

        @JsonProperty("resolution_notes")
        public String resolutionNotes;
    }

    public static class SupportTicketListResponse {
        @JsonProperty("tickets")
        public List<SupportTicketResponse> tickets;
    }
}
