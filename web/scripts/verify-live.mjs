// Explicit live smoke test: env credentials stay out of source, output, screenshots and URLs.
import { chromium, devices } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const base = process.env.URJA_BASE_URL ?? 'http://127.0.0.1:8000';
const token = process.env.URJA_DEMO_TOKEN;
if (!token) throw new Error('Set URJA_DEMO_TOKEN to run the explicit live check.');
const auth = { Authorization: `Bearer ${token}` };
const health = await fetch(`${base}/healthz`);
assert.equal(health.status, 200);
assert.equal((await fetch(`${base}/api/v1/meters`)).status, 401);
const catalogue = await (
  await fetch(`${base}/api/v1/meters?page_size=1`, { headers: auth })
).json();
assert.ok(catalogue.data.total > 0);
const meterId = process.env.URJA_TEST_METER ?? 'J100004';
const energyResponse = await fetch(`${base}/api/v1/meters/${meterId}/consumption`, {
  headers: auth,
});
assert.equal(energyResponse.status, 200);
const energy = await energyResponse.json();
assert.ok(energy.data.readings.length > 0);
const output = new URL('../../artifacts/', import.meta.url);
await mkdir(output, { recursive: true });
const evidence = {
  base,
  verified_at: new Date().toISOString(),
  catalogue_total: catalogue.data.total,
  meter: meterId,
  readings: energy.data.readings.length,
  browsers: [],
};
const browser = await chromium.launch();
try {
  for (const device of ['desktop', 'mobile']) {
    const context = await browser.newContext(
      device === 'mobile'
        ? { ...devices['iPhone 13'] }
        : { viewport: { width: 1440, height: 1000 } },
    );
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(base);
    await page.getByLabel('Demo access token').fill(token);
    await page.getByRole('button', { name: 'Open workspace' }).click();
    await page.getByRole('heading', { name: 'Meter directory.' }).waitFor();
    await page.getByRole('button', { name: 'Next page', exact: true }).click();
    await page.getByRole('button', { name: 'J100020', exact: true }).waitFor();
    await page.getByLabel('Search meters').fill(meterId);
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.getByRole('button', { name: meterId, exact: true }).click();
    await page.getByRole('img', { name: 'Cumulative kWh register readings over time' }).waitFor();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: new URL(`${device}-live-profile.png`, output).pathname.replace(/^\/([A-Za-z]:)/, '$1'),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Network explorer', exact: true }).click();
    await page.locator('.tree-toggle:enabled').first().click();
    await page.locator('.tree-children .tree-row').first().waitFor();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: new URL(`${device}-live-network.png`, output).pathname.replace(/^\/([A-Za-z]:)/, '$1'),
      fullPage: true,
    });
    await page.locator('.tree-row .text-button').first().click();
    await page.locator('.meter-id').first().waitFor();
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
      true,
    );
    assert.deepEqual(errors, []);
    await page
      .getByRole('button', { name: 'Sign out', exact: true })
      .filter({ visible: true })
      .click();
    await page.getByLabel('Demo access token').waitFor();
    assert.equal(
      await page.evaluate(
        () => Object.keys(localStorage).length + Object.keys(sessionStorage).length,
      ),
      0,
    );
    evidence.browsers.push({ device, passed: true });
    await context.close();
  }
} finally {
  await browser.close();
}
await writeFile(new URL('live-evidence.json', output), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify(evidence));
