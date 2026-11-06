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
import {referenceItem, storageItem} from '../src/dispread/workbench/static/live/shell.js';
import {diagnosticsText, trackingModeText} from '../src/dispread/workbench/static/live/run/inspector.js';

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

test('setup progress displays the separate message alongside the phase', () => {
  const view = statusView({state: 'setup_running',
    setup: {step: 'standbilder', elapsed_s: 12.34, message: 'Startsuche Versuch 2'}});
  assert.match(view.headline, /standbilder/);
  assert.equal(view.detail, 'Startsuche Versuch 2');
  assert.equal(statusView({state: 'setup_failed', error: 'original failure',
    setup: {message: 'Startsuche Versuch 2'}}).detail, 'original failure');
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

test('tolerance marks valid detail but STALE still wins', () => {
  const status = {...running, reader_tolerance: {factor: 1.44}};
  assert.equal(statusView(status).headline, '+1.2345 mV/V');
  assert.match(statusView(status).detail, /^erweiterte Toleranz ×1.44 – nicht validiert/);
  assert.equal(statusView({...status, run: {...status.run, latest_age_s: .9}}).headline, 'STALE');
  assert.doesNotMatch(statusView({...status, run: {...status.run, latest_age_s: .9}}).detail, /erweiterte Toleranz/);
});

test('restoration is shown until service finishes stopping', () => {
  const status = {...running, reference: {enabled: true, restoring: true}};
  assert.equal(statusView(status).headline, 'Werte werden zurückgestellt …');
});

test('tracking loss translates the specific reason supplied by fields.py', () => {
  const view = statusView({state: 'running', tracking_reasons: {lcd_rand_fehlt: 'LCD-Rand nicht ausreichend bestaetigt'},
    run: {latest: latest({status: 'unreadable', reject_reasons: ['tracking_lost:lcd_rand_fehlt']}), latest_age_s: 0.2}});
  assert.match(view.detail, /LCD-Rand nicht ausreichend bestaetigt/);
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

test('live.css carries the spec tokens verbatim, 13 px base, radius ≤ 2 px, shadows only on pop-ups', () => {
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
    // Das Innenleuchten des Zustandseffekts (nur inset) ist kein Schatten.
    const shadows = /box-shadow\s*:\s*([^;}]+)/.exec(body)[1].split(/,(?![^(]*\))/);
    if (/\.vglow\b/.test(selector) && shadows.every(part => /^\s*inset\b/.test(part))) continue;
    // Die Abdeckung des Rundgangs (nur Ausdehnung, ohne Unschaerfe) ist kein Schatten.
    if (/\.tour-hl\b/.test(selector) && shadows.every(part => /^\s*0 0 0 \S+/.test(part))) continue;
    // Pop-ups: Popover, Menue, Dialog, Hinweis (toast), das Stillstandsfeld (Mock 8c)
    // und die Pop-ups der Einarbeitung (Rundgang, Angebot, Auftrag im Uebungslauf).
    assert.ok(selector.split(',').every(part => /\.(popover|menu|modal|toast|stalep|tour-pop|tour-offer|coach)\b/.test(part)), `Schatten an ${selector.trim()}`);
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

test('region edit: a lost request shows the wording of the old page, server answers stay verbatim', async () => {
  assert.equal(REGION_NETWORK_ERROR, 'Bereichsänderung nicht bestätigt – Verbindung prüfen und erneut versuchen.');
  const lost = await createClient({fetchImpl: async () => { throw new TypeError('network'); }}).post('/live/setup/regions', {});
  assert.equal(lost.network, true);
  assert.deepEqual(editFeedback({add: [[1, 1]], remove: []}, lost, {}), {ok: false, text: REGION_NETWORK_ERROR});
  assert.deepEqual(editFeedback({add: [[1, 1]], remove: []}, {ok: false, error: 'CSRF rejected'}, {}),
    {ok: false, text: 'CSRF rejected'});
});

test('transition detail does not wrap the server explanation twice (rejection_causes as in the fixture)', () => {
  const status = scene('running_transition');
  status.run.rejection_causes = {window_s: 10.0, frames: 10, limited: false,
    causes: [{reason: 'anzeige_wechselt', count: 3, fraction: 0.3, cell: null, explanation: 'Wert wechselt'}]};
  const view = statusView(status);
  assert.equal(view.headline, 'TRANSITION');
  assert.equal(view.detail, 'Wert wechselt (anzeige_wechselt)');
  // Ohne Erklaerung bleibt der Text von statusView woertlich.
  status.run.rejection_causes.causes = [];
  assert.equal(statusView(status).detail, 'Wert wechselt (anzeige_wechselt)');
});

// ---------------------------------------------------------------------------
// Ehemals DOM-Tests der alten Seite (Aufgabe 12): dieselben Inhalte an den neuen Modulen
// ---------------------------------------------------------------------------
for (const [reason, explanation] of [
  ['zweitbild_peak_zu_niedrig', 'Rahmenbereich im Zweitbild nicht deutlich genug wiedergefunden'],
  ['zweitbild_mehrdeutig', 'Rahmenbereich im Zweitbild nicht eindeutig wiedergefunden'],
  ['zweitbild_suchrand', 'Rahmenbereich im Zweitbild am Rand des Suchbereichs'],
  ['zweitbild_am_bildrand', 'Rahmenbereich im Zweitbild zu nah am Bildrand'],
  ['zweitbild_lage_abweichend', 'Rahmenbereich im Zweitbild an anderer Position wiedergefunden'],
]) {
  test(`region results explain rejected centre ${reason} in German without a server table`, () => {
    assert.equal(resultText({centre: [100, 80], ok: false, reason}), `100,80 (verwendet: 100,80): ${explanation}`);
  });
}

test('region results prefer the German reasons supplied by the server and show requested and used centres', () => {
  const supplied = {zweitbild_mehrdeutig: 'Rahmenbereich im Zweitbild mehrfach wiedergefunden'};
  assert.match(resultText({centre: [100, 80], ok: false, reason: 'zweitbild_mehrdeutig'}, supplied),
    /mehrfach wiedergefunden/);
  assert.match(resultText({requested_centre: [290, 247], centre: [292, 247], used_centre: [292, 247], ok: true}),
    /290,247.*verwendet: 292,247.*geeignet/);
  assert.match(resultText({requested_centre: [400, 140], centre: [400, 142], used_centre: [400, 142], ok: false,
    reason: 'im_zeichenbereich'}), /400,140.*verwendet: 400,142.*Zeichenbereich/);
});

test('storage shows enough space, a warning, a shortage or the unknown-space message without guessing', () => {
  const ok = storageItem({free_bytes: 6_000_000_000, level: 'ok'});
  assert.equal(ok.cls, '');
  assert.match(ok.html, /6,00 GB/);
  const warn = storageItem({free_bytes: 4_200_000_000, level: 'warn'});
  assert.equal(warn.cls, 'warn');
  assert.match(warn.title, /Warnung: unter 5 GB frei\. SD-Speicher: 4,20 GB frei/);
  const low = storageItem({free_bytes: 1_500_000_000, level: 'error'});
  assert.equal(low.cls, 'err');
  assert.match(low.title, /Speicher knapp: SD-Speicher: 1,50 GB frei/);
  const unknown = storageItem({free_bytes: null, level: 'error', message: 'Speicherplatz nicht pruefbar'});
  assert.equal(unknown.cls, 'err');
  assert.match(unknown.html, /nicht pruefbar/);
  assert.doesNotMatch(unknown.html, /GB/);
  assert.match(storageItem(null).title, /Speicherplatz nicht verfuegbar/);
});

test('tracking mode texts as on the old page; before a run only known modes are named', () => {
  assert.equal(trackingModeText('rahmenbereiche'), 'Nachführung: Rahmenbereiche');
  assert.equal(trackingModeText('ecc_alt'), 'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen');
  assert.equal(trackingModeText('frame_local'), 'frame_local');
  assert.equal(trackingModeText('frame_local', {known: true}), '');
  assert.equal(trackingModeText(undefined, {known: true}), '');
});

test('diagnostics text as on the old page: counts, first error, copy in progress and saved, leftovers', () => {
  const diag = {enabled: true, saved: 4, bytes: 12_500_000, dropped_queue: 2, dropped_limit: 1,
    dropped_memory: 2, dropped_mark_rate: 3, write_errors: 1, first_error: 'Platte voll',
    staging: '/dev/shm/dispread-diagnose-x', copied: false};
  const copying = diagnosticsText({diagnostics: diag, diagnose_kopie: true,
    diagnostic_leftovers: [{path: '/test/dispread-diagnose-old', bytes: 2_500_000}, {path: '/test/b', bytes: null}]});
  assert.equal(copying, 'Diagnose: 4 Bilder, 12.5 MB; Queue verworfen: 2, Limit verworfen: 1, RAM verworfen: 2, ' +
    'Markenbilder verworfen: 3, Schreibfehler: 1 · Diagnose wird kopiert … · Platte voll · RAM-Ablage: ' +
    '/dev/shm/dispread-diagnose-x · Verbliebene RAM-Ablage: /test/dispread-diagnose-old (2.5 MB)' +
    ' · Verbliebene RAM-Ablage: /test/b (Größe unbekannt)');
  const copied = diagnosticsText({diagnostics: {...diag, first_error: null, write_errors: 0, copied: true},
    diagnose_kopie: false});
  assert.match(copied, /Schreibfehler: 0 · Kopie gesichert$/);
  assert.doesNotMatch(copied, /wird kopiert|Platte voll|RAM-Ablage/);
  assert.match(diagnosticsText({diagnostics: {...diag, first_error: 'x', staging: null}}), /· x · RAM-Ablage: —/);
  // Ältere Status ohne die neuen Zähler: 0 statt undefined.
  assert.match(diagnosticsText({diagnostics: {enabled: true, saved: 0, bytes: 0, dropped_queue: 0,
    dropped_limit: 0, write_errors: 0}}), /RAM verworfen: 0, Markenbilder verworfen: 0/);
  assert.equal(diagnosticsText({diagnostics: {enabled: false, reason: 'vom Bediener deaktiviert'}}),
    'Diagnose aus: vom Bediener deaktiviert');
  assert.equal(diagnosticsText({}), 'Diagnose aus: nicht gestartet');
});

test('reference count in the status bar: an unknown count reads "–", never 0', () => {
  for (const lines of [undefined, null, Number.NaN]) {
    const item = referenceItem({enabled: true, lines});
    assert.match(item.html, /Referenz <b>–<\/b> Telegramme/);
    assert.equal(item.title, 'Referenz: – Telegramme');
    assert.doesNotMatch(item.html, /<b>0<\/b>/);
  }
  assert.match(referenceItem({enabled: true, lines: 0}).html, /<b>0<\/b>/);
  assert.match(referenceItem({enabled: true, lines: 12345}).html, /<b>12\u202f345<\/b>/);
  assert.equal(referenceItem({enabled: false, reason: 'kein Referenzlauf'}).title, 'ohne Referenz: kein Referenzlauf');
});
