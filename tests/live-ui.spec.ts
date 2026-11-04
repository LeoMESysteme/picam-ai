import { expect, test, type BrowserContext, type Page } from '@playwright/test';

// Die beiden Abläufe der abgelösten alten Seite,
// mit gleichem Prüfinhalt auf der neuen Seite.
test('Live-Seite: Anmeldung, Einrichtung, Freigabe und Verbindungsverlust', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    try { localStorage.setItem('werkbank.rundgang', 'gesehen'); } catch { /* ohne Speicher */ }
  });
  await page.goto('/live');
  await expect(page).toHaveURL(/\/login\?next=\/live$/);
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/live$/);
  sessionCookies = await page.context().cookies();
  await hook(page, '/__test__/state', {});
  const title = page.getByRole('banner');
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  const bar = page.getByRole('contentinfo');
  const lead = left.locator('.lead');
  await expect(lead.locator('h2')).toHaveText('Bereit zur Einrichtung');
  await expect(bar).toContainText('Validiert nur:');
  await expect(inspector.getByLabel('Name')).toBeHidden();
  await expect(bar.locator('[data-item="storage"]')).toHaveAttribute('title', /Warnung: unter 5 GB/);
  await expect(bar.locator('[data-item="storage"]')).toContainText('4,20 GB');
  await expect(title.getByRole('button', { name: 'Ereignis markieren' })).toHaveCount(0);

  const setState = (state: unknown) => hook(page, '/__test__/state', state);
  await title.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  await expect(left.locator('[data-step="fokus"]')).toHaveAttribute('data-state', 'running');
  await setState({ state: 'setup_running', setup: { step: 'punktraster', elapsed_s: 12.3 } });
  await expect(left.locator('[data-part="meta"]')).toHaveText('0:12');
  await expect(inspector.locator('[data-part="meta"]')).toHaveText('');

  const failure = 'Punktraster abgelehnt: keine_startlage — Kamera senkrecht auf Displaymitte';
  await setState({ state: 'setup_failed', error: failure,
    setup: { step: 'punktraster', elapsed_s: 12.3 } });
  await expect(lead.locator('h2')).toHaveText('Einrichtung abgebrochen');
  await expect(lead).toContainText('keine_startlage');
  await expect(lead).toHaveClass(/error/);
  // Ein erfolgreicher anderer Bedienschritt darf den Fehler nicht wegwischen.
  const camera = bar.getByRole('button', { name: /StreamCam/ });
  await camera.click();
  const cameraMenu = page.getByRole('menu', { name: 'Kamera' });
  await expect(cameraMenu).toBeVisible();
  const cameraResponse = page.waitForResponse('**/live/camera/start');
  await cameraMenu.getByRole('menuitem', { name: /Kamera neu verbinden/ }).click();
  expect((await cameraResponse).ok()).toBe(true);
  await expect(cameraMenu).toBeHidden();
  await expect(camera).toBeFocused();
  await page.waitForTimeout(700);
  await expect(lead).toContainText(failure);
  await title.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  await expect(left.locator('[data-step="fokus"]')).toHaveAttribute('data-state', 'running');
  await expect(left).not.toContainText('keine_startlage');

  await setState({ state: 'setup_ready', setup: { overall: 'WARNUNG', checks: { raster: 'WARNUNG' },
    overlays: ['overlay_source', 'overlay_sampling'], step: 'vorschlag', elapsed_s: 15.0 } });
  await expect(lead.locator('h2')).toHaveText('Vorschlag prüfen und bestätigen');
  await expect(inspector).toContainText('Gesamturteil WARNUNG');
  const viewer = page.getByRole('region', { name: 'Bildansicht' });
  const source = viewer.getByRole('group', { name: 'Bildquelle' });
  await expect(source.getByRole('button', { name: 'Standbild' })).toBeEnabled();
  await expect(source.getByRole('button', { name: 'Abtastbild' })).toBeEnabled();
  await expect(source.getByRole('button', { name: 'Entzerrt' })).toBeDisabled();
  for (const [button, name] of [['Standbild', 'overlay_source'], ['Abtastbild', 'overlay_sampling']]) {
    const still = page.waitForResponse((r) => r.url().includes(`/live/setup/${name}.png`));
    await source.getByRole('button', { name: button }).click();
    expect((await still).ok()).toBe(true);
  }
  await source.getByRole('button', { name: 'Live' }).click();
  await expect(inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' })).toBeVisible();
  await expect(inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ })).toBeVisible();

  await inspector.getByLabel('Name').fill('Operator');
  await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
  await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
  const confirmRequest = page.waitForRequest('**/live/confirm');
  await title.getByRole('button', { name: 'Bestätigen', exact: true }).click();
  expect((await confirmRequest).postDataJSON()).toEqual({
    session_id: 'test-session', confirmed_by: 'Operator',
    format_checked: true, acknowledge_warning: true, use_tolerance: false,
  });
  await expect(lead.locator('h2')).toHaveText('Bestätigt – Lauf starten');

  await setState({ state: 'confirmed', run_block: 'Lauf gesperrt: Gegenlesen WARNUNG',
    profile: { tracking_mode: 'ecc_alt' } });
  await expect(lead.locator('h2')).toHaveText('Lauf gesperrt');
  // Der kommende Nachführungsmodus steht schon vor dem Lauf da.
  await expect(inspector.locator('[data-part="tracking-mode"]')).toHaveText(
    'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen');
  const start = title.locator('.hdr-act').getByRole('button', { name: 'Lauf starten', exact: true });
  await expect(start).toBeDisabled();
  await title.getByRole('button', { name: 'Laufoptionen' }).click();
  const options = page.getByRole('dialog', { name: 'Laufoptionen' });
  await expect(options).toContainText('Lauf gesperrt — Leser konnte die Einrichtungsbilder nicht lesen');
  await expect(options.getByRole('checkbox', { name: /^Diagnosebilder aufzeichnen/ })).not.toBeChecked();
  await options.getByText('Testmodus (nur zu Testzwecken)').click();
  await options.getByRole('checkbox', { name: /^Lesesperre übergehen/ }).check();
  await expect(start).toBeEnabled();
  await page.keyboard.press('Escape');

  const run = { latest: { frame_sequence: 7, status: 'valid', raw_text: '+1.2345',
    unit: 'mV/V', reject_reasons: [] }, latest_age_s: 0.2, summary: {},
    rejection_causes: {window_s: 10, frames: 4, limited: false,
      causes: [{reason: 'leser:leerzelle_gestoert:14', count: 1, fraction: 0.25}]}};
  await setState({ state: 'running', run, diagnostics: {enabled: true, saved: 4, bytes: 12_500_000,
    dropped_queue: 0, dropped_limit: 0, dropped_memory: 2, dropped_mark_rate: 3, write_errors: 0},
    diagnostic_leftovers: [{path: '/test/dispread-diagnose-old', bytes: 2_500_000}] });
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge.locator('.jh')).toContainText('Freigegeben');
  await expect(judge.locator('.jv .num')).toHaveText('+1.2345');
  await expect(judge.locator('.jv .unit')).toHaveText('mV/V');
  await inspector.getByRole('tab', { name: 'Referenz' }).click();
  const panel = inspector.getByRole('tabpanel');
  await expect(panel).toContainText('12.5 MB');
  await expect(panel).toContainText('RAM verworfen: 2');
  await expect(panel).toContainText('Markenbilder verworfen: 3');
  await expect(panel).toContainText('/test/dispread-diagnose-old (2.5 MB)');
  await inspector.getByRole('tab', { name: /Ursachen/ }).click();
  await expect(panel).toContainText('Zelle 14 (rechts der Einheit)');
  await expect(panel.locator('tbody tr').first()).toContainText('25 %');
  await title.getByRole('button', { name: 'Ereignis markieren' }).click();
  const markPop = page.getByRole('dialog', { name: 'Ereignis markieren' });
  await markPop.getByLabel('Ereignis (Meldezeit des Bedieners):').fill('Display abgedeckt');
  const markRequest = page.waitForRequest('**/live/run/mark');
  await page.keyboard.press('Enter');
  expect((await markRequest).postDataJSON()).toEqual({text: 'Display abgedeckt'});
  await inspector.getByRole('tab', { name: 'Referenz' }).click();
  await expect(panel).toContainText('Meldezeit');
  await expect(panel).toContainText('Display abgedeckt');
  await expect(inspector.getByLabel('Name')).toBeHidden();
  await setState({ state: 'running', run: { ...run, latest_age_s: 0.9 } });
  await expect(judge.locator('.jh')).toContainText('Veraltet');
  await expect(judge.locator('.jh')).toContainText('STALE');
  await expect(judge.locator('.jv .num')).toHaveCSS('text-decoration-line', 'line-through');

  const lost = { ...run, latest: { ...run.latest, status: 'unreadable', raw_text: '',
    reject_reasons: ['tracking_lost:rahmen_unstimmig'] }, tracking_hint: {
    kind: 'anzeige_bewegt', shift_px: 19, region_shift_px: 27, rotation_deg: -2.23, since_s: 3 } };
  await setState({ state: 'running', run: lost });
  await expect(judge.locator('.jh')).toContainText('UNREADABLE');
  await expect(judge.locator('.jsub')).toContainText('Anzeige hat sich bewegt (ca. 19 px (Ecken), 2,2 Grad)');
  await expect(judge.locator('.jsub')).toContainText('Werte werden nicht freigegeben. Bitte neu einrichten.');
  const moved = page.getByRole('dialog', { name: 'Anzeige hat sich bewegt' });
  await expect(moved).toBeVisible();
  await page.keyboard.press('Escape');
  await setState({ state: 'running', run: { ...lost, tracking_hint: {
    kind: 'rahmen_verdeckt', shift_px: null, rotation_deg: null, since_s: 10 } } });
  await expect(judge.locator('.jsub')).toContainText('Rahmen verdeckt? Hand oder Gegenstand');
  await expect(judge.locator('.jsub')).not.toContainText('Anzeige hat sich bewegt');
  await setState({ state: 'running', run: { ...lost, tracking_hint: {
    kind: 'unbekannt', shift_px: null, rotation_deg: null, since_s: 12 } } });
  await expect(judge.locator('.jsub')).toContainText('Anzeige nicht sicher wiedergefunden');

  // Erst wieder frische Ziffern zeigen, dann die echte Poll-Anfrage abbrechen.
  await setState({ state: 'running', run });
  await expect(judge.locator('.jv .num')).toHaveText('+1.2345');
  await expect(judge.locator('.jsub')).not.toContainText('einrichten');
  await page.route('**/live/status*', (route) => route.abort('connectionfailed'));
  await expect(judge.locator('.jh')).toContainText('Veraltet', { timeout: 5000 });
  await expect(lead.locator('h2')).toHaveText('STALE');
  await expect(lead).toContainText('Verbindung zur Werkbank verloren');
  await expect(page.locator('.netband')).toContainText('Verbindung zur Werkbank verloren');
  await page.unroute('**/live/status*');
  await expect(judge.locator('.jv .num')).toHaveText('+1.2345', { timeout: 5000 });
  // Erwartet: die abgebrochenen Statusabrufe.
  expect(errors.filter((e) => !/ERR_CONNECTION_FAILED|Failed to load resource/.test(e))).toEqual([]);
});

test('Rahmenbereiche: Tastatur und Bildklick ändern Revision und verlangen neue Bestätigung', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/__test__/state', {state: 'setup_ready', setup: {overall: 'OK', proposal_revision: 'regions-v1',
    auswahl: 'automatisch', overlays: ['overlay_source'], checks: {nachfuehrung: 'OK'},
    regions: [{centre: [10, 10], size: 5}]}});
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  const regionList = inspector.locator('[data-part="region-list"] li');
  // Ganzes Bild zeigen: ein vorher geladenes Lauf-HUD kann die Ansicht noch auf seinen Rahmen gelegt haben.
  await page.getByRole('region', { name: 'Bildansicht' }).getByRole('button', { name: 'Einpassen' }).click();
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
  await expect(regionList).toHaveCount(1);
  const name = inspector.getByLabel('Name');
  const format = inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' });
  await name.fill('Operator');
  await format.check();
  // Tastatur: Koordinaten eingeben; Unvollständiges wird ohne Anfrage abgelehnt.
  const edits: any[] = [];
  page.on('request', (r) => { if (r.url().endsWith('/live/setup/regions') && r.method() === 'POST') edits.push(r.postDataJSON()); });
  const coordinates = inspector.getByLabel('Quellbild-Koordinaten x,y');
  await coordinates.fill('123,');
  await inspector.getByRole('button', { name: 'Bereich hinzufügen', exact: true }).click();
  await expect(inspector.locator('[data-part="msg"]')).toContainText('x,y');
  expect(edits).toHaveLength(0);
  await coordinates.fill('30,12');
  const added = page.waitForRequest('**/live/setup/regions');
  await inspector.getByRole('button', { name: 'Bereich hinzufügen', exact: true }).click();
  expect((await added).postDataJSON()).toEqual({proposal_revision: 'regions-v1', add: [[30, 12]], remove: []});
  await expect(regionList).toHaveCount(2);
  await inspector.getByText('Prüfergebnisse').click();
  await expect(inspector.locator('[data-part="results-list"]')).toContainText('30,12 (verwendet: 30,12): geeignet');
  await expect(name).toHaveValue('');
  await expect(format).not.toBeChecked();
  await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: manuell');

  // Bildklick auf einen Bereich entfernt ihn.
  await expect(inspector.getByRole('button', { name: 'Bereich hinzufügen', exact: true })).toBeEnabled({ timeout: 5000 });
  const removed = page.waitForRequest('**/live/setup/regions');
  await clickImage(page, [10, 10]);
  const body = (await removed).postDataJSON();
  expect(body.remove).toEqual([0]);
  expect(body.add).toEqual([]);
  expect(body.proposal_revision).not.toBe('regions-v1');
  await expect(regionList).toHaveCount(1);
  await inspector.getByText('Bereiche einzeln').click();
  await inspector.getByRole('button', { name: /Bereich 1 entfernen/ }).click();
  await expect(regionList).toHaveCount(0);
  await inspector.getByRole('tab', { name: /Prüfungen/ }).click();
  await expect(inspector.getByRole('tabpanel').locator('tbody tr', { hasText: 'Nachführung' })).toContainText('FEHLER');
  await inspector.getByRole('tab', { name: 'Schritt' }).click();

  // Der Server lehnt kaputte Änderungen ab, die Revision bleibt.
  const { csrf } = await (await page.request.get('/live/status')).json();
  const revision = (await (await page.request.get('/live/status')).json()).setup.proposal_revision;
  for (const edit of [{add: [[1e300, 12]], remove: []}, {add: [], remove: ['0']}]) {
    const rejected = await page.request.post('/live/setup/regions', {
      headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf },
      data: {proposal_revision: revision, ...edit},
    });
    expect(rejected.status()).toBe(400);
  }
  expect((await (await page.request.get('/live/status')).json()).setup.proposal_revision).toBe(revision);

  // Bildklick wählt das Quellpixel, in dem der Zeiger liegt (abrunden, nicht runden).
  await expect(inspector.getByRole('button', { name: 'Bereich hinzufügen', exact: true })).toBeEnabled({ timeout: 5000 });
  const canvas = page.locator('canvas.vcanvas');
  await canvas.evaluate((el: any) => {
    el.viewer.zoomBy(16, el.viewer.viewState().imageToScreen([36, 13]));
  });
  expect(await canvas.evaluate((el: any) => el.viewer.viewState().scale)).toBeGreaterThan(3);
  const fractional = page.waitForRequest('**/live/setup/regions');
  await clickImage(page, [35.8, 12.8]);
  expect((await fractional).postDataJSON()).toEqual({proposal_revision: revision, add: [[35, 12]], remove: []});
  await expect(regionList).toHaveCount(1);
  expect(errors.filter((e) => !/status of 400/.test(e))).toEqual([]);
});

// Der Server lässt je Adresse nur 5 Anmeldungen pro Minute zu (auth.py);
// die Tests teilen sich deshalb ein Sitzungs-Cookie (ein Worker).
let sessionCookies: Awaited<ReturnType<BrowserContext['cookies']>> | null = null;

// Rundgang-Angebot: nur beim ersten Besuch. Die übrigen Tests spielen
// wiederkehrende Bediener; der Rundgang-Test meldet sich mit {tour: true} an.
async function login(page: Page, { tour = false } = {}) {
  if (!tour) {
    await page.addInitScript(() => {
      try { localStorage.setItem('werkbank.rundgang', 'gesehen'); } catch { /* ohne Speicher */ }
    });
  }
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
  // Keine Browseruhr im Kopf neben einem alten Wert; "Bild N" steht nur einmal da.
  await expect(judge.locator('.jh')).toHaveText(/^\s*Veraltet\s*STALE\s*$/);
  await expect(judge).toContainText('Bild');
  expect((await judge.textContent())!.match(/Bild/g)!.length).toBe(1);
  // Referenz mit Alter, frisch (0,1 s) also nicht durchgestrichen.
  await expect(judge.locator('.jref .ref')).toHaveText('+ 0.62427');
  await expect(judge.locator('.jref .age')).toHaveText('100 ms');
  await expect(judge.locator('.jref .ref')).not.toHaveCSS('text-decoration-line', 'line-through');
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
  // Ueber mehrere Bilder und Statusabrufe: nie ein Pruefling-Wert (Wertfeld,
  // Grundzeile, Datensaetze). Die Referenz darf stehen; sie ist kein freigegebener Wert.
  const records = page.locator('.inspector');
  for (let i = 0; i < 6; i++) {
    await expect(judge.locator('.jv')).not.toContainText('0.62427');
    await expect(judge.locator('.jsub')).not.toContainText('0.62427');
    await expect(records).not.toContainText('0.62427');
    await page.waitForTimeout(250);
  }
  await expect(judge.locator('.jref')).toContainText('+ 0.62427');
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
  // Werteplan-Schritt aus reference.schedule_step, zurueckdatiert um since_s (12 s).
  const marks = () => strip.locator('canvas').evaluate((el: any) =>
    el.timeline.layout(el.clientWidth).marks.map((m: any) => m.label));
  await expect.poll(marks).toEqual(['set norm 2']);
  await page.waitForTimeout(1200);
  expect(await marks()).toEqual(['set norm 2']); // einmal je Schritt, nicht je Abruf
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
  // Testlauf-Dialog (Text aus der alten Live-Seite): Esc bricht ab, nichts wird gesendet, der Haken bleibt.
  await pop.getByRole('button', { name: 'Lauf starten', exact: true }).click();
  await expect(modal).toContainText('Die Lesesperre wird übergangen.');
  await expect(modal).toContainText('(TESTLAUF.json)');
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(override).toBeChecked();
  expect(requests).toBe(0);

  // Werteplan ohne Referenz: Hinweis aus der alten Live-Seite, kein Start; wie dort ist der Haken danach verbraucht.
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
  // Leer geht wie auf der alten Seite an den Server; dessen Antwort steht woertlich da.
  const empty = page.waitForRequest('**/live/run/mark');
  await markPop.getByLabel('Ereignis (Meldezeit des Bedieners):').press('Enter');
  expect((await empty).postDataJSON()).toEqual({ text: '' });
  await expect(markPop.getByRole('alert')).toHaveText('Ereignismarke braucht 1 bis 200 Zeichen');
  await markPop.getByLabel('Ereignis (Meldezeit des Bedieners):').fill('Display abgedeckt');
  const mark = page.waitForRequest('**/live/run/mark');
  await page.keyboard.press('Enter');
  expect((await mark).postDataJSON()).toEqual({ text: 'Display abgedeckt' });
  await expect(markPop).toBeHidden();
  await expect.poll(() => page.locator('.strip canvas').evaluate((el: any) =>
    el.timeline.layout(el.clientWidth).marks.map((m: any) => m.label))).toContain('Display abgedeckt');
  // Einzige erwartete Konsolenmeldung: die 409-Antwort auf die leere Marke.
  expect(errors).toEqual(['Failed to load resource: the server responded with a status of 409 (Conflict)']);
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

  // Vor dem Zeigen geschlossen: loest mit dem Wert auf, baut nichts auf, kein Tastatur-Haken bleibt.
  const cdp = await page.context().newCDPSession(page);
  const keydownListeners = async () => {
    const { result } = await cdp.send('Runtime.evaluate', { expression: 'document' });
    const { listeners } = await cdp.send('DOMDebugger.getEventListeners', { objectId: result.objectId! });
    return listeners.filter((l: any) => l.type === 'keydown').length;
  };
  const before = await keydownListeners();
  expect(await page.evaluate(async () => {
    const { openModal } = await import('/static/live/ui/modal.js');
    const pending = openModal({ title: 'Früh geschlossen', text: 'x',
      actions: [{ label: 'OK', value: 1, escape: true }] });
    pending.close('x');
    return pending;
  })).toBe('x');
  await expect(page.locator('.modalbg')).toHaveCount(0);
  expect(await inert()).toBe(false);
  expect(await keydownListeners()).toBe(before);
  // Esc und Tab wirken danach wieder auf der Seite.
  await opener.focus();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Zellentext angeben' })).toBeFocused();
  await page.keyboard.press('Enter');
  const cellPop = page.getByRole('dialog', { name: 'Zellentext' });
  await expect(cellPop).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(cellPop).toBeHidden();

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
  await expect(left.locator('.kv').first()).toContainText('Gestartet');
  await expect(left.locator('.kv').first()).toContainText('00:01:00');
  for (const text of ['Verglichen', '842', 'Nicht entscheidbar (Wechsel)', 'Ohne Referenz']) {
    await expect(left).toContainText(text);
  }
  await expect(left).not.toContainText('reference_eval');
  // Referenz 12 s alt: veraltet wie ein Pruefling-Wert.
  await expect(judge.locator('.jref .ref')).toHaveCSS('text-decoration-line', 'line-through');
  await expect(left).toContainText('bediener');
  await expect(left).toContainText('run-01');
  await expect(page.getByRole('banner').getByRole('button', { name: 'Neu einrichten' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('Verbindung verloren: Etikett und Ergebnis veraltet, obwohl Bilder kommen', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge.locator('.jh')).toContainText('Freigegeben');
  const canvas = page.locator('canvas.vcanvas');
  await expect.poll(() => canvas.evaluate((el: any) => el.viewer.tagWord())).toBe('Freigegeben');
  // Nur /live/status bleibt aus, der Bildstrom laeuft weiter.
  const { csrf } = await (await page.request.get('/live/status')).json();
  const offline = (on: boolean) => page.request.post('/test/offline', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf }, data: { on } });
  expect((await offline(true)).ok()).toBe(true);
  try {
    await expect(judge.locator('.jh')).toContainText('Veraltet', { timeout: 5000 });
    expect(await canvas.evaluate((el: any) => el.viewer.tagWord())).toBe('Veraltet');
    const seq = await canvas.getAttribute('data-seq');
    await expect.poll(() => canvas.getAttribute('data-seq')).not.toBe(seq);
    expect(await canvas.evaluate((el: any) => el.viewer.tagWord())).toBe('Veraltet');
    await expect(judge.locator('.jref .ref')).toHaveCSS('text-decoration-line', 'line-through');
  } finally {
    expect((await offline(false)).ok()).toBe(true);
  }
  await expect(judge.locator('.jh')).toContainText('Freigegeben', { timeout: 5000 });
  expect(errors).toEqual([]);
});

// ---------------------------------------------------------------------------
// Zustandseffekte, Hinweise und Dialoge (Aufgabe 10)
// ---------------------------------------------------------------------------
// Mittlerer Rotanteil r/(r+g+b) eines Bildschirmstreifens (Screenshot mit
// Effektebene, Leuchten und Bild). Dekodiert im Browser per createImageBitmap.
async function redShare(page: Page, clip: { x: number; y: number; width: number; height: number }) {
  const png = (await page.screenshot({ clip })).toString('base64');
  return page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(bitmap, 0, 0);
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let red = 0, sum = 0;
    for (let i = 0; i < data.length; i += 4) { red += data[i]; sum += data[i] + data[i + 1] + data[i + 2]; }
    return red / Math.max(1, sum);
  }, png);
}

async function rightEdge(page: Page) {
  const box = (await page.locator('.vstage').boundingBox())!;
  return { x: Math.round(box.x + box.width - 24), y: Math.round(box.y + 40), width: 20, height: Math.round(box.height - 220) };
}

test('Rahmen verdeckt: Leuchten, Hinweis, Ecken rechts', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Freigegeben');
  await page.waitForTimeout(600);
  const calm = await redShare(page, await rightEdge(page));
  await hook(page, '/test/scene', { name: 'running_rahmen_verdeckt' });
  const stage = page.locator('.vstage');
  await expect(stage).toHaveClass(/fx-err/);
  const toast = page.locator('.toast', { hasText: 'Rahmenbereiche verdeckt oder verschoben – Kamera und Sicht prüfen' });
  await expect(toast).toBeVisible();
  await expect(toast).toContainText('Anzeige verloren');
  const fx = page.locator('canvas.vfx');
  await expect.poll(() => fx.evaluate((el: any) => el.effects.stats().kind)).toBe('error');
  expect(await fx.evaluate((el: any) => el.effects.stats().corners)).toEqual([1, 2]);
  await expect.poll(() => fx.evaluate((el: any) => el.effects.stats().particles)).toBeGreaterThan(100);
  await page.waitForTimeout(800);
  const hot = await redShare(page, await rightEdge(page));
  expect(hot).toBeGreaterThan(calm + 0.01);
  // Zeichenzeit der Effektebene: Median ueber 60 Bilder unter 4 ms.
  const median = await fx.evaluate((el: any) => new Promise<number>((resolve) => {
    const samples: number[] = [];
    const step = () => {
      samples.push(el.effects.stats().lastDrawMs);
      if (samples.length < 60) requestAnimationFrame(step);
      else resolve(samples.sort((a, b) => a - b)[30]);
    };
    requestAnimationFrame(step);
  }));
  expect(median).toBeLessThan(4);
  // Der stehende Hinweis wird je Abruf nur nachgezogen, nicht neu gebaut:
  // der Fokus bleibt auf dem Schliessen-Knopf, Enter schliesst ihn.
  const close = toast.getByRole('button', { name: 'Schließen' });
  await close.focus();
  const node = await toast.elementHandle();
  await page.waitForTimeout(1200);
  await expect(close).toBeFocused();
  expect(await node!.evaluate((el) => el.isConnected)).toBe(true);
  await page.keyboard.press('Enter');
  await expect(toast).toHaveCount(0);
  // Weggelegt bleibt weggelegt, solange der Verlust anhaelt.
  await page.waitForTimeout(1200);
  await expect(toast).toHaveCount(0);
  // Bei der Erholung verschwindet das Leuchten.
  await hook(page, '/test/scene', { name: 'running_valid' });
  await expect(stage).not.toHaveClass(/fx-err/);
  expect(errors).toEqual([]);
});

test('Anzeige bewegt: Dialog, Esc = Weiter beobachten, kein Wiederauftauchen nach Neuladen', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await page.evaluate(() => sessionStorage.clear());
  const posts: string[] = [];
  page.on('request', (r) => { if (r.method() === 'POST' && /\/live\//.test(r.url())) posts.push(new URL(r.url()).pathname); });
  await hook(page, '/test/scene', { name: 'running_anzeige_bewegt' });
  const modal = page.getByRole('dialog', { name: 'Anzeige hat sich bewegt' });
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('Anzeige hat sich bewegt (ca. 19 px (Ecken), 2,2 Grad) – Werte werden nicht freigegeben. Bitte neu einrichten.');
  for (const name of ['Weiter beobachten', 'Lauf stoppen', 'Neu einrichten']) {
    await expect(modal.getByRole('button', { name })).toBeVisible();
  }
  await expect(modal.getByRole('button', { name: 'Lauf stoppen' })).toHaveClass(/danger/);
  expect(await page.locator('canvas.vfx').evaluate((el: any) => el.effects.stats().corners)).toEqual([0, 1, 2, 3]);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await page.waitForTimeout(1500);
  await expect(modal).toHaveCount(0);
  // Neuladen: dieselbe Episode fragt nicht wieder.
  await page.reload();
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Unlesbar');
  await page.waitForTimeout(2000);
  await expect(modal).toHaveCount(0);
  expect(posts.filter((p) => p === '/live/run/stop' || p === '/live/setup')).toEqual([]);
  // Lauf stoppen geht ueber den bestehenden Vertrag (POST /live/run/stop).
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await expect(modal).toBeVisible();
  const stop = page.waitForRequest('**/live/run/stop');
  await modal.getByRole('button', { name: 'Lauf stoppen' }).click();
  await stop;
  await expect(modal).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('Streamstillstand: Feld mit Alter', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_stalled' });
  const panel = page.locator('.stalep');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('Streamstillstand: kein neues Kamerabild');
  const age = async () => Number((await panel.locator('.big .num').textContent())!.replace(',', '.'));
  const first = await age();
  expect(first).toBeGreaterThanOrEqual(2);
  await page.waitForTimeout(1200);
  expect(await age()).toBeGreaterThan(first + 0.5);
  await expect(page.locator('.toast', { hasText: 'Streamstillstand: kein neues Kamerabild' })).toBeVisible();
  // Eingefroren, unscharf und entsaettigt (nur das Bild, das HUD bleibt scharf).
  await expect.poll(() => page.locator('canvas.vcanvas').evaluate((el: any) => el.viewer.imageFilter()))
    .toMatch(/blur\(.*saturate/);
  expect(await page.locator('canvas.vfx').evaluate((el: any) => el.effects.stats().kind)).toBe('stalled');
  await hook(page, '/test/scene', { name: 'running_valid' });
  await expect(panel).toBeHidden();
  await expect.poll(() => page.locator('canvas.vcanvas').evaluate((el: any) => el.viewer.imageFilter())).toBe('none');
  expect(errors).toEqual([]);
});

test('Verbindung verloren: Band nach 1,5 s', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Freigegeben');
  const band = page.locator('.netband');
  await expect(band).toBeHidden();
  const { csrf } = await (await page.request.get('/live/status')).json();
  const offline = (on: boolean) => page.request.post('/test/offline', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf }, data: { on } });
  expect((await offline(true)).ok()).toBe(true);
  const started = Date.now();
  try {
    await expect(band).toBeVisible({ timeout: 5000 });
    expect(Date.now() - started).toBeGreaterThan(900);
    await expect(band).toContainText('Verbindung zur Werkbank verloren – Werte veraltet');
    const seconds = async () => Number(/seit ([\d,]+) s/.exec((await band.textContent())!)![1].replace(',', '.'));
    const a = await seconds();
    expect(a).toBeGreaterThanOrEqual(1.5);
    await page.waitForTimeout(700);
    expect(await seconds()).toBeGreaterThan(a);
    await expect(page.locator('body')).toHaveClass(/offline/);
    expect(await page.locator('canvas.vfx').evaluate((el: any) => el.effects.stats().kind)).toBe('offline');
    // Das Band liegt unter der Titelleiste: Lauf stoppen bleibt sichtbar und klickbar
    // (POSTs koennen ankommen, auch wenn der Statusabruf haengt).
    const stopButton = page.getByRole('banner').getByRole('button', { name: 'Lauf stoppen' });
    await expect(stopButton).toBeVisible();
    const stop = page.waitForRequest('**/live/run/stop');
    await stopButton.click();
    await stop;
  } finally {
    expect((await offline(false)).ok()).toBe(true);
  }
  await expect(band).toBeHidden({ timeout: 5000 });
  await hook(page, '/test/scene', { name: 'running_valid' });
  expect(errors).toEqual([]);
});

test('Hinweise: gleicher Schlüssel ersetzt, höchstens drei sichtbar, per Tastatur schließbar', async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });
  await page.evaluate(async () => {
    const { toast } = await import('/static/live/ui/toasts.js');
    toast({ level: 'info', title: 'Eins', key: 'a', sticky: true });
    toast({ level: 'info', title: 'Eins neu', key: 'a', sticky: true });
    for (const t of ['Zwei', 'Drei', 'Vier']) toast({ level: 'warn', title: t, sticky: true });
    toast({ level: 'warn', title: 'Vier', sticky: true });
  });
  const visible = page.locator('.toast:visible');
  await expect(visible).toHaveCount(3);
  await expect(page.locator('.toast', { hasText: 'Eins' })).toHaveCount(1);
  await expect(page.locator('.toast', { hasText: 'Vier' })).toHaveCount(1);
  await expect(visible.first()).toContainText('Zwei');
  const close = page.locator('.toast', { hasText: 'Vier' }).getByRole('button', { name: 'Schließen' });
  await close.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.toast', { hasText: 'Vier' })).toHaveCount(0);
  await expect(visible).toHaveCount(3);
  await page.locator('.toast', { hasText: 'Drei' }).getByRole('button', { name: 'Schließen' }).focus();
  await page.keyboard.press('Escape');
  await expect(page.locator('.toast', { hasText: 'Drei' })).toHaveCount(0);
  // Nicht stehende Hinweise schliessen nach 4 s selbst.
  await page.evaluate(async () => {
    const { toast } = await import('/static/live/ui/toasts.js');
    toast({ level: 'info', title: 'Kurz' });
  });
  await expect(page.locator('.toast', { hasText: 'Kurz' })).toBeVisible();
  await expect(page.locator('.toast', { hasText: 'Kurz' })).toHaveCount(0, { timeout: 6000 });
  expect(errors).toEqual([]);
});

// ---------------------------------------------------------------------------
// Einarbeitung (Aufgabe 11): Übungslauf, Rundgang, Hilfe-Dock
// ---------------------------------------------------------------------------

test('Übungslauf sendet keine POSTs', async ({ page }) => {
  test.setTimeout(90_000);
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  // Szenario-Zeit vorspulen statt 80 s zu warten (performance.now und Timer).
  await page.clock.install();
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });
  const posts: string[] = [];
  page.on('request', (r) => { if (r.method() === 'POST' && /\/live\//.test(new URL(r.url()).pathname)) posts.push(new URL(r.url()).pathname); });
  const title = page.getByRole('banner');
  const bar = page.getByRole('contentinfo');
  await title.getByRole('button', { name: 'Hilfe' }).click();
  await page.getByRole('menuitem', { name: /Übungslauf/ }).click();
  await expect(title.getByText('Übungslauf – keine Messung')).toBeVisible();
  await expect(bar.getByText('Übungslauf – keine Messung')).toBeVisible();
  const coach = page.locator('.coach');
  await expect(coach).toContainText('Einrichtung starten');
  await expect(bar).toContainText(/Sitzung\s*uebung-/);

  await title.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  const left = page.getByRole('complementary', { name: 'Ablauf' });
  await expect(left.locator('[data-step="fokus"]')).toHaveAttribute('data-state', 'running');
  await page.clock.fastForward(50_000);
  await expect(left.locator('[data-step="bestaetigen"]')).toHaveAttribute('data-state', 'running', { timeout: 10_000 });
  await expect(coach).toContainText('Bestätigen');

  // Rahmenbereich per Bildklick: Antwort kommt aus dem Szenario, nicht vom Server.
  const canvas = page.locator('canvas.vcanvas');
  const box = (await canvas.boundingBox())!;
  const [sx, sy] = await canvas.evaluate((el: any) => el.viewer.imageToScreen([700, 330]));
  await page.mouse.click(box.x + sx, box.y + sy);
  await expect(page.locator('.vfb')).toContainText('hinzugefügt – geeignet');

  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await inspector.getByLabel('Name').fill('Übung Bediener');
  await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
  await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
  await title.getByRole('button', { name: 'Bestätigen', exact: true }).click();
  await expect(title).toContainText('Einrichtung bestätigt · Übung Bediener');
  await title.getByRole('button', { name: 'Lauf starten', exact: true }).click();
  const judge = page.getByRole('region', { name: 'Ergebnis' });
  await expect(judge.locator('.jh')).toContainText('Freigegeben');
  await expect(page.locator('.vchip').first()).toContainText('Übung');

  await title.getByRole('button', { name: 'Ereignis markieren' }).click();
  await page.locator('#mark-text').fill('Übungsmarke');
  await page.getByRole('button', { name: 'Marke setzen' }).click();
  await expect(page.locator('.toast', { hasText: 'Ereignis markiert' })).toBeVisible();

  // Mock EP.bump = 35 s: Dialog "Anzeige hat sich bewegt", Lauf stoppen geht ans Szenario.
  await page.clock.fastForward(37_000);
  const modal = page.getByRole('dialog', { name: 'Anzeige hat sich bewegt' });
  await expect(modal).toBeVisible({ timeout: 10_000 });
  await modal.getByRole('button', { name: 'Lauf stoppen' }).click();
  await expect(title.getByRole('button', { name: 'Neu einrichten' })).toBeVisible();
  await expect(left).toContainText('Endgrund bediener');
  await expect(coach).toContainText('Übung beenden');

  await title.getByRole('button', { name: 'Übung beenden' }).click();
  await expect(title.getByText('Übungslauf – keine Messung')).toBeHidden();
  await expect(bar.getByText('Übungslauf – keine Messung')).toBeHidden();
  await expect(coach).toBeHidden();
  await expect(bar).toContainText('test-session');
  await expect(title.getByRole('button', { name: 'Einrichtung starten', exact: true })).toBeVisible();
  expect(posts).toEqual([]);
  expect(errors).toEqual([]);
});

test('Übungslauf gesperrt während eines Laufs', async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await hook(page, '/test/scene', { name: 'running_valid' });
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Freigegeben');
  await page.getByRole('banner').getByRole('button', { name: 'Hilfe' }).click();
  const item = page.getByRole('menuitem', { name: /Übungslauf/ });
  await expect(item).toBeDisabled();
  await expect(item).toContainText('Gesperrt, solange ein Lauf läuft');
  await expect(page.getByRole('menuitem', { name: /Rundgang/ })).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(item).toBeHidden();
  expect(errors).toEqual([]);
});

test('Rundgang: 8 Stationen, Überspringen merkt sich', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, { tour: true });
  await hook(page, '/test/scene', { name: 'idle' });
  await page.evaluate(() => localStorage.removeItem('werkbank.rundgang'));
  await page.reload();
  const offer = page.getByRole('dialog', { name: 'Rundgang anbieten' });
  await expect(offer).toBeVisible();
  await offer.getByRole('button', { name: 'Rundgang starten' }).click();
  const tour = page.getByRole('dialog', { name: 'Rundgang' });
  const titles = ['Titelleiste und Aktionen', 'Ablauf-Dock', 'Viewer mit Werkzeugleiste', 'HUD-Legende', 'Inspektor',
    'Ergebnisanzeige', 'Zeitleiste', 'Statusleiste'];
  for (const [i, name] of titles.entries()) {
    await expect(tour).toContainText(`${i + 1}/8`);
    await expect(tour.locator('h3')).toHaveText(name);
    const frame = (await page.locator('.tour-hl').boundingBox())!;
    expect(frame.width).toBeGreaterThan(40);
    if (name === 'HUD-Legende') await expect(page.locator('.legend')).toBeVisible();
    if (i < titles.length - 1) await tour.getByRole('button', { name: 'Weiter' }).click();
  }
  await tour.getByRole('button', { name: 'Zurück' }).click();
  await expect(tour.locator('h3')).toHaveText('Zeitleiste');
  // Überspringen merkt sich: kein Angebot mehr nach dem Neuladen.
  await tour.getByRole('button', { name: 'Überspringen' }).click();
  await expect(tour).toHaveCount(0);
  await expect(page.locator('.legend')).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem('werkbank.rundgang'))).toBe('übersprungen');
  await page.reload();
  await expect(page.getByRole('banner')).toContainText('Einrichtung starten');
  await page.waitForTimeout(800);
  await expect(offer).toHaveCount(0);
  // Über Hilfe › Rundgang bleibt er erreichbar; Esc beendet ihn.
  await page.getByRole('banner').getByRole('button', { name: 'Hilfe' }).click();
  await page.getByRole('menuitem', { name: /Rundgang/ }).click();
  await expect(tour.locator('h3')).toHaveText('Titelleiste und Aktionen');
  await page.keyboard.press('Escape');
  await expect(tour).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('Rundgang: kein Angebot über einem laufenden Lauf', async ({ page }) => {
  const errors = watchErrors(page);
  await login(page, { tour: true });
  await hook(page, '/test/scene', { name: 'running_valid' });
  await page.evaluate(() => localStorage.removeItem('werkbank.rundgang'));
  await page.reload();
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Freigegeben');
  await page.waitForTimeout(800);
  await expect(page.getByRole('dialog', { name: 'Rundgang anbieten' })).toHaveCount(0);
  await hook(page, '/test/scene', { name: 'idle' });
  expect(errors).toEqual([]);
});

test('Hilfe findet „Gegenlesen“', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });
  await page.getByRole('banner').getByRole('button', { name: 'Hilfe' }).click();
  await page.getByRole('menuitem', { name: /Glossar/ }).click();
  const dock = page.getByRole('complementary', { name: 'Hilfe' });
  await expect(dock).toBeVisible();
  await expect(page.locator('.inspector')).toBeHidden();
  const search = dock.getByRole('searchbox', { name: 'Begriff suchen' });
  await search.fill('gegenl');
  const hit = dock.locator('.gl-entry', { hasText: 'Gegenlesen' }).first();
  await expect(hit).toBeVisible();
  await expect(dock.locator('.gl-entry:visible', { hasText: 'Kontrast' })).toHaveCount(0);
  await expect(hit.getByRole('link', { name: /Wiki/ })).toHaveAttribute('href', /glossar\/#gegenlesen$/);
  // Gründe kommen aus dem Status (fields.py REASONS über tracking_reasons).
  await search.fill('rahmenbewegungen');
  await expect(dock.locator('.gl-entry:visible')).toContainText(['rahmenbewegungen passen nicht zusammen']);
  // Lesegründe aus cause_texts (fields.py LIVE_CAUSE_TEXT im vollen Status).
  await search.fill('zelle_mehrdeutig');
  await expect(dock.locator('.gl-entry:visible')).toHaveCount(1);
  await expect(dock.locator('.gl-entry:visible')).toContainText('Zeichen mehrdeutig');
  await expect(dock.locator('.gl-sec:visible .gl-h')).toContainText(['Lesegründe']);
  await dock.getByRole('button', { name: 'Hilfe schließen' }).click();
  await expect(dock).toBeHidden();
  await expect(page.locator('.inspector')).toBeVisible();
  expect(errors).toEqual([]);
});

// Helfer: Übungslauf über das Hilfe-Menü starten und bis in den Lauf bringen.
async function practiceToRun(page: Page) {
  const title = page.getByRole('banner');
  await title.getByRole('button', { name: 'Hilfe' }).click();
  await page.getByRole('menuitem', { name: /Übungslauf/ }).click();
  await expect(title.getByText('Übungslauf – keine Messung')).toBeVisible();
  await title.getByRole('button', { name: /Einrichtung starten|Neu einrichten/ }).first().click();
  await page.clock.fastForward(50_000);
  const inspector = page.getByRole('complementary', { name: 'Inspektor' });
  await expect(inspector.getByLabel('Name')).toBeVisible({ timeout: 10_000 });
  await inspector.getByLabel('Name').fill('Übung');
  await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
  await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
  await title.getByRole('button', { name: 'Bestätigen', exact: true }).click();
  await title.getByRole('button', { name: 'Lauf starten', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Ergebnis' }).locator('.jh')).toContainText('Freigegeben');
}

test('Übung beenden mitten im Lauf: kein falscher „gestoppt“-Hinweis für die echte Werkbank', async ({ page }) => {
  test.setTimeout(90_000);
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.clock.install();
  await login(page);
  await hook(page, '/test/scene', { name: 'stopped' });
  await expect(page.getByRole('banner').getByRole('button', { name: 'Neu einrichten' })).toBeVisible();
  await practiceToRun(page);
  await expect(page.locator('.toast', { hasText: 'gestartet' })).toBeVisible();
  await page.getByRole('banner').getByRole('button', { name: 'Übung beenden' }).click();
  await expect(page.getByRole('contentinfo')).toContainText('test-session');
  // Echter Stand "Lauf beendet" kommt an; weder "gestoppt" noch ein Übungsereignis taucht auf.
  // Momentaufnahmen statt wartender Erwartung: ein Hinweis schliesst nach 4 s von selbst.
  for (let i = 0; i < 6; i++) {
    expect(await page.locator('.toast').allTextContents()).toEqual([]);
    await page.waitForTimeout(400);
  }
  await expect(page.locator('.modalbg')).toHaveCount(0);
  await expect(page.getByRole('complementary', { name: 'Ablauf' })).toContainText('Lauf beendet');
  expect(errors).toEqual([]);
});

test('Übungslauf läuft weiter, wenn die echte Werkbank nicht antwortet', async ({ page }) => {
  const errors = watchErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await hook(page, '/test/scene', { name: 'idle' });
  const { csrf } = await (await page.request.get('/live/status')).json();
  const offline = (on: boolean) => page.request.post('/test/offline', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': csrf }, data: { on } });
  const title = page.getByRole('banner');
  await title.getByRole('button', { name: 'Hilfe' }).click();
  await page.getByRole('menuitem', { name: /Übungslauf/ }).click();
  await title.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
  const meta = page.getByRole('complementary', { name: 'Ablauf' }).locator('[data-part="meta"]');
  expect((await offline(true)).ok()).toBe(true);
  try {
    const first = await meta.textContent();
    await page.waitForTimeout(4000);
    // Die Einrichtung zählt weiter, kein Band "Verbindung verloren".
    await expect(meta).not.toHaveText(first!);
    await expect(page.locator('.netband')).toBeHidden();
    await expect(page.locator('body')).not.toHaveClass(/offline/);
  } finally {
    expect((await offline(false)).ok()).toBe(true);
  }
  await title.getByRole('button', { name: 'Übung beenden' }).click();
  expect(errors).toEqual([]);
});

// ---------------------------------------------------------------------------
// Gesamtablauf (Aufgabe 12): Einrichtung → Bestätigen → Lauf → Stopp
// ---------------------------------------------------------------------------
// Kein horizontales Rollen und nichts abgeschnitten: Bedienelemente der
// Titelleiste, der Werkzeugleiste und die Felder der Statusleiste liegen ganz
// in ihrer Leiste; ein Feld mit Auslassung (…) trägt den vollen Text als Titel.
async function fits(page: Page, where: string) {
  await noOverflow(page);
  const clipped = await page.evaluate(() => {
    const out: string[] = [];
    const bars = document.querySelectorAll('.titlebar, .vt, .statusbar');
    for (const bar of bars) {
      const edge = bar.getBoundingClientRect();
      const items = bar.matches('.statusbar') ? bar.querySelectorAll(':scope > .it')
        : bar.querySelectorAll('button, .brand, .device, .testband, .pband, .hdr-note');
      for (const el of items as NodeListOf<HTMLElement>) {
        if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
        if (el.closest('.menu, .popover')) continue;
        const box = el.getBoundingClientRect();
        if (!box.width) continue;
        const label = `${bar.className}: ${(el.textContent || '').trim().slice(0, 30)}`;
        if (box.left < edge.left - 0.5 || box.right > edge.right + 0.5) out.push(`${label} ragt hinaus`);
        const inner = [el, ...el.querySelectorAll('*')] as HTMLElement[];
        const cut = inner.some((node) => node.scrollWidth > node.clientWidth + 1 && getComputedStyle(node).overflow !== 'visible');
        if (cut && !el.title) out.push(`${label} abgeschnitten ohne Titel`);
      }
    }
    return out;
  });
  expect(clipped, where).toEqual([]);
}

for (const [width, height] of [[1280, 800], [1440, 900], [1920, 1080]]) {
  test(`Gesamtablauf ${width}×${height}: Einrichtung → Bestätigen → Lauf → Stopp`, async ({ page }) => {
    const errors = watchErrors(page);
    await page.setViewportSize({ width, height });
    await login(page);
    await hook(page, '/test/scene', { name: 'idle' });
    const title = page.getByRole('banner');
    const left = page.getByRole('complementary', { name: 'Ablauf' });
    const inspector = page.getByRole('complementary', { name: 'Inspektor' });
    const bar = page.getByRole('contentinfo');
    const judge = page.getByRole('region', { name: 'Ergebnis' });
    await expect(left).toContainText('Bereit zur Einrichtung');
    await expect(bar).toContainText('test-session');
    await fits(page, 'idle');

    // Einrichtung starten; der Fake springt auf die Fokussuche.
    const setup = page.waitForRequest('**/live/setup');
    await title.getByRole('button', { name: 'Einrichtung starten', exact: true }).click();
    expect((await setup).postDataJSON()).toEqual({ cell_text: null });
    await expect(left.locator('[data-step="fokus"]')).toHaveAttribute('data-state', 'running');
    await expect(inspector.getByRole('tab', { name: 'Fokus' })).toHaveAttribute('aria-selected', 'true');
    await fits(page, 'Fokus');
    await hook(page, '/test/scene', { name: 'setup_standbilder' });
    await expect(left.locator('[data-step="standbilder"] [data-sub="stabilitaet"]')).toContainText('9/15 s');
    await fits(page, 'Standbilder');

    // Vorschlag prüfen: Bildquellen und Prüfungen, dann mit Namen bestätigen.
    await hook(page, '/test/scene', { name: 'setup_ready_warnung' });
    await expect(inspector.locator('[data-part="selection"]')).toHaveText('Auswahl: automatisch');
    const source = page.getByRole('region', { name: 'Bildansicht' }).getByRole('group', { name: 'Bildquelle' });
    for (const name of ['Standbild', 'Abtastbild', 'Entzerrt']) {
      await source.getByRole('button', { name }).click();
      await expect(source.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
      await fits(page, `Quelle ${name}`);
    }
    await source.getByRole('button', { name: 'Live' }).click();
    await inspector.getByRole('tab', { name: /Prüfungen/ }).click();
    await expect(inspector.getByRole('tabpanel').locator('tr[data-check="raster"]')).toContainText('WARNUNG');
    await fits(page, 'Prüfungen');
    await inspector.getByRole('tab', { name: 'Schritt' }).click();
    const titleConfirm = title.getByRole('button', { name: 'Bestätigen', exact: true });
    await expect(titleConfirm).toBeDisabled();
    await inspector.getByLabel('Name').fill('L. Hentschke');
    await inspector.getByRole('checkbox', { name: 'Einheit mV/V und Format geprüft' }).check();
    await inspector.getByRole('checkbox', { name: /WARNUNG zur Kenntnis genommen/ }).check();
    await fits(page, 'Bestätigen');
    const confirm = page.waitForRequest('**/live/confirm');
    await titleConfirm.click();
    expect((await confirm).postDataJSON()).toEqual({ session_id: 'test-session', confirmed_by: 'L. Hentschke',
      format_checked: true, acknowledge_warning: true, use_tolerance: false,
      proposal_revision: 'b358259f721241f0b9e6af42d4fdb390' });

    // Lauf starten mit den Vorgaben aus dem Pop-up.
    const start = title.locator('.hdr-act').getByRole('button', { name: 'Lauf starten', exact: true });
    await expect(start).toBeEnabled();
    await title.getByRole('button', { name: 'Laufoptionen' }).click();
    const options = page.getByRole('dialog', { name: 'Laufoptionen' });
    await expect(options.getByRole('checkbox', { name: 'Referenz vom GSV-2AS mitschreiben' })).toBeChecked();
    await expect(options.getByRole('checkbox', { name: /^Diagnosebilder aufzeichnen/ })).not.toBeChecked();
    const pop = (await options.boundingBox())!;
    expect(pop.x).toBeGreaterThanOrEqual(0);
    expect(pop.x + pop.width).toBeLessThanOrEqual(width);
    expect(pop.y + pop.height).toBeLessThanOrEqual(height);
    await fits(page, 'Laufoptionen');
    const run = page.waitForRequest('**/live/run/start');
    await options.getByRole('button', { name: 'Lauf starten', exact: true }).click();
    expect((await run).postDataJSON()).toEqual({ test_override: false, reference: true,
      norm_schedule: null, diagnostics: false });
    await expect(judge.locator('.jh')).toContainText('Freigegeben');
    await expect(judge.locator('.jv .num')).toHaveText('+0.62427');
    await expect(page.getByRole('region', { name: 'Zeitleiste' })).toContainText('letzte 40 s');
    await fits(page, 'Lauf');
    for (const tab of ['Wert', 'Ursachen', 'Nachführung', 'Referenz']) {
      await inspector.getByRole('tab', { name: new RegExp(`^${tab}`) }).click();
      await expect(inspector.getByRole('tab', { name: new RegExp(`^${tab}`) })).toHaveAttribute('aria-selected', 'true');
      await fits(page, `Lauf, Tab ${tab}`);
    }

    // Stoppen: Zusammenfassung, kein frischer Wert, Neu einrichten.
    const stop = page.waitForRequest('**/live/run/stop');
    await title.getByRole('button', { name: 'Lauf stoppen' }).click();
    await stop;
    await expect(judge.locator('.jh')).toContainText('Lauf beendet');
    await expect(judge.locator('.jv .num')).not.toContainText('0.62427');
    await expect(left).toContainText('Fehllesungen gegen Referenz');
    await expect(title.getByRole('button', { name: 'Neu einrichten' })).toBeVisible();
    await fits(page, 'Stopp');

    // Übungslauf (eigene Sitzungskennung, längste Statusleiste).
    await page.getByRole('button', { name: /^Hilfe/ }).click();
    await page.getByRole('menuitem', { name: /Übungslauf/ }).click();
    await expect(bar).toContainText('Übungslauf – keine Messung');
    await expect(bar.locator('[data-item="session"]')).toContainText('uebung-');
    await fits(page, 'Übungslauf');
    await page.getByRole('button', { name: 'Übung beenden' }).click();
    await expect(bar.locator('[data-item="practice"]')).toBeHidden();
    expect(errors).toEqual([]);
  });
}
