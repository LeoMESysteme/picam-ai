import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { mockSessionArchive } from './session-fixtures';

// Grafiken der lebendigen Darstellung: Messkette der Startseite, Weg-Signets,
// zeichnende Fortschrittslinie, Lichtband der Laufmatrix. Ohne eigene Wahl gilt
// hier wie in docs-site.spec.ts „ruhig“; lebendig(page) setzt die andere.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { if (!localStorage.getItem('wiki-look')) localStorage.setItem('wiki-look', 'ruhig'); } catch { /* gesperrter Speicher */ }
  });
});
const lebendig = (page: Page) => page.addInitScript(() => {
  try { localStorage.setItem('wiki-look', 'lebendig'); } catch { /* gesperrter Speicher */ }
});

const kette = JSON.parse(readFileSync('docs-site/assets/data/kette.json', 'utf8')) as {
  stufen: { id: string; titel: string; zustand: string; zweck: string; doku: string }[];
};
const messkette = (page: Page) => page.locator('.wiki-messkette[data-messkette]');
const meineAnimationen = (page: Page, selector: string) => page.evaluate((sel) => document.getAnimations()
  .filter((animation) => (animation.effect as KeyframeEffect | null)?.target?.closest?.(sel)).length, selector);

test('Messkette: alle Stufen aus kette.json, Links auf die Doku, Zweck beim Überfahren', async ({ page }) => {
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const host = messkette(page);
  const nodes = host.locator('a.wmk-knoten');
  await expect(nodes).toHaveCount(kette.stufen.length);
  await expect(host.locator('.wmk-titel')).toHaveText(kette.stufen.map((stage) => stage.titel));
  for (const [index, stage] of kette.stufen.entries()) {
    const node = nodes.nth(index);
    await expect(node).toHaveAttribute('data-stufe', stage.id);
    expect(new URL(await node.evaluate((link) => (link as HTMLAnchorElement).href)).pathname).toBe(`/${stage.doku}`);
    await expect(node.locator('.wmk-zustand')).toHaveText(stage.zustand);
  }
  // Ehrlicher Zustand der Ausgabe: gesperrte DUT-Ausgabe aus kette.json.
  await expect(host.locator('a[data-stufe="sink"] .wmk-sperre')).toHaveText('DUT gesperrt');
  // In „lebendig“ ersetzt die Bühne die kompakte Kette (keine doppelte Information).
  await expect(page.locator('.wiki-kette[data-variant="kompakt"]')).toBeHidden();

  const ocr = host.locator('a[data-stufe="ocr"]');
  await ocr.hover();
  await expect(host.locator('.wmk-text')).toContainText(kette.stufen.find((stage) => stage.id === 'ocr')!.zweck);
  await expect(host.locator('.wmk')).toHaveAttribute('data-lauf', 'angehalten');
  await expect(host.locator('.wmk-form--an')).toHaveAttribute('data-form', 'ocr');
  await page.mouse.move(5, 5);
  await expect(host.locator('.wmk')).toHaveAttribute('data-lauf', 'läuft', { timeout: 4000 });

  // Tastatur: Stufen sind Links in Lesereihenfolge; Fokus zeigt den Zweck.
  await nodes.first().focus();
  await expect(host.locator('.wmk-text')).toContainText(kette.stufen[0].zweck);
  await page.keyboard.press('Tab');
  await expect(nodes.nth(1)).toBeFocused();
  await expect(host.locator('.wmk-text')).toContainText(kette.stufen[1].zweck);
  await nodes.nth(1).click();
  await expect(page).toHaveURL(new RegExp(`/${kette.stufen[1].doku.replace(/\./g, '\\.')}$`));
});

test('Messkette: der Wert wandert nur in lebendig, in ruhig bleibt der Platzhalter leer', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const host = messkette(page);
  await expect(page.locator('.wiki-kette[data-variant="kompakt"] .wiki-kette-node')).toHaveCount(7);
  await expect(host).toBeEmpty();
  expect(await host.evaluate((node) => node.getBoundingClientRect().height)).toBe(0);

  // Umschalten zur Laufzeit: Bühne erscheint und läuft …
  await page.locator('.wiki-look-switch').click();
  await expect(host.locator('a.wmk-knoten')).toHaveCount(kette.stufen.length);
  await expect(host.locator('.wmk')).toHaveAttribute('data-lauf', 'läuft');
  const seen = new Set<string>();
  for (let i = 0; i < 16 && seen.size < 3; i++) {
    seen.add(await host.locator('.wmk-form--an').getAttribute('data-form') ?? '');
    await page.waitForTimeout(400);
  }
  expect(seen.size, `gesehene Formen: ${[...seen].join(', ')}`).toBeGreaterThanOrEqual(3);

  // … und verschwindet wieder, ohne Animationen zu hinterlassen.
  await page.locator('.wiki-look-switch').click();
  await expect(host).toBeEmpty();
  await expect(page.locator('.wiki-kette[data-variant="kompakt"]')).toBeVisible();
  expect(await meineAnimationen(page, '.wiki-messkette')).toBe(0);
});

test('Messkette: die Linse ist während des Laufs nie leer, Inhalte passen in ihren Rahmen', async ({ page }) => {
  test.setTimeout(60000);
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const host = messkette(page);
  await expect(host.locator('.wmk')).toHaveAttribute('data-lauf', 'läuft');
  // Kein Inhalt ragt über den Rahmen 160 × 84 hinaus (sonst schneidet die Linse ab).
  const overflow = await host.locator('.wmk-formen .wmk-form').evaluateAll((forms) => forms.map((form) => {
    const box = (form as SVGSVGElement).getBBox();
    return box.x >= -0.5 && box.y >= -0.5 && box.x + box.width <= 160.5 && box.y + box.height <= 84.5 ? '' : (form as SVGElement).dataset.form;
  }).filter(Boolean));
  expect(overflow).toEqual([]);
  // Über gut einen Durchlauf samt Rückfahrt: Unter einer laufenden Wischblende
  // liegt immer eine voll sichtbare, nicht beschnittene Form, die Linse ist deckend.
  const seen = new Set<string>();
  for (let i = 0; i < 45; i++) {
    const state = await host.evaluate((node) => {
      const carrier = node.querySelector('.wmk-traeger') as HTMLElement;
      const base = [...node.querySelectorAll('.wmk-formen .wmk-form--an')] as SVGElement[];
      const top = node.querySelector('.wmk-formen .wmk-form--neu') as SVGElement | null;
      const full = base.filter((form) => getComputedStyle(form).opacity === '1' && ['none', 'inset(0px)'].includes(getComputedStyle(form).clipPath));
      return { carrier: getComputedStyle(carrier).opacity, base: base.length, full: full.length, form: full[0]?.dataset.form ?? '', wipe: top?.dataset.form ?? '' };
    });
    expect(state.carrier, `Bild ${i}`).toBe('1');
    expect(state.base, `Bild ${i}`).toBe(1);
    expect(state.full, `Bild ${i}: ${JSON.stringify(state)}`).toBe(1);
    seen.add(state.form);
    if (state.wipe) seen.add(state.wipe);
    await page.waitForTimeout(280);
  }
  expect(seen.size).toBeGreaterThanOrEqual(5);
});

const UNTERSCHRIFT: Record<string, RegExp> = {
  frames: /^Bild mit Zeitstempel$/, detect: /^Anzeige gefunden$/, track: /^Viereck nachgeführt$/,
  rectify: /^entzerrtes Raster$/, ocr: /^gelesen: /, validate: /^Datensatz · VALID$/, sink: /^Audit · DUT gesperrt$/,
};

test('Messkette: Unterschrift, Form und markierter Knoten gehören immer zur selben Stufe', async ({ page }) => {
  test.setTimeout(60000);
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const host = messkette(page);
  await expect(host.locator('.wmk')).toHaveAttribute('data-lauf', 'läuft');
  const seen = new Set<string>();
  for (let i = 0; i < 30; i++) {
    const state = await host.evaluate((node) => ({
      knoten: (node.querySelector('.wmk-hier a.wmk-knoten') as HTMLElement | null)?.dataset.stufe ?? '',
      form: (node.querySelector('.wmk-formen .wmk-form--an') as SVGElement | null)?.dataset.form ?? '',
      text: node.querySelector('.wmk-traeger-text')?.textContent ?? '',
    }));
    expect(state.knoten, `Bild ${i}: ${JSON.stringify(state)}`).toBe(state.form);
    expect(state.text, `Bild ${i}: ${JSON.stringify(state)}`).toMatch(UNTERSCHRIFT[state.form]);
    seen.add(state.form);
    await page.waitForTimeout(230);
  }
  expect(seen.size).toBeGreaterThanOrEqual(5);
});

test('Messkette: nach zwei Durchläufen Ruhe im Endzustand, „Nochmal“ startet neu', async ({ page }) => {
  test.setTimeout(90000);
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const host = messkette(page);
  const figure = host.locator('.wmk');
  const again = host.getByRole('button', { name: 'Messweg nochmal abspielen' });
  await expect(figure).toHaveAttribute('data-lauf', 'läuft');
  await expect(again).toBeHidden();
  await expect(figure).toHaveAttribute('data-lauf', 'ruht', { timeout: 40000 });
  await expect(figure).toHaveAttribute('data-durchlauf', '2');
  await expect(host.locator('.wmk-formen .wmk-form--an')).toHaveAttribute('data-form', 'sink');
  await expect(host.locator('.wmk-hier a.wmk-knoten')).toHaveAttribute('data-stufe', 'sink');
  await expect(again).toBeVisible();
  await page.waitForTimeout(1500);
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running'
    && (a.effect as KeyframeEffect | null)?.target?.closest?.('.wiki-messkette')).length)).toBe(0);
  await expect(figure).toHaveAttribute('data-lauf', 'ruht');
  // Linien-Icon statt Zeichen.
  await expect(again.locator('svg path')).toHaveCount(1);

  await again.click();
  await expect(figure).toHaveAttribute('data-lauf', 'läuft');
  await expect(again).toBeHidden();
  await expect(host.locator('.wmk-formen .wmk-form--an')).toHaveAttribute('data-form', 'frames', { timeout: 3000 });
});

test('Messkette: reduzierte Bewegung zeigt jede Stufe als Standbild, ohne Animation', async ({ page }) => {
  await lebendig(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/index.html');
  const host = messkette(page);
  await expect(host.locator('.wmk')).toHaveAttribute('data-modus', 'standbild');
  await expect(host.locator('.wmk-standbild')).toHaveCount(kette.stufen.length);
  await expect(host.locator('.wmk-traeger')).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running'
    && (a.effect as KeyframeEffect | null)?.target?.closest?.('.wiki-messkette')).length)).toBe(0);
  // Die Schiene ist voll: Endzustand.
  const fill = await host.locator('.wmk-fuellung').evaluate((node) => getComputedStyle(node).transform);
  expect(fill).toBe('matrix(1, 0, 0, 1, 0, 0)');
});

for (const reduce of [false, true]) {
  test(`Messkette schmal (390 px${reduce ? ', reduziert' : ''}): senkrecht, ohne Querscrollen`, async ({ page }) => {
    await lebendig(page);
    await page.setViewportSize({ width: 390, height: 844 });
    if (reduce) await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/index.html');
    const host = messkette(page);
    await expect(host.locator('a.wmk-knoten')).toHaveCount(kette.stufen.length);
    await expect(host.locator('.wmk-schiene')).toHaveAttribute('data-richtung', 'senkrecht');
    const tops = await host.locator('.wmk-punkt').evaluateAll((dots) => dots.map((dot) => dot.getBoundingClientRect().top));
    for (let i = 1; i < tops.length; i++) expect(tops[i]).toBeGreaterThan(tops[i - 1]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    const figure = await host.locator('.wmk').boundingBox();
    expect(figure!.x + figure!.width).toBeLessThanOrEqual(390);
  });
}

for (const width of [390, 1024, 1440]) {
  test(`Messkette ${width} px: Unterschriften ganz lesbar, Schilder gleich hoch`, async ({ page }) => {
    await lebendig(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/index.html');
    const host = messkette(page);
    await expect(host.locator('a.wmk-knoten')).toHaveCount(kette.stufen.length);
    await page.evaluate(() => document.fonts.ready);
    for (const stage of kette.stufen) {
      await host.locator(`a[data-stufe="${stage.id}"]`).hover();
      await expect(host.locator('.wmk-form--an')).toHaveAttribute('data-form', stage.id);
      await page.waitForTimeout(350);
      const fit = await host.evaluate((node) => {
        const figure = node.querySelector('.wmk')!.getBoundingClientRect();
        const lens = node.querySelector('.wmk-traeger')!.getBoundingClientRect();
        const label = node.querySelector('.wmk-traeger-text') as HTMLElement;
        const box = label.getBoundingClientRect();
        return {
          clipped: label.scrollWidth > label.clientWidth + 1,
          lines: Math.round(box.height / parseFloat(getComputedStyle(label).lineHeight)),
          lensInside: lens.left >= figure.left - 1 && lens.right <= figure.right + 1,
          labelInside: box.left >= lens.left - 1 && box.right <= lens.right + 1 && box.bottom <= lens.bottom + 1,
        };
      });
      expect(fit, stage.id).toEqual({ clipped: false, lines: fit.lines, lensInside: true, labelInside: true });
      expect(fit.lines, stage.id).toBeLessThanOrEqual(2);
    }
    const sperre = host.locator('.wmk-sperre');
    expect(await sperre.evaluate((node) => Math.round(node.getBoundingClientRect().height / parseFloat(getComputedStyle(node).lineHeight)))).toBe(1);
    if (width > 390) {
      const heights = await host.locator('.wmk-schild').evaluateAll((signs) => signs.map((sign) => (sign as HTMLElement).offsetHeight));
      expect(new Set(heights).size, heights.join(', ')).toBe(1);
    }
  });
}

test('Messkette: läuft nur im Blick und räumt bei Sofortnavigation auf', async ({ page }) => {
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/index.html');
  const figure = messkette(page).locator('.wmk');
  await expect(figure).toHaveAttribute('data-lauf', 'läuft');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(figure).toHaveAttribute('data-lauf', 'angehalten');
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(figure).toHaveAttribute('data-lauf', 'läuft');
  await page.locator('.md-nav--primary a', { hasText: 'Aktueller Stand' }).first().click();
  await expect(page.locator('.md-content__inner h1')).toBeVisible();
  await expect(page.locator('.wiki-messkette')).toHaveCount(0);
  await page.waitForTimeout(1200);
  expect(await page.evaluate(() => document.getAnimations().filter((a) => {
    const target = (a.effect as KeyframeEffect | null)?.target as Element | null;
    return target && !target.isConnected;
  }).length)).toBe(0);
});

test('Signet: Rollenfarbe und Zeichnen nur in lebendig', async ({ page }) => {
  const path = '/docs/CAMERA_COMMISSIONING.html';
  await page.goto(path);
  const icon = page.locator('.wiki-pagehead-weg svg');
  await expect(page.locator('.wiki-pagehead')).toHaveAttribute('data-ready', 'true');
  const weg = await page.locator('.wiki-pagehead').getAttribute('data-weg');
  expect(weg).toBe('bedienen');
  expect(await icon.locator('path').first().evaluate((node) => (node as SVGPathElement).style.strokeDasharray)).toBe('');
  const ruhigColor = await icon.evaluate((node) => getComputedStyle(node).color);

  await lebendig(page);
  await page.goto(path);
  await expect(icon).toHaveAttribute('data-signet', 'zeichnet');
  const expected = await page.evaluate(() => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--docs-resolved-fg)';
    document.querySelector('.md-content__inner')!.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  });
  expect(await icon.evaluate((node) => getComputedStyle(node).color)).toBe(expected);
  expect(expected).not.toBe(ruhigColor);
  const dashes = await icon.locator('path').evaluateAll((paths) => paths.map((node) => (node as SVGPathElement).style.strokeDasharray));
  expect(dashes.length).toBeGreaterThan(1);
  for (const dash of dashes) expect(Number.parseFloat(dash)).toBeGreaterThan(0);
  const bbox = await icon.boundingBox();
  expect(bbox!.width).toBeLessThanOrEqual(15);

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(path);
  await expect(page.locator('.wiki-pagehead')).toHaveAttribute('data-ready', 'true');
  expect(await icon.locator('path').first().evaluate((node) => (node as SVGPathElement).style.strokeDasharray)).toBe('');
});

test('Fortschritt: die Verlustlinie zeichnet sich beim ersten Sichtbarwerden', async ({ page }) => {
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/docs/FORTSCHRITT.html');
  const chart = page.locator('[data-fs-chart="harvests"]');
  await expect(chart).toHaveAttribute('data-fs-ready', 'true');
  const line = chart.locator('polyline.fs-line');
  if (await line.count() === 0) test.skip(true, 'weniger als zwei Ernten mit Verlustquote');
  await line.scrollIntoViewIfNeeded();
  await expect(line).toHaveAttribute('data-zeichnet', 'true');
  await expect(chart).toHaveAttribute('data-fs-line-drawn', 'true');
  // Ende: kein Strichmuster bleibt zurück, Linie vollständig.
  await expect.poll(() => line.evaluate((node) => (node as SVGElement).style.strokeDasharray), { timeout: 3000 }).toBe('');
});

test('Fortschritt ruhig: die Linie steht ohne Zeichenanimation da', async ({ page }) => {
  await page.goto('/docs/FORTSCHRITT.html');
  const chart = page.locator('[data-fs-chart="harvests"]');
  await expect(chart).toHaveAttribute('data-fs-ready', 'true');
  const line = chart.locator('polyline.fs-line');
  if (await line.count() === 0) test.skip(true, 'weniger als zwei Ernten mit Verlustquote');
  await line.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await expect(chart).not.toHaveAttribute('data-fs-line-drawn', 'true');
  expect(await line.evaluate((node) => (node as SVGElement).style.strokeDasharray)).toBe('');
});

test('Laufmatrix: Lichtband folgt per Pfeiltaste und gleitet', async ({ page }) => {
  await mockSessionArchive(page);
  await lebendig(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/docs/session-explorer.html');
  const plot = page.locator('#session-trends .session-plot svg[tabindex="0"]').first();
  await expect(plot).toBeVisible({ timeout: 15000 });
  const lens = page.locator('#session-trends .session-plot .session-lens').first();
  await plot.focus();
  await expect(lens).toHaveAttribute('data-on', 'true');
  await expect(page.locator('#session-trends .session-band').first()).toBeHidden();
  const x = () => lens.evaluate((node) => new DOMMatrix(getComputedStyle(node).transform).m41);
  await page.waitForTimeout(500);
  const start = await x();
  await page.keyboard.press('Home');
  await page.waitForTimeout(500);
  const first = await x();
  expect(first).toBeLessThan(start);
  // Bildweise mitschreiben: beim Gleiten gibt es Zwischenlagen zwischen altem und neuem Lauf.
  const sampling = lens.evaluate((node) => new Promise<number[]>((resolve) => {
    const values: number[] = [];
    const end = performance.now() + 700;
    const tick = () => {
      values.push(new DOMMatrix(getComputedStyle(node).transform).m41);
      if (performance.now() < end) requestAnimationFrame(tick); else resolve(values);
    };
    requestAnimationFrame(tick);
  }));
  await page.keyboard.press('ArrowRight');
  const values = await sampling;
  const second = values[values.length - 1];
  expect(second).toBeGreaterThan(first);
  expect(values.some((value) => value > first + 1 && value < second - 1), `Lagen: ${values.join(', ')}`).toBe(true);
  // Tabellenzeile bleibt synchron, Tooltip bleibt wie er ist.
  await expect(page.locator('#session-list tr.session-row--active')).toHaveCount(1);
  await expect(page.locator('#session-trends .session-tip[data-open="true"]').first()).toBeVisible();
});

test('Laufmatrix ruhig: festes Band, kein Lichtband', async ({ page }) => {
  await mockSessionArchive(page);
  await page.goto('/docs/session-explorer.html');
  const plot = page.locator('#session-trends .session-plot svg[tabindex="0"]').first();
  await expect(plot).toBeVisible({ timeout: 15000 });
  await plot.focus();
  await expect(page.locator('#session-trends .session-band').first()).toBeVisible();
  await expect(page.locator('#session-trends .session-lens').first()).toBeHidden();
});

for (const look of ['ruhig', 'lebendig'] as const) {
  test(`Fortschritt (${look}): Achsentexte der Ernten überschneiden sich nicht`, async ({ page }) => {
    if (look === 'lebendig') await lebendig(page);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/docs/FORTSCHRITT.html');
      const chart = page.locator('[data-fs-chart="harvests"]');
      await expect(chart).toHaveAttribute('data-fs-ready', 'true');
      const overlaps = await chart.locator('svg.fs-svg').first().evaluate((svg) => {
        const rows = new Map<string, DOMRect[]>();
        for (const text of svg.querySelectorAll('text[text-anchor="middle"]')) {
          const box = (text as SVGTextElement).getBBox();
          const y = text.getAttribute('y') ?? '';
          if (!rows.has(y)) rows.set(y, []);
          rows.get(y)!.push(box as DOMRect);
        }
        const hits: string[] = [];
        for (const [y, boxes] of rows) {
          boxes.sort((a, b) => a.x - b.x);
          for (let i = 1; i < boxes.length; i++) {
            if (boxes[i].x < boxes[i - 1].x + boxes[i - 1].width) hits.push(`y=${y} #${i}`);
          }
        }
        return hits;
      });
      expect(overlaps, `${width} px`).toEqual([]);
    }
  });
}
