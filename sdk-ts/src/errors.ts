/**
 * X-Agent SDK error classes
 */

export class XAgentError extends Error {
  constructor(
    message: string,
    public code: string = 'XAGENT_ERROR',
    public statusCode: number = 500,
  ) {
    super(message);
    this.name = 'XAgentError';
    Object.setPrototypeOf(this, XAgentError.prototype);
  }
}

export class AuthenticationError extends XAgentError {
  constructor(message: string = 'Authentication failed') {
    super(message, 'AUTHENTICATION_ERROR', 401);
    this.name = 'AuthenticationError';
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

export class AuthorizationError extends XAgentError {
  constructor(message: string = 'Insufficient permissions') {
    super(message, 'AUTHORIZATION_ERROR', 403);
    this.name = 'AuthorizationError';
    Object.setPrototypeOf(this, AuthorizationError.prototype);
  }
}

export class NotFoundError extends XAgentError {
  constructor(message: string = 'Resource not found') {
    super(message, 'NOT_FOUND_ERROR', 404);
    this.name = 'NotFoundError';
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }
}

export class ValidationError extends XAgentError {
  constructor(
    message: string = 'Validation failed',
    public details?: Record<string, string[]>,
  ) {
    super(message, 'VALIDATION_ERROR', 422);
    this.name = 'ValidationError';
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

export class TimeoutError extends XAgentError {
  constructor(message: string = 'Request timeout') {
    super(message, 'TIMEOUT_ERROR', 408);
    this.name = 'TimeoutError';
    Object.setPrototypeOf(this, TimeoutError.prototype);
  }
}

export class RateLimitError extends XAgentError {
  constructor(
    message: string = 'Rate limit exceeded',
    public retryAfter?: number,
  ) {
    super(message, 'RATE_LIMIT_ERROR', 429);
    this.name = 'RateLimitError';
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}

export class ServerError extends XAgentError {
  constructor(message: string = 'Server error') {
    super(message, 'SERVER_ERROR', 500);
    this.name = 'ServerError';
    Object.setPrototypeOf(this, ServerError.prototype);
  }
}

export class MCPError extends XAgentError {
  constructor(
    message: string = 'MCP protocol error',
    public mcpServerName?: string,
  ) {
    super(message, 'MCP_ERROR', 500);
    this.name = 'MCPError';
    Object.setPrototypeOf(this, MCPError.prototype);
  }
}
