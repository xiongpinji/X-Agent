/**
 * Vitest Global Setup
 *
 * Runs before every test file (configured in vitest.config.ts).
 * Provides jest-dom matchers and jsdom-compatible browser API stubs.
 */

import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'

// Unmount React trees between tests (globals: false disables RTL auto-cleanup).
afterEach(() => {
  cleanup()
})

// Mock window.matchMedia (not implemented in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock IntersectionObserver (not implemented in jsdom)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as any

// Mock ResizeObserver (not implemented in jsdom)
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any

// jsdom does not implement EventSource; provide a minimal stub so that
// module-level references (e.g. EventSource.OPEN) do not throw. Individual
// tests may override global.EventSource with their own mocks.
if (typeof global.EventSource === 'undefined') {
  class EventSourceStub {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSED = 2
    readyState = 0
    onopen: ((ev: any) => void) | null = null
    onmessage: ((ev: any) => void) | null = null
    onerror: ((ev: any) => void) | null = null
    addEventListener() {}
    removeEventListener() {}
    close() {}
  }
  global.EventSource = EventSourceStub as any
}

// jsdom does not implement scrollIntoView (used by chat auto-scroll)
Element.prototype.scrollIntoView = vi.fn()

// Suppress noisy console output in tests where it is expected
const originalError = console.error
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render')
    ) {
      return
    }
    originalError.call(console, ...args)
  }
})

afterAll(() => {
  console.error = originalError
})
