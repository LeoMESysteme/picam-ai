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
  assert.equal(statusView(status).headline, 'TESTLAUF · +1.2345 mV/V');
  assert.doesNotMatch(statusView(status).detail, /Leser-Vermutung/);
  status.run.latest_age_s = 0.9;
  assert.equal(statusView(status).headline, 'TESTLAUF · STALE');
  assert.equal(statusView(status).cls, 'stale');
  status.run.latest = latest({status: 'unreadable', raw_text: null, reject_reasons: ['zelle_unbekannt']});
  assert.equal(statusView(status).cls, 'stale');
  assert.doesNotMatch(statusView(status).detail, /Leser-Vermutung/);
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
    page.status = {state: 'setup_ready', session_id: 'first', setup: {gegenlesen: {
      metrics: {hinweis: 'Schatten entfernen.', tolerance: {possible: true, factor: 1.44}}}}};
    await poll();
    assert.equal(element('proposal-hint').textContent, 'Hinweis: Schatten entfernen.');
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
