import { expect, test } from '@playwright/test';

test('Live-Seite: Anmeldung, Einrichtung, Freigabe und Verbindungsverlust', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/live');
  await expect(page).toHaveURL(/\/login\?next=\/live$/);
  await page.getByLabel('Linux-Passwort').fill('test-only');
  await page.getByRole('button', { name: 'enter', exact: true }).click();
  await expect(page).toHaveURL(/\/live$/);
  const headline = page.locator('#headline');
  await expect(headline).toHaveText('Bereit zur Einrichtung');
  await expect(page.locator('#notice')).toContainText('Validiert nur:');
  await expect(page.locator('#confirm-box')).toBeHidden();
  await expect(page.locator('#diagnostics-enabled')).not.toBeChecked();
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
    unit: 'mV/V', reject_reasons: [] }, latest_age_s: 0.2 };
  await setState({ state: 'running', run, diagnostics: {enabled: true, saved: 4, bytes: 12_500_000,
    dropped_queue: 0, dropped_limit: 0, dropped_memory: 2, dropped_mark_rate: 3, write_errors: 0},
    diagnostic_leftovers: [{path: '/test/dispread-diagnose-old', bytes: 2_500_000}] });
  await expect(page.locator('#diagnostics-status')).toContainText('12.5 MB');
  await expect(page.locator('#diagnostics-status')).toContainText('RAM verworfen: 2');
  await expect(page.locator('#diagnostics-status')).toContainText('Markenbilder verworfen: 3');
  await expect(page.locator('#diagnostics-status')).toContainText('/test/dispread-diagnose-old (2.5 MB)');
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

  // Erst wieder frische Ziffern zeigen, dann die echte Poll-Anfrage abbrechen.
  await setState({ state: 'running', run });
  await expect(headline).toHaveText('+1.2345 mV/V');
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
  await expect(page).toHaveURL(/\/live$/);
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
