import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'docs-site.spec.ts',
  // Auf dem Pi teilt sich die CI die CPU mit Werkbank und Messläufen, und der
  // Runner läuft gedrosselt. Zeitkritische Tests reißen dort vereinzelt; ein
  // Wiederholungsversuch fängt das ab, der Bericht führt sie als „flaky“.
  retries: process.env.CI ? 1 : 0,
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8766' },
  webServer: {
    command: 'python3 -m http.server 8766 --bind 127.0.0.1 --directory site',
    url: 'http://127.0.0.1:8766',
    reuseExistingServer: !process.env.CI,
  },
});
