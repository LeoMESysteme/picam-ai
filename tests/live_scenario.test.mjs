import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {assertStatusShape} from './live_status_shape.mjs';
import {CHAPTERS, createScenario} from '../src/dispread/workbench/static/live/practice/scenario.js';
import {createClient} from '../src/dispread/workbench/static/live/api.js';
import {filterEntries, glossaryEntries} from '../src/dispread/workbench/static/live/help/dock.js';
import {TOUR_KEY, TOUR_STOPS, practiceLock, tourSeen, rememberTour} from '../src/dispread/workbench/static/live/help/tour.js';

const glossary = JSON.parse(readFileSync(new URL('../src/dispread/workbench/static/live/help/glossar-de.json', import.meta.url), 'utf8'));

// Uhr des Szenarios in ms, von Hand vorgestellt.
function manualClock(start = 5000) {
  let t = start;
  const clock = () => t;
  clock.advance = (s) => { t += s * 1000; };
  return clock;
}

// Laeuft in kleinen Schritten bis zur Bedingung und prueft jeden Status.
function runUntil(scenario, clock, done, {maxS = 120, stepS = 0.25, seen = []} = {}) {
  for (let s = 0; s <= maxS; s += stepS) {
    const status = scenario.status();
    if (status !== null) {
      assertStatusShape(status);
      if (seen.at(-1) !== scenario.chapter) seen.push(scenario.chapter);
      if (done(status)) return status;
    }
    clock.advance(stepS);
  }
  throw new Error(`Bedingung nicht erreicht, Kapitel ${scenario.chapter}`);
}

const confirmBody = (status, over = {}) => ({session_id: status.session_id, confirmed_by: 'Übung', format_checked: true,
  acknowledge_warning: true, use_tolerance: false, proposal_revision: status.setup.proposal_revision, ...over});

test('scenario statuses pass assertStatusShape at every chapter', async () => {
  const clock = manualClock();
  const scenario = createScenario({clock});
  const seen = [];
  let waited = 0;
  runUntil(scenario, clock, () => (waited += 0.25) > 3, {seen});
  assert.equal(scenario.status().state, 'idle');
  assert.deepEqual(await scenario.act('/live/setup', {cell_text: null}), {ok: true, error: null, data: {ok: true}});
  // Einrichtung: Fokus, Kamera, Belichtung, Standbilder, Vorschlag (Mock CH 3–47 s).
  let status = runUntil(scenario, clock, (s) => s.state === 'setup_ready', {seen});
  assert.equal(status.setup.overall, 'WARNUNG');
  assert.equal(status.setup.regions.length, 12);
  // Rahmenbereich bearbeiten: im Zeichenbereich abgelehnt, ausserhalb uebernommen.
  const inside = await scenario.act('/live/setup/regions', {proposal_revision: status.setup.proposal_revision,
    add: [[1000, 550]], remove: []});
  assert.equal(inside.ok, true);
  assert.equal(inside.data.centre_results.at(-1).reason, 'im_zeichenbereich');
  status = scenario.status();
  assertStatusShape(status);
  const outside = await scenario.act('/live/setup/regions', {proposal_revision: status.setup.proposal_revision,
    add: [[700, 300]], remove: []});
  assert.equal(outside.data.centre_results.at(-1).ok, true);
  status = scenario.status();
  assertStatusShape(status);
  assert.equal(status.setup.regions.length, 13);
  assert.equal(status.setup.auswahl, 'manuell');
  const stale = await scenario.act('/live/setup/regions', {proposal_revision: 'alt', add: [], remove: [0]});
  assert.deepEqual(stale, {ok: false, error: 'Vorschlag hat sich geaendert', data: {error: 'Vorschlag hat sich geaendert'}});
  assert.equal((await scenario.act('/live/confirm', confirmBody(status))).ok, true);
  status = scenario.status();
  assertStatusShape(status);
  assert.equal(status.state, 'confirmed');
  assert.equal(status.profile.confirmed_by, 'Übung');
  assert.equal((await scenario.act('/live/run/start', {test_override: false, reference: true,
    norm_schedule: '1, 2', diagnostics: false})).ok, true);
  assert.match(scenario.status().run.started_at_utc, /T\d\d:\d\d:\d\d\.\d{3}\+00:00$/, 'Millisekunden bleiben erhalten');
  // Lauf bis "Anzeige bewegt" (Mock EP.bump = 35 s), dabei Stillstand und Verbindungsverlust.
  let offline = 0;
  for (let s = 0; s < 40; s += 0.25) {
    const next = scenario.status();
    if (next === null) offline++;
    else {
      assertStatusShape(next);
      if (seen.at(-1) !== scenario.chapter) seen.push(scenario.chapter);
      status = next;
    }
    clock.advance(0.25);
  }
  assert.ok(offline > 0, 'Verbindungsverlust (Mock 28–31 s) liefert keinen Status');
  assert.equal(status.state, 'running');
  assert.equal(status.run.tracking_hint.kind, 'anzeige_bewegt');
  assert.equal((await scenario.act('/live/run/mark', {text: 'Übungsmarke'})).ok, true);
  assert.equal(scenario.status().last_mark.text, 'Übungsmarke');
  assert.equal((await scenario.act('/live/run/stop', {})).ok, true);
  status = scenario.status();
  assertStatusShape(status);
  if (seen.at(-1) !== scenario.chapter) seen.push(scenario.chapter);
  assert.equal(status.state, 'stopped');
  assert.equal(status.run.summary.end_reason, 'bediener');
  assert.equal(status.reference_eval.state, 'done');
  assert.deepEqual(seen, CHAPTERS);
  assert.deepEqual(CHAPTERS, ['Bereit', 'Fokus', 'Kamera', 'Belichtung', 'Standbilder', 'Vorschlag',
    'Prüfen & Bestätigen', 'Lauf', 'Lauf beendet']);
});

test('scenario waits for confirm with name', async () => {
  const clock = manualClock();
  const scenario = createScenario({clock});
  // Ohne Klick bleibt das Szenario bereit.
  clock.advance(600);
  assert.equal(scenario.status().state, 'idle');
  assert.equal(scenario.chapter, 'Bereit');
  await scenario.act('/live/setup', {cell_text: null});
  const ready = runUntil(scenario, clock, (s) => s.state === 'setup_ready');
  clock.advance(600);
  assert.equal(scenario.status().state, 'setup_ready');
  const result = await scenario.act('/live/confirm', {confirmed_by: ''});
  assert.equal(result.ok, false);
  assert.equal(result.error, 'Name des Bestaetigenden fehlt');
  assert.equal(scenario.status().state, 'setup_ready');
  // Servertexte woertlich (live/service.py confirm).
  assert.equal((await scenario.act('/live/confirm', confirmBody(ready, {format_checked: false}))).error,
    'Einheit mV/V und Format gsv2as_v1 muessen geprueft sein');
  assert.equal((await scenario.act('/live/confirm', confirmBody(ready, {acknowledge_warning: false}))).error,
    'Einrichtung meldet WARNUNG - ausdruecklich zur Kenntnis nehmen');
  assert.equal((await scenario.act('/live/run/start', {})).error, 'Erst einrichten und bestaetigen');
  assert.equal((await scenario.act('/live/confirm', confirmBody(ready))).ok, true);
  // Bestaetigt: wartet auf Lauf starten.
  clock.advance(600);
  assert.equal(scenario.status().state, 'confirmed');
  assert.equal((await scenario.act('/live/run/start', {reference: true})).ok, true);
  assert.equal(scenario.status().state, 'running');
  assert.equal((await scenario.act('/live/run/start', {})).error, 'Lauf laeuft bereits');
  // Nach "Anzeige bewegt" laeuft der Lauf weiter, bis der Bediener stoppt.
  clock.advance(600);
  const late = scenario.status();
  assert.equal(late.state, 'running');
  assert.equal(late.run.latest.status, 'unreadable');
  assert.equal(late.run.tracking_hint.kind, 'anzeige_bewegt');
  assert.equal((await scenario.act('/live/run/mark', {text: ''})).error, 'Ereignismarke braucht 1 bis 200 Zeichen');
  await scenario.act('/live/run/stop', {});
  assert.equal((await scenario.act('/live/run/stop', {})).error, 'kein Lauf aktiv');
  // Neu einrichten aus dem Laufende beginnt wieder mit dem Fokus.
  assert.equal((await scenario.act('/live/setup', {cell_text: null})).ok, true);
  assert.equal(scenario.status().state, 'setup_running');
  assert.equal(scenario.chapter, 'Fokus');
});

test('scenario run follows the mock: values, transition, hand, stall, correction', async () => {
  const clock = manualClock();
  const scenario = createScenario({clock});
  await scenario.act('/live/setup', {cell_text: null});
  const ready = runUntil(scenario, clock, (s) => s.state === 'setup_ready');
  await scenario.act('/live/confirm', confirmBody(ready));
  await scenario.act('/live/run/start', {reference: true, norm_schedule: '1, 2'});
  const at = (r) => { clock.advance(r - scenario.runSeconds()); return scenario.status(); };
  let s = at(1);
  assert.equal(s.run.latest.status, 'valid');
  assert.equal(s.run.latest.raw_text, '+0.62427');
  assert.equal(s.reference.latest.value, 0.62427);
  assert.ok(s.run.latest_age_s <= 0.5);
  let frame = scenario.frame();
  assert.equal(frame.hud.w, 1920);
  assert.equal(frame.hud.rec.text, '+0.62427');
  assert.equal(frame.hud.rec.status, 'valid');
  assert.equal(frame.bitmapSource.lcd.text.slice(0, 13), '+0.62427 mV/V');
  s = at(9.1);
  assert.equal(s.run.latest.status, 'transition');
  assert.deepEqual(s.run.latest.reject_reasons, ['anzeige_wechselt']);
  assert.equal(s.run.latest.value, null);
  s = at(10);
  assert.equal(s.run.latest.raw_text, '+1.24855');
  assert.equal(s.reference.schedule_step.factor, 2);
  s = at(15);
  assert.equal(s.run.tracking_hint.kind, 'rahmen_verdeckt');
  assert.equal(s.run.latest.status, 'unreadable');
  frame = scenario.frame();
  assert.ok(frame.hud.track.regions.some((r) => !r.ok), 'Bereiche rechts ohne Treffer');
  assert.ok(frame.bitmapSource.hand > 0);
  s = at(18);
  frame = scenario.frame();
  assert.equal(frame.hud.track.correcting, true);
  s = at(23);
  assert.equal(s.camera.stalled, true);
  assert.equal(scenario.frame(), null, 'Stillstand: keine neuen Bilder');
  assert.ok(s.run.latest_age_s > 1.5);
  s = at(26);
  assert.equal(s.camera.stalled, false);
  assert.ok(s.run.counts.valid > 0 && s.run.counts.transition > 0 && s.run.counts.unreadable > 0 && s.run.counts.stale > 0);
  assert.ok(s.run.recent.length > 0);
  assert.ok(s.run.recent.every(([t, code]) => t <= s.run.recent_now_ms && 'vtus'.includes(code)));
  // Wertspur: nur freigegebene Werte tragen eine Zahl.
  assert.ok(s.run.recent.every(([, code, value]) => (code === 'v') === (value !== null)));
  assert.match(s.session_id, /^uebung-/);
});

test('scenario carries focus ROI, CPU and output off; cancel answers like the server', async () => {
  const clock = manualClock();
  const scenario = createScenario({clock});
  let status = scenario.status();
  assert.deepEqual(status.output, {transport: 'off', state: 'off'});
  assert.equal(typeof status.system.cpu_percent, 'number');
  assert.equal(status.system.cpu_window_s > 0, true);
  // Abbruch nur waehrend der Einrichtung (live/service.py cancel_setup, woertlich).
  assert.deepEqual(await scenario.act('/live/setup/cancel', {}),
    {ok: false, error: 'Keine Einrichtung laeuft', data: {error: 'Keine Einrichtung laeuft'}});
  await scenario.act('/live/setup', {cell_text: null});
  clock.advance(2);
  status = scenario.status();
  assertStatusShape(status);
  // Messbereich wie am Geraet: mittleres Drittel des Kamerabilds.
  assert.deepEqual(status.setup.focus.roi, [640, 360, 640, 360]);
  assert.equal((await scenario.act('/live/setup/cancel', {})).ok, true);
  status = scenario.status();
  assertStatusShape(status);
  assert.equal(status.state, 'setup_failed');
  assert.equal(status.error, 'Einrichtung abgebrochen');
  assert.equal(status.setup.progress.steps.find((s) => s.key === 'fokus').state, 'failed');
  // Stehen geblieben: die Zeit laeuft nach dem Abbruch nicht weiter.
  const elapsed = status.setup.elapsed_s;
  clock.advance(30);
  status = scenario.status();
  assert.equal(status.state, 'setup_failed');
  assert.equal(status.setup.elapsed_s, elapsed);
  assert.equal((await scenario.act('/live/setup/cancel', {})).error, 'Keine Einrichtung laeuft');
  // Neu starten geht wie nach jedem Abbruch.
  assert.equal((await scenario.act('/live/setup', {cell_text: null})).ok, true);
  status = scenario.status();
  assert.equal(status.state, 'setup_running');
  assert.equal(status.error, null);
});

test('scenario status never answers from the server and cannot pose as a real session', () => {
  const scenario = createScenario({clock: manualClock()});
  const status = scenario.status();
  assert.match(status.session_id, /^uebung-/);
  assert.equal(status.simulate, true);
  assert.equal(status.camera.source.device, 'Übung');
  assert.equal(scenario.frame().hud.rec, null);
});

test('client in scenario mode never POSTs and reads status from the scenario', async () => {
  const calls = [];
  const fetchImpl = async (path, init = {}) => {
    calls.push([init.method || 'GET', path]);
    return {ok: true, status: 200, json: async () => ({state: 'idle', csrf: 'tok', tracking_reasons: {low_score: 'Bild passt nicht'}}),
      text: async () => '{"ok":true}'};
  };
  const timers = {setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout, setInterval: (fn, ms) => setInterval(fn, ms), clearInterval};
  const client = createClient({fetchImpl, timers});
  const statuses = [];
  const background = [];
  client.start((s) => statuses.push(s), () => {}, {onServerStatus: (s) => background.push(s)});
  await new Promise((r) => setTimeout(r, 30));
  const scenario = createScenario({clock: manualClock()});
  client.useSource(scenario);
  await new Promise((r) => setTimeout(r, 30));
  const result = await client.post('/live/setup', {cell_text: null});
  assert.equal(result.ok, true);
  await new Promise((r) => setTimeout(r, 30));
  assert.equal(statuses.at(-1).state, 'setup_running');
  assert.match(statuses.at(-1).session_id, /^uebung-/);
  // Deutsche Gruende des echten Servers bleiben am Uebungsstatus.
  assert.equal(statuses.at(-1).tracking_reasons.low_score, 'Bild passt nicht');
  assert.deepEqual(calls.filter(([method]) => method === 'POST'), []);
  // Abgelehnt wie vom Server: {ok:false, error, data} mit dem Text des Szenarios.
  const failed = await client.post('/live/confirm', {confirmed_by: ''});
  assert.deepEqual(failed, {ok: false, error: 'Kein Vorschlag zum Bestaetigen', data: {error: 'Kein Vorschlag zum Bestaetigen'}});
  assert.equal(client.source(), scenario);
  client.useSource('server');
  await client.post('/live/setup', {cell_text: null});
  assert.deepEqual(calls.filter(([method]) => method === 'POST'), [['POST', '/live/setup']]);
  client.stop();
  assert.ok(background.length >= 0);
});

test('practice lock and tour memory', () => {
  assert.equal(practiceLock({state: 'idle'}), null);
  assert.equal(practiceLock({state: 'stopped'}), null);
  assert.equal(practiceLock({state: 'setup_failed'}), null);
  assert.equal(practiceLock({state: 'running'}), 'Gesperrt, solange ein Lauf läuft');
  assert.equal(practiceLock({state: 'setup_running'}), 'Gesperrt, solange die Einrichtung läuft');
  assert.match(practiceLock({state: 'confirmed'}), /^Gesperrt/);
  assert.match(practiceLock(null), /^Gesperrt/);
  assert.equal(TOUR_STOPS.length, 8);
  assert.deepEqual(TOUR_STOPS.map((s) => s.title), ['Titelleiste und Aktionen', 'Ablauf-Dock', 'Viewer mit Werkzeugleiste',
    'HUD-Legende', 'Inspektor', 'Ergebnisanzeige', 'Zeitleiste', 'Statusleiste']);
  for (const stop of TOUR_STOPS) {
    const sentences = stop.text.split(/(?<=[.!?])\s+/).filter(Boolean);
    assert.ok(sentences.length >= 1 && sentences.length <= 3, `${stop.title}: 1–3 Sätze`);
  }
  const store = new Map();
  const storage = {getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v)};
  assert.equal(tourSeen(storage), false);
  rememberTour(storage, 'übersprungen');
  assert.equal(tourSeen(storage), true);
  assert.equal(store.get(TOUR_KEY), 'übersprungen');
  const broken = {getItem: () => { throw new Error('gesperrt'); }, setItem: () => { throw new Error('gesperrt'); }};
  assert.equal(tourSeen(broken), false);
  assert.doesNotThrow(() => rememberTour(broken, 'fertig'));
  assert.equal(tourSeen(null), false);
});

test('glossary: short texts, all checks and status words, reasons from status, search', () => {
  const entries = glossaryEntries(glossary, null);
  const terms = entries.map((e) => e.term);
  for (const word of ['Freigegeben', 'Wechselt', 'Unlesbar', 'Veraltet']) assert.ok(terms.includes(word), word);
  const checks = entries.filter((e) => e.section === 'Prüfungen');
  assert.deepEqual(checks.map((e) => e.code).sort(), ['aufloesung', 'belichtung', 'displayfehler', 'fokus', 'gegenlesen', 'glanz',
    'kanten', 'kontrast', 'nachfuehrung', 'rahmen', 'raster', 'rasterversatz', 'stabilitaet']);
  for (const entry of entries) {
    assert.ok(entry.text.length <= 260, `${entry.term}: kurz halten`);
    assert.ok(!/wahrscheinlich|sicherheit\s*%/i.test(entry.text), `${entry.term}: Konfidenz ist keine Wahrscheinlichkeit`);
    assert.match(entry.href, /^https:\/\/picam-docs\.pages\.dev\/docs\/anleitung\/glossar\//);
  }
  // Displayfehler ergibt WARNUNG (setup_checks.py), die vor dem Bestaetigen zu quittieren ist.
  const defect = checks.find((e) => e.code === 'displayfehler');
  assert.match(defect.text, /WARNUNG/);
  assert.match(defect.text, /quittier/);
  assert.doesNotMatch(defect.text, /kein Fehler/);
  // Gruende kommen aus dem Status, nicht aus einer Kopie der Python-Tabellen.
  assert.ok(!entries.some((e) => e.code === 'rahmen_unstimmig'));
  const status = {tracking_reasons: {rahmen_unstimmig: 'rahmenbewegungen passen nicht zusammen'},
    cause_texts: {zelle_unbekannt: 'Zeichen nicht sicher erkannt'},
    run: {rejection_causes: {causes: [{reason: 'anzeige_wechselt', count: 3, fraction: 0.3, explanation: 'Wert wechselt'}]}}};
  const merged = glossaryEntries(glossary, status);
  const tracking = merged.find((e) => e.code === 'rahmen_unstimmig');
  assert.equal(tracking.section, 'Nachführungsgründe');
  assert.equal(tracking.text, 'rahmenbewegungen passen nicht zusammen');
  assert.equal(merged.find((e) => e.code === 'zelle_unbekannt').section, 'Lesegründe');
  assert.equal(merged.find((e) => e.code === 'anzeige_wechselt').text, 'Wert wechselt');
  const found = filterEntries(merged, 'gegenl');
  assert.ok(found.length >= 1);
  assert.ok(found.every((e) => `${e.term} ${e.code} ${e.text}`.toLowerCase().includes('gegenl')));
  assert.ok(filterEntries(merged, 'GEGENLESEN').some((e) => e.term === 'Gegenlesen'));
  assert.ok(filterEntries(merged, 'nachfuhrung').some((e) => e.code === 'nachfuehrung'), 'Umlaute egal');
  assert.equal(filterEntries(merged, '').length, merged.length);
});

// Fix-Runde 1: eigene Uhr fuer Timer und Zeit (wie fakeClock in live_client.test.mjs).
function fakeTimers() {
  let t = 1000;
  const list = [];
  const add = (fn, ms, repeat) => { const id = list.length + 1; list.push({id, fn, at: t + ms, ms, repeat}); return id; };
  const clear = (id) => { const x = list.find((y) => y.id === id); if (x) x.fn = null; };
  return {
    now: () => t,
    timers: {setTimeout: (fn, ms) => add(fn, ms, false), clearTimeout: clear, setInterval: (fn, ms) => add(fn, ms, true), clearInterval: clear},
    async advance(ms) {
      const end = t + ms;
      for (;;) {
        const due = list.filter((x) => x.fn && x.at <= end).sort((a, b) => a.at - b.at)[0];
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

test('practice runs on its own timer: a hanging real server neither stalls nor offline-marks it', async () => {
  const clock = fakeTimers();
  let hang = false;
  const fetchImpl = (path, init = {}) => {
    if (init.method === 'POST') throw new Error('kein POST im Uebungslauf');
    if (hang) return new Promise(() => {}); // haengender Abruf, endet nie
    return Promise.resolve({ok: true, status: 200, json: async () => ({state: 'idle', csrf: 't'})});
  };
  const client = createClient({fetchImpl, now: clock.now, timers: clock.timers});
  const statuses = [];
  const connections = [];
  client.start((s) => statuses.push(s), (c) => connections.push(c));
  await clock.advance(600);
  const scenario = createScenario({clock: clock.now});
  client.useSource(scenario);
  await client.post('/live/setup', {cell_text: null});
  hang = true;
  const before = statuses.length;
  await clock.advance(10_000);
  // Alle 500 ms ein Szenario-Status, obwohl jeder echte Abruf bis zum 3-s-Abbruch haengt.
  assert.ok(statuses.length - before >= 18, `nur ${statuses.length - before} Status in 10 s`);
  assert.equal(statuses.at(-1).state, 'setup_running');
  assert.ok(statuses.at(-1).setup.elapsed_s > 9);
  assert.equal(connections.at(-1).offline, false);
  assert.ok(connections.slice(-15).every((c) => !c.offline), 'kein Verbindungsverlust im Uebungslauf');
  // Zurueck zum Server: dessen haengender Abruf gilt wieder.
  client.useSource('server');
  await clock.advance(3000);
  assert.equal(connections.at(-1).offline, true);
  client.stop();
});
