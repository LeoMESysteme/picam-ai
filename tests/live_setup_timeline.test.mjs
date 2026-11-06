// Zeitleiste der Einrichtung (Finish-Review F1, Mock #t=10 und #t=46): reine
// Ableitung aus status.setup.progress und setup.focus, Zeichnung auf einer
// Attrappe. Die Lage im Browser prueft Playwright.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {NOMINAL_S, paintSetupTimeline, setupTimelineModel}
  from '../src/dispread/workbench/static/live/setup/timeline.js';

const load = (name) => JSON.parse(readFileSync(new URL(`./fixtures/live/scene-${name}.json`, import.meta.url), 'utf8'));
const near = (a, b) => Math.abs(a - b) < 1e-9;

test('setup timeline: running focus step grows to its elapsed time, pending steps keep a planned width', () => {
  const model = setupTimelineModel(load('setup_focus'));
  assert.deepEqual(model.segments.map((s) => s.key), ['fokus', 'kamera', 'belichtung', 'standbilder', 'vorschlag', 'bestaetigen']);
  assert.deepEqual(model.segments.map((s) => s.label),
    ['Fokus', 'Kamera', 'Belichtung', 'Standbilder', 'Vorschlag', 'Bestätigen']);
  const [fokus, kamera] = model.segments;
  assert.equal(fokus.state, 'running');
  assert.equal(fokus.t0, 0);
  assert.equal(fokus.fill, 5);
  // Laufender Schritt: geplante Breite, solange er kuerzer ist; der Fortschritt ist die Fuellung.
  assert.equal(fokus.t1, NOMINAL_S.fokus);
  assert.equal(kamera.t0, fokus.t1);
  assert.equal(kamera.state, 'pending');
  assert.equal(model.playhead, 5);
  // Drei Proben in Messreihenfolge innerhalb des gemessenen Teils.
  assert.equal(model.probes.length, 3);
  assert.ok(model.probes.every((t, i) => t > 0 && t <= 5 && (i === 0 || t > model.probes[i - 1])));
  assert.ok(near(model.span, Object.values(NOMINAL_S).reduce((a, b) => a + b, 0)));
});

test('setup timeline: proposal ready puts the playhead at Bestätigen after the measured steps', () => {
  const status = load('setup_ready_warnung');
  const model = setupTimelineModel(status);
  const measured = status.setup.progress.steps.reduce((sum, s) => sum + s.elapsed_s, 0);
  const review = model.segments.at(-1);
  assert.equal(review.key, 'bestaetigen');
  assert.equal(review.state, 'running');
  assert.ok(near(review.t0, measured));
  assert.ok(near(model.playhead, measured));
  assert.ok(model.segments.slice(0, 5).every((s) => s.state === 'done' && s.fill === s.t1));
  // Alle neun Proben im Fokus-Abschnitt (21,3 s).
  assert.equal(model.probes.length, 9);
  assert.ok(model.probes.every((t) => t > 0 && t < 21.3));
  assert.ok(model.span >= measured + NOMINAL_S.bestaetigen - 1e-9);
});

test('setup timeline: a cancelled step ends the track there, without probes beyond it', () => {
  const status = load('setup_focus');
  status.state = 'setup_failed';
  status.error = 'Einrichtung abgebrochen';
  status.setup.progress.steps[0].state = 'failed';
  const model = setupTimelineModel(status);
  assert.equal(model.segments[0].state, 'failed');
  assert.equal(model.segments[0].t1, 5);
  assert.equal(model.playhead, 5);
});

test('setup timeline: none without setup progress or in the run', () => {
  assert.equal(setupTimelineModel(load('idle')), null);
  assert.equal(setupTimelineModel(load('running_valid')), null);
  const bare = load('setup_focus');
  delete bare.setup.progress;
  assert.equal(setupTimelineModel(bare), null);
});

test('setup timeline paints labels, probe ticks, axis and the playhead inside the strip', () => {
  const texts = [];
  const rects = [];
  const lines = [];
  let path = [];
  const ctx = new Proxy({}, {
    get(target, key) {
      if (key in target) return target[key];
      if (key === 'measureText') return (t) => ({width: String(t).length * 6.5});
      if (key === 'fillText') return (t, x, y) => texts.push([String(t), x, y]);
      if (key === 'fillRect') return (x, y, w, h) => rects.push([x, y, w, h, target.fillStyle]);
      if (key === 'beginPath') return () => { path = []; };
      if (key === 'moveTo' || key === 'lineTo') return (x, y) => path.push([x, y]);
      if (key === 'stroke') return () => lines.push(path.slice());
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
  const W = 824, H = 91;
  const model = setupTimelineModel(load('setup_ready_warnung'));
  paintSetupTimeline(ctx, model, {W, H});
  const words = texts.map(([t]) => t);
  for (const word of ['Fokus', 'Standbilder', 'Bestätigen', 'Fokusproben (Reihenfolge)', '0:00', '0:10']) {
    assert.ok(words.includes(word), `${word} fehlt in ${words.join('|')}`);
  }
  // Schmale Abschnitte (Kamera 2 s) bekommen keine abgeschnittene Beschriftung.
  assert.ok(!words.includes('Kamera'));
  // Neun Probenstriche (1 px breit) in --sel.
  assert.equal(rects.filter(([, , w, , c]) => w === 1 && c === '#86aee8').length, 9);
  // Abspielkopf: senkrechte Linie bei playhead, ganz in der Zeichenflaeche.
  const x = 12 + (model.playhead / model.span) * (W - 24);
  const head = lines.find((l) => l.length === 2 && Math.abs(l[0][0] - l[1][0]) < 1e-9 && Math.abs(l[0][0] - x) <= 1);
  assert.ok(head, `Abspielkopf bei ${x}`);
  assert.ok(head.every(([, y]) => y >= 0 && y <= H));
  assert.ok(texts.every(([, tx, ty]) => tx >= 0 && tx < W && ty > 0 && ty <= H));
});
