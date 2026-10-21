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
    format_checked: true, acknowledge_warning: true,
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
  await setState({ state: 'running', run });
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
