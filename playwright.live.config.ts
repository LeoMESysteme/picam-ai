import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'live-ui.spec.ts',
  workers: 1,
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'https://127.0.0.1:8767',
    ignoreHTTPSErrors: true,
  },
  webServer: {
    command: 'PYTHONPATH=src ./.venv/bin/python tests/live_ui_server.py',
    url: 'https://127.0.0.1:8767/login',
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
  },
});
