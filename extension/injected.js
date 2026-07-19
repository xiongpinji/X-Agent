/**
 * X-Agent Chrome Extension - Injected Script
 * Runs in page context to access DOM and window objects
 */

(function() {
  'use strict';

  class PageInjector {
    constructor() {
      this.elementRefs = new Map();
      this.refCounter = 0;
    }

    initialize() {
      console.log('[X-Agent Injected] Initializing page script...');

      // Expose API to window for content script access
      window.__xagent = {
        getElementByRef: (refId) => this.getElementByRef(refId),
        getElementInfo: (selector) => this.getElementInfo(selector),
        fillForm: (fields) => this.fillForm(fields),
        clickElement: (selector) => this.clickElement(selector),
        extractPageData: () => this.extractPageData(),
        highlightElements: (selectors, color, duration) => this.highlightElements(selectors, color, duration),
        getPageState: () => this.getPageState(),
        waitForElement: (selector, timeout) => this.waitForElement(selector, timeout),
        executeScript: (code) => this.executeScript(code)
      };

      // Listen for messages from content script
      window.addEventListener('message', (event) => {
        if (event.source !== window) return;
        if (event.data.type && event.data.type.startsWith('XAGENT_')) {
          this.handleMessage(event.data);
        }
      });

      console.log('[X-Agent Injected] Page script initialized');
    }

    handleMessage(message) {
      const { type, id, payload } = message;

      try {
        let result;

        switch (type) {
          case 'XAGENT_GET_ELEMENT_INFO':
            result = this.getElementInfo(payload.selector);
            break;

          case 'XAGENT_FILL_FORM':
            result = this.fillForm(payload.fields);
            break;

          case 'XAGENT_CLICK_ELEMENT':
            result = this.clickElement(payload.selector);
            break;

          case 'XAGENT_EXTRACT_DATA':
            result = this.extractPageData();
            break;

          case 'XAGENT_HIGHLIGHT':
            result = this.highlightElements(payload.selectors, payload.color, payload.duration);
            break;

          case 'XAGENT_GET_STATE':
            result = this.getPageState();
            break;

          case 'XAGENT_WAIT_ELEMENT':
            result = this.waitForElement(payload.selector, payload.timeout);
            break;

          default:
            result = { error: `Unknown message type: ${type}` };
        }

        // Send response back
        window.postMessage({
          type: 'XAGENT_RESPONSE',
          id,
          result
        }, '*');
      } catch (error) {
        window.postMessage({
          type: 'XAGENT_RESPONSE',
          id,
          error: error.message
        }, '*');
      }
    }

    getElementInfo(selector) {
      try {
        const element = document.querySelector(selector);
        if (!element) {
          return { error: 'Element not found' };
        }

        const rect = element.getBoundingClientRect();
        const computedStyle = window.getComputedStyle(element);

        return {
          success: true,
          info: {
            tag: element.tagName,
            id: element.id,
            className: element.className,
            text: element.textContent?.substring(0, 200),
            value: element.value,
            placeholder: element.placeholder,
            type: element.type,
            name: element.name,
            rect: {
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
              x: rect.x,
              y: rect.y
            },
            visible: element.offsetParent !== null,
            disabled: element.disabled,
            readonly: element.readOnly,
            attributes: this.getAttributes(element),
            styles: {
              display: computedStyle.display,
              visibility: computedStyle.visibility,
              opacity: computedStyle.opacity,
              position: computedStyle.position
            }
          }
        };
      } catch (error) {
        return { error: error.message };
      }
    }

    fillForm(fields) {
      try {
        const results = [];

        for (const field of fields) {
          const { selector, value, action = 'set' } = field;

          const element = document.querySelector(selector);
          if (!element) {
            results.push({ selector, success: false, error: 'Element not found' });
            continue;
          }

          // Focus element
          element.focus();

          // Clear if needed
          if (action === 'set' || action === 'replace') {
            element.value = '';
            this.triggerEvent(element, 'input');
            this.triggerEvent(element, 'change');
          }

          // Set value
          if (value !== undefined) {
            element.value = value;
            this.triggerEvent(element, 'input');
            this.triggerEvent(element, 'change');

            // Trigger blur for validation
            element.blur();
          }

          results.push({ selector, success: true });
        }

        return { success: true, results };
      } catch (error) {
        return { error: error.message };
      }
    }

    clickElement(selector) {
      try {
        const element = document.querySelector(selector);
        if (!element) {
          return { error: 'Element not found' };
        }

        // Scroll into view
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Wait for scroll to complete
        setTimeout(() => {
          element.click();
          this.triggerEvent(element, 'click');
        }, 100);

        return { success: true };
      } catch (error) {
        return { error: error.message };
      }
    }

    extractPageData() {
      try {
        const data = {
          url: window.location.href,
          title: document.title,
          text: document.body.innerText,
          html: document.documentElement.outerHTML.substring(0, 50000), // Limit size
          links: [],
          images: [],
          forms: [],
          tables: [],
          metadata: this.extractMetadata(),
          performance: this.getPerformanceData()
        };

        // Extract links
        document.querySelectorAll('a').forEach(link => {
          data.links.push({
            text: link.textContent?.substring(0, 100),
            href: link.href,
            title: link.title
          });
        });

        // Extract images
        document.querySelectorAll('img').forEach(img => {
          data.images.push({
            src: img.src,
            alt: img.alt,
            title: img.title
          });
        });

        // Extract forms
        document.querySelectorAll('form').forEach(form => {
          const fields = [];
          form.querySelectorAll('input, textarea, select').forEach(field => {
            fields.push({
              name: field.name,
              type: field.type,
              value: field.value,
              placeholder: field.placeholder,
              required: field.required
            });
          });

          data.forms.push({
            id: form.id,
            name: form.name,
            action: form.action,
            method: form.method,
            fields
          });
        });

        // Extract tables
        document.querySelectorAll('table').forEach(table => {
          const rows = [];
          table.querySelectorAll('tr').forEach(tr => {
            const cells = [];
            tr.querySelectorAll('td, th').forEach(cell => {
              cells.push(cell.textContent?.trim());
            });
            rows.push(cells);
          });

          data.tables.push({
            id: table.id,
            className: table.className,
            rows
          });
        });

        return { success: true, data };
      } catch (error) {
        return { error: error.message };
      }
    }

    highlightElements(selectors, color = '#FFD700', duration = 3000) {
      try {
        const highlighted = [];

        selectors.forEach(selector => {
          const elements = document.querySelectorAll(selector);
          elements.forEach(el => {
            const originalStyle = el.style.cssText;

            el.style.outline = `3px solid ${color}`;
            el.style.outlineOffset = '2px';
            el.style.backgroundColor = `${color}33`;

            highlighted.push(selector);

            // Auto-remove highlight
            setTimeout(() => {
              el.style.cssText = originalStyle;
            }, duration);
          });
        });

        return { success: true, highlighted: highlighted.length };
      } catch (error) {
        return { error: error.message };
      }
    }

    getPageState() {
      try {
        return {
          success: true,
          state: {
            url: window.location.href,
            title: document.title,
            readyState: document.readyState,
            scrollX: window.scrollX,
            scrollY: window.scrollY,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            documentHeight: document.documentElement.scrollHeight,
            documentWidth: document.documentElement.scrollWidth
          }
        };
      } catch (error) {
        return { error: error.message };
      }
    }

    waitForElement(selector, timeout = 5000) {
      return new Promise((resolve) => {
        const startTime = Date.now();

        const checkElement = () => {
          const element = document.querySelector(selector);
          if (element) {
            resolve({ success: true, found: true });
            return;
          }

          if (Date.now() - startTime > timeout) {
            resolve({ success: false, found: false, error: 'Timeout waiting for element' });
            return;
          }

          setTimeout(checkElement, 100);
        };

        checkElement();
      });
    }

    executeScript(code) {
      try {
        // eslint-disable-next-line no-eval
        const result = eval(code);
        return { success: true, result };
      } catch (error) {
        return { error: error.message };
      }
    }

    triggerEvent(element, eventType) {
      const event = new Event(eventType, { bubbles: true, cancelable: true });
      element.dispatchEvent(event);
    }

    getAttributes(element) {
      const attrs = {};
      for (const attr of element.attributes) {
        attrs[attr.name] = attr.value;
      }
      return attrs;
    }

    extractMetadata() {
      const metadata = {};

      document.querySelectorAll('meta').forEach(meta => {
        const name = meta.getAttribute('name') || meta.getAttribute('property');
        const content = meta.getAttribute('content');
        if (name && content) {
          metadata[name] = content;
        }
      });

      return metadata;
    }

    getPerformanceData() {
      try {
        const perfData = window.performance.timing;
        return {
          navigationStart: perfData.navigationStart,
          loadEventEnd: perfData.loadEventEnd,
          loadTime: perfData.loadEventEnd - perfData.navigationStart,
          domContentLoaded: perfData.domContentLoadedEventEnd - perfData.navigationStart
        };
      } catch (error) {
        return {};
      }
    }

    getElementByRef(refId) {
      return this.elementRefs.get(refId) || null;
    }
  }

  // Initialize injector
  const injector = new PageInjector();
  injector.initialize();

  // Expose for debugging
  window.__xagentInjector = injector;
})();
