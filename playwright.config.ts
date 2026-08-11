import { defineConfig, devices } from '@playwright/test';

const port = Number((globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.PLAYWRIGHT_PORT ?? 4321);

export default defineConfig({
  testDir: './tests',
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run preview -- --host 127.0.0.1 --port ${port}`,
    port,
    reuseExistingServer: false,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
    { name: 'narrow', use: { ...devices['Desktop Chrome'], viewport: { width: 320, height: 700 }, isMobile: true, hasTouch: true } },
  ],
});
