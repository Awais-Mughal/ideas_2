import { test, expect } from '@playwright/test';

test('app loads successfully', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await expect(page.getByTestId('app-root')).toBeVisible();
});

test('/api/health works', async ({ request }) => {
  const r = await request.get('http://localhost:8000/api/health');
  expect(r.ok()).toBeTruthy();
  expect((await r.json()).status).toBe('ok');
});

test('chart insight popover opens', async ({ page }) => {
  await page.goto('http://localhost:3000');
  const row = page.getByTestId('chart-insight-row').first();
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByTestId('chart-insight-popover')).toBeVisible();
});
