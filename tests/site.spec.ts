import { expect, test } from '@playwright/test';

test('renders stats, map and complete country table', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: /One day/i })).toBeVisible();
  await expect(page.locator('#walk-map')).toBeVisible();
  await expect(page.locator('.walk-marker')).toHaveCount(100);
  await expect(page.locator('#visible-list-count')).toHaveText('100');
  await expect(page.locator('#countries tbody tr')).toHaveCount(19);
  await expect(page.locator('footer')).toContainText(/not an official/i);

  await page.locator('.walk-place').first().click();
  await expect(page.locator('#country-filter')).toHaveValue('all');
  await expect(page.locator('.walk-marker')).toHaveCount(100);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  for (const selector of ['#country-filter', '#reset-map', '#walk-search', '.walk-card a']) {
    const box = await page.locator(selector).first().boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(errors).toEqual([]);
});

test('filters map and searches walk directory', async ({ page }) => {
  await page.goto('/');
  await page.locator('#country-filter').selectOption('Australia');
  await expect(page.locator('#visible-map-count')).toHaveText('19');
  await expect(page.locator('.walk-marker')).toHaveCount(19);
  await expect(page.locator('#visible-list-count')).toHaveText('19');

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
