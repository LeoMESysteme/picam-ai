import { expect, test, type Page } from '@playwright/test';

// Rahmen der lebendigen Darstellung: Seitenwechsel als Morph, Lesefortschritt,
// Linse im Inhaltsverzeichnis, atmende Atmosphäre (wiki-lebendig.js/.css).
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { if (!localStorage.getItem('wiki-look')) localStorage.setItem('wiki-look', 'ruhig'); } catch { /* gesperrter Speicher */ }
  });
});
const lebendig = (page: Page) => page.addInitScript(() => {
  try { localStorage.setItem('wiki-look', 'lebendig'); } catch { /* gesperrter Speicher */ }
});

// Zeichnet jeden Start einer View Transition mit den benannten Elementen auf.
const vtSpy = (page: Page) => page.addInitScript(() => {
  const w = window as unknown as { __vt: { names: string[] }[] };
  w.__vt = [];
  const original = document.startViewTransition?.bind(document);
  if (!original) return;
  document.startViewTransition = ((callback: ViewTransitionUpdateCallback) => {
    const names = [...document.querySelectorAll<HTMLElement>('[data-wiki-morph]')].map(el => el.style.viewTransitionName);
    w.__vt.push({ names });
    return original(callback);
  }) as typeof document.startViewTransition;
});

const leftovers = (page: Page) => page.evaluate(() => ({
  morphClass: document.documentElement.classList.contains('wiki-morph'),
  named: document.querySelectorAll('[data-wiki-morph]').length,
  inline: [...document.querySelectorAll<HTMLElement>('[style]')].filter(el => el.style.viewTransitionName).length,
  geist: document.querySelectorAll('.wiki-morph-geist').length,
}));
const clean = { morphClass: false, named: 0, inline: 0, geist: 0 };

test('Morph: Navigationslink geht per View Transition in den Titel über und räumt auf', async ({ page }) => {
  await lebendig(page);
  await vtSpy(page);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/uebersicht/messpfad.html');
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click({ noWaitAfter: true });
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme');
  await expect.poll(() => page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(1);
  const names = await page.evaluate(() => (window as unknown as { __vt: { names: string[] }[] }).__vt[0].names);
  expect(names).toEqual(expect.arrayContaining(['wiki-titel', 'wiki-text-alt']));
  await expect.poll(() => leftovers(page)).toEqual(clean);
  // Zurück hängt nicht und startet keinen Morph.
  await page.goBack();
  await expect(page.locator('.md-content__inner h1')).toContainText('Messpfad');
  await expect.poll(() => leftovers(page)).toEqual(clean);
  expect(await page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(1);
});

test('Morph: „Weiter mit“ fliegt zur Zielüberschrift, Doppelklick navigiert einmal', async ({ page }) => {
  await lebendig(page);
  await vtSpy(page);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/CAMERA_COMMISSIONING.html');
  const weiter = page.locator('a.wiki-pagehead-weiter');
  await expect(weiter).toBeVisible();
  const before = await page.evaluate(() => history.length);
  await weiter.dblclick({ noWaitAfter: true });
  await expect(page).toHaveURL(/10-kamera-livevorschau\.html#kamera-einstellen$/);
  await expect.poll(() => leftovers(page)).toEqual(clean);
  expect(await page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(1);
  // Ein Eintrag für die Seite (Zensical legt beim Sprungziel ggf. einen zweiten an), nicht zwei Navigationen.
  expect(await page.evaluate(() => history.length) - before).toBeLessThanOrEqual(2);
  await expect(page.locator('h2#kamera-einstellen')).toBeInViewport();
});

test('Morph ohne View Transitions: Geist des Linktexts fliegt und verschwindet', async ({ page }) => {
  await lebendig(page);
  await page.addInitScript(() => {
    delete (Document.prototype as unknown as { startViewTransition?: unknown }).startViewTransition;
  });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/uebersicht/messpfad.html');
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click({ noWaitAfter: true });
  await expect(page.locator('.wiki-morph-geist')).toHaveCount(1);
  await expect(page.locator('.wiki-morph-geist')).toHaveText('Kamera-Inbetriebnahme');
  await expect(page.locator('.wiki-morph-geist')).toHaveCount(0, { timeout: 3000 });
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme');
  await expect.poll(() => leftovers(page)).toEqual(clean);
});

test('Inhaltsverzeichnis-Linse folgt dem aktiven Abschnitt, Fortschrittslinie wächst', async ({ page }) => {
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/uebersicht/messpfad.html');
  const lens = page.locator('.md-sidebar--secondary .wiki-toc-linse');
  const bar = page.locator('.md-content > .wiki-lesefortschritt');
  await expect(lens).toHaveCount(1);
  await expect(bar).toHaveCount(1);
  const barWidth = () => bar.evaluate(el => el.getBoundingClientRect().width);
  const start = await barWidth();
  const lensOnActive = () => page.evaluate(() => {
    const active = [...document.querySelectorAll('.md-sidebar--secondary a.md-nav__link--active')].pop();
    const linse = document.querySelector('.wiki-toc-linse');
    if (!active || !linse?.hasAttribute('data-on')) return null;
    const a = active.getBoundingClientRect();
    const l = linse.getBoundingClientRect();
    return { text: active.textContent?.trim(), dy: Math.round(Math.abs(a.top - l.top)), dh: Math.round(Math.abs(a.height - l.height)) };
  });

  const headings = page.locator('.md-content__inner h2');
  await headings.nth(1).evaluate(el => window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 80));
  await expect.poll(lensOnActive).toMatchObject({ dy: 0, dh: 0 });
  const first = (await lensOnActive())!.text;
  // Der Übergang läuft (gleitet), statt zu springen.
  await headings.last().evaluate(el => window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 80));
  await expect.poll(() => page.evaluate(() => document.getAnimations()
    .some(a => (a.effect as KeyframeEffect | null)?.target === document.querySelector('.wiki-toc-linse') && a.playState === 'running'))).toBe(true);
  await expect.poll(lensOnActive).toMatchObject({ dy: 0, dh: 0 });
  expect((await lensOnActive())!.text).not.toBe(first);
  expect(await barWidth()).toBeGreaterThan(start + 100);
  // Schmal: keine Linse sichtbar, Fortschrittslinie bleibt.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(lens).toBeHidden();
  await expect(bar).toBeVisible();
});

test('Atmosphäre atmet und ruht bei verborgenem Tab', async ({ page }) => {
  await lebendig(page);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/index.html');
  const states = () => page.evaluate(() => [...document.querySelectorAll('.wiki-atmo-layer')]
    .flatMap(layer => layer.getAnimations()).filter(a => (a as CSSAnimation).animationName === 'wiki-atmo-atem').map(a => a.playState));
  await expect.poll(states).toEqual(['running', 'running']);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(states).toEqual(['paused', 'paused']);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(states).toEqual(['running', 'running']);
});

test('Reduzierte Bewegung: kein Morph, keine Drift, nichts läuft', async ({ page }) => {
  await lebendig(page);
  await vtSpy(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/uebersicht/messpfad.html');
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click();
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme');
  await page.evaluate(() => window.scrollTo(0, 1600));
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(0);
  expect(await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  expect(await page.locator('.wiki-atmo-layer').first().evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  // Fortschritt bleibt als Zustand, ohne Animation; Linse springt.
  await expect(page.locator('.wiki-lesefortschritt')).not.toHaveClass(/wiki-lesefortschritt--css/);
  expect(await page.locator('.wiki-lesefortschritt').evaluate(el => el.getBoundingClientRect().width)).toBeGreaterThan(20);
  expect(await page.locator('.wiki-toc-linse').evaluate(el => getComputedStyle(el).transitionProperty + getComputedStyle(el).transitionDuration)).toMatch(/^(all0s|none)/);
  await expect.poll(() => leftovers(page)).toEqual(clean);
});

test('Ruhig: weder Fortschrittslinie noch Linse noch Morph, auch nach dem Umschalten', async ({ page }) => {
  await vtSpy(page);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/uebersicht/messpfad.html');
  const extras = page.locator('.wiki-lesefortschritt, .wiki-toc-linse, .wiki-morph-geist');
  await expect(extras).toHaveCount(0);
  await expect(page.locator('.wiki-atmo')).toBeHidden();
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click();
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme');
  expect(await page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(0);
  await expect(extras).toHaveCount(0);

  const toggle = page.getByRole('switch', { name: 'Lebendige Darstellung' });
  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-wiki-look', 'lebendig');
  await expect(page.locator('.wiki-lesefortschritt')).toHaveCount(1);
  await expect(page.locator('.wiki-toc-linse')).toHaveCount(1);
  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-wiki-look', 'ruhig');
  await expect(extras).toHaveCount(0);
  await expect(page.locator('.wiki-atmo')).toBeHidden();
});

// ------------------------------------------------------- Seitenskelett ----
// Langsame Seiten simulieren: die Antwort auf Zensicals XHR verzögern
// (page.route schaltet den HTTP-Cache ab, jede Ladung geht also hierdurch).
// Die Verzögerung ist mit 2 s deutlich länger als Skelett-Schwelle (250 ms)
// plus Last auf dem Pi, damit das Fenster, in dem das Skelett steht, nicht
// mit dem Polling der Erwartung um die Wette läuft.
const SLOW = 2000;
const slow = (page: Page, pattern: RegExp, ms = SLOW) => page.route(pattern, async (route) => {
  if (route.request().resourceType() === 'xhr' || route.request().resourceType() === 'fetch') {
    await new Promise(resolve => setTimeout(resolve, ms));
  }
  await route.continue();
});
// Zeitprotokoll im Browser: Beginn der Navigation (pushState/popstate),
// Skelett an/weg, Wechsel des Titels. Prüft Abläufe ohne Rennen gegen die Uhr
// des Testprozesses.
type Spur = { nav: number[]; an: number[]; weg: number[]; titel: number[] };
const spur = (page: Page) => page.addInitScript(() => {
  const w = window as unknown as { __spur: Spur };
  const s: Spur = w.__spur = { nav: [], an: [], weg: [], titel: [] };
  const now = () => performance.now();
  const push = history.pushState;
  history.pushState = function (...args: Parameters<History['pushState']>) { s.nav.push(now()); return push.apply(this, args); };
  addEventListener('popstate', () => s.nav.push(now()), true);
  let on = false;
  let h1: Element | null = null;
  new MutationObserver(() => {
    const has = !!document.querySelector('.wiki-skelett');
    if (has !== on) { on = has; (has ? s.an : s.weg).push(now()); }
    const title = document.querySelector('.md-content__inner h1');
    if (title && h1 && title !== h1) s.titel.push(now());
    if (title) h1 = title;
  }).observe(document, { childList: true, subtree: true });
});
const leseSpur = (page: Page) => page.evaluate(() => (window as unknown as { __spur: Spur }).__spur);
const LIVE = /10-kamera-livevorschau\.html/;
const textLink = (page: Page) => page.locator('.md-content__inner p a[href*="10-kamera-livevorschau"]').first();

// Das Skelett erscheint frühestens nach der Schwelle und steht, wenn es
// erscheint, mindestens 200 ms (kein Flackern).
// Jedes Erscheinen zählt gegen die Navigation, die ihm vorausging; ein
// früherer Wechsel im selben Test (unter Last zulässig) bleibt so getrennt.
const pruefeSpur = (s: Spur, erwartet: boolean) => {
  const nav = s.nav[s.nav.length - 1];
  expect(nav, 'Navigation erkannt').toBeDefined();
  if (erwartet) expect(s.an.filter(an => an >= nav).length, 'Skelett erschienen').toBeGreaterThan(0);
  for (const an of s.an) {
    const davor = Math.max(...s.nav.filter(n => n <= an));
    expect(an - davor, 'nicht vor der Schwelle').toBeGreaterThanOrEqual(240);
  }
  s.an.forEach((an, k) => { if (s.weg[k] !== undefined) expect(s.weg[k] - an, 'Mindestdauer').toBeGreaterThanOrEqual(190); });
};

for (const look of ['ruhig', 'lebendig'] as const) {
  test(`Seitenskelett (${look}): erscheint bei langsamer Seite, verschwindet nach dem Laden`, async ({ page }) => {
    if (look === 'lebendig') await lebendig(page);
    await spur(page);
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/docs/uebersicht/messpfad.html');
    await slow(page, LIVE);
    await textLink(page).click({ noWaitAfter: true });
    const skelett = page.locator('.md-content > .wiki-skelett');
    await expect(skelett).toBeVisible({ timeout: SLOW - 300 });
    await expect(page.locator('.md-content')).toHaveAttribute('aria-busy', 'true');
    await expect(page.locator('.wiki-laden-status')).toHaveText('Seite wird geladen');
    await expect(page.locator('.md-content__inner')).toBeHidden();
    const motion = await page.locator('.wiki-skelett-inner').evaluate(el => ({
      self: getComputedStyle(el).animationName,
      glanz: getComputedStyle(el, '::after').animationName,
    }));
    if (look === 'lebendig') expect(motion).toEqual({ self: 'none', glanz: 'wiki-skelett-glanz' });
    else expect(motion).toEqual({ self: 'wiki-skelett-puls', glanz: 'none' });
    await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Workbench', { timeout: SLOW + 3000 });
    await expect(skelett).toHaveCount(0);
    await expect(page.locator('.md-content')).not.toHaveAttribute('aria-busy', /.*/);
    await expect(page.locator('.md-content__inner')).toBeVisible();
    await expect(page.locator('.wiki-laden-status')).toHaveText('');
    pruefeSpur(await leseSpur(page), true);
  });
}

test('Seitenskelett: schneller Wechsel zeigt nichts; wenn doch, nur weil das Laden die Schwelle überschritt', async ({ page }) => {
  await spur(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/uebersicht/messpfad.html');
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click();
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme');
  await page.waitForTimeout(500);
  const s = await leseSpur(page);
  // Unter Last kann auch ein „schneller“ Wechsel länger als 250 ms dauern;
  // dann ist ein Skelett richtig. Geprüft wird die Regel, nicht die Uhr.
  const dauer = s.titel[s.titel.length - 1] - s.nav[s.nav.length - 1];
  if (dauer < 240) expect(s.an, `Wechsel in ${Math.round(dauer)} ms ohne Skelett`).toEqual([]);
  pruefeSpur(s, false);
  await expect(page.locator('.md-content')).not.toHaveAttribute('aria-busy', /.*/);
  await expect(page.locator('.wiki-skelett')).toHaveCount(0);
});

test('Seitenskelett: reduzierte Bewegung steht still, Zurück zeigt es ebenfalls', async ({ page }) => {
  await lebendig(page);
  await spur(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/uebersicht/messpfad.html');
  await textLink(page).click();
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Workbench');
  await slow(page, /messpfad\.html/);
  await page.goBack({ waitUntil: 'commit' });
  await expect(page.locator('.md-content > .wiki-skelett')).toBeVisible({ timeout: SLOW - 300 });
  expect(await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await expect(page.locator('.md-content__inner h1')).toContainText('Messpfad', { timeout: SLOW + 3000 });
  await expect(page.locator('.wiki-skelett')).toHaveCount(0);
  pruefeSpur(await leseSpur(page), true);
});

test('Seitenskelett: Netzfehler – Zensical lädt vollständig, nichts bleibt hängen', async ({ page }) => {
  await page.goto('/docs/uebersicht/messpfad.html');
  let aborted = false;
  await page.route(LIVE, async (route) => {
    if (!aborted && route.request().resourceType() === 'xhr') {
      aborted = true;
      await new Promise(resolve => setTimeout(resolve, SLOW));
      return route.abort('failed');
    }
    return route.continue();
  });
  await textLink(page).click({ noWaitAfter: true });
  await expect(page.locator('.md-content > .wiki-skelett')).toBeVisible({ timeout: SLOW - 300 });
  await expect(page).toHaveURL(LIVE);
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Workbench', { timeout: SLOW + 5000 });
  expect(aborted).toBe(true);
  await expect(page.locator('.wiki-skelett')).toHaveCount(0);
  await expect(page.locator('.md-content')).not.toHaveAttribute('aria-busy', /.*/);
});

test('Seitenskelett im Morph: Bild wird freigegeben, Skelett statt altem Text, danach sauber', async ({ page }) => {
  await lebendig(page);
  await vtSpy(page);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/docs/uebersicht/messpfad.html');
  // Freigabe nach 800 ms, plus Last: die Ladung dauert deutlich länger.
  await slow(page, /CAMERA_COMMISSIONING\.html/, 4000);
  await page.locator('.md-nav--primary a', { hasText: 'Kamera-Inbetriebnahme' }).click({ noWaitAfter: true });
  await expect(page.locator('.md-content > .wiki-skelett')).toBeVisible({ timeout: 3000 });
  await expect(page.locator('.md-content')).toHaveAttribute('aria-busy', 'true');
  expect(await page.evaluate(() => (window as unknown as { __vt: unknown[] }).__vt.length)).toBe(1);
  await expect(page.locator('.md-content__inner h1')).toContainText('Kamera-Inbetriebnahme', { timeout: 9000 });
  await expect(page.locator('.wiki-skelett')).toHaveCount(0);
  await expect.poll(() => leftovers(page)).toEqual(clean);
  await expect(page.locator('.md-content')).not.toHaveAttribute('aria-busy', /.*/);
});
