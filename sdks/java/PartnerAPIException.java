package io.xagent.partner;

import java.util.Map;

/**
 * Base exception for Partner API errors
 */
public class PartnerAPIException extends Exception {
    private final int statusCode;
    private final Map<String, Object> response;

    public PartnerAPIException(String message) {
        super(message);
        this.statusCode = 0;
        this.response = null;
    }

    public PartnerAPIException(String message, int statusCode, Map<String, Object> response) {
        super(message);
        this.statusCode = statusCode;
        this.response = response;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public Map<String, Object> getResponse() {
        return response;
    }

    @Override
    public String toString() {
        return String.format("PartnerAPIException: %s (status: %d)", getMessage(), statusCode);
    }
}

/**
 * Authentication error
 */
class PartnerAuthException extends PartnerAPIException {
    public PartnerAuthException(String message, Map<String, Object> response) {
        super(message, 401, response);
    }
}

/**
 * Resource not found error
 */
class PartnerNotFoundException extends PartnerAPIException {
    public PartnerNotFoundException(String message, Map<String, Object> response) {
        super(message, 404, response);
    }
}

/**
 * Rate limit exceeded error
 */
class PartnerRateLimitException extends PartnerAPIException {
    public PartnerRateLimitException(String message, Map<String, Object> response) {
        super(message, 429, response);
    }
}
