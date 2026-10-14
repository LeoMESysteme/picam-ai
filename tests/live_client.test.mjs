import test from 'node:test';
import assert from 'node:assert/strict';
import {statusView, connectionView} from '../src/dispread/workbench/static/live.js';

const latest = (over) => ({frame_sequence: 7, status: 'valid', raw_text: '+1.2345', unit: 'mV/V',
  reject_reasons: [], ...over});

test('valid value shows text, unit and green class', () => {
  const view = statusView({state: 'running', run: {latest: latest(), latest_age_s: 0.2}});
  assert.equal(view.headline, '+1.2345 mV/V');
  assert.equal(view.cls, 'valid');
});

test('stale never shows the old number', () => {
  const view = statusView({state: 'running', run: {latest: latest({status: 'stale', raw_text: '',
    reject_reasons: ['no_value']})}});
  assert.equal(view.headline, 'STALE');
  assert.ok(!view.headline.includes('1.2345'));
});

test('setup failure shows the error', () => {
  const view = statusView({state: 'setup_failed', error: 'Punktraster abgelehnt: keine_startlage'});
  assert.equal(view.cls, 'error');
  assert.match(view.detail, /keine_startlage/);
});

test('valid but old value is STALE without digits', () => {
  const view = statusView({state: 'running', run: {latest: latest(), latest_age_s: 0.9}});
  assert.equal(view.headline, 'STALE');
  assert.equal(view.cls, 'stale');
  assert.ok(!view.headline.includes('1.2345'));
});

test('valid with unknown age is STALE without digits', () => {
  const view = statusView({state: 'running', run: {latest: latest(), latest_age_s: null}});
  assert.equal(view.headline, 'STALE');
  assert.ok(!view.headline.includes('1.2345'));
});

test('stopped never shows valid latest digits', () => {
  const view = statusView({state: 'stopped', run: {latest: latest(), latest_age_s: 0.2}});
  assert.equal(view.headline, 'STALE');
  assert.ok(!view.headline.includes('1.2345'));
});

test('500 ms boundary still shows a valid number', () => {
  const view = statusView({state: 'running', run: {latest: latest(), latest_age_s: 0.5}});
  assert.equal(view.headline, '+1.2345 mV/V');
});

test('fresh rejected record shows its own status without digits', () => {
  const view = statusView({state: 'running', run: {latest: latest({status: 'transition',
    reject_reasons: ['confirmation_pending']}), latest_age_s: 0.2}});
  assert.equal(view.headline, 'TRANSITION');
  assert.equal(view.detail, 'confirmation_pending');
});

const running = {state: 'running', run: {latest: latest(), latest_age_s: 0.2}};

for (const httpStatus of [null, 400, 404, 500, 503]) {
  test(`failed poll (${httpStatus}) replaces fresh digits with STALE`, () => {
    const view = connectionView(running, 1000, 1100, httpStatus);
    assert.deepEqual(view, {headline: 'STALE', cls: 'stale',
      detail: 'Verbindung zur Werkbank verloren'});
  });
}

test('expired login shows STALE and explains authentication failure', () => {
  assert.deepEqual(connectionView(running, 1000, 1100, 401),
    {headline: 'STALE', cls: 'stale', detail: 'Anmeldung abgelaufen'});
});

test('successful render older than 1.5 seconds is STALE even during a pending poll', () => {
  const view = connectionView(running, 1000, 2501, 200);
  assert.equal(view.headline, 'STALE');
  assert.equal(view.cls, 'stale');
});

test('fresh successful status uses normal statusView including the 1.5 second boundary', () => {
  for (const nowMs of [1000, 1100, 2500]) {
    assert.deepEqual(connectionView(running, 1000, nowMs, 200), statusView(running));
  }
});

test('no successful render yet is STALE', () => {
  assert.equal(connectionView(running, null, 1000, 200).headline, 'STALE');
});

test('tracking loss gives an operator hint and keeps the reason', () => {
  const view = statusView({state: 'running', run: {latest: latest({status: 'unreadable',
    reject_reasons: ['tracking_lost:low_score']}), latest_age_s: 0.2}});
  assert.equal(view.headline, 'UNREADABLE');
  assert.equal(view.detail, 'Anzeige verloren — Kamera bewegt? Neu einrichten (tracking_lost:low_score)');
});

test('setup progress uses nested step and monotonic elapsed seconds', () => {
  const view = statusView({state: 'setup_running', step: 'old',
    setup: {step: 'punktraster', elapsed_s: 12.34}});
  assert.match(view.headline, /punktraster/);
  assert.match(view.headline, /12\.3 s/);
  assert.ok(!view.headline.includes('old'));
});

test('action error survives running polls until an accepted setup start', async () => {
  const elements = new Map();
  const timers = [];
  const originals = {document: globalThis.document, fetch: globalThis.fetch,
    setInterval: globalThis.setInterval, setTimeout: globalThis.setTimeout};
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {textContent: '', value: '', replaceChildren() {}});
    return elements.get(id);
  };
  const status = {state: 'setup_running', csrf: 'test',
    setup: {step: 'fokus', elapsed_s: 1.2}};
  let acceptSetup = false;
  globalThis.document = {getElementById: element};
  globalThis.setInterval = () => 0;
  globalThis.setTimeout = (callback) => { timers.push(callback); return 0; };
  globalThis.fetch = async (_path, options) => options
    ? {ok: acceptSetup, json: async () => ({error: 'Einrichtung laeuft bereits'})}
    : {ok: true, status: 200, json: async () => status};
  try {
    await import('../src/dispread/workbench/static/live.js?error-persistence-test');
    // tick() laeuft beim Modulstart; seine Fortsetzung bis zur naechsten Runde abwarten.
    await new Promise(setImmediate);
    await element('setup').onclick();
    assert.equal(element('error').textContent, 'Einrichtung laeuft bereits');
    await timers.shift()();
    assert.equal(element('error').textContent, 'Einrichtung laeuft bereits');
    acceptSetup = true;
    await element('setup').onclick();
    assert.equal(element('error').textContent, '');
  } finally {
    for (const [name, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  }
});

test('setup progress displays the separate message alongside the phase', () => {
  const view = statusView({state: 'setup_running',
    setup: {step: 'standbilder', elapsed_s: 12.34, message: 'Startsuche Versuch 2'}});
  assert.match(view.headline, /standbilder/);
  assert.equal(view.detail, 'Startsuche Versuch 2');
  assert.equal(statusView({state: 'setup_failed', error: 'original failure',
    setup: {message: 'Startsuche Versuch 2'}}).detail, 'original failure');
});
