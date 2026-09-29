import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    timezoneId: 'Asia/Seoul',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'apps/api/.venv/bin/python scripts/e2e-server.py',
      url: 'http://127.0.0.1:18000/api/health',
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'pnpm --filter @leadflow/web dev --host 127.0.0.1 --port 4173 --strictPort',
      url: 'http://127.0.0.1:4173',
      env: { LEADFLOW_API_URL: 'http://127.0.0.1:18000' },
      reuseExistingServer: false,
    },
    {
      command: 'pnpm --filter @leadflow/admin dev --host 127.0.0.1 --port 4174 --strictPort',
      url: 'http://127.0.0.1:4174',
      env: { LEADFLOW_API_URL: 'http://127.0.0.1:18000' },
      reuseExistingServer: false,
    },
  ],
});
