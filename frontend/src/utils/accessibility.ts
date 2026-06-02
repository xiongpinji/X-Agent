/**
 * Accessibility Utilities
 *
 * WCAG 2.1 AA compliance helpers
 */

export interface AccessibilityOptions {
  ariaLabel?: string
  ariaDescribedBy?: string
  ariaLabelledBy?: string
  role?: string
  tabIndex?: number
}

/**
 * Generate unique ID for accessibility attributes
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Check color contrast ratio (WCAG 2.1)
 * Returns true if contrast ratio meets AA standard (4.5:1 for normal text)
 */
export function checkContrast(foreground: string, background: string): boolean {
  const fgLuminance = getLuminance(foreground)
  const bgLuminance = getLuminance(background)

  const lighter = Math.max(fgLuminance, bgLuminance)
  const darker = Math.min(fgLuminance, bgLuminance)

  const contrast = (lighter + 0.05) / (darker + 0.05)
  return contrast >= 4.5 // AA standard for normal text
}

/**
 * Calculate relative luminance (WCAG 2.1)
 */
function getLuminance(color: string): number {
  const rgb = hexToRgb(color)
  if (!rgb) return 0

  const [r, g, b] = rgb.map((c) => {
    c = c / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  })

  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/**
 * Convert hex color to RGB
 */
function hexToRgb(hex: string): [number, number, number] | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)]
    : null
}

/**
 * Keyboard navigation helpers
 */
export const KeyCode = {
  ENTER: 'Enter',
  SPACE: ' ',
  ESCAPE: 'Escape',
  ARROW_UP: 'ArrowUp',
  ARROW_DOWN: 'ArrowDown',
  ARROW_LEFT: 'ArrowLeft',
  ARROW_RIGHT: 'ArrowRight',
  TAB: 'Tab',
  HOME: 'Home',
  END: 'End',
  PAGE_UP: 'PageUp',
  PAGE_DOWN: 'PageDown',
} as const

/**
 * Check if key is navigation key
 */
export function isNavigationKey(key: string): boolean {
  return [
    KeyCode.ARROW_UP,
    KeyCode.ARROW_DOWN,
    KeyCode.ARROW_LEFT,
    KeyCode.ARROW_RIGHT,
    KeyCode.HOME,
    KeyCode.END,
    KeyCode.PAGE_UP,
    KeyCode.PAGE_DOWN,
  ].includes(key as any)
}

/**
 * Check if key is activation key
 */
export function isActivationKey(key: string): boolean {
  return [KeyCode.ENTER, KeyCode.SPACE].includes(key as any)
}

/**
 * Announce message to screen readers
 */
export function announceToScreenReader(
  message: string,
  priority: 'polite' | 'assertive' = 'polite'
): void {
  const announcement = document.createElement('div')
  announcement.setAttribute('role', 'status')
  announcement.setAttribute('aria-live', priority)
  announcement.setAttribute('aria-atomic', 'true')
  announcement.className = 'sr-only'
  announcement.textContent = message

  document.body.appendChild(announcement)

  // Remove after announcement
  setTimeout(() => {
    document.body.removeChild(announcement)
  }, 1000)
}

/**
 * Focus management utilities
 */
export class FocusManager {
  private previousActiveElement: Element | null = null

  /**
   * Save current focus
   */
  saveFocus(): void {
    this.previousActiveElement = document.activeElement
  }

  /**
   * Restore previous focus
   */
  restoreFocus(): void {
    if (this.previousActiveElement instanceof HTMLElement) {
      this.previousActiveElement.focus()
    }
  }

  /**
   * Focus element with optional scroll
   */
  focusElement(element: HTMLElement, scroll: boolean = true): void {
    if (scroll) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    element.focus()
  }

  /**
   * Get focusable elements within container
   */
  getFocusableElements(container: HTMLElement): HTMLElement[] {
    const selector = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(',')

    return Array.from(container.querySelectorAll(selector))
  }

  /**
   * Trap focus within container
   */
  trapFocus(container: HTMLElement, event: KeyboardEvent): void {
    if (event.key !== KeyCode.TAB) return

    const focusableElements = this.getFocusableElements(container)
    if (focusableElements.length === 0) return

    const firstElement = focusableElements[0] as HTMLElement
    const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement
    const activeElement = document.activeElement

    if (event.shiftKey) {
      if (activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      }
    } else {
      if (activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }
  }
}

/**
 * ARIA attributes builder
 */
export class AriaBuilder {
  private attributes: Record<string, string | boolean | number> = {}

  label(text: string): this {
    this.attributes['aria-label'] = text
    return this
  }

  labelledBy(id: string): this {
    this.attributes['aria-labelledby'] = id
    return this
  }

  describedBy(id: string): this {
    this.attributes['aria-describedby'] = id
    return this
  }

  live(priority: 'polite' | 'assertive' | 'off' = 'polite'): this {
    this.attributes['aria-live'] = priority
    return this
  }

  atomic(value: boolean = true): this {
    this.attributes['aria-atomic'] = value
    return this
  }

  busy(value: boolean = true): this {
    this.attributes['aria-busy'] = value
    return this
  }

  disabled(value: boolean = true): this {
    this.attributes['aria-disabled'] = value
    return this
  }

  expanded(value: boolean): this {
    this.attributes['aria-expanded'] = value
    return this
  }

  hidden(value: boolean = true): this {
    this.attributes['aria-hidden'] = value
    return this
  }

  invalid(value: boolean = true): this {
    this.attributes['aria-invalid'] = value
    return this
  }

  required(value: boolean = true): this {
    this.attributes['aria-required'] = value
    return this
  }

  selected(value: boolean): this {
    this.attributes['aria-selected'] = value
    return this
  }

  checked(value: boolean | 'mixed'): this {
    this.attributes['aria-checked'] = value
    return this
  }

  pressed(value: boolean | 'mixed'): this {
    this.attributes['aria-pressed'] = value
    return this
  }

  role(role: string): this {
    this.attributes['role'] = role
    return this
  }

  build(): Record<string, string | boolean | number> {
    return { ...this.attributes }
  }
}

/**
 * Skip link helper
 */
export function createSkipLink(targetId: string, label: string = 'Skip to main content'): HTMLElement {
  const link = document.createElement('a')
  link.href = `#${targetId}`
  link.textContent = label
  link.className = 'sr-only focus:not-sr-only'
  link.style.position = 'absolute'
  link.style.top = '0'
  link.style.left = '0'
  link.style.zIndex = '9999'
  return link
}

/**
 * Check if element is visible to screen readers
 */
export function isAccessible(element: HTMLElement): boolean {
  const style = window.getComputedStyle(element)
  return (
    style.display !== 'none' &&
    style.visibility !== 'hidden' &&
    style.opacity !== '0' &&
    element.getAttribute('aria-hidden') !== 'true'
  )
}

/**
 * Get accessible name of element (WCAG 2.1)
 */
export function getAccessibleName(element: HTMLElement): string {
  // Check aria-labelledby
  const labelledBy = element.getAttribute('aria-labelledby')
  if (labelledBy) {
    const labels = labelledBy.split(' ').map((id) => document.getElementById(id)?.textContent || '')
    return labels.join(' ')
  }

  // Check aria-label
  const ariaLabel = element.getAttribute('aria-label')
  if (ariaLabel) return ariaLabel

  // Check associated label
  if (element instanceof HTMLInputElement) {
    const label = document.querySelector(`label[for="${element.id}"]`)
    if (label) return label.textContent || ''
  }

  // Check text content
  return element.textContent || ''
}
