import { expect, test } from '@playwright/test';

test('OQ-Fokus, Filter und Suche bleiben mit den Einträgen verlinkt', async ({ page }) => {
  await page.goto('/docs/open-questions.html');
  const index = page.locator('#oq-index');
  await expect(index).toBeVisible();
  const rows = index.locator('tbody tr');
  const questionCount = await rows.count();
  expect(questionCount).toBeGreaterThan(0);
  const focusCount = await rows.locator('td:nth-child(2):text-is("Jetzt")').count();
  await page.getByRole('button', { name: 'Jetzt' }).click();
  const visible = index.locator('tbody tr:visible');
  await expect(visible).toHaveCount(focusCount);
  for (const focus of await visible.locator('td:nth-child(2)').allTextContents()) {
    expect(focus.trim()).toBe('Jetzt');
  }

  await page.getByRole('button', { name: 'Geklärt' }).click();
  const resolvedCount = await rows.locator('td:nth-child(3)').evaluateAll((cells) =>
    cells.filter((cell) => /^(geklärt|beantwortet)$/.test(cell.textContent?.trim() ?? '')).length,
  );
  await expect(visible).toHaveCount(resolvedCount);
  for (const status of await visible.locator('td:nth-child(3)').allTextContents()) {
    expect(status.trim()).toMatch(/^(geklärt|beantwortet)$/);
  }

  await page.getByRole('button', { name: 'Alle' }).click();
  const titles = (await rows.locator('td:nth-child(4)').allTextContents()).map((title) => title.trim());
  const title = titles[0];
  const matchingTitles = titles.filter((candidate) =>
    candidate.toLocaleLowerCase('de').includes(title.toLocaleLowerCase('de')),
  );
  expect(matchingTitles.length).toBeLessThan(questionCount);
  await page.getByRole('searchbox', { name: 'OQ suchen' }).fill(title);
  await expect(visible).toHaveCount(matchingTitles.length);
  for (const match of await visible.locator('td:nth-child(4)').allTextContents()) {
    expect(match.toLocaleLowerCase('de')).toContain(title.toLocaleLowerCase('de'));
  }
  const firstMatch = visible.first();
  const anchor = await firstMatch.locator('td:first-child a').getAttribute('href');
  const hash = new URL(anchor!, page.url()).hash;
  expect(hash).toMatch(/^#oq-\d+$/);
  await expect(page.locator(hash)).toHaveCount(1);
  await firstMatch.locator('td:first-child a').click();
  await expect(page).toHaveURL(new RegExp(`${hash}$`));
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
  const questionCount = await page.locator('#oq-index tbody tr').count();
  expect(questionCount).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Geklärt' }).click();
  await page.getByRole('link', { name: 'Roadmap', exact: true }).first().click();
  await expect(page.locator('[data-roadmap] details')).toHaveCount(9);
  await page.getByRole('link', { name: 'Offene Punkte (OQ)' }).first().click();
  await expect(page.getByRole('button', { name: 'Geklärt' })).toBeVisible();
  await expect(page.locator('#oq-index tbody tr:visible')).toHaveCount(questionCount);
});

test('schmale Ansicht bleibt ohne horizontales Scrollen bedienbar', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto('/docs/open-questions.html');
  await expect(page.getByRole('searchbox', { name: 'OQ suchen' })).toBeVisible();
  expect(await page.locator('#oq-index tbody tr:visible').count()).toBeGreaterThan(0);
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
  expect(await questions.count()).toBeGreaterThan(0);
  await expect(questions.first().locator('td:first-child a')).toHaveAttribute('href', /^#oq-\d+$/);
  await page.goto('http://127.0.0.1:8766/docs/ROADMAP.html');
  await expect(page.locator('.md-content__inner table tbody tr').first()).toContainText('P0');
  await context.close();
});

test('Glossarbegriff und Dokumentabschnitt zeigen eine Vorschau', async ({ page }) => {
  await page.goto('/docs/anleitung/01-kette-verstehen.html');

  const term = page.locator('.md-content__inner a[href*="glossar.html#value-record"]');
  await expect(term).toHaveAttribute('data-preview', '');
  await term.hover();
  await expect(page.locator('.md-tooltip2--active').filter({ hasText: 'interne Datensatz' })).toBeVisible();

  const document = page.locator('.md-content__inner a[href*="TIMING.html#grundsatz-latenz-ist-nicht-zeitunsicherheit"]');
  await expect(document).toHaveAttribute('data-preview', '');
  await document.hover();
  await expect(page.locator('.md-tooltip2--active').filter({ hasText: 'Latenz ist' })).toBeVisible();
});

test('API-Stufen zeigen kurze Erklärungen aus der Anleitung', async ({ page }) => {
  await page.goto('/docs/anleitung/01-kette-verstehen.html');
  const links = page.locator('.md-content__inner table a[href*="/api/"]');
  await expect(links).toHaveCount(6);
  for (const link of await links.all()) {
    await expect(link).not.toHaveAttribute('data-preview', '');
    await expect(link).toHaveAttribute('title', /.+/);
  }
  await links.first().hover();
  const popup = page.locator('.md-tooltip2--active').last();
  await expect(popup).toContainText('Frame und Zeitbasis');
  expect((await popup.innerText()).length).toBeLessThan(250);
});

test('Link auf die Glossarseite zeigt nur die kurze Einleitung', async ({ page }) => {
  await page.goto('/docs/anleitung/');
  const link = page.locator('.md-content__inner a[href$="glossar.html"]');
  await expect(link).toHaveAttribute('data-preview', '');
  await link.hover();
  const popup = page.locator('.md-tooltip2--active').last();
  await expect(popup).toContainText('Jeder Begriff');
  expect((await popup.innerText()).length).toBeLessThan(250);
});

test('Glossarvorschau ist mit der Tastatur erreichbar', async ({ page }) => {
  await page.goto('/docs/anleitung/01-kette-verstehen.html');
  const term = page.locator('.md-content__inner a[href*="glossar.html#value-record"]');
  await term.focus();
  await expect(page.locator('.md-tooltip2--active').filter({ hasText: 'interne Datensatz' })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/glossar\.html#value-record$/);
});

test('Glossarbegriff bleibt auf schmalem Bildschirm verlinkt', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 375, height: 800 },
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8766/docs/anleitung/01-kette-verstehen.html');
  await page.locator('.md-content__inner a[href*="glossar.html#value-record"]').tap();
  await expect(page).toHaveURL(/glossar\.html#value-record$/);
  await context.close();
});

test('Codebeispiele erläutern markierte Zeilen', async ({ page }) => {
  await page.goto('/docs/anleitung/01-kette-verstehen.html');
  const first = page.locator('.md-content__inner .md-annotation');
  await expect(first).toHaveCount(1);
  await first.click();
  await expect(page.locator('.md-tooltip--active').filter({ hasText: 'synthetischen Beispiel' })).toBeVisible();
  await page.goto('/docs/anleitung/02-vertraege.html');
  const second = page.locator('.md-content__inner .md-annotation');
  await expect(second).toHaveCount(1);
  await second.click();
  await expect(page.locator('.md-tooltip--active').filter({ hasText: 'keinen Referenzwert' })).toBeVisible();
});

test('API-Verweise erklären Klasse und Funktion kurz', async ({ page }) => {
  await page.goto('/docs/anleitung/02-vertraege.html');
  const api = page.locator('.md-content__inner a[href$="api/vertraege.html#dispread.records.ValueRecord"]');
  await expect(api).not.toHaveAttribute('data-preview', '');
  await api.hover();
  const classPopup = page.locator('.md-tooltip2--active').last();
  await expect(classPopup).toContainText('interne Datensatz');
  expect((await classPopup.innerText()).length).toBeLessThan(250);

  const method = page.locator('.md-content__inner a[href$="api/vertraege.html#dispread.records.ValueRecord.to_dict"]');
  await expect(method).not.toHaveAttribute('data-preview', '');
  await method.hover();
  const methodPopup = page.locator('.md-tooltip2--active').last();
  await expect(methodPopup).toContainText('JSONL-Log');
  expect((await methodPopup.innerText()).length).toBeLessThan(250);
});
