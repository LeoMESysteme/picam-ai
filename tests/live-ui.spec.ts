import { expect, test, type Page } from '@playwright/test';

test('Live-Seite: Anmeldung, Einrichtung, Freigabe und Verbindungsverlust', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/live');
  await expect(page).toHaveURL(/\/login\?next=\/live$/);
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/live$/);
  // Alte Seite bis zur Ablösung in Aufgabe 12 unter /live/alt.
  await page.goto('/live/alt');
  const headline = page.locator('#headline');
  await expect(headline).toHaveText('Bereit zur Einrichtung');
  await expect(page.locator('#notice')).toContainText('Validiert nur:');
  await expect(page.locator('#confirm-box')).toBeHidden();
  await expect(page.locator('#diagnostics-enabled')).not.toBeChecked();
  await expect(page.locator('#storage-status')).toContainText('Warnung: unter 5 GB');
  await expect(page.locator('#storage-status')).toContainText('4,20 GB frei');
  await expect(page.getByLabel('Diagnosebilder aufzeichnen')).toBeVisible();
  await expect(page.locator('#mark-box')).toBeHidden();

  const setState = async (state) => {
    const statusResponse = await page.request.get('/live/status');
    expect(statusResponse.ok()).toBe(true);
    const { csrf } = await statusResponse.json();
    const response = await page.request.post('/__test__/state', {
      headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf },
      data: state,
    });
    expect(response.ok()).toBe(true);
  };

  await page.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  await expect(headline).toContainText('fokus');
  await setState({ state: 'setup_running', setup: { step: 'punktraster', elapsed_s: 12.3 } });
  await expect(headline).toContainText('punktraster');
  await expect(headline).toContainText('12.3 s');

  const failure = 'Punktraster abgelehnt: keine_startlage — Kamera senkrecht auf Displaymitte';
  await setState({ state: 'setup_failed', error: failure,
    setup: { step: 'punktraster', elapsed_s: 12.3 } });
  await expect(headline).toHaveText('Einrichtung abgebrochen');
  await expect(page.locator('#detail')).toContainText('keine_startlage');
  await expect(page.locator('#error')).toHaveText(failure);
  // Ein erfolgreicher anderer Bedienschritt darf den Fehler nicht wegwischen.
  const cameraResponse = page.waitForResponse('**/live/camera/start');
  await page.getByRole('button', { name: 'Kamera neu verbinden' }).click();
  expect((await cameraResponse).ok()).toBe(true);
  await expect(page.locator('#error')).toHaveText(failure);
  await page.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  await expect(headline).toContainText('fokus');
  await expect(page.locator('#error')).toBeEmpty();

  await setState({ state: 'setup_ready', setup: { overall: 'WARNUNG',
    overlays: ['still', 'checks'], step: 'vorschlag', elapsed_s: 15.0 } });
  await expect(headline).toHaveText('Vorschlag prüfen und bestätigen');
  await expect(page.locator('#setup-state')).toHaveText('Gesamturteil: WARNUNG');
  const overlays = page.locator('#overlays img');
  await expect(overlays).toHaveCount(2);
  await expect(overlays.nth(0)).toHaveAttribute('alt', 'still');
  await expect(overlays.nth(1)).toHaveAttribute('alt', 'checks');
  await expect.poll(() => overlays.evaluateAll((images) =>
    images.every((image) => image.complete && image.naturalWidth > 0))).toBe(true);
  await expect(page.locator('#confirm-box')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'WARNUNG zur Kenntnis genommen' })).toBeVisible();

  await page.locator('#confirmed-by').fill('Operator');
  await page.locator('#format-checked').check();
  await page.locator('#ack').check();
  const confirmRequest = page.waitForRequest('**/live/confirm');
  await page.locator('#confirm').click();
  expect((await confirmRequest).postDataJSON()).toEqual({
    session_id: 'test-session', confirmed_by: 'Operator',
    format_checked: true, acknowledge_warning: true, use_tolerance: false,
  });
  await expect(headline).toHaveText('Bestätigt – Lauf starten');

  await setState({ state: 'confirmed', run_block: 'Lauf gesperrt: Gegenlesen WARNUNG' });
  await expect(headline).toHaveText('Lauf gesperrt');
  await expect(page.locator('#run-block')).toBeVisible();
  await expect(page.locator('#run-start')).toBeDisabled();
  await page.locator('#test-override-box summary').click();
  await page.locator('#test-override').check();
  await expect(page.locator('#run-start')).toBeEnabled();

  const run = { latest: { frame_sequence: 7, status: 'valid', raw_text: '+1.2345',
    unit: 'mV/V', reject_reasons: [] }, latest_age_s: 0.2,
    rejection_causes: {window_s: 10, frames: 4, limited: false,
      causes: [{reason: 'leser:leerzelle_gestoert:14', count: 1, fraction: 0.25}]}};
  await setState({ state: 'running', run, diagnostics: {enabled: true, saved: 4, bytes: 12_500_000,
    dropped_queue: 0, dropped_limit: 0, dropped_memory: 2, dropped_mark_rate: 3, write_errors: 0},
    diagnostic_leftovers: [{path: '/test/dispread-diagnose-old', bytes: 2_500_000}] });
  await expect(page.locator('#diagnostics-status')).toContainText('12.5 MB');
  await expect(page.locator('#diagnostics-status')).toContainText('RAM verworfen: 2');
  await expect(page.locator('#diagnostics-status')).toContainText('Markenbilder verworfen: 3');
  await expect(page.locator('#diagnostics-status')).toContainText('/test/dispread-diagnose-old (2.5 MB)');
  await expect(page.locator('#recent-causes')).toBeVisible();
  await expect(page.locator('#recent-causes-list')).toContainText('Zelle 14 (rechts der Einheit)');
  await expect(page.locator('#recent-causes-list')).toContainText('25 % der Bilder');
  await expect(page.locator('#mark-box')).toBeVisible();
  await page.locator('#mark-text').fill('Display abgedeckt');
  const markRequest = page.waitForRequest('**/live/run/mark');
  await page.getByRole('button', { name: 'Ereignis markieren', exact: true }).click();
  expect((await markRequest).postDataJSON()).toEqual({text: 'Display abgedeckt'});
  await expect(page.locator('#last-mark')).toContainText('Meldezeit');
  await expect(page.locator('#last-mark')).toContainText('Display abgedeckt');
  await expect(headline).toHaveText('+1.2345 mV/V');
  await expect(headline).toHaveClass('value valid');
  await expect(headline).toHaveCSS('color', 'rgb(126, 231, 135)');
  await expect(page.locator('#confirm-box')).toBeHidden();
  await setState({ state: 'running', run: { ...run, latest_age_s: 0.9 } });
  await expect(headline).toHaveText('STALE');
  await expect(headline).toHaveClass('value stale');
  await expect(headline).not.toContainText('1.2345');

  const lost = { ...run, latest: { ...run.latest, status: 'unreadable', raw_text: '',
    reject_reasons: ['tracking_lost:rahmen_unstimmig'] }, tracking_hint: {
    kind: 'anzeige_bewegt', shift_px: 19, region_shift_px: 27, rotation_deg: -2.23, since_s: 3 } };
  await setState({ state: 'running', run: lost });
  await expect(headline).toHaveText('UNREADABLE');
  await expect(page.locator('#detail')).toContainText('Anzeige hat sich bewegt (ca. 19 px (Ecken), 2,2 Grad)');
  await expect(page.locator('#detail')).toContainText('Werte werden nicht freigegeben. Bitte neu einrichten.');
  await setState({ state: 'running', run: { ...lost, tracking_hint: {
    kind: 'rahmen_verdeckt', shift_px: null, rotation_deg: null, since_s: 10 } } });
  await expect(page.locator('#detail')).toContainText('Rahmen verdeckt? Hand oder Gegenstand');
  await expect(page.locator('#detail')).not.toContainText('Anzeige hat sich bewegt');
  await setState({ state: 'running', run: { ...lost, tracking_hint: {
    kind: 'unbekannt', shift_px: null, rotation_deg: null, since_s: 12 } } });
  await expect(page.locator('#detail')).toContainText('Anzeige nicht sicher wiedergefunden');

  // Erst wieder frische Ziffern zeigen, dann die echte Poll-Anfrage abbrechen.
  await setState({ state: 'running', run });
  await expect(headline).toHaveText('+1.2345 mV/V');
  await expect(page.locator('#detail')).not.toContainText('einrichten');
  await page.route('**/live/status', (route) => route.abort('connectionfailed'));
  await expect(headline).toHaveText('STALE');
  await expect(headline).not.toContainText('1.2345');
  await expect(page.locator('#detail')).toHaveText('Verbindung zur Werkbank verloren');
  expect(errors).toEqual([]);
});

test('Rahmenbereiche: Tastatur und Bildklick ändern Revision und verlangen neue Bestätigung', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/live');
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/live$/);
  // Alte Seite bis zur Ablösung in Aufgabe 12 unter /live/alt.
  await page.goto('/live/alt');
  const { csrf } = await (await page.request.get('/live/status')).json();
  const stateResponse = await page.request.post('/__test__/state', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf },
    data: {state: 'setup_ready', setup: {overall: 'OK', proposal_revision: 'regions-v1',
      auswahl: 'automatisch', overlays: ['overlay_source'], checks: {nachfuehrung: 'OK'},
      regions: [{centre: [10, 10], size: 5}]}},
  });
  expect(stateResponse.ok()).toBe(true);
  await expect(page.locator('#region-editor')).toBeVisible();
  await page.locator('#confirmed-by').fill('Operator');
  await page.locator('#format-checked').check();
  await page.getByLabel('Quellbild-Koordinaten x,y').fill('30,12');
  const added = page.waitForRequest('**/live/setup/regions');
  await page.getByRole('button', {name: 'Bereich hinzufügen', exact: true}).click();
  expect((await added).postDataJSON()).toEqual({proposal_revision: 'regions-v1', add: [[30, 12]], remove: []});
  await expect(page.locator('#region-list li')).toHaveCount(2);
  await expect(page.locator('#region-results')).toContainText('30,12 (verwendet: 30,12): geeignet');
  await expect(page.locator('#confirmed-by')).toHaveValue('');
  await expect(page.locator('#format-checked')).not.toBeChecked();
  await expect(page.locator('#region-selection')).toHaveText('Auswahl: manuell');
  await page.getByRole('checkbox', {name: 'Rahmenbereiche bearbeiten', exact: true}).check();
  const image = page.locator('img[alt="overlay_source"]');
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(48);
  const box = await image.boundingBox();
  const removed = page.waitForRequest('**/live/setup/regions');
  await image.click({position: {x: box!.width * 10 / 48, y: box!.height * 10 / 24}});
  const body = (await removed).postDataJSON();
  expect(body.remove).toEqual([0]);
  expect(body.add).toEqual([]);
  expect(body.proposal_revision).not.toBe('regions-v1');
  await expect(page.locator('#region-list li')).toHaveCount(1);
  await page.getByRole('button', {name: /Bereich 1 entfernen/}).click();
  await expect(page.locator('#region-list li')).toHaveCount(0);
  await expect(page.locator('#setup-checks')).toContainText('Nachführung: FEHLER');
  const revision = (await (await page.request.get('/live/status')).json()).setup.proposal_revision;
  for (const edit of [{add: [[1e300, 12]], remove: []}, {add: [], remove: ['0']}]) {
    const rejected = await page.request.post('/live/setup/regions', {
      headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf },
      data: {proposal_revision: revision, ...edit},
    });
    expect(rejected.status()).toBe(400);
  }
  expect((await (await page.request.get('/live/status')).json()).setup.proposal_revision).toBe(revision);
  const scaled = (await image.boundingBox())!;
  const fractional = page.waitForRequest('**/live/setup/regions');
  await image.click({position: {x: scaled.width * 35.8 / 48, y: scaled.height * 12.8 / 24}});
  expect((await fractional).postDataJSON()).toEqual({proposal_revision: revision, add: [[35, 12]], remove: []});
  await expect(page.locator('#region-list li')).toHaveCount(1);
  expect(errors).toEqual([]);
});

async function login(page: Page) {
  await page.goto('/live');
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/live$/);
}

async function hook(page: Page, path: string, data: unknown) {
  const { csrf } = await (await page.request.get('/live/status')).json();
  const response = await page.request.post(path, {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf }, data,
  });
  expect(response.ok()).toBe(true);
}

test('Hülle zeigt Titel, Docks und Statusleiste in Szene idle', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });

  const title = page.getByRole('banner');
  await expect(title).toContainText('picam-ai Werkbank');
  await expect(title.getByRole('navigation', { name: 'Ablauf' })).toHaveText(/Einrichtung\s*Lauf/);
  await expect(title.locator('[aria-current="step"]')).toHaveText('Einrichtung');
  await expect(title).toContainText('GSV-2AS · Displaytech 161A');
  const start = title.getByRole('button', { name: 'Einrichtung starten', exact: true });
  await expect(start).toBeEnabled();

  const left = page.getByRole('complementary', { name: 'Ablauf' });
  await expect(left).toContainText('Bereit zur Einrichtung');
  await expect(left.locator('[data-step] b')).toHaveText(
    ['Fokus', 'Kamera', 'Belichtung', 'Standbilder', 'Vorschlag', 'Prüfen & Bestätigen']);
  await expect(left.locator('[data-step]').first()).toHaveAttribute('data-state', 'pending');
  await expect(left).toContainText('test-session');
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector).toContainText('Inspektor');
  await expect(inspector.getByRole('tab')).toHaveText(['Schritt', 'Fokus', 'Prüfungen']);
  await expect(inspector.getByRole('tab', { name: 'Schritt' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('region', { name: 'Bildansicht' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Zeitleiste' })).toBeVisible();

  const bar = page.getByRole('contentinfo');
  for (const text of ['StreamCam', 'Vorschau', 'Bilder', 'Lücken', 'Latenz', 'SD', '4,20 GB', 'Sitzung', 'test-session']) {
    await expect(bar).toContainText(text);
  }
  await expect(bar).toContainText('Validiert nur:');

  // Maße wie im Mock, keine horizontale Rollleiste, Schriften lokal geladen.
  expect(Math.round((await left.boundingBox())!.width)).toBe(248);
  expect(Math.round((await inspector.boundingBox())!.width)).toBe(368);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([document.fonts.load('13px "Noto Sans"'), document.fonts.load('13px "Noto Sans Mono"')]);
    return document.fonts.check('13px "Noto Sans"') && document.fonts.check('13px "Noto Sans Mono"');
  })).toBe(true);
  // Echte Schnitte statt synthetischer Fettung: die Titel nutzen 600, die Marke 600, Knöpfe 500.
  expect(await page.evaluate(async () => {
    await Promise.all(['500', '600', '700'].map((w) => document.fonts.load(`${w} 13px "Noto Sans"`)));
    return [...document.fonts].filter((f) => f.family.replace(/"/g, '') === 'Noto Sans' && f.status === 'loaded')
      .map((f) => f.weight).sort();
  })).toEqual(['400', '500', '600', '700']);
  await expect(page.locator('body')).toHaveCSS('font-synthesis-weight', 'none');
  await expect(page.locator('body')).toHaveCSS('font-size', '13px');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(22, 21, 19)');

  // Die Kontextaktion geht mit CSRF an den Server, der Ablauf folgt dem Status.
  const request = page.waitForRequest('**/live/setup');
  await start.click();
  expect((await request).postDataJSON()).toEqual({ cell_text: null });
  await expect(left.locator('[data-step="fokus"]')).toHaveAttribute('data-state', 'running');
  await expect(title.getByRole('button', { name: 'Einrichtung starten', exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('Viewer zoomt um den Zeiger und Popover erklärt Rahmenbereich', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });

  const viewer = page.getByRole('region', { name: 'Bildansicht' });
  const canvas = viewer.locator('canvas.vcanvas');
  // Bild und HUD kommen aus demselben MJPEG-Teil.
  await expect(canvas).toHaveAttribute('data-seq', /^\d+$/);
  await expect(canvas).toHaveAttribute('data-hud', 'track');
  const box = (await canvas.boundingBox())!;
  const toScreen = (point: number[]) => canvas.evaluate((el: any, p) => el.viewer.imageToScreen(p), point);
  const toImage = (point: number[]) => canvas.evaluate((el: any, p) => el.viewer.screenToImage(p), point);

  // Rahmenbereich 4 (Index 3) liegt im Fake bei 1485, 658.
  const [rx, ry] = await toScreen([1485, 658]);
  await page.mouse.move(box.x + rx, box.y + ry);
  const pop = viewer.locator('.vpop');
  await expect(pop).toBeVisible();
  await expect(pop).toContainText('Rahmenbereich 4');
  await expect(pop).toContainText('Suchfenster-Mitte');
  await expect(pop).toContainText('1485, 658');
  await expect(pop).toContainText('Treffer');
  await expect(pop).toContainText('0,92');
  await expect(pop).not.toContainText('%');

  // Zellen kommen aus dem Leser-Raster des Status (setup.grid).
  const [cx, cy] = await canvas.evaluate(async (el: any) => {
    const {cellQuads} = await import('/static/live/viewer/hud.js');
    const box = cellQuads(el.viewer.hud().track.quad, el.viewer.grid())[8];
    const mid = [0, 1].map((k) => box.reduce((sum: number, p: number[]) => sum + p[k], 0) / 4);
    return el.viewer.imageToScreen(mid);
  });
  await page.mouse.move(box.x + cx, box.y + cy);
  await expect(pop).toContainText('Zelle 8');
  await expect(pop).toContainText('Abstand');
  await page.mouse.move(box.x + rx, box.y + ry);
  await expect(pop).toContainText('Rahmenbereich 4');

  // Klick heftet an, Wegbewegen schliesst nicht, Esc schliesst.
  await page.mouse.click(box.x + rx, box.y + ry);
  await page.mouse.move(box.x + 20, box.y + box.height - 20);
  await expect(pop).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(pop).toBeHidden();

  // Mausrad zoomt um den Zeiger: der Bildpunkt darunter bleibt stehen.
  const zoomLabel = viewer.locator('[data-part="zoom"]');
  const before = await zoomLabel.textContent();
  const pointer = [box.width * 0.3, box.height * 0.4];
  await page.mouse.move(box.x + pointer[0], box.y + pointer[1]);
  const anchor = await toImage(pointer);
  await page.mouse.wheel(0, -400);
  await expect(zoomLabel).not.toHaveText(before!);
  const moved = await toImage(pointer);
  expect(Math.hypot(moved[0] - anchor[0], moved[1] - anchor[1])).toBeLessThan(1);
  expect(Number.parseInt((await zoomLabel.textContent())!, 10)).toBeGreaterThan(Number.parseInt(before!, 10));

  // Einpassen und 1:1 aus der Werkzeugleiste.
  await viewer.getByRole('button', { name: '1:1' }).click();
  await expect(zoomLabel).toHaveText('100 %');
  await viewer.getByRole('button', { name: 'Einpassen' }).click();
  await expect(zoomLabel).not.toHaveText('100 %');

  // Ebenen einzeln schaltbar; ohne Rahmenbereiche gibt es dort keinen Treffer.
  await viewer.getByRole('button', { name: 'Ebenen' }).click();
  const menu = viewer.getByRole('menu');
  await expect(menu.getByRole('menuitemcheckbox')).toHaveText(
    ['Anzeige', 'Raster', 'Zellen', 'Rahmenbereiche', 'Fokus-ROI', 'Wert-Etikett']);
  await menu.getByRole('menuitemcheckbox', { name: 'Rahmenbereiche' }).click();
  await expect(menu.getByRole('menuitemcheckbox', { name: 'Rahmenbereiche' })).toHaveAttribute('aria-checked', 'false');
  await page.keyboard.press('Escape');
  const [qx, qy] = await toScreen([1485, 658]);
  await page.mouse.move(box.x + qx, box.y + qy);
  await expect(pop).toBeHidden();

  // Legende erklärt die Symbole; Quellen ohne Bild sind gesperrt mit Grund.
  await viewer.getByRole('button', { name: 'Legende' }).click();
  await expect(viewer.locator('.legend')).toContainText('Rahmenbereich ohne Treffer');
  await expect(viewer.getByRole('button', { name: 'Live', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(viewer.getByRole('button', { name: 'Standbild' })).toBeEnabled();
  // Standbild aus der Einrichtung: eigenes Bild, kein Live-HUD darüber.
  const still = page.waitForResponse((r) => r.url().includes('/live/setup/overlay_source.png'));
  await viewer.getByRole('button', { name: 'Standbild' }).click();
  expect((await still).ok()).toBe(true);
  await expect(viewer.locator('[data-part="chip"]')).toContainText('Standbild · aus der Einrichtung');
  await page.mouse.move(box.x + qx, box.y + qy);
  await expect(pop).toBeHidden();
  await viewer.getByRole('button', { name: 'Live', exact: true }).click();
  await expect(viewer.locator('[data-part="chip"]')).toContainText(/Live · \d+ fps/);

  // Gemessene Vorschau-Rate in der Statusleiste.
  await expect(page.locator('[data-slot="preview-fps"]')).toHaveText(/^\d+ fps$/);
  expect(errors).toEqual([]);
});
