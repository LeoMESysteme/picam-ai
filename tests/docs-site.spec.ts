import { expect, test } from '@playwright/test';

test('OQ-Fokus, Filter und Suche bleiben mit den Einträgen verlinkt', async ({ page }) => {
  await page.goto('/docs/open-questions.html');
  const index = page.locator('#oq-index');
  await expect(index).toBeVisible();
  await expect(index.locator('tbody tr').first()).toContainText('OQ-40');
  await expect(index.locator('tbody tr').first()).toContainText('Jetzt');
  await expect(page.locator('h2[id^="oq-01-"]')).toHaveCount(1);
  await expect(page.locator('#oq-01')).toHaveCount(1);

  await page.getByRole('button', { name: 'Geklärt' }).click();
  await expect(index.locator('tbody tr:visible').first()).toContainText('OQ-08');
  await expect(index.locator('tbody tr:visible')).not.toContainText(['OQ-40']);

  await page.getByRole('button', { name: 'Alle' }).click();
  await page.getByRole('searchbox', { name: 'OQ suchen' }).fill('OQ-40');
  await expect(index.locator('tbody tr:visible')).toHaveCount(1);
  await index.locator('tbody tr:visible a').first().click();
  await expect(page).toHaveURL(/#oq-40$/);
  await expect(page.locator('h2[id^="oq-40-"]')).toBeVisible();
});

test('Roadmap zeigt Phasen mit Exit-Kriterium und OQ-Link', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const phases = page.locator('[data-roadmap]');
  await expect(phases.locator('details')).toHaveCount(9);
  await expect(page.locator('#roadmap-phases')).toBeHidden();
  await expect(phases.locator('details').first().locator('.roadmap-state')).toHaveText('erreicht');
  await expect(phases.locator('details').nth(1).locator('.roadmap-state')).toHaveText('teilweise');
  const p4 = phases.locator('details').filter({ hasText: 'P4' });
  await p4.locator('summary').click();
  await expect(p4).toContainText('GSVmulti nimmt den Strom an');
  await expect(p4.getByRole('link', { name: 'OQ-01' })).toHaveAttribute('href', /open-questions\.html#oq-01$/);
});

test('Sofortnavigation initialisiert die OQ-Ansicht erneut', async ({ page }) => {
  await page.goto('/docs/open-questions.html');
  await page.getByRole('button', { name: 'Geklärt' }).click();
  await page.getByRole('link', { name: 'Roadmap', exact: true }).first().click();
  await expect(page.locator('[data-roadmap] details')).toHaveCount(9);
  await page.getByRole('link', { name: 'Offene Punkte (OQ)' }).first().click();
  await expect(page.getByRole('button', { name: 'Geklärt' })).toBeVisible();
  await expect(page.locator('#oq-index tbody tr:visible')).toHaveCount(41);
});

test('schmale Ansicht bleibt ohne horizontales Scrollen bedienbar', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto('/docs/open-questions.html');
  await expect(page.getByRole('searchbox', { name: 'OQ suchen' })).toBeVisible();
  await expect(page.locator('#oq-index tbody tr:visible')).toHaveCount(41);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('Statusfarben bleiben im dunklen Design lesbar', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/docs/open-questions.html');
  await expect(page.locator('body')).toHaveAttribute('data-md-color-scheme', 'slate');
  const contrast = await page.locator('.oq-badge--open').first().evaluate((badge) => {
    const rgb = (value: string) => value.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((channel) => {
      const normalized = channel / 255;
      return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    });
    const luminance = (value: string) => {
      const [red, green, blue] = rgb(value);
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    };
    const style = getComputedStyle(badge);
    const foreground = luminance(style.color);
    const background = luminance(style.backgroundColor);
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
});

test('Quelltabellen bleiben ohne JavaScript nutzbar', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8766/docs/open-questions.html');
  const questions = page.locator('.md-content__inner table').first().locator('tbody tr');
  await expect(questions).toHaveCount(41);
  await expect(questions.first()).toContainText('OQ-40');
  await page.goto('http://127.0.0.1:8766/docs/ROADMAP.html');
  await expect(page.locator('.md-content__inner table tbody tr').first()).toContainText('P0');
  await context.close();
});
