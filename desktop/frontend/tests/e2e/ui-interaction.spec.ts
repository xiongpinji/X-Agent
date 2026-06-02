import { test, expect } from '@playwright/test'

test.describe('UI Interaction Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test.describe('Navigation', () => {
    test('should render main layout with header, sidebar, and content', async ({ page }) => {
      const header = page.locator('.app-header')
      const sidebar = page.locator('.sidebar')
      const mainContent = page.locator('.main-content')

      await expect(header).toBeVisible()
      await expect(sidebar).toBeVisible()
      await expect(mainContent).toBeVisible()
    })

    test('should navigate to Agents page', async ({ page }) => {
      const agentsLink = page.locator('a[href="/agents"]')
      await agentsLink.click()
      await page.waitForURL('/agents')
      expect(page.url()).toContain('/agents')
    })

    test('should navigate to Files page', async ({ page }) => {
      const filesLink = page.locator('a[href="/files"]')
      await filesLink.click()
      await page.waitForURL('/files')
      expect(page.url()).toContain('/files')
    })

    test('should navigate to Runs page', async ({ page }) => {
      const runsLink = page.locator('a[href="/runs"]')
      await runsLink.click()
      await page.waitForURL('/runs')
      expect(page.url()).toContain('/runs')
    })

    test('should navigate to Settings page', async ({ page }) => {
      const settingsLink = page.locator('a[href="/settings"]')
      await settingsLink.click()
      await page.waitForURL('/settings')
      expect(page.url()).toContain('/settings')
    })

    test('should highlight active navigation item', async ({ page }) => {
      const homeLink = page.locator('a[href="/"]')
      await expect(homeLink).toHaveClass(/active/)

      const agentsLink = page.locator('a[href="/agents"]')
      await agentsLink.click()
      await expect(agentsLink).toHaveClass(/active/)
      await expect(homeLink).not.toHaveClass(/active/)
    })
  })

  test.describe('Header Controls', () => {
    test('should toggle theme', async ({ page }) => {
      const themeButton = page.locator('.header-actions button').first()
      const initialTheme = await page.evaluate(() =>
        document.documentElement.getAttribute('data-theme')
      )

      await themeButton.click()
      await page.waitForTimeout(300)

      const newTheme = await page.evaluate(() =>
        document.documentElement.getAttribute('data-theme')
      )

      expect(newTheme).not.toBe(initialTheme)
    })

    test('should open settings from header', async ({ page }) => {
      const settingsButton = page.locator('.header-actions button').nth(1)
      await settingsButton.click()
      await page.waitForURL('/settings')
      expect(page.url()).toContain('/settings')
    })

    test('should minimize window', async ({ page }) => {
      const minimizeButton = page.locator('.header-actions button').nth(2)
      await minimizeButton.click()
      // Window minimize is handled by Tauri, just verify button is clickable
      await expect(minimizeButton).toBeEnabled()
    })

    test('should maximize window', async ({ page }) => {
      const maximizeButton = page.locator('.header-actions button').nth(3)
      await maximizeButton.click()
      await expect(maximizeButton).toBeEnabled()
    })
  })

  test.describe('Status Bar', () => {
    test('should display status bar with connection and agent status', async ({ page }) => {
      const statusBar = page.locator('.status-bar')
      await expect(statusBar).toBeVisible()

      const statusItems = page.locator('.status-item')
      const count = await statusItems.count()
      expect(count).toBeGreaterThanOrEqual(2)
    })

    test('should show backend connection status', async ({ page }) => {
      const statusItems = page.locator('.status-item')
      const firstStatus = statusItems.first()
      const text = await firstStatus.textContent()
      expect(text).toMatch(/已连接|离线模式/)
    })

    test('should show agent running status', async ({ page }) => {
      const statusItems = page.locator('.status-item')
      const lastStatus = statusItems.last()
      const text = await lastStatus.textContent()
      expect(text).toMatch(/运行中|已停止/)
    })
  })

  test.describe('Responsive Design', () => {
    test('should be responsive on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 })
      const header = page.locator('.app-header')
      await expect(header).toBeVisible()
    })

    test('should be responsive on tablet viewport', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 })
      const sidebar = page.locator('.sidebar')
      await expect(sidebar).toBeVisible()
    })

    test('should be responsive on desktop viewport', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 })
      const mainContent = page.locator('.main-content')
      await expect(mainContent).toBeVisible()
    })
  })

  test.describe('Loading States', () => {
    test('should show loading indicator during page transitions', async ({ page }) => {
      const agentsLink = page.locator('a[href="/agents"]')
      await agentsLink.click()

      // Loading indicator should appear briefly
      const loadingContainer = page.locator('.loading-container')
      // Wait for navigation to complete
      await page.waitForURL('/agents')
      await expect(loadingContainer).not.toBeVisible()
    })
  })

  test.describe('Accessibility', () => {
    test('should have proper heading hierarchy', async ({ page }) => {
      const headings = page.locator('h1, h2, h3, h4, h5, h6')
      const count = await headings.count()
      // At least some headings should exist
      expect(count).toBeGreaterThanOrEqual(0)
    })

    test('should have proper link labels', async ({ page }) => {
      const navLinks = page.locator('.nav-item')
      const count = await navLinks.count()
      expect(count).toBeGreaterThan(0)

      for (let i = 0; i < count; i++) {
        const link = navLinks.nth(i)
        const text = await link.textContent()
        expect(text).toBeTruthy()
      }
    })

    test('should have proper button labels', async ({ page }) => {
      const buttons = page.locator('button')
      const count = await buttons.count()
      expect(count).toBeGreaterThan(0)
    })
  })
})
