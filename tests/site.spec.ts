import { expect, test } from '@playwright/test';

test('renders stats, map and complete country table', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Global walk dashboard/i })).toBeVisible();
  await expect(page.locator('#walk-map')).toBeVisible();
  const totalWalks = Number(await page.locator('#visible-map-count').textContent());
  expect(totalWalks).toBeGreaterThan(0);
  await expect(page.locator('.walk-marker')).toHaveCount(totalWalks);
  await expect(page.locator('#visible-list-count')).toHaveText(String(totalWalks));
  await expect(page.locator('.walk-card:not([hidden])')).toHaveCount(20);
  await page.locator('#show-more').click();
  await expect(page.locator('.walk-card:not([hidden])')).toHaveCount(40);
  expect(await page.locator('#countries tbody tr').count()).toBeGreaterThan(0);
  await expect(page.locator('footer')).toContainText(/not an official/i);

  await page.locator('.walk-place').first().click();
  await expect(page.locator('#country-filter')).toHaveValue('all');
  await expect(page.locator('.walk-marker')).toHaveCount(totalWalks);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  for (const selector of ['#country-filter', '#reset-map', '#walk-search', '#show-more', '.walk-card a']) {
    const box = await page.locator(selector).first().boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(errors).toEqual([]);
});

test('mouse wheel over map zooms the map without scrolling the page', async ({ page }) => {
  await page.goto('/');
  const map = page.locator('#walk-map');
  await map.scrollIntoViewIfNeeded();
  await map.hover();
  const beforeZoom = await map.getAttribute('data-zoom');
  const beforeScroll = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, -120);
  await expect.poll(() => map.getAttribute('data-zoom')).not.toBe(beforeZoom);
  const afterScroll = await page.evaluate(() => window.scrollY);
  expect(Math.abs(afterScroll - beforeScroll)).toBeLessThanOrEqual(2);

  const beforeLineModeZoom = await map.getAttribute('data-zoom');
  await map.dispatchEvent('wheel', { deltaY: 3, deltaMode: 1, bubbles: true, cancelable: true });
  await expect.poll(() => map.getAttribute('data-zoom')).not.toBe(beforeLineModeZoom);
});

test('filters map and searches walk directory', async ({ page }) => {
  await page.goto('/');
  await page.locator('#country-filter').selectOption('Australia');
  const australiaWalks = Number(await page.locator('#visible-map-count').textContent());
  expect(australiaWalks).toBeGreaterThan(0);
  await expect(page.locator('.walk-marker')).toHaveCount(australiaWalks);
  await expect(page.locator('#visible-list-count')).toHaveText(String(australiaWalks));

  await page.locator('#walk-search').fill('Dayboro');
  await expect(page.locator('#visible-list-count')).toHaveText('1');
  await expect(page.locator('.walk-card:not([hidden]) h3')).toHaveText('Dayboro');
});

test('captures the canonical review page', async ({ page }, testInfo) => {
  await page.goto('/');
  await page.screenshot({ path: `artifacts/${testInfo.project.name}-home.png`, fullPage: true });
});

test('marker popup links to the official event listing', async ({ page }) => {
  await page.goto('/');
  await page.locator('#country-filter').selectOption('Japan');
  await expect(page.locator('.walk-marker-wrap')).toHaveCount(1);
  await page.locator('.walk-marker-wrap').click();
  const link = page.locator('.map-popup a');
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', /^https:\/\/greatglobalgreyhoundwalk\.co\.uk\/walks\//);
});
