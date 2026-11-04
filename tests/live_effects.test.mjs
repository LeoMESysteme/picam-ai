// Zustandseffekte und Laufhinweise (Aufgabe 10): Effektebene ohne DOM
// (Zeichenkontext-Attrappe), Hinweis- und Dialoglogik mit eingespeisten
// Hinweisen, Dialog und Speicher. Die sichtbare Wirkung prueft Playwright.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createEffects, mountEffects, TEXT_MS} from '../src/dispread/workbench/static/live/viewer/effects.js';
import {createAlerts, LOST_TITLE, STALL_TITLE, watchAlerts} from '../src/dispread/workbench/static/live/run/alerts.js';
import {effectState} from '../src/dispread/workbench/static/live/model.js';

const scene = (name) => JSON.parse(readFileSync(new URL(`./fixtures/live/scene-${name}.json`, import.meta.url), 'utf8'));
// Geometrie wie im Mock: Rahmenbereiche 5-8 liegen rechts der Anzeige.
const QUAD = [[608, 383], [1027, 383], [1033, 435], [610, 443]];
const REGIONS = [[528, 292], [800, 290], [520, 420], [545, 560], [1082, 292], [1112, 385], [1120, 470], [1090, 535]];
const hudWith = ({failed = [], correcting = false, quad = QUAD} = {}) => ({seq: 1, w: 1920, h: 1080, track: {
  quad, score: 0.5, shift_px: 0.4, rotation_deg: 0, reason: null, correcting,
  regions: REGIONS.map((c, i) => ({c, s: 15, peak: failed.includes(i) ? 0.2 : 0.92, ok: !failed.includes(i)}))}});

// Zeichenkontext-Attrappe: merkt sich Farben und Zeichenaufrufe.
function fakeCanvas(width = 820, height = 680) {
  const log = {styles: new Set(), fills: 0, strokes: 0, images: 0};
  const ctx = new Proxy({}, {
    get(target, key) {
      if (key in target) return target[key];
      if (key === 'fillRect') return () => { log.fills++; };
      if (key === 'stroke') return () => { log.strokes++; };
      if (key === 'drawImage') return () => { log.images++; };
      return () => {};
    },
    set(target, key, value) {
      target[key] = value;
      if (key === 'fillStyle' || key === 'strokeStyle') log.styles.add(String(value).toLowerCase());
      return true;
    },
  });
  return {clientWidth: width, clientHeight: height, width: 0, height: 0, log, getContext: () => ctx};
}

function geometry(hud = hudWith()) {
  const s = 0.75, ox = -50, oy = 20;
  return {quad: hud.track.quad, regions: hud.track.regions.map((r) => r.c), live: true,
    imageToScreen: ([x, y]) => [ox + x * s, oy + y * s], scale: s, width: 820, height: 680, dpr: 1};
}

// Deterministischer Zufall (mulberry32), damit Partikelzahlen vergleichbar sind.
function seeded(a = 1) {
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function run(fx, state, geo, {seconds = 3, dtMs = 1000 / 60} = {}) {
  for (let t = 0; t < seconds * 1000; t += dtMs) {
    fx.set(state, geo);
    fx.frame(dtMs);
  }
}

const TEAL = '#30c6b7';
const isRed = (style) => /255,\s*98,\s*80|#ee5b4d|#ff6250/.test(style);

test('effects priority follows spec', () => {
  // Alle Ausloeser gleichzeitig: Verbindung verloren, Stillstand, Rahmen verdeckt, Korrektur.
  const all = scene('running_rahmen_verdeckt');
  all.camera.stalled = true;
  const hud = hudWith({failed: [4, 5, 6, 7], correcting: true});
  const order = [
    [{offline: true, frameAgeS: 9, hud}, 'offline'],
    [{offline: false, frameAgeS: 9, hud}, 'stalled'],
  ];
  for (const [conn, kind] of order) {
    const canvas = fakeCanvas();
    const fx = createEffects(canvas, {random: seeded()});
    run(fx, effectState(all, conn), geometry(hud), {seconds: 1});
    assert.equal(fx.stats().kind, kind);
    // Verbindung und Stillstand zeichnen keine Wolke und keine Korrektur.
    assert.equal(fx.stats().particles, 0, kind);
    assert.ok(![...canvas.log.styles].some(isRed), `${kind}: kein Rot`);
    assert.ok(!canvas.log.styles.has(TEAL), `${kind}: kein Teal`);
  }
  // Ohne Stillstand: Unlesbar schlaegt Korrektur. Nur rote Partikel, kein Teal.
  const lost = scene('running_rahmen_verdeckt');
  const canvas = fakeCanvas();
  const fx = createEffects(canvas, {random: seeded()});
  run(fx, effectState(lost, {offline: false, frameAgeS: 0.1, hud}), geometry(hud), {seconds: 1});
  assert.equal(fx.stats().kind, 'error');
  assert.ok(fx.stats().particles > 50, String(fx.stats().particles));
  assert.deepEqual(fx.stats().corners, [1, 2]);
  assert.ok(!canvas.log.styles.has(TEAL), 'Korrektur wird nicht zusaetzlich gezeichnet');
  // Wechselt der Zustand auf Korrektur, laeuft nur noch sie: die Wolke ist weg.
  const valid = scene('running_valid');
  run(fx, effectState(valid, {offline: false, frameAgeS: 0.1, hud: hudWith({correcting: true})}),
    geometry(hudWith({correcting: true})), {seconds: 0.2});
  assert.equal(fx.stats().kind, 'correcting');
  assert.equal(fx.stats().particles, 0);
  assert.ok(canvas.log.styles.has(TEAL));
  // Korrektur schlaegt Wechsel; die Korrektur klingt nach ihrer Dauer ab.
  const transition = scene('running_transition');
  assert.equal(effectState(transition, {offline: false, hud: hudWith({correcting: true})}).kind, 'correcting');
  // Die Korrektur gilt fuer ein Bild, ihr Effekt laeuft 1,6 s aus und schlaegt
  // einen Wechsel, der in dieser Zeit beginnt.
  run(fx, effectState(transition, {offline: false, hud: hudWith()}), geometry(), {seconds: 0.3});
  assert.equal(fx.stats().kind, 'correcting');
  run(fx, effectState(valid, {offline: false, hud: hudWith()}), geometry(), {seconds: 2.5});
  assert.equal(fx.stats().kind, null);
  run(fx, effectState(transition, {offline: false, hud: hudWith()}), geometry(), {seconds: 0.3});
  assert.equal(fx.stats().kind, 'transition');
  assert.equal(fx.stats().particles, 0);
});

test('effects reducedMotion draws no particles', () => {
  const canvas = fakeCanvas();
  const fx = createEffects(canvas, {reducedMotion: true, random: seeded()});
  const hud = hudWith({failed: [4, 5, 6, 7]});
  run(fx, effectState(scene('running_rahmen_verdeckt'), {offline: false, hud}), geometry(hud), {seconds: 2});
  assert.equal(fx.stats().kind, 'error');
  assert.equal(fx.stats().particles, 0);
  // Statt der Wolke: statische Punkte und markierte Ecken.
  assert.ok(canvas.log.fills > 0);
  assert.ok(canvas.log.strokes > 0);
  // Korrektur: Geisterbild ohne Teilchen.
  const corr = createEffects(fakeCanvas(), {reducedMotion: true, random: seeded()});
  run(corr, effectState(scene('running_valid'), {offline: false, hud: hudWith({correcting: true})}),
    geometry(hudWith({correcting: true})), {seconds: 0.5});
  assert.equal(corr.stats().kind, 'correcting');
  assert.equal(corr.stats().particles, 0);
  assert.equal(corr.stats().streaks, 0);
});

test('effects halves particles under 20 fps', () => {
  const hud = hudWith({failed: [4, 5, 6, 7]});
  const state = effectState(scene('running_rahmen_verdeckt'), {offline: false, hud});
  const fast = createEffects(fakeCanvas(), {random: seeded(3)});
  run(fast, state, geometry(hud), {seconds: 4, dtMs: 1000 / 60});
  const slow = createEffects(fakeCanvas(), {random: seeded(3)});
  run(slow, state, geometry(hud), {seconds: 4, dtMs: 1000 / 12});
  const [a, b] = [fast.stats().particles, slow.stats().particles];
  assert.ok(a > 100, `60 fps: ${a}`);
  assert.ok(b > a * 0.35 && b < a * 0.65, `12 fps: ${b} statt etwa ${a / 2}`);
  assert.ok(slow.stats().fps < 20 && fast.stats().fps > 50);
  // Die Geometrie folgt Zoom und Verschieben: Partikel liegen in Bildkoordinaten.
  assert.ok(fast.stats().particles <= fast.stats().maxParticles);
});

// ---------------------------------------------------------------------------
// Hinweise und Dialog "Anzeige bewegt"
// ---------------------------------------------------------------------------
function memoryStorage() {
  const data = new Map();
  return {getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k), data};
}

function harness({storage = memoryStorage(), answer = 'weiter'} = {}) {
  const toasts = new Map();
  const closed = [];
  const modals = [];
  const calls = [];
  let wall = Date.parse('2026-11-04T12:00:00Z');
  const deps = {
    storage,
    wallNow: () => wall,
    toast: (opts) => {
      toasts.set(opts.key, opts);
      return {close: () => toasts.delete(opts.key)};
    },
    closeToast: (key) => { closed.push(key); toasts.delete(key); },
    openModal: (opts) => {
      let resolve;
      const promise = new Promise((r) => { resolve = r; });
      const modal = {opts, open: true, resolve: (v) => { modal.open = false; resolve(v); }};
      promise.close = (v) => modal.resolve(v);
      modals.push(modal);
      if (answer) queueMicrotask(() => modal.resolve(answer));
      return promise;
    },
    run: {stop: async () => { calls.push('stop'); return {ok: true}; },
      setup: async () => { calls.push('setup'); return {ok: true}; }},
  };
  return {deps, toasts, closed, modals, calls, storage, tick: (ms) => { wall += ms; }};
}

const settle = () => new Promise((r) => setTimeout(r, 0));

test('alerts: Anzeige bewegt opens the dialog once per episode, Esc is remembered across reloads', async () => {
  const h = harness();
  const moved = scene('running_anzeige_bewegt');
  const alerts = createAlerts(h.deps);
  alerts.update(moved);
  assert.equal(h.modals.length, 1);
  const {opts} = h.modals[0];
  assert.equal(opts.title, 'Anzeige hat sich bewegt');
  assert.match(opts.text, /^Anzeige hat sich bewegt \(ca\. 19 px \(Ecken\), 2,2 Grad\) – Werte werden nicht freigegeben\. Bitte neu einrichten\./);
  assert.deepEqual(opts.actions.map((a) => [a.label, a.value]),
    [['Weiter beobachten', 'weiter'], ['Lauf stoppen', 'stopp'], ['Neu einrichten', 'neu']]);
  assert.equal(opts.actions.find((a) => a.escape).value, 'weiter');
  assert.equal(opts.actions.find((a) => a.primary).value, 'neu');
  await settle();
  // Weiter beobachten: kein POST, kein zweiter Dialog bei weiteren Abrufen.
  for (let i = 0; i < 5; i++) { h.tick(500); alerts.update(moved); }
  assert.equal(h.modals.length, 1);
  assert.deepEqual(h.calls, []);
  // Danach erinnert ein stehender Hinweis an den Zustand.
  assert.equal(h.toasts.get('nachfuehrung')?.title, LOST_TITLE);
  assert.ok(h.toasts.get('nachfuehrung').sticky);
  // Neuladen: neuer Beobachter, gleicher Sitzungsspeicher.
  const reloaded = harness({storage: h.storage});
  createAlerts(reloaded.deps).update(moved);
  assert.equal(reloaded.modals.length, 0);
  // Echter Server: since_s waechst; derselbe Verlust bleibt weggelegt.
  const growing = structuredClone(moved);
  growing.run.tracking_hint.since_s = 3 + 12.5;
  reloaded.tick(12_500);
  createAlerts(reloaded.deps).update(growing);
  assert.equal(reloaded.modals.length, 0);
  // Ein neuer Verlust (nach der Erholung, since_s klein) fragt wieder.
  const again = harness({storage: h.storage});
  const watcher = createAlerts(again.deps);
  again.tick(60_000);
  const fresh = structuredClone(moved);
  fresh.run.tracking_hint.since_s = 0.5;
  watcher.update(fresh);
  assert.equal(again.modals.length, 1);
});

test('alerts: dialog choices use the existing POSTs and storage may be missing', async () => {
  const throwing = {getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }};
  const h = harness({storage: throwing, answer: 'neu'});
  const alerts = createAlerts(h.deps);
  alerts.update(scene('running_anzeige_bewegt'));
  await settle();
  await settle();
  assert.deepEqual(h.calls, ['stop', 'setup']);
  const s = harness({answer: 'stopp'});
  createAlerts(s.deps).update(scene('running_anzeige_bewegt'));
  await settle();
  await settle();
  assert.deepEqual(s.calls, ['stop']);
  // Ohne Antwort: verschwindet der Anlass, schliesst der Dialog von selbst.
  const w = harness({answer: null});
  const watcher = createAlerts(w.deps);
  watcher.update(scene('running_anzeige_bewegt'));
  assert.equal(w.modals[0].open, true);
  watcher.update(scene('running_valid'));
  assert.equal(w.modals[0].open, false);
  await settle();
  assert.deepEqual(w.calls, []);
});

test('alerts: hidden frame stays until recovery, stall and run events are toasts', () => {
  const h = harness();
  const alerts = createAlerts(h.deps);
  alerts.update(scene('running_valid'));
  assert.equal(h.toasts.size, 0, 'erster Abruf: kein Hinweis fuer laengst Geschehenes');
  alerts.update(scene('running_rahmen_verdeckt'));
  const lost = h.toasts.get('nachfuehrung');
  assert.equal(lost.title, LOST_TITLE);
  assert.equal(lost.level, 'err');
  assert.ok(lost.sticky);
  alerts.update(scene('running_valid'));
  assert.ok(h.closed.includes('nachfuehrung'));
  alerts.update(scene('running_stalled'));
  assert.equal(h.toasts.get('stillstand')?.title, STALL_TITLE);
  assert.equal(h.toasts.get('stillstand').level, 'err');
  // Lauf gestoppt: Hinweis, schliesst selbst.
  const stopped = scene('stopped');
  alerts.update(stopped);
  const stop = [...h.toasts.values()].find((t) => /gestoppt/.test(t.title));
  assert.ok(stop && !stop.sticky, JSON.stringify([...h.toasts.keys()]));
});

test('alerts: a swapped action source is used by the dialog (practice run never POSTs)', async () => {
  const h = harness({answer: null});
  const client = {};
  const real = [];
  const practice = [];
  const runOf = (log) => ({stop: async () => { log.push('stop'); return {ok: true}; },
    setup: async () => { log.push('setup'); return {ok: true}; }});
  watchAlerts(scene('running_anzeige_bewegt'), {...h.deps, client, run: runOf(real)});
  assert.equal(h.modals.length, 1);
  // Der Uebungslauf (Aufgabe 11) tauscht die Bedienschritte, waehrend der Dialog offen ist.
  watchAlerts(scene('running_anzeige_bewegt'), {client, run: runOf(practice)});
  h.modals[0].resolve('neu');
  await settle();
  await settle();
  assert.deepEqual(real, []);
  assert.deepEqual(practice, ['stop', 'setup']);
});

test('alerts: a stale record does not keep the loss toast next to the stall', () => {
  const h = harness();
  const alerts = createAlerts(h.deps);
  alerts.update(scene('running_valid'));
  alerts.update(scene('running_rahmen_verdeckt'));
  assert.ok(h.toasts.has('nachfuehrung'));
  const stale = scene('running_rahmen_verdeckt');
  stale.run.latest_age_s = 2;
  stale.camera.stalled = true;
  alerts.update(stale);
  assert.ok(!h.toasts.has('nachfuehrung'));
  assert.ok(h.toasts.has('stillstand'));
});

// Minimal-DOM fuer mountEffects: Elemente, Fenster mit gezaehltem rAF und Takt.
function fakeDom({reduce = false} = {}) {
  const el = (tag) => {
    const classes = new Set();
    const node = {tag, hidden: false, textContent: '', innerHTML: '', className: '', clientWidth: 820, clientHeight: 680,
      width: 0, height: 0, setAttribute() {}, append() {}, after() {}, addEventListener() {},
      classList: {toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)), add: (c) => classes.add(c),
        remove: (c) => classes.delete(c), contains: (c) => classes.has(c)}};
    if (tag === 'canvas') node.getContext = () => fakeCanvas().getContext();
    return node;
  };
  let t = 0;
  const rafs = [];
  const intervals = new Map();
  let id = 0;
  const listeners = [];
  const mql = {matches: reduce, addEventListener: (type, fn) => listeners.push(fn)};
  const win = {
    performance: {now: () => t},
    requestAnimationFrame: (fn) => { rafs.push(fn); return ++id; },
    cancelAnimationFrame() {},
    setInterval: (fn, ms) => { intervals.set(++id, {fn, ms, next: t + ms}); return id; },
    clearInterval: (k) => intervals.delete(k),
    setTimeout: () => 0, clearTimeout() {},
    matchMedia: () => mql,
  };
  const doc = {hidden: false, body: {append() {}}, createElement: el, addEventListener() {}, defaultView: win};
  const stage = {ownerDocument: doc, querySelector: () => el('canvas'), classList: el('div').classList};
  let frameAt = 0;
  let filter = 'none';
  const viewer = {
    viewState: () => ({imageToScreen: ([x, y]) => [x * 0.5, y * 0.5], scale: 0.5, width: 820, height: 680, dpr: 1, source: 'live'}),
    hud: () => hudWith(), frameAgeS: () => (t - frameAt) / 1000, setImageFilter: (f) => { filter = f; },
  };
  // Zeit vorstellen: rAF-Rueckrufe dieses Bilds ausfuehren, faellige Takte ausloesen.
  const advance = (ms, step = 16) => {
    let frames = 0;
    for (let end = t + ms; t < end; t += step) {
      const due = rafs.splice(0);
      frames += due.length;
      for (const fn of due) fn(t);
      for (const timer of intervals.values()) while (timer.next <= t) { timer.next += timer.ms; timer.fn(); }
    }
    return frames;
  };
  return {stage, viewer, win, advance, filter: () => filter, intervals, mql, listeners,
    frame: () => { frameAt = t; }};
}

test('effects loop rests while stalled or offline: no rAF, age on a slow timer', () => {
  for (const reduce of [true, false]) {
    const dom = fakeDom({reduce});
    const fx = mountEffects(dom.stage, dom.viewer, {win: dom.win});
    const stalled = scene('running_stalled');
    fx.update(stalled, {offline: false, httpStatus: 200, lastOkMs: 0});
    assert.equal(fx.kind(), 'stalled');
    let frames = 0;
    for (let i = 0; i < 24; i++) {
      frames += dom.advance(250);
      fx.update(stalled, {offline: false, httpStatus: 200, lastOkMs: 0});
    }
    assert.equal(frames, 0, `reduce=${reduce}: kein Bild-fuer-Bild im Stillstand`);
    assert.equal([...dom.intervals.values()][0]?.ms, TEXT_MS);
    // Die Unschaerfe kommt im ruhigen Takt an und steht danach still.
    assert.match(dom.filter(), /blur\(5\.00px\) saturate\(0\.12\) brightness\(0\.750\)/);
    // Verbindung verloren: ebenso ruhend.
    fx.update(stalled, {offline: true, httpStatus: null, lastOkMs: 0});
    assert.equal(fx.kind(), 'offline');
    assert.equal(dom.advance(1000), 0, 'offline: kein rAF');
    assert.equal(dom.filter(), 'none');
    // Zurueck im Lauf ohne Stoerung (neues Bild): kein Takt mehr.
    dom.frame();
    fx.update(scene('running_valid'), {offline: false, httpStatus: 200, lastOkMs: 0});
    assert.equal(dom.intervals.size, 0, 'kein Takt ohne Stoerung');
  }
});

test('effects animate only what moves and follow a reduced-motion change at runtime', () => {
  const dom = fakeDom({reduce: false});
  const fx = mountEffects(dom.stage, dom.viewer, {win: dom.win});
  const lost = scene('running_rahmen_verdeckt');
  dom.frame();
  fx.update(lost, {offline: false, httpStatus: 200, lastOkMs: 0});
  assert.equal(fx.kind(), 'error');
  assert.ok(dom.advance(500) > 20, 'Wolke laeuft Bild fuer Bild');
  assert.ok(fx.effects.stats().particles > 0);
  // Systemeinstellung wechselt auf reduzierte Bewegung: keine Teilchen, kein rAF mehr.
  dom.mql.matches = true;
  for (const fn of dom.listeners) fn({matches: true});
  dom.advance(100);
  assert.equal(fx.effects.stats().particles, 0);
  dom.frame();
  fx.update(lost, {offline: false, httpStatus: 200, lastOkMs: 0});
  assert.equal(dom.advance(500), 0);
});
