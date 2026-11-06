import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'live-ui.spec.ts',
  workers: 1,
  // Der Pi-Runner wird gedrosselt; die Suite prueft 0,5-s- und 1,5-s-Grenzen. Lokal ohne Wiederholung.
  retries: process.env.CI ? 1 : 0,
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
