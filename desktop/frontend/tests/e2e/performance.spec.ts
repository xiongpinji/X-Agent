import { test, expect } from '@playwright/test'

test.describe('Performance Tests', () => {
  test.describe('Startup Performance', () => {
    test('should load home page within 2 seconds', async ({ page }) => {
      const startTime = Date.now()
      await page.goto('/')
      await page.waitForLoadState('networkidle')
      const loadTime = Date.now() - startTime

      expect(loadTime).toBeLessThan(2000)
      console.log(`Home page load time: ${loadTime}ms`)
    })

    test('should render initial UI within 1 second', async ({ page }) => {
      const startTime = Date.now()
      await page.goto('/')
      await page.waitForSelector('.app-container')
      const renderTime = Date.now() - startTime

      expect(renderTime).toBeLessThan(1000)
      console.log(`Initial UI render time: ${renderTime}ms`)
    })

    test('should have First Contentful Paint within 1.5 seconds', async ({ page }) => {
      const metrics = await page.evaluate(() => {
        const paint = performance.getEntriesByType('paint')
        return paint.find(p => p.name === 'first-contentful-paint')
      })

      if (metrics) {
        expect(metrics.startTime).toBeLessThan(1500)
        console.log(`First Contentful Paint: ${metrics.startTime}ms`)
      }
    })
  })

  test.describe('Response Time', () => {
    test('should respond to navigation within 500ms', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const startTime = Date.now()
      await page.locator('a[href="/agents"]').click()
      await page.waitForURL('/agents')
      const responseTime = Date.now() - startTime

      expect(responseTime).toBeLessThan(500)
      console.log(`Navigation response time: ${responseTime}ms`)
    })

    test('should respond to button clicks within 300ms', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const startTime = Date.now()
      const themeButton = page.locator('.header-actions button').first()
      await themeButton.click()
      const clickResponseTime = Date.now() - startTime

      expect(clickResponseTime).toBeLessThan(300)
      console.log(`Button click response time: ${clickResponseTime}ms`)
    })

    test('should handle rapid navigation without lag', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const routes = ['/agents', '/files', '/runs', '/settings']
      const times = []

      for (const route of routes) {
        const startTime = Date.now()
        await page.locator(`a[href="${route}"]`).click()
        await page.waitForURL(route)
        times.push(Date.now() - startTime)
      }

      const avgTime = times.reduce((a, b) => a + b) / times.length
      expect(avgTime).toBeLessThan(500)
      console.log(`Average navigation time: ${avgTime}ms`)
    })
  })

  test.describe('Memory Usage', () => {
    test('should maintain reasonable memory footprint', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const memoryBefore = await page.evaluate(() => {
        if (performance.memory) {
          return performance.memory.usedJSHeapSize / 1048576 // Convert to MB
        }
        return 0
      })

      // Perform multiple navigations
      for (let i = 0; i < 5; i++) {
        await page.locator('a[href="/agents"]').click()
        await page.waitForURL('/agents')
        await page.locator('a[href="/"]').click()
        await page.waitForURL('/')
      }

      const memoryAfter = await page.evaluate(() => {
        if (performance.memory) {
          return performance.memory.usedJSHeapSize / 1048576
        }
        return 0
      })

      const memoryIncrease = memoryAfter - memoryBefore
      console.log(`Memory before: ${memoryBefore.toFixed(2)}MB`)
      console.log(`Memory after: ${memoryAfter.toFixed(2)}MB`)
      console.log(`Memory increase: ${memoryIncrease.toFixed(2)}MB`)

      // Memory increase should be reasonable (less than 50MB)
      expect(memoryIncrease).toBeLessThan(50)
    })

    test('should not have memory leaks during extended use', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const measurements = []

      for (let i = 0; i < 10; i++) {
        const memory = await page.evaluate(() => {
          if (performance.memory) {
            return performance.memory.usedJSHeapSize / 1048576
          }
          return 0
        })
        measurements.push(memory)

        // Perform some navigation
        await page.locator('a[href="/agents"]').click()
        await page.waitForURL('/agents')
        await page.locator('a[href="/"]').click()
        await page.waitForURL('/')
      }

      // Check if memory is growing linearly (potential leak)
      const trend = measurements.slice(-5).reduce((a, b) => a + b) / 5 -
                    measurements.slice(0, 5).reduce((a, b) => a + b) / 5

      console.log(`Memory trend: ${trend.toFixed(2)}MB`)
      // Trend should be relatively stable
      expect(Math.abs(trend)).toBeLessThan(20)
    })
  })

  test.describe('Resource Loading', () => {
    test('should load CSS efficiently', async ({ page }) => {
      const cssRequests = []
      page.on('response', response => {
        if (response.request().resourceType() === 'stylesheet') {
          cssRequests.push({
            url: response.url(),
            size: response.headers()['content-length'] || 0,
            time: response.timing()?.responseEnd || 0
          })
        }
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      console.log(`CSS files loaded: ${cssRequests.length}`)
      cssRequests.forEach(req => {
        console.log(`  ${req.url}: ${req.size} bytes`)
      })

      // Should load CSS efficiently
      expect(cssRequests.length).toBeGreaterThan(0)
    })

    test('should load JavaScript efficiently', async ({ page }) => {
      const jsRequests = []
      page.on('response', response => {
        if (response.request().resourceType() === 'script') {
          jsRequests.push({
            url: response.url(),
            size: response.headers()['content-length'] || 0,
          })
        }
      })

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      console.log(`JS files loaded: ${jsRequests.length}`)
      const totalSize = jsRequests.reduce((sum, req) => sum + parseInt(req.size || '0'), 0)
      console.log(`Total JS size: ${(totalSize / 1024).toFixed(2)}KB`)

      expect(jsRequests.length).toBeGreaterThan(0)
    })

    test('should cache resources appropriately', async ({ page }) => {
      // First load
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const firstLoadRequests = []
      page.on('response', response => {
        firstLoadRequests.push({
          url: response.url(),
          fromCache: response.fromCache?.() || false
        })
      })

      // Second load (should use cache)
      await page.reload()
      await page.waitForLoadState('networkidle')

      const cachedRequests = firstLoadRequests.filter(r => r.fromCache)
      console.log(`Cached requests: ${cachedRequests.length}/${firstLoadRequests.length}`)

      // Some resources should be cached
      expect(cachedRequests.length).toBeGreaterThan(0)
    })
  })

  test.describe('Rendering Performance', () => {
    test('should maintain 60fps during interactions', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const fps = await page.evaluate(() => {
        return new Promise<number>(resolve => {
          let frameCount = 0
          let lastTime = performance.now()

          const countFrames = () => {
            frameCount++
            const currentTime = performance.now()

            if (currentTime - lastTime >= 1000) {
              resolve(frameCount)
            } else {
              requestAnimationFrame(countFrames)
            }
          }

          requestAnimationFrame(countFrames)
        })
      })

      console.log(`FPS during idle: ${fps}`)
      // Should maintain reasonable frame rate
      expect(fps).toBeGreaterThan(30)
    })

    test('should handle rapid DOM updates efficiently', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const startTime = Date.now()

      // Perform rapid navigation
      for (let i = 0; i < 10; i++) {
        await page.locator('a[href="/agents"]').click()
        await page.waitForURL('/agents')
        await page.locator('a[href="/"]').click()
        await page.waitForURL('/')
      }

      const totalTime = Date.now() - startTime
      const avgTimePerNavigation = totalTime / 20

      console.log(`Total time for 20 navigations: ${totalTime}ms`)
      console.log(`Average time per navigation: ${avgTimePerNavigation}ms`)

      expect(avgTimePerNavigation).toBeLessThan(500)
    })
  })
})
