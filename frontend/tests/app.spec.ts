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

test('search input and stock header render', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.getByTestId('header-search').fill('AAPL');
  await expect(page.getByTestId('stock-header')).toBeVisible();
});

test('chart tabs are clickable', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.getByTestId('chart-range-tab').nth(2).click();
  await expect(page.getByTestId('price-chart')).toBeVisible();
});
