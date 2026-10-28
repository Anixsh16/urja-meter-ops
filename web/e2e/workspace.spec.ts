import { test, expect, type Page } from '@playwright/test';

const token = 'synthetic-test-token-at-least-24-characters';
async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('Demo access token').fill(token);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Meter directory.' })).toBeVisible();
}

test('private access, meter lookup, register chart and sign-out', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await login(page);
  await expect(page.getByRole('button', { name: 'T001', exact: true })).toBeVisible();
  await page.screenshot({ path: `../artifacts/${info.project.name}-directory.png`, fullPage: true });
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.getByRole('button', { name: 'T021', exact: true })).toBeVisible();
  await page.getByLabel('Search meters').fill('SN-001');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Showing 1–1 of 1 meters')).toBeVisible();
  await page.getByRole('button', { name: 'T001', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Energy over time' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Cumulative kWh register readings over time' })).toBeVisible();
  await page.getByText('Inspect 3 source readings').click();
  await expect(page.getByRole('cell', { name: '0', exact: true }).first()).toBeVisible();
  await page.screenshot({ path: `../artifacts/${info.project.name}-profile.png`, fullPage: true });
  await page.getByLabel('From date').fill('2026-07-01');
  await page.getByLabel('To date').fill('2026-07-02');
  await page.getByRole('button', { name: 'Apply dates' }).click();
  await expect(page.getByRole('heading', { name: 'No readings in this window' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).filter({ visible: true }).click();
  await expect(page.getByLabel('Demo access token')).toHaveValue('');
  expect(await page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length)).toBe(0);
  expect(errors).toEqual([]);
});

test('empty search, status filter, hierarchy traversal and network filter', async ({ page }, info) => {
  await login(page);
  await page.getByLabel('Filter by status').selectOption('Faulty');
  await expect(page.getByRole('button', { name: 'T003', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'T001', exact: true })).not.toBeVisible();
  await page.getByLabel('Search meters').fill('missing');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No meters found' })).toBeVisible();
  await page.getByRole('button', { name: 'Network explorer', exact: true }).click();
  await page.getByRole('button', { name: 'Expand Test zone', exact: true }).click();
  await expect(page.getByText('Test circle', { exact: true })).toBeVisible();
  await page.screenshot({ path: `../artifacts/${info.project.name}-network.png`, fullPage: true });
  await page.getByRole('button', { name: 'View meters in Test circle', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Test circle/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'T001', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('wrong token and upstream failure have visible recovery', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Demo access token').fill('wrong');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('alert')).toContainText('valid demo bearer token');
  await page.getByLabel('Demo access token').fill(token);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await page.getByRole('button', { name: 'T003', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable');
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
});
