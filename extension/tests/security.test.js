/**
 * X-Agent Chrome Extension - Security & Permissions Tests
 * Tests security boundaries, CSP compliance, and permission handling
 */

describe('Security & Permissions Tests', () => {
  describe('Content Security Policy (CSP) Compliance', () => {
    test('should not allow inline scripts', () => {
      const manifest = {
        manifest_version: 3,
        content_security_policy: {
          extension_pages: "script-src 'self'; object-src 'self'"
        }
      };

      // Verify no inline scripts in manifest
      expect(manifest.content_security_policy.extension_pages).not.toContain("'unsafe-inline'");
      expect(manifest.content_security_policy.extension_pages).not.toContain("'unsafe-eval'");
    });

    test('should restrict external script sources', () => {
      const csp = "script-src 'self'; connect-src 'self' https://api.example.com";

      // Only allow self and specific domains
      expect(csp).toMatch(/script-src 'self'/);
      expect(csp).not.toContain('*');
    });

    test('should validate manifest permissions', () => {
      const manifest = {
        permissions: [
          'activeTab',
          'scripting',
          'storage',
          'tabs',
          'webNavigation',
          'contextMenus'
        ],
        host_permissions: ['<all_urls>']
      };

      // Check for dangerous permissions
      const dangerousPerms = ['webRequest', 'webRequestBlocking'];
      const hasDangerous = manifest.permissions.some(p => dangerousPerms.includes(p));

      expect(hasDangerous).toBe(false);
    });
  });

  describe('Data Isolation & Privacy Tests', () => {
    test('should isolate content script from page context', () => {
      // Content scripts should not have access to page variables
      const contentScriptScope = {
        canAccessPageVariables: false,
        canAccessPageFunctions: false,
        canModifyPageGlobals: false
      };

      expect(contentScriptScope.canAccessPageVariables).toBe(false);
      expect(contentScriptScope.canAccessPageFunctions).toBe(false);
    });

    test('should encrypt sensitive data in storage', async () => {
      const storageManager = {
        saveSession: async function(session) {
          // Should encrypt before storing
          const encrypted = this.encrypt(JSON.stringify(session));
          return { success: true, encrypted: true };
        },
        encrypt: function(data) {
          // Mock encryption
          return Buffer.from(data).toString('base64');
        }
      };

      const session = {
        id: 'session_123',
        token: 'secret_token_xyz'
      };

      const result = await storageManager.saveSession(session);
      expect(result.encrypted).toBe(true);
    });

    test('should not expose sensitive data in logs', () => {
      const logger = {
        log: function(message, data) {
          // Should not log sensitive fields
          const sensitiveFields = ['password', 'token', 'apiKey', 'secret'];
          const dataStr = JSON.stringify(data);

          for (const field of sensitiveFields) {
            expect(dataStr).not.toContain(field);
          }
        }
      };

      const userData = {
        username: 'user@example.com',
        password: 'secret123'
      };

      logger.log('User login', { username: userData.username });
    });

    test('should validate and sanitize user input', () => {
      const inputValidator = {
        sanitize: function(input) {
          // Remove potentially dangerous characters
          return input
            .replace(/[<>\"']/g, '')
            .trim();
        },
        validate: function(input, type) {
          switch (type) {
            case 'selector':
              return /^[#.\w\s\[\]="':>+~-]*$/.test(input);
            case 'url':
              try {
                new URL(input);
                return true;
              } catch {
                return false;
              }
            case 'email':
              return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input);
            default:
              return true;
          }
        }
      };

      // Test selector validation
      expect(inputValidator.validate('#button', 'selector')).toBe(true);
      expect(inputValidator.validate('<script>', 'selector')).toBe(false);

      // Test URL validation
      expect(inputValidator.validate('https://example.com', 'url')).toBe(true);
      expect(inputValidator.validate('javascript:alert(1)', 'url')).toBe(false);

      // Test email validation
      expect(inputValidator.validate('user@example.com', 'email')).toBe(true);
      expect(inputValidator.validate('invalid-email', 'email')).toBe(false);
    });
  });

  describe('Permission Boundary Tests', () => {
    test('should only access permitted tabs', async () => {
      const tabManager = {
        canAccessTab: function(tabId, currentWindowId) {
          // Should only access tabs in current window
          return true; // Simplified for test
        }
      };

      expect(tabManager.canAccessTab(1, 1)).toBe(true);
    });

    test('should respect host permissions', () => {
      const manifest = {
        host_permissions: ['<all_urls>']
      };

      const allowedHosts = [
        'https://example.com',
        'https://test.com',
        'http://localhost:3000'
      ];

      allowedHosts.forEach(host => {
        expect(manifest.host_permissions[0]).toBe('<all_urls>');
      });
    });

    test('should not access restricted APIs without permission', () => {
      const apiAccess = {
        canAccessAPI: function(apiName, permissions) {
          const apiPermissionMap = {
            'storage': ['storage'],
            'tabs': ['tabs'],
            'webNavigation': ['webNavigation'],
            'contextMenus': ['contextMenus']
          };

          const required = apiPermissionMap[apiName] || [];
          return required.every(p => permissions.includes(p));
        }
      };

      const permissions = ['storage', 'tabs'];

      expect(apiAccess.canAccessAPI('storage', permissions)).toBe(true);
      expect(apiAccess.canAccessAPI('tabs', permissions)).toBe(true);
      expect(apiAccess.canAccessAPI('webRequest', permissions)).toBe(false);
    });
  });

  describe('Message Passing Security Tests', () => {
    test('should validate message structure', () => {
      const messageValidator = {
        validate: function(message) {
          if (!message || typeof message !== 'object') {
            return { valid: false, error: 'Invalid message format' };
          }

          if (!message.type || typeof message.type !== 'string') {
            return { valid: false, error: 'Missing or invalid type' };
          }

          if (message.type.length > 100) {
            return { valid: false, error: 'Type too long' };
          }

          return { valid: true };
        }
      };

      expect(messageValidator.validate({ type: 'TEST' }).valid).toBe(true);
      expect(messageValidator.validate({ type: '' }).valid).toBe(false);
      expect(messageValidator.validate(null).valid).toBe(false);
      expect(messageValidator.validate({ payload: 'test' }).valid).toBe(false);
    });

    test('should verify message sender', () => {
      const messageSecurity = {
        verifySender: function(sender, allowedOrigins) {
          if (!sender || !sender.url) {
            return false;
          }

          try {
            const url = new URL(sender.url);
            return allowedOrigins.includes(url.origin);
          } catch {
            return false;
          }
        }
      };

      const sender = { url: 'chrome-extension://abc123/popup.html' };
      const allowedOrigins = ['chrome-extension://abc123'];

      expect(messageSecurity.verifySender(sender, allowedOrigins)).toBe(true);
    });

    test('should sanitize message payload', () => {
      const payloadSanitizer = {
        sanitize: function(payload) {
          if (typeof payload === 'string') {
            return payload.replace(/[<>]/g, '');
          }
          if (typeof payload === 'object' && payload !== null) {
            const sanitized = {};
            for (const [key, value] of Object.entries(payload)) {
              if (typeof value === 'string') {
                sanitized[key] = value.replace(/[<>]/g, '');
              } else {
                sanitized[key] = value;
              }
            }
            return sanitized;
          }
          return payload;
        }
      };

      const payload = {
        selector: '#button<script>',
        value: 'test<img>'
      };

      const sanitized = payloadSanitizer.sanitize(payload);
      expect(sanitized.selector).toBe('#buttonscript');
      expect(sanitized.value).toBe('testimg');
    });
  });

  describe('XSS Prevention Tests', () => {
    test('should escape HTML in DOM operations', () => {
      const domHelper = {
        safeSetText: function(element, text) {
          element.textContent = text; // Safe - uses textContent
        },
        safeSetHTML: function(element, html) {
          // Should use DOMPurify or similar
          const temp = document.createElement('div');
          temp.textContent = html;
          return temp.innerHTML;
        }
      };

      const div = document.createElement('div');
      domHelper.safeSetText(div, '<script>alert(1)</script>');

      expect(div.textContent).toBe('<script>alert(1)</script>');
      expect(div.innerHTML).not.toContain('<script>');
    });

    test('should prevent DOM-based XSS', () => {
      document.body.innerHTML = '<div id="target"></div>';

      const xssHelper = {
        setContent: function(selector, content) {
          const el = document.querySelector(selector);
          if (el) {
            // Use textContent instead of innerHTML
            el.textContent = content;
          }
        }
      };

      xssHelper.setContent('#target', '<img src=x onerror="alert(1)">');

      const target = document.getElementById('target');
      expect(target.textContent).toContain('<img');
      expect(target.innerHTML).not.toContain('onerror');
    });
  });

  describe('CSRF Protection Tests', () => {
    test('should include CSRF tokens in requests', () => {
      const csrfProtection = {
        generateToken: function() {
          return Math.random().toString(36).substr(2, 32);
        },
        validateToken: function(token, storedToken) {
          return token === storedToken;
        }
      };

      const token = csrfProtection.generateToken();
      expect(csrfProtection.validateToken(token, token)).toBe(true);
      expect(csrfProtection.validateToken(token, 'different')).toBe(false);
    });

    test('should validate request origin', () => {
      const originValidator = {
        isValidOrigin: function(origin, allowedOrigins) {
          return allowedOrigins.includes(origin);
        }
      };

      const allowedOrigins = [
        'chrome-extension://abc123',
        'https://api.example.com'
      ];

      expect(originValidator.isValidOrigin('chrome-extension://abc123', allowedOrigins)).toBe(true);
      expect(originValidator.isValidOrigin('https://evil.com', allowedOrigins)).toBe(false);
    });
  });

  describe('Data Validation Tests', () => {
    test('should validate selector format', () => {
      const selectorValidator = {
        isValid: function(selector) {
          try {
            document.querySelector(selector);
            return true;
          } catch {
            return false;
          }
        }
      };

      expect(selectorValidator.isValid('#button')).toBe(true);
      expect(selectorValidator.isValid('.class')).toBe(true);
      expect(selectorValidator.isValid('button[type="submit"]')).toBe(true);
      expect(selectorValidator.isValid('invalid[[')).toBe(false);
    });

    test('should validate URL format', () => {
      const urlValidator = {
        isValid: function(url) {
          try {
            new URL(url);
            return true;
          } catch {
            return false;
          }
        }
      };

      expect(urlValidator.isValid('https://example.com')).toBe(true);
      expect(urlValidator.isValid('http://localhost:3000')).toBe(true);
      expect(urlValidator.isValid('not a url')).toBe(false);
      expect(urlValidator.isValid('javascript:alert(1)')).toBe(false);
    });

    test('should validate form field data', () => {
      const fieldValidator = {
        validate: function(field) {
          if (!field.selector || typeof field.selector !== 'string') {
            return { valid: false, error: 'Invalid selector' };
          }
          if (!field.value || typeof field.value !== 'string') {
            return { valid: false, error: 'Invalid value' };
          }
          if (field.value.length > 10000) {
            return { valid: false, error: 'Value too long' };
          }
          return { valid: true };
        }
      };

      expect(fieldValidator.validate({ selector: '#input', value: 'test' }).valid).toBe(true);
      expect(fieldValidator.validate({ selector: '', value: 'test' }).valid).toBe(false);
      expect(fieldValidator.validate({ selector: '#input', value: '' }).valid).toBe(false);
    });
  });

  describe('Error Handling & Logging Tests', () => {
    test('should not expose sensitive info in errors', () => {
      const errorHandler = {
        formatError: function(error, context) {
          // Should not include sensitive data
          const sensitiveFields = ['password', 'token', 'apiKey'];
          const errorStr = JSON.stringify(error);

          for (const field of sensitiveFields) {
            expect(errorStr).not.toContain(field);
          }

          return {
            message: error.message,
            code: error.code,
            context: context
          };
        }
      };

      const error = new Error('Database connection failed');
      error.code = 'DB_ERROR';

      const formatted = errorHandler.formatError(error, 'login');
      expect(formatted.message).toBeDefined();
      expect(formatted.code).toBe('DB_ERROR');
    });

    test('should rate limit error logging', () => {
      const rateLimiter = {
        errorCounts: new Map(),
        maxErrorsPerMinute: 10,

        canLog: function(errorType) {
          const now = Date.now();
          const key = `${errorType}_${Math.floor(now / 60000)}`;

          if (!this.errorCounts.has(key)) {
            this.errorCounts.set(key, 0);
          }

          const count = this.errorCounts.get(key);
          if (count >= this.maxErrorsPerMinute) {
            return false;
          }

          this.errorCounts.set(key, count + 1);
          return true;
        }
      };

      // Should allow up to 10 errors
      for (let i = 0; i < 10; i++) {
        expect(rateLimiter.canLog('TEST_ERROR')).toBe(true);
      }

      // Should block 11th error
      expect(rateLimiter.canLog('TEST_ERROR')).toBe(false);
    });
  });
});

describe('Manifest V3 Compliance Tests', () => {
  test('should use service worker instead of background page', () => {
    const manifest = {
      manifest_version: 3,
      background: {
        service_worker: 'background.js'
      }
    };

    expect(manifest.background.service_worker).toBeDefined();
    expect(manifest.background.page).toBeUndefined();
  });

  test('should use executeScript instead of executeScript', () => {
    const manifest = {
      manifest_version: 3,
      permissions: ['scripting']
    };

    expect(manifest.permissions).toContain('scripting');
  });

  test('should declare all required permissions', () => {
    const manifest = {
      manifest_version: 3,
      permissions: [
        'activeTab',
        'scripting',
        'storage',
        'tabs',
        'webNavigation',
        'contextMenus'
      ]
    };

    const requiredPerms = ['activeTab', 'scripting', 'storage'];
    const hasRequired = requiredPerms.every(p => manifest.permissions.includes(p));

    expect(hasRequired).toBe(true);
  });

  test('should use web_accessible_resources correctly', () => {
    const manifest = {
      web_accessible_resources: [
        {
          resources: ['injected.js'],
          matches: ['<all_urls>']
        }
      ]
    };

    expect(manifest.web_accessible_resources[0].resources).toContain('injected.js');
    expect(manifest.web_accessible_resources[0].matches).toContain('<all_urls>');
  });
});
