import { test, expect } from '@playwright/test';

/**
 * X-Agent Core E2E Tests
 * Covers: login flow, navigation, dashboard, performance monitor.
 */

const API_KEY = 'xagent-dev-key-2024';

test.describe('Authentication', () => {
  test('login page renders', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1, h2, form')).first().toBeVisible();
  });

  test('API key login navigates to dashboard', async ({ page }) => {
    await page.goto('/login');
    // Switch to API Key mode if button exists
    const apiKeyBtn = page.getByText(/API Key/i);
    if (await apiKeyBtn.isVisible()) {
      await apiKeyBtn.click();
      await page.fill('input[type="password"], input[type="text"]', API_KEY);
      await page.click('button[type="submit"]');
      await page.waitForURL('**/', { timeout: 5000 });
    }
  });
});

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Inject auth state
    await page.goto('/login');
    await page.evaluate((key) => {
      localStorage.setItem('api_key', key);
      const store = JSON.parse(localStorage.getItem('app-store') || '{}');
      store.state = { ...store.state, isAuthenticated: true, user: { id: 'e2e', username: 'e2e' } };
      localStorage.setItem('app-store', JSON.stringify(store));
    }, API_KEY);
    await page.goto('/');
  });

  test('dashboard loads', async ({ page }) => {
    await expect(page.locator('body')).not.toBeEmpty();
    await page.waitForTimeout(1000);
  });

  test('performance monitor page loads', async ({ page }) => {
    await page.goto('/performance');
    await expect(page.getByText('Performance Monitor')).toBeVisible({ timeout: 5000 });
  });

  test('agents page loads', async ({ page }) => {
    await page.goto('/agents');
    await page.waitForTimeout(1000);
    await expect(page.locator('body')).not.toBeEmpty();
  });
});

test.describe('Performance Monitor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate((key) => {
      localStorage.setItem('api_key', key);
      const store = JSON.parse(localStorage.getItem('app-store') || '{}');
      store.state = { ...store.state, isAuthenticated: true, user: { id: 'e2e', username: 'e2e' } };
      localStorage.setItem('app-store', JSON.stringify(store));
    }, API_KEY);
  });

  test('displays metric cards', async ({ page }) => {
    await page.goto('/performance');
    await page.waitForTimeout(2000);
    // Should have CPU card
    const cpuCard = page.getByText('CPU');
    await expect(cpuCard.first()).toBeVisible({ timeout: 5000 });
  });
});
