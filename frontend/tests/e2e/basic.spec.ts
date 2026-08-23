import { test, expect } from '@playwright/test';

test('has title and dashboard elements', async ({ page }) => {
  // Simple navigation check. In E2E tests we can check page elements
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('Autonomous Recovery Platform');
  await expect(page.getByText('API Gateway')).toBeVisible();
});
