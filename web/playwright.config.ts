import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.PYTHON ?? fileURLToPath(new URL(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python', import.meta.url));

export default defineConfig({
  testDir: './e2e',
  timeout: 35_000,
  retries: 0,
  workers: 1,
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8011', trace: 'retain-on-failure' },
  projects: [ { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
              { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } } ],
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: `"${python}" scripts/fixture_server.py`,
    cwd: root,
    url: 'http://127.0.0.1:8011/healthz',
    reuseExistingServer: !process.env.CI,
  },
});
