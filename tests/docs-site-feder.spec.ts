import { expect, test, type Page } from '@playwright/test';

// Federn und Zähler der lebendigen Darstellung (wiki-feder.js, wiki-hint.js).
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { if (!localStorage.getItem('wiki-look')) localStorage.setItem('wiki-look', 'ruhig'); } catch { /* gesperrter Speicher */ }
  });
});
const lebendig = (page: Page) => page.addInitScript(() => {
  try { localStorage.setItem('wiki-look', 'lebendig'); } catch { /* gesperrter Speicher */ }
});

const LAYER = '/docs/CAMERA_COMMISSIONING.html';
const contentHeight = (page: Page) => page.evaluate(() => {
  const details = document.querySelector('details.wiki-layer') as HTMLDetailsElement;
  return parseFloat(getComputedStyle(details, '::details-content').height);
});

test('Tiefenebene öffnet animiert und ist danach voll sichtbar', async ({ page }) => {
  await lebendig(page);
  await page.goto(LAYER);
  const layer = page.locator('details.wiki-layer').first();
  await expect(layer).not.toHaveAttribute('open', /.*/);
  await layer.locator('> summary').click();
  // Die Höhe läuft über mehrere Bilder von 0 zum Endwert (kein Sprung).
  const samples = await page.evaluate(() => new Promise<number[]>((resolve) => {
    const details = document.querySelector('details.wiki-layer') as HTMLDetailsElement;
    const out: number[] = [];
    const t0 = performance.now();
    (function frame() {
      out.push(parseFloat(getComputedStyle(details, '::details-content').height));
      if (performance.now() - t0 < 1500) requestAnimationFrame(frame); else resolve(out);
    })();
  }));
  const end = await page.evaluate(() => {
    const details = document.querySelector('details.wiki-layer') as HTMLDetailsElement;
    const inner = details.querySelector(':scope > summary + *') as HTMLElement;
    return { height: parseFloat(getComputedStyle(details, '::details-content').height), inner: inner.getBoundingClientRect().height };
  });
  expect(end.height).toBeGreaterThanOrEqual(end.inner - 1);
  expect(samples.some((h) => h > 0 && h < end.height - 1)).toBe(true);
  expect(Math.max(...samples)).toBeLessThanOrEqual(end.height * 1.02);
  await expect(layer.locator('> summary + *')).toBeVisible();
  // Schließen: danach wieder zu.
  await layer.locator('> summary').click();
  await expect.poll(() => contentHeight(page), { timeout: 3000 }).toBe(0);
  await expect(layer.locator('> summary + *')).toBeHidden();
});

test('Tiefenebene ist per Tastatur bedienbar', async ({ page }) => {
  await lebendig(page);
  await page.goto(LAYER);
  const layer = page.locator('details.wiki-layer').first();
  const summary = layer.locator('> summary');
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(layer).toHaveAttribute('open', '');
  await expect(layer.locator('> summary + *')).toBeVisible();
  await page.keyboard.press('Space');
  await expect(layer).not.toHaveAttribute('open', /.*/);
});

test('Rückfall ohne CSS-Technik: FLIP animiert die Höhe und endet in auto', async ({ page }) => {
  await lebendig(page);
  await page.addInitScript(() => {
    const supports = CSS.supports.bind(CSS);
    CSS.supports = (...args: [string, string?]) => (String(args[0]).includes('details-content') ? false : supports(...(args as [string])));
  });
  await page.goto(LAYER);
  const layer = page.locator('details.wiki-layer').first();
  await layer.locator('> summary').click();
  await expect(layer).toHaveAttribute('open', '');
  const running = await page.evaluate(() => (document.querySelector('details.wiki-layer') as HTMLElement)
    .getAnimations().some((a) => a.playState === 'running'));
  expect(running).toBe(true);
  await expect.poll(() => page.evaluate(() => (document.querySelector('details.wiki-layer') as HTMLElement).getAnimations().length)).toBe(0);
  await expect(layer.locator('> summary + *')).toBeVisible();
  await layer.locator('> summary').click();
  await expect(layer).not.toHaveAttribute('open', /.*/, { timeout: 3000 });
  await expect(layer).not.toHaveAttribute('data-closing', /.*/);
});

test('Ruhig: keine Transition auf details, Hinweis ohne Wachstum', async ({ page }) => {
  await page.goto(LAYER);
  const info = await page.evaluate(() => {
    const details = document.querySelector('details.wiki-layer') as HTMLElement;
    const after = getComputedStyle(details, '::details-content');
    return { transition: getComputedStyle(details).transitionDuration, content: after.transitionDuration, interpolate: getComputedStyle(document.documentElement).getPropertyValue('interpolate-size') };
  });
  expect(info.transition).toBe('0s');
  expect(info.content).toBe('0s');
  await page.goto('/docs/GSVMULTI_PROTOCOL.html');
  await page.locator('.md-content__inner a[data-hint="oq"]').first().focus();
  const hint = page.locator('#wiki-hint[data-open="true"]');
  await expect(hint).toHaveCount(1);
  expect(await hint.evaluate((el) => getComputedStyle(el).filter)).toBe('none');
});

test('Pop-up wächst in lebendig aus dem Begriff', async ({ page }) => {
  await lebendig(page);
  await page.goto('/docs/GSVMULTI_PROTOCOL.html');
  const link = page.locator('.md-content__inner a[data-hint="oq"]').first();
  await link.scrollIntoViewIfNeeded();
  await link.focus();
  const hint = page.locator('#wiki-hint[data-open="true"]');
  await expect(hint).toHaveCount(1);
  const origin = await hint.evaluate((el) => {
    const box = el.getBoundingClientRect();
    const [x, y] = getComputedStyle(el).transformOrigin.split(' ').map(parseFloat);
    return { x: box.left + x, y: box.top + y, transition: getComputedStyle(el).transitionDuration };
  });
  // Nach der Ankunft ist transform none, der Ursprung steht trotzdem am Begriff.
  await expect.poll(() => hint.evaluate((el) => getComputedStyle(el).filter)).toBe('none');
  const anchor = await link.evaluate((el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; });
  const box = await hint.evaluate((el) => { const r = el.getBoundingClientRect(); return { left: r.left, top: r.top }; });
  const ox = await hint.evaluate((el) => parseFloat(getComputedStyle(el).transformOrigin.split(' ')[0]));
  const oy = await hint.evaluate((el) => parseFloat(getComputedStyle(el).transformOrigin.split(' ')[1]));
  expect(box.left + ox).toBeGreaterThanOrEqual(anchor.left - 1);
  expect(box.left + ox).toBeLessThanOrEqual(anchor.right + 1);
  expect(Math.min(Math.abs(box.top + oy - anchor.bottom), Math.abs(box.top + oy - anchor.top))).toBeLessThanOrEqual(12);
  expect(origin.transition).toContain('0.22s');
  // Schließen: erst data-open weg, kurz danach hidden.
  await page.keyboard.press('Escape');
  await expect(page.locator('#wiki-hint')).toBeHidden({ timeout: 1000 });
});

test('Zähler endet exakt beim Originaltext', async ({ page }) => {
  await lebendig(page);
  await page.goto('/docs/uebersicht/codebase.html');
  const para = page.locator('#wachstum + p');
  const before = await para.evaluate((el) => el.textContent);
  await para.scrollIntoViewIfNeeded();
  await expect(para.locator('.wiki-zahl').first()).toBeAttached();
  // Mitten im Zählen weicht der sichtbare Text ab, der Endwert bleibt lesbar.
  const mid = await para.evaluate((el) => new Promise<{ visible: string; sr: string }>((resolve) => setTimeout(() => {
    const span = el.querySelector('.wiki-zahl') as HTMLElement;
    resolve({ visible: span.querySelector('[aria-hidden]')?.textContent ?? span.textContent ?? '', sr: span.querySelector('.wiki-zahl-sr')?.textContent ?? span.textContent ?? '' });
  }, 150)));
  expect(mid.sr).toMatch(/\d/);
  await expect.poll(() => para.evaluate((el) => el.querySelectorAll('.wiki-zahl.is-counting').length), { timeout: 4000 }).toBe(0);
  expect(await para.evaluate((el) => el.textContent)).toBe(before);
});

test('Reduzierte Bewegung: sofort Endzustand, kein Zählen', async ({ page }) => {
  await lebendig(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/uebersicht/codebase.html');
  const para = page.locator('#wachstum + p');
  const before = await para.evaluate((el) => el.textContent);
  await para.scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  expect(await para.evaluate((el) => el.textContent)).toBe(before);
  expect(await para.locator('.wiki-zahl').count()).toBe(0);
  await page.goto(LAYER);
  const layer = page.locator('details.wiki-layer').first();
  await layer.locator('> summary').click();
  await expect(layer.locator('> summary + *')).toBeVisible();
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
});

test('Wertpillen zählen und enden beim Originaltext', async ({ page }) => {
  await lebendig(page);
  await page.goto('/docs/uebersicht/codebase.html');
  const pills = page.locator('.wiki-chart-pill .wiki-chart-value');
  await expect(pills.first()).toBeAttached();
  const first = pills.first();
  const final = await first.evaluate((el) => el.textContent);
  const seen = await first.evaluate((el) => new Promise<string[]>((resolve) => {
    el.scrollIntoView({ block: 'center' });
    const out = new Set<string>();
    const t0 = performance.now();
    (function frame() {
      out.add(el.textContent ?? '');
      if (performance.now() - t0 < 3500) requestAnimationFrame(frame); else resolve([...out]);
    })();
  }));
  expect(seen.some((text) => text !== final)).toBe(true);
  expect(await first.evaluate((el) => el.textContent)).toBe(final);
});
