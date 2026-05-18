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

import { test, expect } from '@playwright/test';

const baseUrl = process.env.BASE_URL;

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
});
