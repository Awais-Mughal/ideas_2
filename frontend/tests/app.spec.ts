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

test('stock endpoint works for AAPL/MSFT/NVDA', async ({ request }) => {
  for (const t of ['AAPL', 'MSFT', 'NVDA']) {
    const r = await request.get(`http://localhost:8000/api/stock/${t}`);
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(d.ticker).toBe(t);
  }
});

test('sentiment percentages sum to 100', async ({ request }) => {
  const r = await request.get('http://localhost:8000/api/stock/AAPL/sentiment');
  expect(r.ok()).toBeTruthy();
  const d = await r.json();
  expect((d.bullish + d.neutral + d.bearish)).toBe(100);
});
