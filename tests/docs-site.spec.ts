import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';

test('Startseite verlinkt alle Navigationsziele im Inhalt', async ({ page }) => {
  await page.goto('/');
  const targets = await page.locator('.md-nav--primary a[href]').evaluateAll((links) =>
    [...new Set(links.map((link) => new URL((link as HTMLAnchorElement).href).pathname))]
      .filter((path) => path.endsWith('.html') && path !== '/index.html'),
  );
  const homeLinks = await page.locator('.md-content__inner a[href]').evaluateAll((links) =>
    [...new Set(links.map((link) => new URL((link as HTMLAnchorElement).href).pathname))],
  );
  for (const target of targets) expect(homeLinks.includes(target), `fehlender Startseiten-Link: ${target}`).toBe(true);
});

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

test('Roadmap-Karte öffnet Schritte als innere Kartenebene statt als Dialog', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  const phases = roadmap.locator('.roadmap-node[data-phase]');
  await expect(phases).toHaveCount(9);
  await expect(page.locator('#roadmap-phases')).toBeHidden();
  await expect(phases.first().locator('.roadmap-state')).toHaveText('erreicht');
  await expect(phases.nth(1).locator('.roadmap-state')).toHaveText('teilweise');
  await expect(roadmap.locator('.roadmap-nested-preview')).toHaveCount(9);
  await expect(roadmap).not.toContainText(/hineinzoomen|zum Zoomen|klicken oder/i);
  await roadmap.locator('[data-phase="P2"] .roadmap-enter').click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(roadmap.locator('.roadmap-step')).toHaveCount(4);
  await expect(roadmap.locator('.roadmap-step')).toContainText([
    'Sammelmodus', 'Timing-Kalibrierung', 'Geräteinstanzen sperren', 'Displaytypen',
  ]);
  await expect(roadmap.getByRole('dialog')).toHaveCount(0);
  const viewport = await roadmap.locator('.roadmap-viewport').boundingBox();
  const frame = await roadmap.locator('.roadmap-portal-frame').boundingBox();
  for (const step of await roadmap.locator('.roadmap-step').all()) {
    const box = await step.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(viewport!.x);
    expect(box!.y).toBeGreaterThanOrEqual(viewport!.y);
    expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.x + viewport!.width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.y + viewport!.height);
  }
  expect(frame).not.toBeNull();
  expect(Math.abs(frame!.x - viewport!.x)).toBeLessThanOrEqual(3);
  expect(Math.abs(frame!.y - viewport!.y)).toBeLessThanOrEqual(3);
  expect(Math.abs(frame!.width - viewport!.width)).toBeLessThanOrEqual(6);
  expect(Math.abs(frame!.height - viewport!.height)).toBeLessThanOrEqual(6);
  await expect(roadmap.locator('.roadmap-edge-particles')).toBeVisible();
  expect(await roadmap.locator('.roadmap-edge-particles circle').count()).toBeGreaterThan(30);
  await expect(roadmap.locator('.roadmap-phase-context')).toContainText('Manifeste vollständig');
  await page.getByRole('button', { name: 'Zur Roadmap', exact: true }).click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'overview');
  await roadmap.locator('[data-phase="P4"] .roadmap-enter').click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(roadmap.locator('.roadmap-phase-context')).toContainText('GSVmulti nimmt den Strom an');
  await expect(roadmap.getByRole('link', { name: 'OQ-01', exact: true }).first()).toHaveAttribute('href', /open-questions\.html#oq-01$/);
});

test('Roadmap zeigt belegte Aktualisierungen und erfindet keine Datierungen', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const p2 = page.locator('.roadmap-node[data-phase="P2"]');
  await expect(p2.locator('.roadmap-checkpoints time')).toHaveCount(0);
  await expect(p2.locator('.roadmap-checkpoints')).toContainText('Geräteinstanzen sperren');
  const p3 = page.locator('.roadmap-node[data-phase="P3"]');
  await expect(p3.locator('.roadmap-checkpoints li').first()).toContainText('Live-Bedienerläufe');
  await expect(p3.locator('time')).toHaveAttribute('datetime', '2026-10-21');
});

test('Roadmap zeigt auch bei erreichten Meilensteinen zwei verbundene Schritte mit Status rechts', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const checkpoints = page.locator('.roadmap-node[data-phase="P0"] .roadmap-checkpoints li');
  await expect(checkpoints).toHaveCount(2);
  await expect(checkpoints).toContainText(['Repo-Grundgerüst', 'ValueRecord und Trennstellen']);
  for (const checkpoint of await checkpoints.all()) {
    await expect(checkpoint.locator('.roadmap-checkpoint-label')).toHaveText('gebaut');
    const title = await checkpoint.locator('.roadmap-checkpoint-title').boundingBox();
    const status = await checkpoint.locator('.roadmap-checkpoint-label').boundingBox();
    expect(status!.x).toBeGreaterThan(title!.x + title!.width);
    expect(Math.abs(status!.y - title!.y)).toBeLessThan(3);
  }
});

test('Roadmap-Mausrad und Tastatur führen durch denselben Ebenenwechsel', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  const enter = roadmap.locator('[data-phase="P2"] .roadmap-enter');
  await enter.hover();
  for (let i = 0; i < 10; i += 1) {
    if (await roadmap.getAttribute('data-roadmap-view') === 'inside') break;
    await page.mouse.wheel(0, -220);
    await page.waitForTimeout(90);
  }
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  const wheelSteps = await roadmap.locator('.roadmap-step h3').allTextContents();
  await page.mouse.wheel(0, 1000);
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'overview');
  await enter.focus();
  await page.keyboard.press('Enter');
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  expect(await roadmap.locator('.roadmap-step h3').allTextContents()).toEqual(wheelSteps);
  await page.keyboard.press('Escape');
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'overview');
  await expect(enter).toBeFocused();
});

test('Roadmap-Mausrad zoomt geglättet über mehrere Bilder statt in Sprüngen', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  await page.waitForFunction(() => Boolean((window as any).anime?.createAnimatable));
  await page.locator('.roadmap-viewport').hover({ position: { x: 40, y: 120 } });
  const capture = page.evaluate(async () => {
    const world = document.querySelector<HTMLElement>('.roadmap-phase-world')!;
    const scales = new Set<string>();
    const start = performance.now();
    while (performance.now() - start < 700) {
      scales.add(world.style.transform.match(/scale\(([^)]+)\)/)![1]);
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    }
    return scales.size;
  });
  await page.mouse.wheel(0, -120);
  expect(await capture).toBeGreaterThan(4);
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'overview');
});

test('Roadmap rastet nach einem halben Zoom in eine Ebene ein', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  await page.waitForFunction(() => Boolean((window as any).anime?.createAnimatable));
  const roadmap = page.locator('[data-roadmap]');
  const node = await roadmap.locator('[data-phase="P2"]').boundingBox();
  await page.mouse.move(node!.x + node!.width / 2, node!.y + node!.height / 2);
  for (let i = 0; i < 20 && await roadmap.getAttribute('data-roadmap-view') !== 'entering'; i += 1) {
    await page.mouse.wheel(0, -60);
    await page.waitForTimeout(70);
  }
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'entering');
  await expect(roadmap).toHaveAttribute('data-roadmap-view', /^(inside|overview)$/);
  await expect(roadmap.locator('.roadmap-mini-view')).toHaveCount(1);
});

test('Roadmap-Knoten verschieben folgt den Verbindungen und bleibt nach Neuladen erhalten', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const node = page.locator('.roadmap-node[data-phase="P2"]');
  const originalX = await node.evaluate((el) => (el as HTMLElement).offsetLeft);
  const line = page.locator('.roadmap-connections path[data-from="P2"]');
  const originalPath = await line.getAttribute('d');
  const handle = await node.getByRole('button', { name: 'P2 verschieben', exact: true }).boundingBox();
  await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2);
  await page.mouse.down();
  await page.mouse.move(handle!.x + handle!.width / 2 + 75, handle!.y + handle!.height / 2 + 24, { steps: 6 });
  await page.mouse.up();
  const movedX = await node.evaluate((el) => (el as HTMLElement).offsetLeft);
  expect(movedX).toBeGreaterThan(originalX + 20);
  await expect(line).not.toHaveAttribute('d', originalPath!);
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'overview');
  await page.reload();
  await expect(node).toBeVisible();
  expect(await node.evaluate((el) => (el as HTMLElement).offsetLeft)).toBe(movedX);
  await page.getByRole('button', { name: 'Anordnung zurücksetzen', exact: true }).click();
  await expect.poll(() => node.evaluate((el) => (el as HTMLElement).offsetLeft)).toBe(originalX);
});

test('Roadmap bleibt bei fehlendem Anime und gesperrtem Speicher bedienbar', async ({ page }) => {
  await page.route('**/assets/vendor/anime-*.js', (route) => route.abort());
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get: () => { throw new Error('gesperrt'); } });
  });
  await page.goto('/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  await roadmap.locator('[data-phase="P2"] .roadmap-enter').click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(roadmap.locator('.roadmap-step')).toHaveCount(4);
  await page.getByRole('button', { name: 'Zur Roadmap', exact: true }).click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'overview');
});

test('Roadmap bleibt bei doppelten Schritt-IDs als Quelltext lesbar', async ({ page }) => {
  await page.route('**/docs/ROADMAP.html', async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replaceAll('p2-ernte', 'p2-sammeln');
    await route.fulfill({ response, body });
  });
  await page.goto('/docs/ROADMAP.html');
  await expect(page.locator('.md-content__inner table').first()).toBeVisible();
  await expect(page.locator('[data-roadmap]')).toHaveCount(0);
});

test('Roadmap-Tabellenansicht und mobile innere Ebene bleiben zugänglich', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.goto('/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  await page.getByRole('button', { name: 'Tabellenansicht', exact: true }).click();
  await expect(page.locator('#roadmap-phases')).toBeVisible();
  await expect(page.locator('.roadmap-steps-source')).toBeVisible();
  await page.getByRole('button', { name: 'Kartenansicht', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Meilenstein suchen' }).fill('P2');
  await page.keyboard.press('Enter');
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(roadmap.locator('.roadmap-step')).toHaveCount(4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await expect(page.getByRole('button', { name: 'Zur Roadmap', exact: true })).toBeVisible();
});

test('Roadmap reduziert eine laufende Kamerafahrt ohne unsichtbare Schritte', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  await page.waitForFunction(() => Boolean((window as any).anime?.createTimeline));
  const roadmap = page.locator('[data-roadmap]');
  await roadmap.locator('[data-phase="P2"] .roadmap-enter').click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'entering');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  for (const content of await roadmap.locator('.roadmap-step-content').all()) {
    await expect(content).toHaveCSS('opacity', '1');
  }
  await page.keyboard.press('Escape');
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'overview');
});

test('Roadmap löst die Kartenfüllung während des räumlichen Übergangs allmählich auf', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  await page.waitForFunction(() => Boolean((window as any).anime?.createTimeline));
  const capture = page.evaluate(async () => {
    const node = document.querySelector('.roadmap-node[data-phase="P2"]')!;
    const context = document.createElement('canvas').getContext('2d')!;
    const alphas: number[] = [];
    const start = performance.now();
    while (performance.now() - start < 950) {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = getComputedStyle(node).backgroundColor;
      context.fillRect(0, 0, 1, 1);
      alphas.push(context.getImageData(0, 0, 1, 1).data[3] / 255);
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    }
    return alphas;
  });
  await page.locator('[data-phase="P2"] .roadmap-enter').click();
  const alphas = await capture;
  expect(alphas.some((alpha) => alpha > 0.02 && alpha < 0.98)).toBe(true);
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'inside');
});

test('Roadmap behält verschobene Schrittkarten beim Wechsel zwischen den Ebenen', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  const phase = roadmap.locator('[data-phase="P2"] .roadmap-enter');
  await phase.click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  const step = roadmap.locator('[data-step="p2-sammeln"]');
  const before = await step.evaluate((el) => (el as HTMLElement).offsetLeft);
  await step.locator('.roadmap-drag').focus();
  await page.keyboard.press('Shift+ArrowRight');
  const moved = await step.evaluate((el) => (el as HTMLElement).offsetLeft);
  expect(moved).toBeGreaterThan(before);
  await page.getByRole('button', { name: 'Zur Roadmap', exact: true }).click();
  await phase.click();
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  expect(await step.evaluate((el) => (el as HTMLElement).offsetLeft)).toBe(moved);
});

test('Roadmap erhält unbesuchte Schrittpositionen beim Speichern nach Neuladen', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/docs/ROADMAP.html');
  await page.locator('[data-phase="P2"] .roadmap-enter').click();
  const step = page.locator('[data-step="p2-sammeln"]');
  await step.locator('.roadmap-drag').focus();
  await page.keyboard.press('Shift+ArrowRight');
  const moved = await step.evaluate((el) => (el as HTMLElement).offsetLeft);
  for (const otherLevel of ['overview', 'steps']) {
    await page.reload();
    if (otherLevel === 'steps') await page.locator('[data-phase="P1"] .roadmap-enter').click();
    const handle = otherLevel === 'overview'
      ? page.locator('[data-phase="P1"] .roadmap-drag')
      : page.locator('.roadmap-step .roadmap-drag').first();
    await handle.focus();
    await page.keyboard.press('Shift+ArrowRight');
    if (otherLevel === 'steps') await page.getByRole('button', { name: 'Zur Roadmap', exact: true }).click();
    await page.locator('[data-phase="P2"] .roadmap-enter').click();
    expect(await step.evaluate((el) => (el as HTMLElement).offsetLeft)).toBe(moved);
  }
});

test('Roadmap räumt ihre Kartenansicht bei wiederholter Sofortnavigation auf', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  for (let i = 0; i < 2; i += 1) {
    await page.getByRole('link', { name: 'Offene Punkte (OQ)' }).first().click();
    await expect(page.locator('body')).not.toHaveClass(/roadmap-page/);
    await page.getByRole('link', { name: 'Roadmap', exact: true }).first().click();
    await expect(page.locator('[data-roadmap]')).toHaveCount(1);
    await expect(page.locator('.roadmap-node[data-phase]')).toHaveCount(9);
  }
});

test('Roadmap-Touchzoom öffnet den Meilenstein ohne die Wiki-Seite zu skalieren', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8766/docs/ROADMAP.html');
  const roadmap = page.locator('[data-roadmap]');
  const node = await roadmap.locator('[data-phase="P1"]').boundingBox();
  const x = node!.x + node!.width / 2, y = node!.y + node!.height / 2;
  const cdp = await context.newCDPSession(page);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ id: 1, x: x - 30, y }, { id: 2, x: x + 30, y }] });
  for (let distance = 40; distance <= 125; distance += 10) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ id: 1, x: x - distance, y }, { id: 2, x: x + distance, y }] });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await expect(roadmap).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(roadmap.locator('.roadmap-step')).toHaveCount(4);
  expect(await page.evaluate(() => visualViewport!.scale)).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
  await context.close();
});

test('Roadmap-Schritte führen zu vorhandenen Belegabschnitten', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const links = await page.locator('.roadmap-steps-source a[href]').evaluateAll((anchors) =>
    [...new Set(anchors.map((anchor) => (anchor as HTMLAnchorElement).href))],
  );
  const documents = new Map<string, string>();
  for (const link of links) {
    const url = new URL(link);
    const target = `${url.origin}${url.pathname}`;
    if (!documents.has(target)) {
      const response = await page.request.get(target);
      expect(response.ok(), target).toBe(true);
      documents.set(target, await response.text());
    }
    if (url.hash) {
      const exists = await page.evaluate(({ html, hash }) =>
        Boolean(new DOMParser().parseFromString(html, 'text/html').getElementById(decodeURIComponent(hash.slice(1)))),
      { html: documents.get(target)!, hash: url.hash });
      expect(exists, link).toBe(true);
    }
  }
});

test('Roadmap macht eine erfolglose Suche erkennbar und lässt sie korrigieren', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  const search = page.getByRole('searchbox', { name: 'Meilenstein suchen' });
  await search.fill('P99');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status', { name: 'Suchergebnis' })).toContainText('Kein Treffer');
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'overview');
  await search.fill('P2');
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'inside');
  await expect(search).not.toHaveAttribute('aria-invalid', 'true');
});

test('Roadmap-Beleglinks haben in beiden Themes ausreichenden Textkontrast', async ({ page }) => {
  await page.goto('/docs/ROADMAP.html');
  await page.locator('[data-phase="P2"] .roadmap-enter').click();
  await expect(page.locator('[data-roadmap]')).toHaveAttribute('data-roadmap-view', 'inside');
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect(page.locator('body')).toHaveAttribute('data-md-color-scheme', scheme === 'dark' ? 'slate' : 'default');
    const contrast = await page.locator('.roadmap-step-evidence a').first().evaluate((link) => {
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d')!;
      const luminance = (color: string) => {
        context.clearRect(0, 0, 1, 1);
        context.fillStyle = color;
        context.fillRect(0, 0, 1, 1);
        const values = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).map((value) => {
          const n = value / 255;
          return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
        });
        return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
      };
      const foreground = luminance(getComputedStyle(link).color);
      const background = luminance(getComputedStyle(link.closest('.roadmap-step')!).backgroundColor);
      return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    });
    expect(contrast, scheme).toBeGreaterThanOrEqual(4.5);
  }
});

test('Sofortnavigation initialisiert die OQ-Ansicht erneut', async ({ page }) => {
  await page.goto('/docs/open-questions.html');
  const questionCount = await page.locator('#oq-index tbody tr').count();
  expect(questionCount).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Geklärt' }).click();
  await page.getByRole('link', { name: 'Roadmap', exact: true }).first().click();
  await expect(page.locator('[data-roadmap] .roadmap-node[data-phase]')).toHaveCount(9);
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

const progressFixture = readFileSync(join(__dirname, 'fixtures', 'fortschritt-beispiel.json'), 'utf-8');

async function openProgress(page: Page) {
  await page.route('**/assets/data/fortschritt.json', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: progressFixture }),
  );
  await page.goto('/docs/FORTSCHRITT.html');
}

test('Fortschrittsseite rendert alle vier Diagramme aus den Daten', async ({ page }) => {
  await openProgress(page);
  for (const chart of ['dataset', 'harvests', 'loo', 'abnahmen']) {
    const container = page.locator(`[data-fs-chart="${chart}"]`);
    await expect(container).toHaveAttribute('data-fs-ready', 'true');
    await expect(container.locator('svg')).toHaveCount(1);
  }
  await expect(page.locator('[data-fs-chart="dataset"] .fs-headline')).toContainText('Summe: 657 Proben');
  await expect(page.locator('[data-fs-chart="harvests"] [data-ram]')).toHaveCount(1);
  await expect(page.locator('[data-fs-chart="harvests"]')).toContainText('RAM-Zwischenablage seit 2026-09-29');
  const abnahmen = page.locator('[data-fs-chart="abnahmen"]');
  await expect(abnahmen.locator('.fs-abnahme--fail')).toHaveCount(1);
  await expect(abnahmen.locator('.fs-abnahme--pending')).toHaveCount(0);
  await expect(abnahmen.locator('.fs-limit')).toHaveCount(1);
  await expect(page.locator('[data-fs-chart="loo"] .fs-colhead')).toContainText(['Raster korr.']);
});

test('Fortschrittsdiagramm zeigt beim Überfahren einen Tooltip', async ({ page }) => {
  await openProgress(page);
  const tooltip = page.locator('.fs-tooltip');
  await page.locator('[data-fs-chart="harvests"] .fs-hit[data-run="sc6-run"]').hover();
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText('sc6-run');
  await expect(tooltip).toContainText('Aufgenommen: 2.468 Bilder');
  await page.locator('[data-fs-chart="loo"] g[data-group="auf2"][data-run="loo (e)"] .fs-cell').hover();
  await expect(tooltip).toContainText('richtig 0 · abgelehnt 76 · falsch 0');
  await expect(tooltip).toContainText('d_max');
});

test('Legende blendet eine Rolle im Datensatz aus und wieder ein', async ({ page }) => {
  await openProgress(page);
  const chart = page.locator('[data-fs-chart="dataset"]');
  await expect(chart.locator('[data-role="abnahme"]')).toHaveCount(2);
  const toggle = chart.getByRole('button', { name: 'Abnahme' });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');
  await expect(chart.locator('[data-role="abnahme"]')).toHaveCount(0);
  await expect(chart.locator('[data-role="training"]')).toHaveCount(3);
  await toggle.click();
  await expect(chart.locator('[data-role="abnahme"]')).toHaveCount(2);
});

test('loo-Zelle mit falscher Lesung ist rot hervorgehoben', async ({ page }) => {
  await openProgress(page);
  const wrong = page.locator('[data-fs-chart="loo"] .fs-cell--falsch');
  await expect(wrong).toHaveCount(1);
  await expect(page.locator('[data-fs-chart="loo"] g.fs-cell-group--falsch')).toHaveAttribute('data-group', 'test_rot');
  const [red, green, blue] = await wrong.evaluate((cell) =>
    getComputedStyle(cell).fill.match(/\d+/g)!.slice(0, 3).map(Number),
  );
  expect(red).toBeGreaterThan(150);
  expect(green).toBeLessThan(90);
  expect(blue).toBeLessThan(90);
  await expect(page.locator('[data-fs-chart="loo"] .fs-headline')).toContainText('1 Zelle mit falschen Lesungen');
});

test('fehlende Fortschrittsdaten ergeben eine lesbare Meldung', async ({ page }) => {
  await page.route('**/assets/data/fortschritt.json', (route) => route.fulfill({ status: 404, body: 'not found' }));
  await page.goto('/docs/FORTSCHRITT.html');
  const status = page.locator('[data-fs-status]');
  await expect(status).toHaveAttribute('data-state', 'error');
  await expect(status).toContainText('Die Fortschrittsdaten fehlen noch');
  await expect(page.locator('[data-fs-chart="dataset"]')).toContainText('Keine Daten.');
});

test('Fortschrittsseite bleibt auf dem Handy ohne horizontales Seiten-Scrollen', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 375, height: 800 }, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await page.route('**/assets/data/fortschritt.json', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: progressFixture }),
  );
  await page.goto('http://127.0.0.1:8766/docs/FORTSCHRITT.html');
  await expect(page.locator('[data-fs-chart="loo"]')).toHaveAttribute('data-fs-ready', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.locator('[data-fs-chart="abnahmen"] .fs-hit').first().tap();
  await expect(page.locator('.fs-tooltip')).toBeVisible();
  await context.close();
});

test('Sofortnavigation zeichnet die Fortschrittsdiagramme erneut', async ({ page }) => {
  await page.route('**/assets/data/fortschritt.json', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: progressFixture }),
  );
  await page.goto('/docs/TIMING.html');
  await page.getByRole('link', { name: 'Fortschritt Ernten/Training' }).first().click();
  await expect(page.locator('[data-fs-chart="abnahmen"]')).toHaveAttribute('data-fs-ready', 'true');
  await expect(page.locator('[data-fs-chart="loo"] .fs-cell--falsch')).toHaveCount(1);
});

const TOUR = '/docs/uebersicht/projekt-tour.html';

test('Projekt-Tour hat zu jedem Schritt eine Szene und blättert per Direktlink', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`http://127.0.0.1:8766${TOUR}`);
  const stage = page.locator('.tour-stage');
  await expect(stage).toHaveAttribute('data-scene', 'ueberblick-aufbau');
  const ids = await page.locator('.tour-step h3').evaluateAll((headings) => headings.map((h) => h.id));
  expect(ids.length).toBeGreaterThan(10);
  for (const id of ids) {
    await page.evaluate((target) => { location.hash = target; }, id);
    await expect(stage).toHaveAttribute('data-scene', id);
  }
  expect(errors).toEqual([]);
  await context.close();
});

test('Projekt-Tour: Kapitelwahl, Schrittpunkte und Tastatur', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(`http://127.0.0.1:8766${TOUR}#erkennung-zelle`);
  await expect(page.locator('.tour-caption')).toContainText('Eine Zelle lesen');
  await expect(page.locator('.tour-count')).toHaveText('6 / 10');
  // Im Endzustand (reduzierte Bewegung) ist das Ergebnis sichtbar.
  await expect(page.locator('.scene .result')).toHaveCSS('opacity', '1');

  await page.getByRole('button', { name: 'Überblick', exact: true }).click();
  await expect(page).toHaveURL(/#ueberblick-aufbau$/);
  await page.getByRole('button', { name: 'Kapitel Erkennung' }).click();
  await expect(page).toHaveURL(/#erkennung-bild$/);
  await page.getByRole('button', { name: /^Schritt 4:/ }).click();
  await expect(page).toHaveURL(/#erkennung-entzerren$/);
  await page.getByRole('button', { name: 'Weiter', exact: true }).press('ArrowRight');
  await expect(page).toHaveURL(/#erkennung-raster$/);

  // Ein Klick ins Inhaltsfeld auf einen Anker eines anderen Kapitels springt dorthin.
  await page.getByRole('button', { name: 'Training', exact: true }).click();
  await expect(page).toHaveURL(/#training-vorlagen$/);
  await page.getByRole('button', { name: /^Schritt 3:/ }).click();
  await page.locator('.tour-caption a[href$="#zeit-anzeige"]').click();
  await expect(page.locator('.tour-stage')).toHaveAttribute('data-scene', 'zeit-anzeige');
  // Kein Kapitel ist mehr nur geplant.
  await expect(page.locator('.tour-chapter-button--planned')).toHaveCount(0);
  await context.close();
});

test('Projekt-Tour spielt ohne reduzierte Bewegung selbst weiter', async ({ page }) => {
  await page.clock.install();
  await page.goto(`${TOUR}#ueberblick-weg`);
  await expect(page.locator('.tour-stage')).toHaveAttribute('data-scene', 'ueberblick-weg');
  await page.locator('.tour-ui').scrollIntoViewIfNeeded();
  await page.clock.runFor(30000);
  await expect(page).not.toHaveURL(/#ueberblick-weg$/);
  // Am Ende der Tour hält sie an.
  await page.goto(`${TOUR}#regeln-grenzen`);
  await page.locator('.tour-ui').scrollIntoViewIfNeeded();
  await page.clock.runFor(30000);
  await expect(page).toHaveURL(/#regeln-grenzen$/);
  await expect(page.getByRole('button', { name: /^Automatisch weiter/ })).toHaveAttribute('aria-pressed', 'false');
});

test('Projekt-Tour bleibt ohne JavaScript als Text lesbar und auf dem Handy ohne Querscrollen', async ({ browser }) => {
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const page = await noJs.newPage();
  await page.goto(`http://127.0.0.1:8766${TOUR}`);
  await expect(page.locator('#erkennung-zelle')).toBeVisible();
  await expect(page.locator('.tour-step').first()).toContainText('GSV-2AS');
  await noJs.close();

  const mobile = await browser.newContext({ viewport: { width: 375, height: 800 }, reducedMotion: 'reduce' });
  const phone = await mobile.newPage();
  await phone.goto(`http://127.0.0.1:8766${TOUR}#erkennung-freigabe`);
  await expect(phone.locator('.tour-stage')).toHaveAttribute('data-scene', 'erkennung-freigabe');
  expect(await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await mobile.close();
});

test('Sofortnavigation baut die Projekt-Tour als Vollseite auf, Bühnenlinks führen in die Doku', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/docs/uebersicht/messpfad.html');
  await page.getByRole('link', { name: 'Projekt-Tour', exact: true }).first().click();
  await expect(page.locator('.tour-ui .tour-stage')).toHaveAttribute('data-scene', 'ueberblick-aufbau');
  await expect(page.locator('body')).toHaveClass(/tour-page/);
  // Ohne Seitenleisten füllt die Tour die Breite, die Bühne die Höhe.
  await expect(page.locator('.md-sidebar--primary')).toBeHidden();
  const box = await page.locator('.tour-ui .tour-stage').boundingBox();
  expect(box!.width).toBeGreaterThan(900);
  expect(box!.height).toBeGreaterThan(700);

  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.tour-ui .tour-stage')).toHaveAttribute('data-scene', 'ueberblick-weg');
  await page.getByRole('link', { name: 'Ausgabe-API öffnen' }).click();
  await expect(page).toHaveURL(/\/api\/sink\.html$/);
  await expect(page.locator('body')).not.toHaveClass(/tour-page/);
  await page.goBack();
  await expect(page.locator('.tour-ui .tour-stage')).toHaveAttribute('data-scene', 'ueberblick-weg');
  await expect(page.locator('.tour-ui')).toHaveCount(1);
});

test('Projekt-Tour zeichnet Werte aus der Faktendatei und kommt ohne sie aus', async ({ browser }) => {
  const facts = JSON.parse(readFileSync(join(process.cwd(), 'site/assets/data/tour-facts.json'), 'utf8'));
  facts.facts['gate.stale_after_ns'].value = 250_000_000;
  facts.facts['record.fields'].value = [...facts.facts['record.fields'].value, 'neues_feld'];
  facts.facts['camera.focus_absolute'].value = 51;
  facts.facts['live.confirm_frames'].value = 3;
  facts.facts['gate.transition_max_cells'].value = 1;
  facts.facts['gate.transition_window_ns'].value = 120_000_000;
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.route('**/assets/data/tour-facts.json', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(facts) }),
  );
  await page.goto(`http://127.0.0.1:8766${TOUR}#erkennung-veraltet`);
  const stage = page.locator('.tour-stage');
  await expect(stage).toContainText('stale_after = 0,25 s');
  await expect(stage).toContainText('Grenze 0,25 s');
  await page.evaluate(() => { location.hash = 'erkennung-ausgabe'; });
  await expect(stage).toContainText('neues_feld');
  await expect(stage).toContainText('10 Felder');
  await page.evaluate(() => { location.hash = 'bedienung-kamera'; });
  await expect(stage).toContainText('fester Wert (51)');
  await page.evaluate(() => { location.hash = 'erkennung-freigabe'; });
  await expect(stage).toContainText('Live-Grundeinstellung: 3 Bilder');
  await expect(stage).toContainText('bis 1 unlesbare Zellen');
  await expect(stage).toContainText('höchstens 0,12 s');
  await expect(stage).toContainText('anzeige_wechselt');
  await page.evaluate(() => { location.hash = 'bedienung-werkbank'; });
  await expect(stage).toContainText('Dot-Matrix · am Aufbau gelaufen');
  await expect(stage).toContainText('TESTLAUF: markiert, keine Messnutzung');
  await expect(stage).toContainText('Kann dennoch VALID anzeigen / protokollieren');
  await expect(stage).not.toContainText('StreamCam-Anbindung folgt');
  await context.close();

  const missing = await browser.newContext({ reducedMotion: 'reduce' });
  const fallback = await missing.newPage();
  await fallback.route('**/assets/data/tour-facts.json', (route) => route.fulfill({ status: 404, body: '' }));
  await fallback.goto(`http://127.0.0.1:8766${TOUR}#erkennung-veraltet`);
  await expect(fallback.locator('.tour-stage')).toContainText('Grenze 0,5 s');
  await missing.close();
});

// Tour-Szenen als Abbildung in normalen Doku-Seiten (tour.js, Klasse Figure).
function builtPages(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return builtPages(path);
    return entry.name.endsWith('.html') ? [path] : [];
  });
}

test('Abbildungen zeigen nur Szenen, die es als Tour-Schritt gibt', async ({ browser }) => {
  const site = join(process.cwd(), 'site');
  const tour = readFileSync(join(site, 'docs/uebersicht/projekt-tour.html'), 'utf8');
  const steps = new Set([...tour.matchAll(/<h3 id="([^"]+)"/g)].map((m) => m[1]));
  const figures = new Map<string, string[]>();
  for (const file of builtPages(site)) {
    const scenes = [...readFileSync(file, 'utf8').matchAll(/<figure class="tour-figure" data-scene="([^"]*)"/g)].map((m) => m[1]);
    if (scenes.length) figures.set(file.slice(site.length), scenes);
  }
  const all = [...figures.values()].flat();
  expect(all.length).toBeGreaterThanOrEqual(13);
  expect(all.filter((scene) => !steps.has(scene))).toEqual([]);

  // Jede Abbildung findet ihre Szene und zeichnet etwas.
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const [path, scenes] of figures) {
    await page.goto(`http://127.0.0.1:8766${path}`);
    const stages = page.locator('.tour-figure .tour-stage');
    await expect(stages).toHaveCount(scenes.length);
    for (let i = 0; i < scenes.length; i++) {
      await stages.nth(i).scrollIntoViewIfNeeded();
      await expect(stages.nth(i)).toHaveAttribute('data-scene', scenes[i]);
      await expect(stages.nth(i).locator('.scene > *').first()).toBeAttached();
    }
  }
  expect(errors).toEqual([]);
  await context.close();
});

test('Abbildung spielt beim Sichtbarwerden, wiederholt per Knopf und führt in die Tour', async ({ page }) => {
  await page.clock.install();
  await page.goto('/docs/uebersicht/messpfad.html');
  const figure = page.locator('.tour-figure[data-scene="erkennung-veraltet"]');
  await expect(figure).toHaveAttribute('data-figure-ready', 'true');
  // Weit unten auf der Seite: noch nicht aufgebaut.
  await expect(figure.locator('.scene')).toHaveCount(0);
  await figure.scrollIntoViewIfNeeded();
  await expect(figure.locator('.scene')).toHaveCount(1);
  await page.clock.runFor(15000);
  // Die Klammer „… ohne gültigen Wert“ erscheint erst gegen Ende der Szene;
  // ausgeblendet wird sie über ihre Gruppe, deshalb zählt die Deckkraft aller Ebenen.
  const late = figure.locator('.scene text', { hasText: 'ohne gültigen Wert' });
  const opacity = () => late.evaluate((el) => {
    let value = 1;
    for (let node: Element | null = el; node && node.tagName !== 'svg'; node = node.parentElement) value *= Number(getComputedStyle(node).opacity);
    return value;
  });
  await expect.poll(opacity).toBe(1);

  await figure.getByRole('button', { name: /Nochmal/ }).click();
  await expect(figure.locator('.scene')).toHaveCount(1);
  await expect.poll(opacity).toBe(0);
  await page.clock.runFor(15000);
  await expect.poll(opacity).toBe(1);

  await figure.getByRole('link', { name: /In der Projekt-Tour ansehen/ }).click();
  await expect(page).toHaveURL(/projekt-tour\.html#erkennung-veraltet$/);
  // Die Sofortnavigation setzt die Adresse vor dem Austausch des Inhalts;
  // nur die Bühne der Tour zählt, nicht die Abbildungen der alten Seite.
  await expect(page.locator('.tour-ui .tour-stage')).toHaveAttribute('data-scene', 'erkennung-veraltet');
});
