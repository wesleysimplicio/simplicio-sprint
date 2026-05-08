import { defineConfig, devices } from '@playwright/test';

/**
 * Configuração Playwright do SendSprint.
 *
 * Contexto: o SendSprint usa Playwright primariamente como transport fallback
 * dos operators Jira/ADO via lib Python (`playwright.sync_api`). Esta config TS
 * existe para o gate DoD (`.github/workflows/dod.yml`) e para qualquer suite
 * de browser smoke test futura. Specs Python ficam em `tests/e2e/test_*.py`
 * e usam `pytest-playwright`.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /.*\.(spec|test)\.(ts|js)$/,
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  outputDir: 'test-results/',
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/results.xml' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.BASE_URL,
    trace: 'on',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
