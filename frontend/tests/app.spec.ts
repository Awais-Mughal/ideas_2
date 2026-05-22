import { test, expect } from '@playwright/test';

test('app loads', async ({ page }) => { await page.goto('http://localhost:3000'); await expect(page.getByTestId('app-root')).toBeVisible(); });
test('health works', async ({ request }) => { const r = await request.get('http://localhost:8000/api/health'); expect((await r.json()).status).toBe('ok'); });
