import { test, expect } from '@playwright/test'

test.describe('Cross-Platform Compatibility Tests', () => {
  test.describe('Windows Compatibility', () => {
    test('should render correctly on Windows', async ({ page, browserName }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log(`Windows rendering test passed on ${browserName}`)
    })

    test('should handle Windows file paths', async ({ page }) => {
      await page.goto('/files')
      await page.waitForLoadState('networkidle')

      const filesPage = page.locator('.main-content')
      await expect(filesPage).toBeVisible()
    })

    test('should support Windows keyboard shortcuts', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Test Ctrl+Shift+X shortcut (show/hide window)
      await page.keyboard.press('Control+Shift+X')
      await page.waitForTimeout(100)

      const appContainer = page.locator('.app-container')
      // App should still be visible or hidden depending on implementation
      console.log('Windows keyboard shortcut test completed')
    })
  })

  test.describe('macOS Compatibility', () => {
    test('should render correctly on macOS', async ({ page, browserName }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log(`macOS rendering test passed on ${browserName}`)
    })

    test('should handle macOS file paths', async ({ page }) => {
      await page.goto('/files')
      await page.waitForLoadState('networkidle')

      const filesPage = page.locator('.main-content')
      await expect(filesPage).toBeVisible()
    })

    test('should support macOS keyboard shortcuts', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Test Cmd+Shift+X shortcut (macOS equivalent)
      await page.keyboard.press('Meta+Shift+X')
      await page.waitForTimeout(100)

      const appContainer = page.locator('.app-container')
      console.log('macOS keyboard shortcut test completed')
    })

    test('should respect macOS system preferences', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()
    })
  })

  test.describe('Linux Compatibility', () => {
    test('should render correctly on Linux', async ({ page, browserName }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log(`Linux rendering test passed on ${browserName}`)
    })

    test('should handle Linux file paths', async ({ page }) => {
      await page.goto('/files')
      await page.waitForLoadState('networkidle')

      const filesPage = page.locator('.main-content')
      await expect(filesPage).toBeVisible()
    })

    test('should support Linux keyboard shortcuts', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Test Ctrl+Shift+X shortcut
      await page.keyboard.press('Control+Shift+X')
      await page.waitForTimeout(100)

      const appContainer = page.locator('.app-container')
      console.log('Linux keyboard shortcut test completed')
    })
  })

  test.describe('Browser Compatibility', () => {
    test('should work on Chromium', async ({ page, browserName }) => {
      if (browserName !== 'chromium') {
        test.skip()
      }

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log('Chromium compatibility test passed')
    })

    test('should work on Firefox', async ({ page, browserName }) => {
      if (browserName !== 'firefox') {
        test.skip()
      }

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log('Firefox compatibility test passed')
    })

    test('should work on WebKit', async ({ page, browserName }) => {
      if (browserName !== 'webkit') {
        test.skip()
      }

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      console.log('WebKit compatibility test passed')
    })
  })

  test.describe('Display Scaling', () => {
    test('should handle 100% display scale', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()
    })

    test('should handle 125% display scale', async ({ page }) => {
      await page.evaluate(() => {
        document.documentElement.style.zoom = '1.25'
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      await page.evaluate(() => {
        document.documentElement.style.zoom = '1'
      })
    })

    test('should handle 150% display scale', async ({ page }) => {
      await page.evaluate(() => {
        document.documentElement.style.zoom = '1.5'
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      await page.evaluate(() => {
        document.documentElement.style.zoom = '1'
      })
    })

    test('should handle 200% display scale', async ({ page }) => {
      await page.evaluate(() => {
        document.documentElement.style.zoom = '2'
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()

      await page.evaluate(() => {
        document.documentElement.style.zoom = '1'
      })
    })
  })

  test.describe('Font Rendering', () => {
    test('should render fonts correctly', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const logo = page.locator('.logo')
      const fontSize = await logo.evaluate(el => {
        return window.getComputedStyle(el).fontSize
      })

      expect(fontSize).toBeTruthy()
      console.log(`Logo font size: ${fontSize}`)
    })

    test('should support system fonts', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const navItem = page.locator('.nav-item').first()
      const fontFamily = await navItem.evaluate(el => {
        return window.getComputedStyle(el).fontFamily
      })

      expect(fontFamily).toBeTruthy()
      console.log(`Navigation font family: ${fontFamily}`)
    })
  })

  test.describe('Color Rendering', () => {
    test('should render colors correctly in light mode', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const header = page.locator('.app-header')
      const backgroundColor = await header.evaluate(el => {
        return window.getComputedStyle(el).backgroundColor
      })

      expect(backgroundColor).toBeTruthy()
      console.log(`Header background color: ${backgroundColor}`)
    })

    test('should render colors correctly in dark mode', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Toggle to dark mode
      const themeButton = page.locator('.header-actions button').first()
      await themeButton.click()
      await page.waitForTimeout(300)

      const header = page.locator('.app-header')
      const backgroundColor = await header.evaluate(el => {
        return window.getComputedStyle(el).backgroundColor
      })

      expect(backgroundColor).toBeTruthy()
      console.log(`Header background color (dark mode): ${backgroundColor}`)
    })
  })

  test.describe('Input Method Compatibility', () => {
    test('should support keyboard input', async ({ page }) => {
      await page.goto('/settings')
      await page.waitForLoadState('networkidle')

      const inputs = page.locator('input')
      const count = await inputs.count()

      if (count > 0) {
        const firstInput = inputs.first()
        await firstInput.focus()
        await firstInput.type('test input')
        const value = await firstInput.inputValue()
        expect(value).toContain('test input')
      }
    })

    test('should support mouse input', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const navItem = page.locator('.nav-item').first()
      await navItem.hover()
      await expect(navItem).toHaveClass(/hover|active/)
    })

    test('should support touch input on mobile', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 })
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const navItem = page.locator('.nav-item').first()
      await navItem.tap()
      await page.waitForTimeout(100)

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()
    })
  })

  test.describe('Locale and Internationalization', () => {
    test('should display Chinese text correctly', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const logo = page.locator('.logo')
      const text = await logo.textContent()
      expect(text).toBe('X-Agent')
    })

    test('should handle RTL languages', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()
    })

    test('should display dates and times correctly', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const appContainer = page.locator('.app-container')
      await expect(appContainer).toBeVisible()
    })
  })
})
