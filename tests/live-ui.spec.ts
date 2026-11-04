import { expect, test, type BrowserContext, type Page } from '@playwright/test';

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

// Der Server lässt je Adresse nur 5 Anmeldungen pro Minute zu (auth.py);
// die Tests teilen sich deshalb ein Sitzungs-Cookie (ein Worker).
let sessionCookies: Awaited<ReturnType<BrowserContext['cookies']>> | null = null;

async function login(page: Page) {
  if (sessionCookies) {
    await page.context().addCookies(sessionCookies);
    await page.goto('/live');
    if (/:\d+\/live$/.test(page.url())) return;
  }
  await page.goto('/live');
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/live$/);
  sessionCookies = await page.context().cookies();
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

// ---------------------------------------------------------------------------
// Einrichtungsansicht (Aufgabe 8)
// ---------------------------------------------------------------------------
function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  return errors;
}

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

// Klickt im Viewer auf einen Punkt des Kamerabilds (1920×1080).
async function clickImage(page: Page, point: number[]) {
  const canvas = page.locator('canvas.vcanvas');
  await expect(canvas).toHaveAttribute('data-seq', /^\d+$/);
  const box = (await canvas.boundingBox())!;
  const [x, y] = await canvas.evaluate((el: any, p) => el.viewer.imageToScreen(p), point);
  await page.mouse.click(box.x + x, box.y + y);
  return [box.x + x, box.y + y];
}

test('Einrichtung zeigt Fokuskurve live', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_focus' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  // Während der Fokussuche steht der Inspektor von selbst auf Fokus.
  await expect(inspector.getByRole('tab', { name: 'Fokus' })).toHaveAttribute('aria-selected', 'true');
  const chart = inspector.locator('svg.chart');
  const samples = chart.locator('[data-sample]');
  await expect(samples).toHaveCount(3);
  expect(await samples.evaluateAll((els) => els.map((el) => el.getAttribute('data-sample')))).toEqual(['1', '2', '3']);
  await expect(chart.locator('[data-best="true"]')).toHaveCount(1);
  await expect(chart.locator('[data-part="threshold"]')).toHaveAttribute('data-value', '536');
  await expect(chart.locator('[data-part="verify"]')).toHaveCount(0);
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  await expect(left.locator('[data-step="fokus"]')).toContainText('Probe 3');

  await hook(page, '/test/scene', { name: 'setup_focus_done' });
  await expect(samples).toHaveCount(9);
  await expect(chart.locator('[data-part="threshold"]')).toHaveAttribute('data-value', '536');
  await expect(chart).toContainText('85 % = 536');
  await expect(chart.locator('[data-part="verify"]')).toHaveCount(1);
  await expect(inspector).toContainText('624 ≥ 536 (99 %)');
  await expect(inspector).not.toContainText('Wahrscheinlichkeit');
  await expect(left.locator('[data-sub="gegenpruefung"]')).toContainText('624 ≥ 536');
  await noOverflow(page);
  expect(errors).toEqual([]);
});

test('Stabilität zählt 9/15', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_standbilder' });
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  const step = left.locator('[data-step="standbilder"]');
  await expect(step).toHaveAttribute('data-state', 'running');
  await expect(step.locator('[data-sub="stabilitaet"]')).toContainText('9/15 s');
  await expect(step).toContainText('noch 6 s');
  await expect(step.locator('.prog i')).toHaveAttribute('style', /width:\s*60%/);
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  // Ab dem Raster zeigt der Inspektor die Prüfungen, sobald sie gemeldet werden.
  await expect(inspector.getByRole('tab', { name: /Prüfungen/ })).toHaveAttribute('aria-selected', 'true');
  const table = inspector.locator('table.grid');
  await expect(table.locator('tbody tr', { hasText: 'Kontrast' })).toContainText('OK');
  await expect(table.locator('tbody tr', { hasText: 'Stabilität' })).toContainText('läuft');
  await expect(table.locator('tbody tr', { hasText: 'Stabilität' })).toContainText('noch 6 s');
  await inspector.getByRole('tab', { name: 'Schritt' }).click();
  await expect(inspector.getByRole('tabpanel')).toContainText('Versuch');
  await expect(inspector.getByRole('tabpanel')).toContainText('9/15 s');
  await noOverflow(page);
  expect(errors).toEqual([]);
});

test('Bestätigen setzt sich bei neuer Revision zurück', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector.getByRole('tab', { name: 'Schritt' })).toHaveAttribute('aria-selected', 'true');
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  const name = inspector.getByLabel('Name');
  const format = inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' });
  const ack = inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ });
  const titleConfirm = page.getByRole('banner').getByRole('button', { name: 'Bestätigen', exact: true });
  await expect(titleConfirm).toBeDisabled();
  await name.fill('L. Hentschke');
  await format.check();
  await ack.check();
  await expect(titleConfirm).toBeEnabled();

  await hook(page, '/test/revision', {});
  await expect(name).toHaveValue('');
  await expect(format).not.toBeChecked();
  await expect(ack).not.toBeChecked();
  await expect(titleConfirm).toBeDisabled();
  // Die Eingabe überlebt Statusabrufe ohne neue Revision.
  await name.fill('L. Hentschke');
  await page.waitForTimeout(1200);
  await expect(name).toHaveValue('L. Hentschke');

  await format.check();
  await ack.check();
  const request = page.waitForRequest('**/live/confirm');
  await inspector.getByRole('button', { name: 'Bestätigen', exact: true }).click();
  const sent = await request;
  expect(sent.headers()['x-csrf-token']).toBeTruthy();
  expect(sent.postDataJSON()).toEqual({ session_id: 'test-session', confirmed_by: 'L. Hentschke',
    format_checked: true, acknowledge_warning: true, use_tolerance: false,
    proposal_revision: 'b358259f721241f0b9e6af42d4fdb390-bump' });
  await expect(page.getByRole('banner').getByRole('button', { name: 'Lauf starten' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('Rahmenbereich-Klick sperrt bis zur Antwort', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  await inspector.getByLabel('Name').fill('L. Hentschke');
  await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
  await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
  const formConfirm = inspector.getByRole('button', { name: 'Bestätigen', exact: true });
  const titleConfirm = page.getByRole('banner').getByRole('button', { name: 'Bestätigen', exact: true });
  await expect(formConfirm).toBeEnabled();

  const edits: any[] = [];
  page.on('request', (r) => { if (r.url().endsWith('/live/setup/regions') && r.method() === 'POST') edits.push(r.postDataJSON()); });
  await hook(page, '/test/delay', { path: '/live/setup/regions', ms: 1000 });
  const answered = page.waitForResponse('**/live/setup/regions');
  await clickImage(page, [700, 300]);
  // Solange die Antwort aussteht: Bestätigen gesperrt, weitere Klicks wirkungslos.
  await expect(formConfirm).toBeDisabled();
  await expect(titleConfirm).toBeDisabled();
  await expect(inspector).toContainText('Rahmenbereich wird geprüft');
  await clickImage(page, [740, 300]);
  await inspector.getByRole('button', { name: 'Bereich hinzufügen' }).isDisabled().then((d) => expect(d).toBe(true));
  expect((await answered).ok()).toBe(true);
  await page.waitForTimeout(400);
  // Genau eine Anfrage; der Punkt ist das Quellpixel unter dem Zeiger (± ein Bildschirmpixel).
  expect(edits).toHaveLength(1);
  expect(edits[0]).toMatchObject({ proposal_revision: 'b358259f721241f0b9e6af42d4fdb390', remove: [] });
  expect(edits[0].add).toHaveLength(1);
  expect(Math.abs(edits[0].add[0][0] - 700)).toBeLessThanOrEqual(4);
  expect(Math.abs(edits[0].add[0][1] - 300)).toBeLessThanOrEqual(4);
  await expect(page.locator('.vfb')).toContainText('Rahmenbereich 13 hinzugefügt');
  await expect(inspector).not.toContainText('Rahmenbereich wird geprüft');
  // Neue Revision: Bestätigung beginnt von vorn.
  await expect(inspector.getByLabel('Name')).toHaveValue('');

  // Klick auf einen Bereich entfernt ihn (Index 3 liegt bei 1485, 658).
  const removed = page.waitForRequest('**/live/setup/regions');
  await clickImage(page, [1485, 658]);
  expect((await removed).postDataJSON()).toMatchObject({ add: [], remove: [3] });
  await expect(page.locator('.vfb')).toContainText('Rahmenbereich 4 entfernt');
  expect(errors).toEqual([]);
});

test('Klick im Zeichenbereich zeigt Grund', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  // Erst klicken, wenn der Status der Szene angekommen ist (sonst alte Revision -> 409).
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  const answered = page.waitForResponse('**/live/setup/regions');
  const [x, y] = await clickImage(page, [1092, 548]);
  expect((await answered).ok()).toBe(true);
  const label = page.locator('.vfb');
  await expect(label).toBeVisible();
  await expect(label).toContainText('im Zeichenbereich – nicht geeignet');
  const box = (await label.boundingBox())!;
  expect(Math.abs(box.x - x)).toBeLessThan(40);
  expect(Math.abs(box.y - y)).toBeLessThan(40);
  await expect(inspector.locator('[data-part="results-list"]')).toContainText(
    /109\d,54\d \(verwendet: 109\d,54\d\): im Zeichenbereich/);
  await expect(inspector.locator('[data-part="region-list"] li')).toHaveCount(12);
  expect(errors).toEqual([]);
});

test('Einrichtung rahmt die Anzeige statt des ganzen Bilds', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  const canvas = page.locator('canvas.vcanvas');
  await expect(canvas).toHaveAttribute('data-seq', /^\d+$/);
  const view = () => canvas.evaluate((el: any) => {
    const v = el.viewer.viewState();
    const quad = el.viewer.grid().quad.map((p: number[]) => el.viewer.imageToScreen(p));
    return { scale: v.scale, full: Math.min(v.width / 1920, v.height / 1080) * 0.98, w: v.width, h: v.height, quad };
  });
  const check = async () => {
    const v = await view();
    // Rahmenbereiche (15 px) erscheinen deutlich größer als bei eingepasstem Gesamtbild.
    expect(v.scale).toBeGreaterThan(1.5 * v.full);
    for (const [x, y] of v.quad) {
      expect(x).toBeGreaterThan(0); expect(x).toBeLessThan(v.w);
      expect(y).toBeGreaterThan(0); expect(y).toBeLessThan(v.h);
    }
  };
  await expect.poll(async () => (await view()).scale / (await view()).full).toBeGreaterThan(1.5);
  await check();
  // Einpassen rahmt in der Einrichtung ebenfalls die Anzeige.
  const viewer = page.getByRole('region', { name: 'Bildansicht' });
  await viewer.getByRole('button', { name: '1:1' }).click();
  await viewer.getByRole('button', { name: 'Einpassen' }).click();
  await check();
  expect(errors).toEqual([]);
});

test('Rahmenbereich-Sperre hält bis zum Status der neuen Revision', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page);
  await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  const name = inspector.getByLabel('Name');
  await name.fill('L. Hentschke');
  await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
  await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
  const formConfirm = inspector.getByRole('button', { name: 'Bestätigen', exact: true });
  const titleConfirm = page.getByRole('banner').getByRole('button', { name: 'Bestätigen', exact: true });
  const addButton = inspector.getByRole('button', { name: 'Bereich hinzufügen' });
  await expect(formConfirm).toBeEnabled();

  // Statusabrufe der Seite festhalten: Lücke zwischen POST-Antwort und neuem Status.
  let release: () => void = () => {};
  let gate: Promise<void> | null = null;
  await page.route('**/live/status*', async (route) => {
    if (gate) await gate;
    try { await route.continue(); } catch { /* vom Client nach 3 s abgebrochen */ }
  });
  gate = new Promise<void>((resolve) => { release = resolve; });
  const edits: unknown[] = [];
  page.on('request', (r) => { if (r.url().endsWith('/live/setup/regions') && r.method() === 'POST') edits.push(r.postDataJSON()); });
  const answered = page.waitForResponse('**/live/setup/regions');
  await clickImage(page, [700, 300]);
  expect((await answered).ok()).toBe(true);
  const answeredAt = Date.now();
  await expect(page.locator('.vfb')).toContainText('hinzugefügt');
  await page.waitForTimeout(400);
  // Antwort da, neuer Status noch nicht: Bestätigen und weitere Klicks bleiben wirkungslos.
  await expect(formConfirm).toBeDisabled();
  await expect(titleConfirm).toBeDisabled();
  await expect(addButton).toBeDisabled();
  await clickImage(page, [740, 300]);
  await page.waitForTimeout(300);
  expect(edits).toHaveLength(1);
  // Rückfall: ohne neuen Status löst die Sperre nach etwa 3 s.
  await expect(addButton).toBeEnabled({ timeout: 5000 });
  expect(Date.now() - answeredAt).toBeGreaterThan(2500);
  gate = null;
  release();
  // Der Status der neuen Revision setzt die Bestätigung zurück.
  await expect(name).toHaveValue('');
  await page.unroute('**/live/status*');
  expect(errors.filter((e) => !/live\/status/.test(e))).toEqual([]);
});

// ---------------------------------------------------------------------------
// Laufansicht (Aufgabe 9)
// ---------------------------------------------------------------------------
const STATUS_RGB = [[85, 196, 110], [229, 165, 53], [238, 91, 77], [143, 138, 130]];

// Spalten der Zeitleiste, in denen ein Statusband-Pixel liegt.
async function coloredColumns(page: Page) {
  return page.locator('.strip canvas').evaluate((canvas: HTMLCanvasElement, colors) => {
    const ctx = canvas.getContext('2d')!;
    const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let columns = 0;
    for (let x = 0; x < width; x++) {
      for (let y = 0; y < height; y++) {
        const i = (y * width + x) * 4;
        if (colors.some(([r, g, b]) => Math.abs(data[i] - r) < 8 && Math.abs(data[i + 1] - g) < 8
            && Math.abs(data[i + 2] - b) < 8)) { columns++; break; }
      }
    }
    return Math.round(columns / (window.devicePixelRatio || 1));
  }, STATUS_RGB);
}

test('Ergebnis zeigt Veraltet durchgestrichen', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_stalled' });
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge).toBeVisible();
  await expect(judge.locator('.jh')).toContainText('Veraltet');
  await expect(judge.locator('.jh')).toContainText('STALE');
  const value = judge.locator('.jv .num');
  await expect(value).toHaveText('+0.62427');
  await expect(value).toHaveCSS('text-decoration-line', 'line-through');
  await expect(judge).not.toContainText('Freigegeben');
  await expect(judge).toContainText('kein neues Kamerabild');
  // Fehllesungen gibt es erst nach Laufende (Spec OP-1).
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  await expect(left).toContainText('Fehllesungen gegen Referenz');
  await expect(left).toContainText('Abgleich nach Laufende');
  await expect(left).toContainText('Veraltet');
  expect(errors).toEqual([]);
});

test('Testlauf zeigt nie einen Wert', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid', test_run: true });
  await expect(page.getByRole('banner')).toContainText('TESTLAUF – Werte nicht freigegeben');
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge.locator('.jh')).toContainText('Unlesbar');
  await expect(judge.locator('.jh')).toContainText('UNREADABLE');
  await expect(judge.locator('.jv .num')).toHaveText('Kein Wert');
  await expect(judge).toContainText('Testlauf: keine Wertfreigabe');
  // Ueber mehrere Bilder und Statusabrufe: nirgends rechts ein Wert.
  const right = page.getByRole('complementary', { name: 'Inspektor' });
  for (let i = 0; i < 6; i++) {
    await expect(judge).not.toContainText('0.62427');
    await expect(right).not.toContainText('0.62427');
    await page.waitForTimeout(250);
  }
  await expect(page.locator('.strip')).toBeVisible();
  expect(errors).toEqual([]);
});

test('Neuladen füllt die Zeitleiste aus run.recent', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });
  await page.reload();
  const strip = page.getByRole('region', { name: 'Zeitleiste' });
  await expect(strip).toContainText('letzte 40 s');
  await expect.poll(() => coloredColumns(page), { timeout: 5000 }).toBeGreaterThanOrEqual(100);
  // Stillstand: die Luecke bis "jetzt" bleibt frei, der letzte Eimer rutscht nicht an den Rand.
  await hook(page, '/test/scene', { name: 'running_stalled' });
  await expect.poll(() => strip.locator('canvas').evaluate((el: any) => {
    const l = el.timeline.layout(el.clientWidth);
    return l.x(l.nowMs) - l.bands.at(-1).x1;
  }), { timeout: 5000 }).toBeGreaterThan(30);
  expect(errors).toEqual([]);
});

test('Laufstart: Optionen im Popover, Testlauf und Werteplan bestätigen im Dialog', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/__test__/state', { state: 'confirmed', run_block: 'Lauf gesperrt: Gegenlesen WARNUNG',
    profile: { confirmed_by: 'L. Hentschke' } });
  const title = page.getByRole('banner');
  const start = title.locator('.hdr-act').getByRole('button', { name: 'Lauf starten', exact: true });
  await expect(start).toBeDisabled();
  await title.getByRole('button', { name: 'Laufoptionen' }).click();
  const pop = page.getByRole('dialog', { name: 'Laufoptionen' });
  await expect(pop).toContainText('Lauf gesperrt — Leser konnte die Einrichtungsbilder nicht lesen');
  await expect(pop).toContainText('Lauf gesperrt: Gegenlesen WARNUNG');
  const reference = pop.getByRole('checkbox', { name: 'Referenz vom GSV-2AS mitschreiben' });
  await expect(reference).toBeChecked();
  await expect(pop.getByRole('checkbox', { name: /^Diagnosebilder aufzeichnen/ })).not.toBeChecked();
  await expect(pop).toContainText('EEnow = 0');
  await pop.getByText('Testmodus (nur zu Testzwecken)').click();
  await pop.getByRole('checkbox', { name: /^Lesesperre übergehen/ }).check();
  await expect(start).toBeEnabled();

  let requests = 0;
  page.on('request', (r) => { if (r.url().endsWith('/live/run/start')) requests++; });
  const override = pop.getByRole('checkbox', { name: /^Lesesperre übergehen/ });
  const modal = page.getByRole('dialog', { name: 'TESTLAUF starten?' });
  // Testlauf-Dialog (Text aus live.js): Esc bricht ab, nichts wird gesendet, der Haken bleibt.
  await pop.getByRole('button', { name: 'Lauf starten', exact: true }).click();
  await expect(modal).toContainText('Die Lesesperre wird übergangen.');
  await expect(modal).toContainText('(TESTLAUF.json)');
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(override).toBeChecked();
  expect(requests).toBe(0);

  // Werteplan ohne Referenz: Hinweis aus live.js, kein Start; wie dort ist der Haken danach verbraucht.
  await pop.getByLabel(/^Werteplan \(set norm\)/).fill('1:20,2:20');
  await reference.uncheck();
  await start.click();
  await modal.getByRole('button', { name: 'Testlauf starten' }).click();
  await expect(pop.getByRole('alert')).toHaveText('Werteplan braucht Referenzaufzeichnung');
  await expect(override).not.toBeChecked();
  await expect(start).toBeDisabled();
  expect(requests).toBe(0);

  await reference.check();
  await override.check();
  await start.click();
  await modal.getByRole('button', { name: 'Testlauf starten' }).click();
  const plan = page.getByRole('dialog', { name: 'Werteplan anwenden?' });
  await expect(plan).toContainText('Der Plan schreibt in den RAM des GSV-2AS.');
  const request = page.waitForRequest('**/live/run/start');
  await plan.getByRole('button', { name: 'Werteplan anwenden' }).click();
  expect((await request).postDataJSON()).toEqual({ test_override: true, reference: true,
    norm_schedule: '1:20,2:20', diagnostics: false });
  await expect(title).toContainText('TESTLAUF – Werte nicht freigegeben');
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jv .num')).toHaveText('Kein Wert');

  // Ereignis markieren: Text geht an den Server, Marke erscheint.
  await title.getByRole('button', { name: 'Ereignis markieren' }).click();
  const markPop = page.getByRole('dialog', { name: 'Ereignis markieren' });
  await markPop.getByLabel('Ereignis (Meldezeit des Bedieners):').fill('Display abgedeckt');
  const mark = page.waitForRequest('**/live/run/mark');
  await page.keyboard.press('Enter');
  expect((await mark).postDataJSON()).toEqual({ text: 'Display abgedeckt' });
  await expect(markPop).toBeHidden();
  await expect.poll(() => page.locator('.strip canvas').evaluate((el: any) =>
    el.timeline.layout(el.clientWidth).marks.map((m: any) => m.label))).toContain('Display abgedeckt');
  expect(errors).toEqual([]);
});

test('Dialog hält den Fokus, Esc wählt die Esc-Aktion, Fokus kehrt zurück', async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });
  const opener = page.getByRole('banner').getByRole('button', { name: 'Einrichtung starten', exact: true });
  await opener.focus();
  await page.evaluate(async () => {
    const { openModal } = await import('/static/live/ui/modal.js');
    (window as any).modalResult = openModal({ title: 'Anzeige hat sich bewegt', text: 'Bitte neu einrichten.',
      actions: [{ label: 'Neu einrichten', value: 'neu', primary: true }, { label: 'Lauf stoppen', value: 'stopp' },
        { label: 'Weiter beobachten', value: 'weiter', escape: true }] });
  });
  const modal = page.getByRole('dialog', { name: 'Anzeige hat sich bewegt' });
  await expect(modal).toBeVisible();
  await expect(modal).toHaveAttribute('aria-modal', 'true');
  const focused = () => page.evaluate(() => document.activeElement?.textContent);
  await expect.poll(focused).toBe('Weiter beobachten');
  // Fokusfalle: Tab und Umschalt+Tab bleiben im Dialog.
  for (const expected of ['Neu einrichten', 'Lauf stoppen', 'Weiter beobachten', 'Neu einrichten']) {
    await page.keyboard.press('Tab');
    expect(await focused()).toBe(expected);
  }
  await page.keyboard.press('Shift+Tab');
  expect(await focused()).toBe('Weiter beobachten');
  // Der Hintergrund ist gesperrt.
  const inert = () => page.evaluate(() => Boolean(document.querySelector('.app')!.closest('[inert]')));
  expect(await inert()).toBe(true);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).modalResult)).toBe('weiter');
  await expect(opener).toBeFocused();
  expect(await inert()).toBe(false);

  // Ohne Esc-Aktion schliesst Esc nicht; ein Knopf liefert seinen Wert.
  await page.evaluate(async () => {
    const { openModal } = await import('/static/live/ui/modal.js');
    (window as any).modalResult = openModal({ title: 'Zweiter Dialog', text: 'A\n\nB',
      actions: [{ label: 'OK', value: 42, primary: true }] });
  });
  const second = page.getByRole('dialog', { name: 'Zweiter Dialog' });
  await page.keyboard.press('Escape');
  await expect(second).toBeVisible();
  await expect(second.locator('p')).toHaveCount(2);
  await second.getByRole('button', { name: 'OK' }).click();
  expect(await page.evaluate(() => (window as any).modalResult)).toBe(42);
  expect(errors).toEqual([]);
});

test('Lauf beendet: Zusammenfassung, Fehllesungen erst nach Laufende', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'stopped' });
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge.locator('.jh')).toContainText('Lauf beendet');
  await expect(judge.locator('.jv .num')).not.toContainText('0.62427');
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  await expect(left).toContainText('Lauf beendet');
  await expect(left).toContainText('Fehllesungen gegen Referenz');
  await expect(left).not.toContainText('Abgleich nach Laufende');
  await expect(left).toContainText('bediener');
  await expect(left).toContainText('run-01');
  await expect(page.getByRole('banner').getByRole('button', { name: 'Neu einrichten' })).toBeVisible();
  expect(errors).toEqual([]);
});
