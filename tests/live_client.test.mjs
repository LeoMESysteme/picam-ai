import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {statusView, connectionView, effectState, stepRows} from '../src/dispread/workbench/static/live/model.js';
import {createClient} from '../src/dispread/workbench/static/live/api.js';
import {focusChartModel, focusChartSVG} from '../src/dispread/workbench/static/live/setup/focus-chart.js';
import {checkRows, checksHTML, checksSummary, overallView, warningCount} from '../src/dispread/workbench/static/live/setup/checks.js';
import {confirmBody, confirmModel, fieldsReady} from '../src/dispread/workbench/static/live/setup/confirm.js';
import {exposureHTML} from '../src/dispread/workbench/static/live/setup/exposure.js';
import {stepsHTML} from '../src/dispread/workbench/static/live/setup/steps.js';
import {REGION_NETWORK_ERROR, editFeedback, regionAt, resultText} from '../src/dispread/workbench/static/live/viewer/regions-edit.js';

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

test('display change is shown as TRANSITION "Wert wechselt", STALE still wins', () => {
  const status = {state: 'running', run: {latest: latest({status: 'transition', raw_text: null,
    reject_reasons: ['anzeige_wechselt', 'unreadable_cells:1']}), latest_age_s: 0.2}};
  const view = statusView(status);
  assert.equal(view.headline, 'TRANSITION');
  assert.equal(view.cls, 'transition');
  assert.equal(view.detail, 'Wert wechselt (anzeige_wechselt, unreadable_cells:1)');
  status.run.latest_age_s = 0.9;
  assert.equal(statusView(status).headline, 'STALE');
});

test('setup progress uses nested step and monotonic elapsed seconds', () => {
  const view = statusView({state: 'setup_running', step: 'old',
    setup: {step: 'punktraster', elapsed_s: 12.34}});
  assert.match(view.headline, /punktraster/);
  assert.match(view.headline, /12\.3 s/);
  assert.ok(!view.headline.includes('old'));
});

async function withLivePage(check, initial = {}) {
  const elements = new Map();
  const timers = [];
  const originals = {document: globalThis.document, fetch: globalThis.fetch,
    setInterval: globalThis.setInterval, setTimeout: globalThis.setTimeout};
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {textContent: '', value: '',
      checked: id === 'reference-enabled', children: [],
      replaceChildren(...nodes) { this.children = nodes; }, append(...nodes) { this.children.push(...nodes); }});
    return elements.get(id);
  };
  const page = {status: {state: 'setup_running', csrf: 'test',
    setup: {step: 'fokus', elapsed_s: 1.2}}, actionError: 'Einrichtung laeuft bereits',
    httpStatus: 200, ...initial};
  let created = 0;
  globalThis.document = {getElementById: element, createElement: (tag) => element(`${tag}-${created++}`)};
  globalThis.setInterval = () => 0;
  globalThis.setTimeout = (callback) => { timers.push(callback); return 0; };
  page.posts = [];
  page.gets = [];
  globalThis.fetch = async (_path, options) => {
    if (!options) page.gets.push(_path);
    if (options) page.posts.push({path: _path, body: JSON.parse(options.body)});
    return options
    ? {ok: !page.actionError, json: async () => ({error: page.actionError})}
    : {ok: page.httpStatus >= 200 && page.httpStatus < 300,
      status: page.httpStatus, json: async () => page.status};
  };
  try {
    await import(`../src/dispread/workbench/static/live.js?dom-test=${domTestNumber++}`);
    // tick() laeuft beim Modulstart; seine Fortsetzung bis zur naechsten Runde abwarten.
    await new Promise(setImmediate);
    await check(page, element, () => timers.shift()());
  } finally {
    for (const [name, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  }
}
let domTestNumber = 0;

test('camera status shows stream stall even while its reader still runs', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {...running, run: {...running.run, latest_age_s: 2.1},
      camera: {running: true, stalled: true, error: 'Streamstillstand: kein Bild seit 2.0 s'}};
    await poll();
    assert.equal(element('camera').textContent, 'Streamstillstand: kein Bild seit 2.0 s');
    assert.equal(element('headline').className, 'value stale');
    page.status = {state: 'stopped', error: 'kamera: Streamstillstand: kein Bild seit 2.0 s',
      camera: page.status.camera};
    await poll();
    assert.match(element('error').textContent, /Streamstillstand/);
  });
});

test('action error survives running polls until an accepted setup start', async () => {
  await withLivePage(async (page, element, poll) => {
    await element('setup').onclick();
    assert.equal(element('error').textContent, 'Einrichtung laeuft bereits');
    await poll();
    assert.equal(element('error').textContent, 'Einrichtung laeuft bereits');
    page.actionError = '';
    await element('setup').onclick();
    assert.equal(element('error').textContent, '');
  });
});

test('successful confirm clears action error through a new run', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', error: null};
    await poll();
    page.actionError = 'Name fehlt';
    await element('confirm').onclick();
    assert.equal(element('error').textContent, 'Name fehlt');
    await poll();
    assert.equal(element('error').textContent, 'Name fehlt');
    page.actionError = '';
    element('confirmed-by').value = 'Operator';
    await element('confirm').onclick();
    assert.equal(element('error').textContent, '');
    await element('run-start').onclick();
    page.status = {...running, error: null};
    await poll();
    assert.equal(element('headline').className, 'value valid');
    assert.equal(element('error').textContent, '');
  });
});

test('cleared server error disappears on the next status poll', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'stopped', error: 'Kamera verloren'};
    await poll();
    assert.equal(element('error').textContent, 'Kamera verloren');
    page.status = {...running, error: null};
    await poll();
    assert.equal(element('error').textContent, '');
    assert.equal(element('headline').className, 'value valid');
  });
});

test('setup failure stays authoritative across camera reconnect', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_failed', error: 'Punktraster abgelehnt'};
    await poll();
    page.actionError = 'Kamera nicht gestartet';
    await element('camera-start').onclick();
    assert.equal(element('error').textContent, 'Punktraster abgelehnt\nKamera nicht gestartet');
    page.actionError = '';
    await element('camera-start').onclick();
    assert.equal(element('error').textContent, 'Punktraster abgelehnt');
    await poll();
    assert.equal(element('error').textContent, 'Punktraster abgelehnt');
  });
});

test('setup progress displays the separate message alongside the phase', () => {
  const view = statusView({state: 'setup_running',
    setup: {step: 'standbilder', elapsed_s: 12.34, message: 'Startsuche Versuch 2'}});
  assert.match(view.headline, /standbilder/);
  assert.equal(view.detail, 'Startsuche Versuch 2');
  assert.equal(statusView({state: 'setup_failed', error: 'original failure',
    setup: {message: 'Startsuche Versuch 2'}}).detail, 'original failure');
});


test('session change clears review form and confirmation carries rendered session', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', session_id: 'first'};
    await poll();
    element('confirmed-by').value = 'Operator';
    element('format-checked').checked = true;
    element('ack').checked = true;
    await poll();
    assert.equal(element('confirmed-by').value, 'Operator');
    await element('confirm').onclick();
    assert.equal(page.posts.at(-1).body.session_id, 'first');
    page.status = {state: 'setup_ready', session_id: 'second'};
    await poll();
    assert.equal(element('confirmed-by').value, '');
    assert.equal(element('format-checked').checked, false);
    assert.equal(element('ack').checked, false);
    await element('confirm').onclick();
    assert.equal(page.posts.at(-1).body.session_id, 'second');
  });
});

test('new setup session clears all review fields before the next proposal', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', session_id: 'reviewed'};
    await poll();
    element('confirmed-by').value = 'Operator';
    element('format-checked').checked = true;
    element('ack').checked = true;
    page.status = {state: 'setup_running', session_id: 'replacement'};
    await poll();
    assert.equal(element('confirmed-by').value, '');
    assert.equal(element('format-checked').checked, false);
    assert.equal(element('ack').checked, false);
  });
});

test('blocked confirmed proposal explains why run cannot start', () => {
  assert.deepEqual(statusView({state: 'confirmed', run_block: 'Leser abgelehnt'}),
    {headline: 'Lauf gesperrt', cls: 'error', detail: 'Leser abgelehnt'});
});

test('test run labels rejected guess separately and keeps STALE authoritative', () => {
  const status = {state: 'running', test_run: {testlauf: true}, run: {
    latest: latest({status: 'unreadable', raw_text: null, reject_reasons: ['zelle_unbekannt']}),
    latest_age_s: 0.2, guess: {text: '+0.12345 ', uncertain: [4, 5, 6, 7]},
  }};
  const view = statusView(status);
  assert.equal(view.headline, 'TESTLAUF · UNREADABLE');
  assert.match(view.detail, /Leser-Vermutung \(verworfen, nicht freigegeben\): \+0.12345 /);
  assert.match(view.detail, /unsichere Zellen: 4, 5, 6, 7/);
  status.run.guess = {text: '+0.12345 ', uncertain: []};
  assert.match(statusView(status).detail, /unsichere Zellen: keine/);
  status.run.latest = latest();
  assert.equal(statusView(status).headline, 'TESTLAUF · UNREADABLE');
  assert.equal(statusView(status).cls, 'unreadable');
  assert.match(statusView(status).detail, /Testlauf: keine Wertfreigabe/);
  assert.match(statusView(status).detail, /Leser-Vermutung/);
  status.run.latest_age_s = 0.9;
  assert.equal(statusView(status).headline, 'TESTLAUF · STALE');
  assert.equal(statusView(status).cls, 'stale');
  status.run.latest = latest({status: 'unreadable', raw_text: null, reject_reasons: ['zelle_unbekannt']});
  assert.equal(statusView(status).cls, 'stale');
  assert.doesNotMatch(statusView(status).detail, /Leser-Vermutung/);
});

test('server-suppressed test record explains rejection using the German cause text', () => {
  const status = {state: 'running', test_run: {testlauf: true}, run: {
    latest: latest({status: 'unreadable', value: null, reject_reasons: ['testlauf_keine_freigabe']}),
    latest_age_s: 0.2, guess: {text: '+1.2345', uncertain: [], gate_status: 'valid'},
    rejection_causes: {causes: [{reason: 'testlauf_keine_freigabe',
      explanation: 'Testlauf: keine Wertfreigabe', count: 1, fraction: 1}]},
  }};
  const view = statusView(status);
  assert.equal(view.headline, 'TESTLAUF · UNREADABLE');
  assert.match(view.detail, /Testlauf: keine Wertfreigabe \(testlauf_keine_freigabe\)/);
  assert.match(view.detail, /Leser-Vermutung/);
  assert.doesNotMatch(view.headline, /1\.2345/);
});

test('override requires explicit dialog approval and resets with session', async () => {
  const originalWindow = globalThis.window;
  try {
    await withLivePage(async (page, element, poll) => {
      page.status = {state: 'confirmed', session_id: 'blocked', run_block: 'Leser abgelehnt'};
      await poll();
      assert.equal(element('run-start').disabled, true);
      assert.equal(element('run-block').hidden, false);
      await element('run-start').onclick();
      assert.equal(page.posts.length, 0);
      element('test-override').checked = true;
      element('test-override').onchange();
      assert.equal(element('run-start').disabled, false);
      let dialog;
      globalThis.window = {confirm: (text) => { dialog = text; return false; }};
      await element('run-start').onclick();
      assert.match(dialog, /TESTLAUF.json/);
      assert.equal(page.posts.length, 0);
      globalThis.window.confirm = () => true;
      await element('run-start').onclick();
      assert.deepEqual(page.posts.at(-1).body, {test_override: true, reference: true, norm_schedule: null, diagnostics: false});
      assert.equal(element('test-override').checked, false);
      page.status = {...page.status, session_id: 'new'};
      await poll();
      assert.equal(element('test-override').checked, false);
      assert.equal(element('run-start').disabled, true);
    });
  } finally {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
  }
});

test('tolerance marks valid detail but STALE still wins', () => {
  const status = {...running, reader_tolerance: {factor: 1.44}};
  assert.equal(statusView(status).headline, '+1.2345 mV/V');
  assert.match(statusView(status).detail, /^erweiterte Toleranz ×1.44 – nicht validiert/);
  assert.equal(statusView({...status, run: {...status.run, latest_age_s: .9}}).headline, 'STALE');
  assert.doesNotMatch(statusView({...status, run: {...status.run, latest_age_s: .9}}).detail, /erweiterte Toleranz/);
});

test('proposal hint and tolerance selection are shown, posted and cleared', async () => {
  await withLivePage(async (page, element, poll) => {
    const hint = 'Ungleichmaessige Beleuchtung auf dem Display (Kontrastsprung zwischen Zelle 3 und 4, '
      + 'vermutlich Schatten oder Verschmutzung). Glas reinigen bzw. abschatten und neu einrichten.';
    page.status = {state: 'setup_ready', session_id: 'first', setup: {gegenlesen: {
      metrics: {hinweis: hint, tolerance: {possible: true, factor: 1.44}}}}};
    await poll();
    assert.equal(element('proposal-hint').textContent, `Hinweis: ${hint}`);
    assert.equal(element('tolerance-label').hidden, false);
    assert.match(element('tolerance-text').textContent, /×1.44/);
    element('use-tolerance').checked = true;
    await element('confirm').onclick();
    assert.equal(page.posts.at(-1).body.use_tolerance, true);
    page.status = {state: 'confirmed', session_id: 'first', reader_tolerance: {factor: 1.44}};
    await poll();
    assert.equal(element('tolerance-banner').hidden, false);
    assert.match(element('tolerance-banner').textContent, /×1.44.*nicht validiert/);
    page.status = {state: 'setup_running', session_id: 'second'};
    await poll();
    assert.equal(element('use-tolerance').checked, false);
    assert.equal(element('tolerance-banner').hidden, true);
    assert.equal(element('proposal-hint').hidden, true);
  });
});

test('restoration is shown until service finishes stopping', () => {
  const status = {...running, reference: {enabled: true, restoring: true}};
  assert.equal(statusView(status).headline, 'Werte werden zurückgestellt …');
});

test('norm plan needs confirmation and is sent with explicit reference selection', async () => {
  const oldWindow = globalThis.window;
  let confirmations = 0;
  globalThis.window = {confirm: () => { confirmations += 1; return false; }};
  try {
    await withLivePage(async (page, element) => {
      element('norm-schedule').value = '1:20,2:20';
      await element('run-start').onclick();
      assert.equal(confirmations, 1);
      assert.equal(page.posts.length, 0);
      globalThis.window.confirm = () => true;
      await element('run-start').onclick();
      assert.deepEqual(page.posts.at(-1).body, {test_override: false, reference: true, norm_schedule: '1:20,2:20', diagnostics: false});
      element('reference-enabled').checked = false;
      await element('run-start').onclick();
      assert.equal(page.posts.length, 1);
    });
  } finally {
    if (oldWindow === undefined) delete globalThis.window;
    else globalThis.window = oldWindow;
  }
});

test('new exposure check and its operator hint are visible', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', setup: {
      checks: {belichtung: 'WARNUNG'},
      check_reasons: {belichtung: 'Display zu dunkel belichtet (Glaspegel 98): Kamera näher stellen und neu einrichten'},
    }};
    await poll();
    assert.match(element('setup-checks').textContent, /belichtung: WARNUNG.*Glaspegel 98.*neu einrichten/);
  });
});

test('tracking check, German reason and mode are visible', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', setup: {
      checks: {nachfuehrung: 'FEHLER'}, check_reasons: {nachfuehrung: 'zu wenige geeignete Rahmenbereiche'},
      proposal_revision: 'v1',
    }};
    await poll();
    assert.match(element('setup-checks').textContent, /Nachführung: FEHLER.*zu wenige geeignete Rahmenbereiche/);
    page.status = {...running, run: {...running.run, tracking: {mode: 'rahmenbereiche'}}};
    await poll();
    assert.equal(element('tracking-mode').textContent, 'Nachführung: Rahmenbereiche');
    page.status.run.tracking.mode = 'ecc_alt';
    await poll();
    assert.equal(element('tracking-mode').textContent, 'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen');
  });
});

test('same session with new proposal revision clears review and posts current revision', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', session_id: 'same', setup: {proposal_revision: 'v1'}};
    await poll();
    element('confirmed-by').value = 'Operator';
    element('format-checked').checked = true;
    await element('confirm').onclick();
    assert.equal(page.posts.at(-1).body.proposal_revision, 'v1');
    page.status = {...page.status, setup: {proposal_revision: 'v2'}};
    await poll();
    assert.equal(element('confirmed-by').value, '');
    assert.equal(element('format-checked').checked, false);
    await element('confirm').onclick();
    assert.equal(page.posts.at(-1).body.proposal_revision, 'v2');
  });
});

test('tracking loss translates the specific reason supplied by fields.py', () => {
  const view = statusView({state: 'running', tracking_reasons: {lcd_rand_fehlt: 'LCD-Rand nicht ausreichend bestaetigt'},
    run: {latest: latest({status: 'unreadable', reject_reasons: ['tracking_lost:lcd_rand_fehlt']}), latest_age_s: 0.2}});
  assert.match(view.detail, /LCD-Rand nicht ausreichend bestaetigt/);
});


test('confirmed profile shows the upcoming tracking mode before a run', async () => {
  await withLivePage(async (page, element, poll) => {
    for (const [mode, text] of [
      ['rahmenbereiche', 'Nachführung: Rahmenbereiche'],
      ['ecc_alt', 'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen'],
    ]) {
      page.status = {state: 'confirmed', profile: {tracking_mode: mode}, run: null};
      await poll();
      assert.equal(element('tracking-mode').textContent, text);
    }
    page.status = {state: 'setup_running', profile: null};
    await poll();
    assert.equal(element('tracking-mode').textContent, '');
  });
});

test('page requests full status once and keeps German reasons across small polls', async () => {
  await withLivePage(async (page, element, poll) => {
    assert.equal(page.gets[0], '/live/status?full=1');
    page.status = {state: 'running', run: {latest: latest({status: 'unreadable',
      reject_reasons: ['tracking_lost:lcd_rand_fehlt']}), latest_age_s: 0.2}};
    await poll();
    assert.equal(page.gets.at(-1), '/live/status');
    assert.match(element('detail').textContent, /LCD-Rand nicht ausreichend bestaetigt/);
    await poll();
    assert.equal(page.gets.filter(path => path.includes('full=1')).length, 1);
  }, {status: {...running, tracking_reasons: {lcd_rand_fehlt: 'LCD-Rand nicht ausreichend bestaetigt'}}});
});

test('successful full status without a reasons table switches to small polls', async () => {
  await withLivePage(async (page, element, poll) => {
    assert.equal(page.gets[0], '/live/status?full=1');
    page.status = {...running};
    await poll();
    await poll();
    assert.deepEqual(page.gets, ['/live/status?full=1', '/live/status', '/live/status']);
    assert.equal(element('headline').textContent, '+1.2345 mV/V');
  });
});

test('failed full status is retried until the first successful response', async () => {
  await withLivePage(async (page, element, poll) => {
    assert.equal(element('detail').textContent, 'Verbindung zur Werkbank verloren');
    page.httpStatus = 200;
    await poll();
    await poll();
    assert.deepEqual(page.gets, ['/live/status?full=1', '/live/status?full=1', '/live/status']);
    assert.match(element('headline').textContent, /Einrichtung läuft/);
  }, {httpStatus: 500});
});


test('diagnostics default off, explicit opt-in and operator marks', async () => {
  await withLivePage(async (page, element, poll) => {
    await element('run-start').onclick();
    assert.equal(page.posts.at(-1).body.diagnostics, false);
    element('diagnostics-enabled').checked = true;
    await element('run-start').onclick();
    assert.equal(page.posts.at(-1).body.diagnostics, true);
    page.status = {state: 'running', diagnostics: {enabled: true, saved: 4, dropped_queue: 2,
      dropped_limit: 1, dropped_memory: 2, dropped_mark_rate: 3,
      write_errors: 1, first_error: 'Platte voll', bytes: 12_500_000},
      diagnostic_leftovers: [{path: '/test/dispread-diagnose-old', bytes: 2_500_000}],
      diagnose_kopie: true, last_mark: {text: '<Abdeckung>', received_at_utc: '2026-10-21T10:00:00Z'}};
    await poll();
    assert.equal(element('mark-box').hidden, false);
    assert.match(element('diagnostics-status').textContent, /4/);
    assert.match(element('diagnostics-status').textContent, /12[.,]5 MB/);
    assert.match(element('diagnostics-status').textContent, /RAM verworfen: 2/);
    assert.match(element('diagnostics-status').textContent, /Markenbilder verworfen: 3/);
    assert.match(element('diagnostics-status').textContent, /\/test\/dispread-diagnose-old.*2[.,]5 MB/);
    assert.match(element('diagnostics-status').textContent, /Platte voll/);
    assert.match(element('diagnostics-status').textContent, /kopiert/);
    assert.match(element('last-mark').textContent, /Meldezeit.*<Abdeckung>/);
    element('mark-text').value = 'Abdeckung';
    await element('run-mark').onclick();
    assert.equal(page.posts.at(-1).path, '/live/run/mark');
    assert.equal(page.posts.at(-1).body.text, 'Abdeckung');
    page.status = {state: 'stopped'};
    await poll();
    assert.equal(element('mark-box').hidden, true);
  });
});


test('region editor converts natural pixels, removes patches and clears confirmation on revision', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', session_id: 'same', setup: {proposal_revision: 'v1',
      regions: [{centre: [100, 80], size: 15}], overlays: ['overlay_source'], auswahl: 'automatisch'}};
    page.actionError = '';
    await poll();
    assert.equal(element('region-editor').hidden, false);
    element('edit-regions').checked = true;
    element('edit-regions').onchange();
    const img = element('overlays').children[0];
    img.naturalWidth = 1000; img.naturalHeight = 500;
    img.getBoundingClientRect = () => ({left: 10, top: 20, width: 500, height: 250});
    await img.onclick({clientX: 60, clientY: 60});
    assert.deepEqual(page.posts.at(-1), {path: '/live/setup/regions',
      body: {proposal_revision: 'v1', add: [], remove: [0]}});
    await img.onclick({clientX: 160, clientY: 120});
    assert.deepEqual(page.posts.at(-1).body, {proposal_revision: 'v1', add: [[300, 200]], remove: []});
    element('confirmed-by').value = 'Operator';
    element('format-checked').checked = true;
    page.status = {...page.status, setup: {...page.status.setup, proposal_revision: 'v2', auswahl: 'manuell',
      checks: {nachfuehrung: 'FEHLER'}, centre_results: [{centre: [300, 200], ok: false, reason: 'im_zeichenbereich'}]}};
    await poll();
    assert.equal(element('confirmed-by').value, '');
    assert.equal(element('format-checked').checked, false);
    assert.match(element('region-results').textContent, /300.*200.*Zeichenbereich/);
    assert.match(element('overlays').children[0].src, /v2/);
    assert.match(element('setup-checks').textContent, /Nachführung: FEHLER/);
    assert.equal(element('edit-regions').checked, true);
  });
});

test('region editor shows requested and used centres including rejected snapped points', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', setup: {proposal_revision: 'snap', centre_results: [
      {requested_centre: [290, 247], centre: [292, 247], used_centre: [292, 247], ok: true, reason: null},
      {requested_centre: [400, 140], centre: [400, 142], used_centre: [400, 142], ok: false, reason: 'im_zeichenbereich'},
      {requested_centre: [100, 100], centre: [100, 100], used_centre: null, ok: false, reason: 'zu_wenig_struktur'},
    ]}};
    await poll();
    const lines = element('region-results').textContent.split('\n');
    assert.match(lines[0], /290,247.*verwendet: 292,247.*geeignet/);
    assert.match(lines[1], /400,140.*verwendet: 400,142.*Zeichenbereich/);
    assert.match(lines[2], /100,100.*verwendet:.*kein.*Struktur/);
  });
});

for (const [reason, explanation] of [
  ['zweitbild_peak_zu_niedrig', 'Rahmenbereich im Zweitbild nicht deutlich genug wiedergefunden'],
  ['zweitbild_mehrdeutig', 'Rahmenbereich im Zweitbild nicht eindeutig wiedergefunden'],
  ['zweitbild_suchrand', 'Rahmenbereich im Zweitbild am Rand des Suchbereichs'],
  ['zweitbild_am_bildrand', 'Rahmenbereich im Zweitbild zu nah am Bildrand'],
  ['zweitbild_lage_abweichend', 'Rahmenbereich im Zweitbild an anderer Position wiedergefunden'],
]) {
  test(`region editor explains rejected centre ${reason} in German without a server table`, async () => {
    await withLivePage(async (page, element, poll) => {
      page.status = {state: 'setup_ready', setup: {proposal_revision: 'v1', centre_results: [
        {centre: [100, 80], ok: false, reason},
      ]}};
      await poll();
      assert.equal(element('region-results').textContent, `100,80 (verwendet: 100,80): ${explanation}`);
    });
  });
}

test('region editor uses supplied German reasons and retains them across small status polls', async () => {
  await withLivePage(async (page, element, poll) => {
    const setup = {proposal_revision: 'v1', centre_results: [
      {centre: [100, 80], ok: false, reason: 'zweitbild_mehrdeutig'},
    ]};
    page.status = {state: 'setup_ready', setup,
      tracking_reasons: {zweitbild_mehrdeutig: 'Rahmenbereich im Zweitbild mehrfach wiedergefunden'}};
    await poll();
    assert.match(element('region-results').textContent, /Rahmenbereich im Zweitbild mehrfach wiedergefunden/);
    page.status = {state: 'setup_ready', setup};
    await poll();
    assert.match(element('region-results').textContent, /Rahmenbereich im Zweitbild mehrfach wiedergefunden/);
  });
});

test('region editor has keyboard add/remove and rejects malformed coordinates locally', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', setup: {proposal_revision: 'v1',
      regions: [{centre: [100, 80], size: 15}]}};
    page.actionError = '';
    await poll();
    element('region-coordinates').value = '123,456';
    await element('region-add').onclick();
    assert.deepEqual(page.posts.at(-1).body, {proposal_revision: 'v1', add: [[123, 456]], remove: []});
    const removeButton = element('region-list').children[0].children[0];
    await removeButton.onclick();
    assert.deepEqual(page.posts.at(-1).body, {proposal_revision: 'v1', add: [], remove: [0]});
    element('region-coordinates').value = '123,';
    const count = page.posts.length;
    await element('region-add').onclick();
    assert.equal(page.posts.length, count);
    assert.match(element('error').textContent, /x,y/);
    page.status = {state: 'running', setup: page.status.setup};
    await poll();
    assert.equal(element('region-editor').hidden, true);
    await element('region-add').onclick();
    assert.equal(page.posts.length, count);
  });
});

test('region image clicks select the containing source pixel, including the last pixel', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {state: 'setup_ready', session_id: 'same', setup: {proposal_revision: 'v1',
      regions: [], overlays: ['overlay_source']}};
    await poll();
    element('edit-regions').checked = true;
    const img = element('overlays').children[0];
    img.naturalWidth = 1000; img.naturalHeight = 500;
    img.getBoundingClientRect = () => ({left: 10, top: 20, width: 500, height: 250});
    await img.onclick({clientX: 160.4, clientY: 120.4});
    assert.deepEqual(page.posts.at(-1).body.add, [[300, 200]]);
    await img.onclick({clientX: 509.9, clientY: 269.9});
    assert.deepEqual(page.posts.at(-1).body.add, [[999, 499]]);
  });
});

test('recent causes show the affected cell and percentage and clear after the run', async () => {
  await withLivePage(async (page, element, poll) => {
    page.status = {...running, run: {...running.run, rejection_causes: {frames: 4, window_s: 10,
      causes: [{reason: 'leser:leerzelle_gestoert:14', cell: 14, count: 1, fraction: 0.25,
        explanation: 'Zelle 14 (rechts der Einheit) gestoert - Kratzer, Staub oder Reflex?'}]}}};
    await poll();
    assert.equal(element('recent-causes').hidden, false);
    assert.match(element('recent-causes-list').children[0].textContent, /Zelle 14.*25 % der Bilder/);
    page.status = {state: 'stopped'};
    await poll();
    assert.equal(element('recent-causes').hidden, true);
    assert.deepEqual(element('recent-causes-list').children, []);
  });
});

test('tracking advice gives a concrete recovery action without changing the record class', async () => {
  await withLivePage(async (page, element, poll) => {
    const lost = {latest: latest({status: 'unreadable', raw_text: '',
      reject_reasons: ['tracking_lost:rahmen_unstimmig']}), latest_age_s: 0.2};
    page.status = {state: 'running', run: {...lost, tracking_hint: {
      kind: 'anzeige_bewegt', shift_px: 19.1, region_shift_px: 27, rotation_deg: -2.23, since_s: 3}}};
    await poll();
    assert.match(element('detail').textContent, /Anzeige hat sich bewegt.*19 px \(Ecken\).*2,2 Grad/);
    assert.match(element('detail').textContent, /Werte werden nicht freigegeben.*Bitte neu einrichten/);
    assert.equal(element('headline').className, 'value unreadable');
    for (const [kind, text] of [['rahmen_verdeckt', /Rahmen verdeckt\?.*Hand oder Gegenstand/],
      ['unbekannt', /Anzeige nicht sicher wiedergefunden.*Bitte Sicht.*neu einrichten/]]) {
      page.status.run.tracking_hint = {kind, shift_px: null, rotation_deg: null, since_s: 10};
      await poll();
      assert.match(element('detail').textContent, text);
      assert.doesNotMatch(element('detail').textContent, /Anzeige hat sich bewegt/);
    }
    page.status = {...running, run: {...running.run, tracking_hint: null}};
    await poll();
    assert.equal(element('headline').textContent, '+1.2345 mV/V');
    assert.doesNotMatch(element('detail').textContent, /bewegt|verdeckt|einrichten/);
  });
});

test('storage warning shows free SD space and diagnostics remain opt-in', async () => {
  await withLivePage(async (_page, element) => {
    assert.match(element('storage-status').textContent, /Warnung.*5 GB.*4,20 GB/);
    assert.equal(element('diagnostics-enabled').checked, false);
    await element('run-start').onclick();
    assert.equal(_page.posts.at(-1).body.diagnostics, false);
  }, {status: {state: 'confirmed', storage: {free_bytes: 4_200_000_000, level: 'warn'}}});
});

test('storage displays enough space or an unknown-space error without guessing', async () => {
  for (const [storage, expected] of [
    [{free_bytes: 6_000_000_000, level: 'ok'}, /6,00 GB/],
    [{free_bytes: 1_500_000_000, level: 'error'}, /Speicher knapp.*1,50 GB/],
    [{free_bytes: null, level: 'error', message: 'Speicherplatz nicht pruefbar'}, /nicht pruefbar/],
  ]) {
    await withLivePage(async (_page, element) => {
      assert.match(element('storage-status').textContent, expected);
    }, {status: {state: 'idle', storage}});
  }
});

// ---------------------------------------------------------------------------
// Neue Seite (static/live/): Modell, Abruf, Gestaltungsregeln
// ---------------------------------------------------------------------------
const scene = (name) => JSON.parse(readFileSync(new URL(`./fixtures/live/scene-${name}.json`, import.meta.url), 'utf8'));
// Geometrie wie im Mock: Rahmenbereiche 5-8 liegen rechts der Anzeige.
const MOCK_QUAD = [[608, 383], [1027, 383], [1033, 435], [610, 443]];
const MOCK_REGIONS = [[528, 292], [800, 290], [520, 420], [545, 560], [1082, 292], [1112, 385], [1120, 470], [1090, 535]];
const hudWith = ({failed = [], correcting = false} = {}) => ({seq: 1, w: 1920, h: 1080, track: {
  quad: MOCK_QUAD, score: 0.5, shift_px: 0.4, rotation_deg: 0, reason: null, correcting,
  regions: MOCK_REGIONS.map((c, i) => ({c, s: 15, peak: failed.includes(i) ? 0.2 : 0.92, ok: !failed.includes(i)}))}});

test('effectState: offline wins over everything', () => {
  const status = scene('running_rahmen_verdeckt');
  status.camera.stalled = true;
  status.run.tracking_hint = {kind: 'anzeige_bewegt', shift_px: 19, rotation_deg: -2.2, since_s: 3};
  const effect = effectState(status, {offline: true, frameAgeS: 9, hud: hudWith({failed: [4, 5], correcting: true})});
  assert.deepEqual(effect, {kind: 'offline', corners: [], regions: []});
});

test('effectState: stalled beats unreadable', () => {
  const status = scene('running_rahmen_verdeckt');
  status.camera.stalled = true;
  assert.equal(effectState(status, {offline: false, hud: hudWith({failed: [4]})}).kind, 'stalled');
  // Auch ohne Servermeldung: kein neues Bild seit mehr als 1,5 s.
  assert.equal(effectState(scene('running_rahmen_verdeckt'), {offline: false, frameAgeS: 1.6}).kind, 'stalled');
  assert.equal(effectState(scene('running_rahmen_verdeckt'), {offline: false, frameAgeS: 1.5}).kind, 'error');
  assert.equal(effectState(scene('running_stalled'), {offline: false}).kind, 'stalled');
});

test('effectState: rahmen_verdeckt marks right corners', () => {
  const status = scene('running_rahmen_verdeckt');
  status.run.tracking_hint = {kind: 'rahmen_verdeckt', shift_px: null, rotation_deg: null, since_s: 10};
  const effect = effectState(status, {offline: false, hud: hudWith({failed: [4, 5, 6, 7]})});
  assert.equal(effect.kind, 'error');
  assert.deepEqual(effect.regions, [4, 5, 6, 7]);
  assert.ok(effect.corners.includes(1) && effect.corners.includes(2), JSON.stringify(effect.corners));
  assert.ok(!effect.corners.includes(0) && !effect.corners.includes(3), 'linke Ecken bleiben ruhig');
});

test('effectState: moved display marks all corners, correction beats transition, valid is calm', () => {
  const moved = scene('running_anzeige_bewegt');
  assert.deepEqual(effectState(moved, {offline: false, hud: hudWith({failed: [4]})}).corners, [0, 1, 2, 3]);
  const transition = scene('running_transition');
  assert.equal(effectState(transition, {offline: false}).kind, 'transition');
  assert.equal(effectState(transition, {offline: false, hud: hudWith({correcting: true})}).kind, 'correcting');
  // Ein veralteter Wechsel ist Veraltet, kein Wechsel-Effekt.
  transition.run.latest_age_s = 0.9;
  assert.equal(effectState(transition, {offline: false}).kind, null);
  assert.deepEqual(effectState(scene('running_valid'), {offline: false}), {kind: null, corners: [], regions: []});
  assert.equal(effectState(scene('idle'), {offline: false}).kind, null);
});

test('stepRows: running standbilder shows wait 9/15', () => {
  const rows = stepRows(scene('setup_standbilder'));
  assert.deepEqual(rows.map(row => row.key), ['fokus', 'kamera', 'belichtung', 'standbilder', 'vorschlag', 'bestaetigen']);
  assert.deepEqual(rows.map(row => row.label), ['Fokus', 'Kamera', 'Belichtung', 'Standbilder', 'Vorschlag', 'Prüfen & Bestätigen']);
  assert.deepEqual(rows.map(row => row.state), ['done', 'done', 'done', 'running', 'pending', 'pending']);
  const still = rows[3];
  assert.equal(still.elapsed_s, 9);
  assert.match(still.detail, /Versuch 1\/3/);
  assert.match(still.detail, /noch 6 s/);
  const wait = still.sub.find(item => item.key === 'stabilitaet');
  assert.equal(wait.state, 'running');
  assert.equal(wait.value, '9/15 s');
  assert.deepEqual(still.sub.map(item => item.state), ['done', 'done', 'done', 'running', 'pending', 'pending']);
  assert.match(rows[0].detail, /Bestwert 48 · Schärfe 630/);
  assert.match(rows[2].detail, /p80 124 im Band 115–150 · Runde 1\/4/);
  assert.deepEqual(rows[4].sub, []);
});

test('stepRows: focus shows probes in order and the cross-check', () => {
  const running = stepRows(scene('setup_focus'))[0];
  assert.equal(running.state, 'running');
  assert.deepEqual(running.sub.map(item => [item.label, item.state]),
    [['Probe 3', 'running'], ['Gegenprüfung ≥ 85 %', 'pending']]);
  assert.equal(running.sub[0].value, 'focus_absolute 40');
  const done = stepRows(scene('setup_focus_done'))[0];
  assert.deepEqual(done.sub.map(item => item.state), ['done', 'done']);
  assert.equal(done.sub[1].value, '624 ≥ 536 (99 %)');
});

test('stepRows: failure before the first step is shown on the first step', () => {
  const status = {state: 'setup_failed', error: 'Kamera laeuft nicht', setup: {step: 'start', elapsed_s: 0.4,
    progress: {steps: ['fokus', 'kamera', 'belichtung', 'standbilder', 'vorschlag'].map(key =>
      ({key, state: 'pending', elapsed_s: null})), attempt: 1, attempts_max: 3, phase: null, wait: null}}};
  const rows = stepRows(status);
  assert.deepEqual(rows.map(row => row.state), ['failed', 'pending', 'pending', 'pending', 'pending', 'pending']);
  assert.match(rows[0].detail, /Abgebrochen/);
});

test('stepRows: after setup_failed phase and wait show where it failed, not a running countdown', () => {
  const status = scene('setup_standbilder');
  status.state = 'setup_failed';
  status.error = 'Vorpruefung meldet FEHLER: kontrast';
  status.setup.progress.steps[3].state = 'failed';
  const still = stepRows(status)[3];
  assert.equal(still.state, 'failed');
  assert.match(still.detail, /Abgebrochen bei Stabilität/);
  assert.doesNotMatch(still.detail, /noch/);
  const wait = still.sub.find(item => item.key === 'stabilitaet');
  assert.equal(wait.state, 'failed');
  assert.equal(wait.value, '9/15 s');
  assert.ok(still.sub.every(item => item.state !== 'running'));
  // Defensiv: ein nach dem Abbruch noch "laufender" Schritt gilt als fehlgeschlagen.
  status.setup.progress.steps[3].state = 'running';
  assert.equal(stepRows(status)[3].state, 'failed');
});

test('stepRows: idle lists the steps pending, ready asks for review', () => {
  const idle = stepRows(scene('idle'));
  assert.equal(idle.length, 6);
  assert.ok(idle.every(row => row.state === 'pending' && row.elapsed_s === null && row.sub.length === 0));
  const ready = stepRows(scene('setup_ready_warnung'));
  assert.deepEqual(ready.map(row => row.state), ['done', 'done', 'done', 'done', 'done', 'running']);
  assert.equal(ready[4].tone, 'warn');
  assert.match(ready[4].detail, /Gesamturteil WARNUNG/);
});

function fakeClock() {
  let t = 1000;
  const timers = [];
  const add = (fn, ms, repeat) => { const id = timers.length + 1; timers.push({id, fn, at: t + ms, ms, repeat}); return id; };
  return {
    now: () => t,
    timers: {setTimeout: (fn, ms) => add(fn, ms, false), clearTimeout: id => { const x = timers.find(y => y.id === id); if (x) x.fn = null; },
      setInterval: (fn, ms) => add(fn, ms, true), clearInterval: id => { const x = timers.find(y => y.id === id); if (x) x.fn = null; }},
    async advance(ms) {
      const end = t + ms;
      for (;;) {
        const due = timers.filter(x => x.fn && x.at <= end).sort((a, b) => a.at - b.at)[0];
        if (!due) break;
        t = due.at;
        const fn = due.fn;
        if (due.repeat) due.at += due.ms; else due.fn = null;
        fn();
        await new Promise(setImmediate);
      }
      t = end;
      await new Promise(setImmediate);
    },
  };
}

test('client polls full status once, keeps German reasons, and posts with the CSRF token', async () => {
  const clock = fakeClock();
  const gets = [];
  const posts = [];
  let reply = {ok: true, status: 200, body: {state: 'idle', csrf: 'tok-1', tracking_reasons: {rahmen_unstimmig: 'Rahmen passt nicht'}}};
  const fetchImpl = async (path, options) => {
    if (options?.method === 'POST') {
      posts.push({path, headers: options.headers, body: JSON.parse(options.body)});
      return {ok: false, status: 409, statusText: 'Conflict', text: async () => JSON.stringify({error: 'Einrichtung laeuft bereits'})};
    }
    gets.push(path);
    return {ok: reply.ok, status: reply.status, json: async () => structuredClone(reply.body)};
  };
  const client = createClient({fetchImpl, now: clock.now, timers: clock.timers});
  const statuses = [];
  const connections = [];
  client.start(s => statuses.push(s), c => connections.push(c));
  await new Promise(setImmediate);
  reply = {ok: true, status: 200, body: {state: 'idle', csrf: 'tok-2'}};
  await clock.advance(1100);
  assert.equal(gets[0], '/live/status?full=1');
  assert.ok(gets.slice(1).length >= 2 && gets.slice(1).every(path => path === '/live/status'), gets.join(' '));
  assert.equal(statuses.at(-1).tracking_reasons.rahmen_unstimmig, 'Rahmen passt nicht');
  assert.equal(connections.at(-1).offline, false);
  assert.equal(connections.at(-1).view.headline, 'Bereit zur Einrichtung');
  const result = await client.post('/live/setup', {cell_text: null});
  assert.deepEqual(result, {ok: false, error: 'Einrichtung laeuft bereits', data: {error: 'Einrichtung laeuft bereits'}});
  assert.equal(posts[0].headers['X-CSRF-Token'], 'tok-2');
  assert.deepEqual(posts[0].body, {cell_text: null});
  client.stop();
  const count = gets.length;
  await clock.advance(5000);
  assert.equal(gets.length, count, 'nach stop keine Abrufe mehr');
});

test('client retries the full status until the first success and reports a hanging poll as offline', async () => {
  const clock = fakeClock();
  const gets = [];
  let mode = 'fail';
  const fetchImpl = async (path) => {
    gets.push(path);
    if (mode === 'fail') return {ok: false, status: 503, json: async () => ({})};
    if (mode === 'hang') return new Promise(() => {});
    return {ok: true, status: 200, json: async () => ({state: 'idle', csrf: 'x'})};
  };
  const client = createClient({fetchImpl, now: clock.now, timers: clock.timers});
  const connections = [];
  client.start(() => {}, c => connections.push(c));
  await new Promise(setImmediate);
  await clock.advance(600);
  assert.deepEqual(gets, ['/live/status?full=1', '/live/status?full=1']);
  assert.equal(connections.at(-1).offline, true);
  assert.equal(connections.at(-1).view.detail, 'Verbindung zur Werkbank verloren');
  mode = 'ok';
  await clock.advance(600);
  assert.equal(connections.at(-1).offline, false);
  mode = 'hang';
  await clock.advance(1400);
  assert.equal(connections.at(-1).offline, false, '1,4 s ohne Antwort ist noch verbunden');
  await clock.advance(700);
  assert.equal(connections.at(-1).offline, true);
  assert.equal(connections.at(-1).view.headline, 'STALE');
  const post = await createClient({fetchImpl: async () => { throw new TypeError('network'); }, now: clock.now,
    timers: clock.timers}).post('/live/run/stop');
  assert.equal(post.ok, false);
  assert.match(post.error, /Verbindung prüfen/);
  client.stop();
});

test('live.css carries the spec tokens verbatim, 13 px base, radius ≤ 2 px, shadows only on popover/menu/modal', () => {
  const css = readFileSync(new URL('../src/dispread/workbench/static/live/live.css', import.meta.url), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  const tokens = {'--bg0': '#0d0c0b', '--bg1': '#161513', '--dock': '#1c1b19', '--title': '#24231f',
    '--ctl': '#2c2a26', '--ctl-h': '#363430', '--line': '#3a3833', '--line2': '#292724', '--stripe': '#201f1c',
    '--tx': '#ebe7e0', '--tx2': '#bab4aa', '--tx3': '#958f85', '--sel': '#3f6fb8', '--sel-hi': '#86aee8',
    '--sel-bg': '#212d40', '--sel-line': '#36507a', '--ok': '#55c46e', '--warn': '#e5a535', '--err': '#ee5b4d',
    '--stale': '#8f8a82', '--teal': '#30c6b7', '--mag': '#d65ccf',
    '--sans': '"Segoe UI","Noto Sans",system-ui,sans-serif', '--mono': '"Noto Sans Mono",ui-monospace,monospace'};
  const root = css.match(/:root\s*\{([^}]*)\}/)[1];
  for (const [name, value] of Object.entries(tokens)) {
    const found = root.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
    assert.ok(found, `${name} fehlt`);
    assert.equal(found[1].trim(), value, name);
  }
  assert.match(css, /body\s*\{[^}]*font:\s*13px\/[\d.]+ var\(--sans\)/);
  for (const [, radius] of css.matchAll(/border-radius\s*:\s*([^;}]+)/g)) {
    for (const part of radius.trim().split(/\s+/)) assert.ok(parseFloat(part) <= 2, `Radius ${radius}`);
  }
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/box-shadow/.test(body) || /box-shadow\s*:\s*none/.test(body)) continue;
    assert.ok(selector.split(',').every(part => /\.(popover|menu|modal)\b/.test(part)), `Schatten an ${selector.trim()}`);
  }
  for (const font of ['NotoSans-Regular.woff2', 'NotoSans-Medium.woff2', 'NotoSans-SemiBold.woff2',
    'NotoSans-Bold.woff2', 'NotoSansMono-Regular.woff2', 'NotoSansMono-Bold.woff2']) {
    assert.match(css, new RegExp(`url\\("\\.\\./vendor/fonts/${font}"\\)`));
    assert.ok(readFileSync(new URL(`../src/dispread/workbench/static/vendor/fonts/${font}`, import.meta.url))
      .subarray(0, 4).toString('latin1') === 'wOF2', font);
  }
});

test('new page loads only module scripts from /static/live (CSP: no inline script)', () => {
  const html = readFileSync(new URL('../src/dispread/workbench/static/live/index.html', import.meta.url), 'utf8');
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  assert.ok(scripts.length >= 1);
  for (const [, attrs, body] of scripts) {
    assert.match(attrs, /type="module"/);
    assert.match(attrs, /src="\/static\/live\/[\w/.-]+\.js"/);
    assert.equal(body.trim(), '');
  }
  assert.match(html, /<html lang="de">/);
  assert.match(html, /href="\/static\/live\/live\.css"/);
});

test('client: a throwing status renderer stays online and surfaces the error', async () => {
  const clock = fakeClock();
  const errors = [];
  const fetchImpl = async () => ({ok: true, status: 200, json: async () => ({state: 'idle', csrf: 'x'})});
  const client = createClient({fetchImpl, now: clock.now, timers: clock.timers, onError: e => errors.push(e)});
  const connections = [];
  client.start(() => { throw new TypeError('Renderfehler'); }, c => connections.push(c));
  await new Promise(setImmediate);
  await clock.advance(600);
  assert.ok(errors.length >= 2 && errors.every(e => e.message === 'Renderfehler'), String(errors));
  assert.equal(connections.at(-1).offline, false);
  assert.equal(connections.at(-1).httpStatus, 200);
  assert.equal(connections.at(-1).view.headline, 'Bereit zur Einrichtung');
  client.stop();
});

test('client: a status request without answer is abandoned after 3 s and polling continues', async () => {
  const clock = fakeClock();
  const gets = [];
  const signals = [];
  const fetchImpl = (path, options) => { gets.push(path); signals.push(options?.signal); return new Promise(() => {}); };
  const client = createClient({fetchImpl, now: clock.now, timers: clock.timers});
  const connections = [];
  client.start(() => {}, c => connections.push(c));
  await new Promise(setImmediate);
  await clock.advance(2900);
  assert.equal(gets.length, 1, 'vor dem Zeitlimit kein zweiter Abruf');
  await clock.advance(200);
  assert.ok(signals[0]?.aborted, 'der haengende Abruf wird abgebrochen');
  await clock.advance(500);
  assert.equal(gets.length, 2, 'nach dem Zeitlimit geht der Takt weiter');
  assert.equal(connections.at(-1).offline, true);
  client.stop();
});

test('effectState: test run suppresses only the server-rewritten records, not genuinely unreadable ones', () => {
  const status = scene('running_valid');
  status.test_run = {testlauf: true};
  status.run.latest = {...status.run.latest, status: 'unreadable', value: null,
    reject_reasons: ['testlauf_keine_freigabe']};
  assert.equal(effectState(status, {offline: false}).kind, null);
  status.run.latest.reject_reasons = ['leser:leerzelle_gestoert:14'];
  assert.equal(effectState(status, {offline: false}).kind, 'error');
});

// ---------------------------------------------------------------------------
// Einrichtungsansicht (Aufgabe 8)
// ---------------------------------------------------------------------------
const focusOf = (name) => scene(name).setup.focus;

test('focus chart: points in measurement order, best marked, line at 85 % of the maximum while running', () => {
  const model = focusChartModel(focusOf('setup_focus'));
  assert.deepEqual(model.points.map(p => [p.order, p.focus]), [[1, 48], [2, 56], [3, 40]]);
  assert.deepEqual(model.points.filter(p => p.best).map(p => p.focus), [48]);
  assert.equal(model.latest.focus, 40);
  assert.equal(model.line.source, 'maximum');
  assert.equal(Math.round(model.line.value), 536);
  assert.equal(model.verify, null);
  const svg = focusChartSVG(focusOf('setup_focus'));
  assert.equal((svg.match(/data-sample="/g) || []).length, 3);
  assert.match(svg, /data-sample="1"[^>]*data-best="true"/);
  assert.match(svg, /85 % = 536/);
  assert.doesNotMatch(svg, /data-part="verify"/);
  assert.doesNotMatch(svg, /%\s*Wahrscheinlich|Sicherheit/);
});

test('focus chart: the line follows verify.threshold and the cross-check is drawn at the best focus', () => {
  const focus = focusOf('setup_focus_done');
  const model = focusChartModel(focus);
  assert.equal(model.points.length, 9);
  assert.equal(model.line.source, 'verify');
  assert.equal(model.line.value, focus.verify.threshold);
  assert.deepEqual([model.verify.focus, Math.round(model.verify.score)], [48, 624]);
  const svg = focusChartSVG(focus);
  assert.equal((svg.match(/data-sample="/g) || []).length, 9);
  assert.match(svg, /data-part="threshold"[^>]*data-value="536"/);
  assert.match(svg, /data-part="verify"/);
  // Ein anderer Schwellwert vom Server gewinnt gegen 85 % des Maximums.
  const other = focusChartModel({...focus, verify: {score: 500, threshold: 512.4}});
  assert.equal(Math.round(other.line.value), 512);
  // "85 %" nur, wenn die Server-Schwelle nachweislich 85 % des Maximums ist.
  assert.equal(model.line.label, '85 % = 536');
  assert.equal(other.line.label, 'Schwelle 512');
  const otherSvg = focusChartSVG({...focus, verify: {score: 500, threshold: 512.4}});
  assert.match(otherSvg, /Schwelle 512/);
  assert.doesNotMatch(otherSvg, /85 % =/);
});

test('focus chart: failed verification without verify keeps the 85 % line and invents no score', () => {
  const focus = {...focusOf('setup_focus_done'), verify: null};
  const model = focusChartModel(focus);
  assert.equal(model.line.source, 'maximum');
  assert.equal(Math.round(model.line.value), 536);
  assert.equal(model.verify, null);
  assert.doesNotMatch(focusChartSVG(focus), /data-part="verify"/);
  assert.equal(focusChartModel({method: 'climb', samples: [], verify: null}).line, null);
  assert.match(focusChartSVG({method: 'climb', samples: [], verify: null}), /noch keine Probe/);
});

test('checks: live checks appear before the proposal, with the stability wait as a running row', () => {
  const status = scene('setup_standbilder');
  status.setup.checks_live.raster = {status: 'WARNUNG', reason: 'Raster am Rand knapp'};
  status.setup.checks_live.glanz = {status: 'NICHT_GEPRUEFT', reason: null};
  const rows = checkRows(status);
  assert.deepEqual(rows.map(row => [row.label, row.word, row.tone, row.hint]), [
    ['Kontrast', 'OK', 'ok', ''],
    ['Raster', 'WARNUNG', 'warn', 'Raster am Rand knapp'],
    ['Glanz', 'nicht geprüft', 'pend', ''],
    ['Stabilität', 'läuft', 'run', 'noch 6 s'],
  ]);
  assert.equal(warningCount(status), 1);
  assert.match(checksSummary(status).text, /Erst nach dem Vorschlag/);
});

test('checks: after the proposal the table shows checks with check_reasons and the overall verdict', () => {
  const status = scene('setup_ready_warnung');
  status.setup.check_reasons = {raster: 'Raster am Rand knapp'};
  const rows = checkRows(status);
  assert.equal(rows.length, 12);
  const raster = rows.find(row => row.key === 'raster');
  assert.deepEqual([raster.label, raster.word, raster.tone, raster.hint], ['Raster', 'WARNUNG', 'warn', 'Raster am Rand knapp']);
  assert.equal(rows.find(row => row.key === 'nachfuehrung').label, 'Nachführung');
  assert.equal(rows.find(row => row.key === 'aufloesung').label, 'Auflösung');
  assert.ok(!rows.some(row => row.word === 'läuft'));
  const summary = checksSummary(status);
  assert.equal(summary.overall, 'WARNUNG');
  assert.match(summary.counts, /11 OK · 1 Warnung/);
  assert.equal(warningCount(status), 1);
});

test('confirm: fields and texts as on the old page, readiness needs name, format and the warning tick', () => {
  const status = scene('setup_ready_warnung');
  const model = confirmModel(status);
  assert.equal(model.visible, true);
  assert.equal(model.needAck, true);
  assert.equal(model.tolerance, null);
  assert.equal(model.block, null);
  assert.equal(fieldsReady(model, {name: 'L. Hentschke', format: true, ack: false}), false);
  assert.equal(fieldsReady(model, {name: '  ', format: true, ack: true}), false);
  assert.equal(fieldsReady(model, {name: 'L. Hentschke', format: true, ack: true}), true);
  assert.deepEqual(confirmBody(status, {name: 'L. Hentschke', format: true, ack: true, tolerance: false}), {
    session_id: 'test-session', confirmed_by: 'L. Hentschke', format_checked: true, acknowledge_warning: true,
    use_tolerance: false, proposal_revision: 'b358259f721241f0b9e6af42d4fdb390'});
  status.run_block = 'Lauf gesperrt: Gegenlesen WARNUNG';
  status.setup.gegenlesen = {status: 'WARNUNG', metrics: {hinweis: 'Zelle 8 knapp', tolerance: {possible: true, factor: 1.5}}};
  const blocked = confirmModel(status);
  assert.equal(blocked.tolerance, 'Angepasste Toleranz ×1.5 verwenden – Lesung nur in dieser Aufstellung gegen den Referenzwert geprüft, nicht validiert');
  assert.equal(blocked.block, 'Achtung: Der strikte Lauf ist gesperrt. Angepasste Toleranz kann ausdrücklich gewählt werden; sonst ist nur ein Testlauf möglich.');
  assert.equal(blocked.hint, 'Hinweis: Zelle 8 knapp');
  status.setup.gegenlesen.metrics.tolerance = {possible: false};
  assert.equal(confirmModel(status).block, 'Achtung: Mit diesem Vorschlag ist der Lauf gesperrt (siehe unten). Bestätigen ist möglich, ein Lauf nur als Testlauf.');
  assert.equal(confirmModel(scene('setup_standbilder')).visible, false);
  const ok = scene('setup_ready_warnung');
  ok.setup.overall = 'OK';
  assert.equal(confirmModel(ok).needAck, false);
  assert.equal(fieldsReady(confirmModel(ok), {name: 'A', format: true, ack: false}), true);
  delete ok.setup.proposal_revision;
  assert.ok(!('proposal_revision' in confirmBody(ok, {name: 'A', format: true})));
});

test('region editing: hit test uses the region box, feedback names the reason at the click', () => {
  const regions = scene('setup_ready_warnung').setup.regions;
  assert.equal(regionAt(regions, [1485, 658], 1), 3);
  assert.equal(regionAt(regions, [1492, 665], 1), 3, 'Rand des 15-px-Bereichs');
  assert.equal(regionAt(regions, [1500, 658], 1), -1);
  assert.equal(regionAt(regions, [1497, 658], 0.5), 3, 'bei kleinem Zoom mindestens 6 Bildschirmpixel');
  const rejected = {requested_centre: [1090, 550], centre: [1090, 550], used_centre: [1090, 550], ok: false, reason: 'im_zeichenbereich'};
  assert.deepEqual(editFeedback({add: [[1090, 550]], remove: []}, {ok: true, data: {centre_results: [rejected]}}, {}),
    {ok: false, text: 'im Zeichenbereich – nicht geeignet'});
  assert.equal(editFeedback({add: [[10, 10]], remove: []}, {ok: true, data: {centre_results: [{...rejected, reason: 'zu_nah'}]}},
    {zu_nah: 'zu nah am Nachbarn'}).text, 'zu nah am Nachbarn – nicht geeignet');
  assert.deepEqual(editFeedback({add: [[10, 10]], remove: []}, {ok: true, data: {centre_results: [
    {requested_centre: [1, 1], centre: [1, 1], used_centre: [1, 1], ok: true, reason: null},
    {requested_centre: [10, 10], centre: [11, 10], used_centre: [11, 10], ok: true, reason: null}]}}, {}),
  {ok: true, text: 'Rahmenbereich 2 hinzugefügt – geeignet'});
  assert.deepEqual(editFeedback({add: [], remove: [3]}, {ok: true, data: {}}, {}), {ok: true, text: 'Rahmenbereich 4 entfernt'});
  assert.deepEqual(editFeedback({add: [[1, 1]], remove: []}, {ok: false, error: 'Vorschlag hat sich geaendert'}, {}),
    {ok: false, text: 'Vorschlag hat sich geaendert'});
  assert.equal(resultText({requested_centre: [30, 12], centre: [30, 12], used_centre: [30, 12], ok: true}, {}),
    '30,12 (verwendet: 30,12): geeignet');
  assert.equal(resultText({requested_centre: [5, 5], centre: [5, 5], used_centre: null, ok: false, reason: 'zu_wenig_struktur'}, {}),
    '5,5 (verwendet: kein Mittelpunkt): zu wenig zweidimensionale Struktur');
});

test('steps and exposure render squares with words, the stability wait as a bar, and the p80 band', () => {
  const html = stepsHTML(stepRows(scene('setup_standbilder')));
  assert.match(html, /data-step="standbilder" data-state="running"/);
  assert.match(html, /data-sub="stabilitaet"[^]*9\/15 s/);
  assert.match(html, /class="prog"[^>]*><i style="width:60%"/);
  assert.match(html, /aria-label="erledigt"/);
  const exposure = exposureHTML(scene('setup_standbilder').setup.exposure, {state: 'done'});
  assert.match(exposure, /p80 124/);
  assert.match(exposure, /115/);
  assert.match(exposure, /150/);
  assert.match(exposure, /Runde<\/dt><dd>1\/4/);
  assert.match(exposure, /4742 K/);
  assert.match(exposureHTML({target: 130, band: [115, 150], rounds: []}, {state: 'running'}), /Ziel p80 130/);
});

test('overall verdict: NICHT_GEPRUEFT or unknown is grey, never release green or undefined-t', () => {
  assert.deepEqual(overallView('OK'), {word: 'OK', square: 'ok', cls: 'ok-t'});
  assert.deepEqual(overallView('WARNUNG'), {word: 'WARNUNG', square: 'warn', cls: 'warn-t'});
  assert.deepEqual(overallView('NICHT_GEPRUEFT'), {word: 'nicht geprüft', square: 'stale', cls: 'mut'});
  assert.deepEqual(overallView('SPAETER'), {word: 'SPAETER', square: 'stale', cls: 'mut'});
  assert.equal(overallView(null), null);
  for (const overall of ['NICHT_GEPRUEFT', 'SPAETER']) {
    const status = scene('setup_ready_warnung');
    status.setup.overall = overall;
    const html = checksHTML(status);
    const verdict = html.slice(html.indexOf('class="verdict"'));
    assert.doesNotMatch(html, /undefined/);
    assert.doesNotMatch(verdict, /ok-t|sq ok/);
    assert.match(verdict, /sq stale/);
  }
});

test('region edit: a lost request shows the old live.js wording, server answers stay verbatim', async () => {
  assert.equal(REGION_NETWORK_ERROR, 'Bereichsänderung nicht bestätigt – Verbindung prüfen und erneut versuchen.');
  const lost = await createClient({fetchImpl: async () => { throw new TypeError('network'); }}).post('/live/setup/regions', {});
  assert.equal(lost.network, true);
  assert.deepEqual(editFeedback({add: [[1, 1]], remove: []}, lost, {}), {ok: false, text: REGION_NETWORK_ERROR});
  assert.deepEqual(editFeedback({add: [[1, 1]], remove: []}, {ok: false, error: 'CSRF rejected'}, {}),
    {ok: false, text: 'CSRF rejected'});
});
