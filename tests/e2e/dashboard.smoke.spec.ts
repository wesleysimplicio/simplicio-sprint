/**
 * Smoke E2E for the SendSprint web dashboard.
 *
 * Runs against `BASE_URL` (Expo web `npm run dev` → http://localhost:8081).
 * Skipped when BASE_URL is not set so CI / sandboxes without the dev server
 * stay green. Run locally with:
 *
 *   cd web && npm install && npm run dev &
 *   BASE_URL=http://localhost:8081 npx playwright test
 *
 * Covers Sprint 1 #4–#15 integration sanity: page loads, root shows the
 * provider picker, no JS console errors block render.
 */

import { test, expect, type Page } from '@playwright/test';

const baseUrl = process.env.BASE_URL;

const mockUnconfiguredBackend = async (page: Page) => {
  await page.route(/\/health$/, async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        version: 'test',
        providers_configured: { jira: false, azuredevops: false },
      },
    });
  });

  await page.route(/\/auth\/status$/, async (route) => {
    await route.fulfill({
      json: {
        default_provider: null,
        jira_configured: false,
        azuredevops_configured: false,
        providers: {
          jira: { configured: false, account: null },
          azuredevops: {
            configured: false,
            account: null,
            team_path: null,
            iteration_path: null,
          },
          github: { configured: false },
        },
      },
    });
  });
};

const mockConfiguredDashboardBackend = async (page: Page) => {
  await page.route(/\/health$/, async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        version: '0.20.0',
        providers_configured: { jira: true, azuredevops: false },
      },
    });
  });

  await page.route(/\/auth\/status$/, async (route) => {
    await route.fulfill({
      json: {
        default_provider: 'jira',
        jira_configured: true,
        azuredevops_configured: false,
        providers: {
          jira: { configured: true, account: 'dev@example.com' },
          azuredevops: {
            configured: false,
            account: null,
            team_path: null,
            iteration_path: null,
          },
          github: { configured: false },
        },
      },
    });
  });

  await page.route(/\/api\/runs$/, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.route(/\/api\/dashboard\/validations$/, async (route) => {
    await route.fulfill({
      json: {
        lanes: [],
        total_events: 0,
      },
    });
  });

  await page.route(/\/version\/check$/, async (route) => {
    await route.fulfill({
      json: {
        current_version: '0.20.0',
        latest_version: '0.21.0',
        update_available: true,
        status: 'ok',
        source: 'pypi',
        source_url: 'https://pypi.org/project/sendsprint/',
        message: 'Update available: 0.21.0',
      },
    });
  });
};

const mockUnavailableVersionBackend = async (page: Page) => {
  await mockConfiguredDashboardBackend(page);
  await page.route(/\/version\/check$/, async (route) => {
    await route.fulfill({
      json: {
        current_version: '0.20.0',
        latest_version: null,
        update_available: false,
        status: 'unavailable',
        source: 'pypi',
        source_url: 'https://pypi.org/project/sendsprint/',
        message: 'Could not check PyPI for updates: network blocked',
      },
    });
  });
};

test.describe('SendSprint web dashboard smoke', () => {
  test.skip(!baseUrl, 'BASE_URL not set — skipping E2E smoke (run with web dev server).');

  test('loads root without console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/');
    // Wait for any heading-style text the dashboard renders.
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 15_000 });

    // Filter out noisy Expo dev warnings — only assert on real errors.
    const real = errors.filter(
      (e) => !/dev[- ]bundle|HMR|fast-refresh|expo-router/i.test(e),
    );
    expect(real, `unexpected console errors: ${real.join('\n')}`).toEqual([]);
  });

  test('navigation surface is reachable', async ({ page }) => {
    await page.goto('/');
    // The SendSprint dashboard exposes either an auth screen or a sprints
    // picker depending on the persisted token. Either is acceptable.
    const anchorRegex = /(connect|provider|sprint|jira|azure|sign in|login)/i;
    await expect(page.locator('body')).toContainText(anchorRegex, { timeout: 15_000 });
  });

  test('azure auth flow keeps operator feedback visible', async ({ page }) => {
    await mockUnconfiguredBackend(page);
    await page.goto('/');

    const body = page.locator('body');
    await expect(body).not.toBeEmpty({ timeout: 15_000 });
    await expect(body).toContainText(/backend vtest ok/i);

    const providerLink = page.getByText(/azure devops/i).first();
    if (!(await providerLink.isVisible().catch(() => false))) {
      const connect = page.getByText(/^conectar$|^connect$/i).first();
      if (await connect.isVisible().catch(() => false)) {
        await connect.click();
      }
    }

    await page.getByText(/azure devops/i).first().click();
    await expect(body).toContainText(/sprint url|url da sprint|personal access token|pat/i);

    await page
      .getByLabel(/sprint url|url da sprint/i)
      .or(page.getByPlaceholder(/dev\.azure\.com/i))
      .first()
      .fill('https://dev.azure.com/example/project/_sprints/taskboard/team/project/sprint-1');
    await page.locator('input[type="password"]').fill('example-token');

    await expect(page.getByText(/o pat fica no keyring do so/i)).toBeVisible();
  });

  test('project setup keeps repository routing choices usable', async ({ page }) => {
    await page.goto('/');

    const body = page.locator('body');
    await expect(body).not.toBeEmpty({ timeout: 15_000 });

    const setupLink = page.getByText(/^setup$/i).first();
    await expect(setupLink).toBeVisible();

    await setupLink.click();
    await expect(body).toContainText(/project setup/i);
    await expect(page.getByText(/^single project$/i)).toBeVisible();
    await expect(page.getByText(/^portfolio$/i)).toBeVisible();

    await page.getByLabel(/repository name/i).fill('web-dashboard');
    await page.getByLabel(/local path or remote url/i).fill('C:/workspace/web-dashboard');
    await page.getByLabel(/^project$/i).fill('Dashboard');
    await page.getByLabel(/branch pattern/i).fill('feature/{item_key}-{slug}');
    await page.getByLabel(/commit pattern/i).fill('test: {summary}');
    await page.getByPlaceholder(/npm run typecheck/i).fill('npm run typecheck\nnpm test');

    await expect(body).toContainText(/current routing/i);
    await expect(body).toContainText(/mode: single/i);
    await expect(body).toContainText(/repos active: 1/i);

    await page.getByText(/^portfolio$/i).click();
    await expect(page.getByText(/portfolio mode permite/i)).toBeVisible();
    await page.getByText(/^add repo$/i).click();
    await expect(body).toContainText(/repository 2/i);
    await expect(body).toContainText(/repos active: 2/i);

    await page.getByText(/^single project$/i).click();
    await expect(body).toContainText(/single-project mode usa somente o primeiro repositorio/i);
    await expect(body).toContainText(/repos active: 1/i);
    await expect(body).not.toContainText(/repository 2/i);
  });

  test('settings can check for SendSprint updates', async ({ page }) => {
    await mockConfiguredDashboardBackend(page);
    await page.goto('/');

    const body = page.locator('body');
    await expect(body).toContainText(/SendSprint Dashboard|Logado/i, { timeout: 15_000 });

    await page.getByText(/parametros e conexoes|par[aâ]metros/i).click();
    await expect(body).toContainText(/UPDATE SENDSPRINT/i);

    await page.getByText(/verificar update sendsprint/i).click();
    await expect(body).toContainText(/Update disponivel: 0\.21\.0/i);
    await expect(body).toContainText(/Instalado 0\.20\.0/i);
  });

  test('settings show degraded message when update check is unavailable', async ({ page }) => {
    await mockUnavailableVersionBackend(page);
    await page.goto('/');

    const body = page.locator('body');
    await expect(body).toContainText(/SendSprint Dashboard|Logado/i, { timeout: 15_000 });

    await page.getByText(/parametros e conexoes|par[aâ]metros/i).click();
    await page.getByText(/verificar update sendsprint/i).click();
    await expect(body).toContainText(/Nao foi possivel verificar updates agora\./i);
    await expect(body).toContainText(/network blocked/i);
  });
});
