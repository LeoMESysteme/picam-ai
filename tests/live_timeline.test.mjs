// Zeitleiste und Ergebnisanzeige des Laufs (Aufgabe 9): reine Ableitungen,
// ohne DOM. Die Zeichnung selbst prueft Playwright (Neuladen, Pixelspalten).
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {BUCKET_MS, VIEW_MS, createTimeline, layoutTimeline, valueTrace}
  from '../src/dispread/workbench/static/live/run/timeline.js';
import {resultModel} from '../src/dispread/workbench/static/live/run/result.js';
import {statusView} from '../src/dispread/workbench/static/live/model.js';

const load = (name) => JSON.parse(readFileSync(new URL(`./fixtures/live/scene-${name}.json`, import.meta.url), 'utf8'));
const points = (runs) => runs.flat();

test('timeline value trace ignores non-valid and never interpolates', () => {
  const runs = valueTrace([[0, 'v', 0.5], [250, 't', null], [500, 'u', null], [750, 'v', 1.25]]);
  const all = points(runs);
  // Nur die beiden freigegebenen Werte, keine Zwischenwerte.
  assert.deepEqual([...new Set(all.map(([, v]) => v))], [0.5, 1.25]);
  // Genau eine Stufe: die Pegelfolge wechselt einmal von v1 nach v2.
  const levels = all.map(([, v]) => v).filter((v, i, a) => i === 0 || v !== a[i - 1]);
  assert.deepEqual(levels, [0.5, 1.25]);
  // Keine Punkte in der Zeit der nicht freigegebenen Eimer.
  assert.equal(all.filter(([t]) => t > 250 && t < 750).length, 0);
  // Die Spur ist dort unterbrochen, nicht ueberbrueckt.
  assert.deepEqual(runs, [[[0, 0.5], [250, 0.5]], [[750, 1.25], [1000, 1.25]]]);
});

test('timeline value trace keeps jumps as vertical steps', () => {
  const runs = valueTrace([[0, 'v', 0.5], [250, 'v', 0.5], [500, 'v', 1.25], [750, 'v', 1.25]]);
  assert.deepEqual(runs, [[[0, 0.5], [500, 0.5], [500, 1.25], [1000, 1.25]]]);
});

test('timeline value trace breaks at gaps and ignores values of worse buckets', () => {
  // Ein Eimer "t" kann einen letzten freigegebenen Wert tragen; die Spur zeigt ihn nicht.
  const runs = valueTrace([[0, 'v', 1], [250, 't', 1], [500, 'v', 1], [1250, 'v', 1], [1500, 's', null]]);
  assert.deepEqual(runs, [[[0, 1], [250, 1]], [[500, 1], [750, 1]], [[1250, 1], [1500, 1]]]);
  assert.deepEqual(valueTrace([[0, 'v', null], [250, 'v', Number.NaN]]), []);
});

test('seed anchors run.recent at recent_now_ms; a stalled run shows its gap up to now', () => {
  let now = 100_000;
  const timeline = createTimeline(null, {now: () => now});
  // 60 s Verlauf, "jetzt" 40 ms nach dem letzten Eimer.
  const recent = Array.from({length: 240}, (_, i) => [i * BUCKET_MS, 'v', 0.62427]);
  timeline.seed(recent, 239 * BUCKET_MS + 40);
  let layout = timeline.layout(800);
  const last = layout.bands.at(-1);
  assert.ok(Math.abs(last.x1 - layout.x(now)) < 800 * 250 / VIEW_MS, 'letzter Eimer endet bei jetzt');
  const covered = layout.bands.reduce((sum, b) => sum + b.x1 - b.x0, 0);
  assert.ok(covered > 775, `sichtbare 40 s voll (${covered} px)`);
  assert.ok(Math.abs(layout.x(now) - 788) < 0.5, 'jetzt am rechten Rand');

  // Stillstand: jetzt liegt 10 s hinter dem letzten Eimer; die Luecke bleibt sichtbar.
  timeline.seed(recent, 239 * BUCKET_MS + 10_000);
  layout = timeline.layout(800);
  const gapPx = layout.x(now) - layout.bands.at(-1).x1;
  assert.ok(Math.abs(gapPx - (10_000 - 250) * layout.pxPerMs) < 1, `Luecke ${gapPx}`);

  // Ohne recent_now_ms (aelterer Server) endet die Spur bei jetzt.
  timeline.seed([[0, 'u', null], [250, 'v', 1]]);
  layout = timeline.layout(800);
  assert.ok(Math.abs(layout.bands.at(-1).x1 - layout.x(now)) < 0.5);
  // Junger Lauf: die Spur waechst von links (Mock #t=58).
  assert.ok(layout.bands[0].x0 < 20);
  now += 1000;
  assert.ok(timeline.layout(800).bands[0].x0 < 20);
});

test('push merges into 250-ms buckets with the worst status and the last released value', () => {
  const now = 10_000;
  const timeline = createTimeline(null, {now: () => now});
  timeline.push(9_000, 'valid', 1);
  timeline.push(9_100, 'transition', null);
  timeline.push(9_200, 'v', 2);
  timeline.push(9_300, 'v', 2);
  assert.deepEqual(timeline.buckets(), [[9_000, 't', 2], [9_250, 'v', 2]]);
  timeline.push(9_400, 'stale', null);
  assert.deepEqual(timeline.buckets().at(-1), [9_250, 's', 2]);
  // Unbekannte Codes gelten als unlesbar, nie als freigegeben.
  timeline.push(9_600, 'maybe', 3);
  assert.deepEqual(timeline.buckets().at(-1), [9_500, 'u', null]);
});

test('marks appear at their time and fall out of the window', () => {
  let now = 50_000;
  const timeline = createTimeline(null, {now: () => now});
  timeline.seed([[0, 'v', 1]], 40_000);
  timeline.mark(45_000, 'Display abgedeckt');
  let layout = timeline.layout(800);
  assert.equal(layout.marks.length, 1);
  assert.equal(layout.marks[0].label, 'Display abgedeckt');
  assert.ok(Math.abs(layout.marks[0].x - layout.x(45_000)) < 0.01);
  now += 70_000;
  layout = timeline.layout(800);
  assert.equal(layout.marks.length, 0);
});

test('layoutTimeline scales released values only and keeps zero on the axis', () => {
  const layout = layoutTimeline([[0, 'v', 0.62427], [250, 'u', 99], [500, 'v', 1.24855]], [],
    {nowMs: 750, width: 800});
  assert.ok(layout.scale.lo <= 0 && layout.scale.hi >= 1.24855);
  assert.ok(layout.scale.hi < 99, 'Wert eines unlesbaren Eimers zaehlt nicht');
  assert.equal(layout.trace.length, 2);
});

// ---------------------------------------------------------------------------
// Ergebnisanzeige: dieselbe Veraltet-Regel wie das HUD-Etikett, Testlauf ohne Wert.
// ---------------------------------------------------------------------------
const hudRec = (status) => {
  const run = status.run.latest;
  return {seq: run.frame_sequence, status: status.run.latest_age_s > 0.5 ? 'stale' : run.status,
    text: run.raw_text, unit: run.unit, reasons: run.reject_reasons, age_s: status.run.latest_age_s};
};

test('result shows a released value with unit', () => {
  const status = load('running_valid');
  const model = resultModel(status, statusView(status), hudRec(status));
  assert.equal(model.cls, 'V');
  assert.equal(model.word, 'Freigegeben');
  assert.equal(model.code, 'VALID');
  assert.equal(model.value, '+0.62427');
  assert.equal(model.unit, 'mV/V');
  assert.equal(model.struck, false);
});

test('result shows stale values struck through, by the HUD tag rule', () => {
  const status = load('running_stalled');
  const model = resultModel(status, statusView(status), hudRec(status), {frameAgeS: 2});
  assert.equal(model.cls, 'S');
  assert.equal(model.word, 'Veraltet');
  assert.equal(model.code, 'STALE');
  assert.equal(model.struck, true);
  assert.equal(model.value, '+0.62427');
  // Frisches HUD, aber kein neues Bild seit > 0,5 s: veraltet wie das Etikett.
  const fresh = load('running_valid');
  const aged = resultModel(fresh, statusView(fresh), {...hudRec(fresh), age_s: 0.3}, {frameAgeS: 0.3});
  assert.equal(aged.cls, 'S');
  // Verbindung verloren: nie freigegeben.
  assert.equal(resultModel(fresh, statusView(fresh), hudRec(fresh), {offline: true}).cls, 'S');
});

test('result never shows a value in a test run', () => {
  const status = {...load('running_valid'), test_run: {testlauf: true}};
  for (const rec of [hudRec(status), {...hudRec(status), status: 'stale', age_s: 3}, null]) {
    const model = resultModel(status, statusView(status), rec, {frameAgeS: rec?.age_s > 1 ? 2 : 0});
    assert.notEqual(model.cls, 'V');
    assert.ok(!JSON.stringify(model).includes('0.62427'), JSON.stringify(model));
  }
  const model = resultModel(status, statusView(status), hudRec(status));
  assert.equal(model.code, 'UNREADABLE');
  assert.equal(model.value, 'Kein Wert');
});

test('result: unreadable says Kein Wert, transition never shows digits, stopped ends the run', () => {
  const lost = load('running_rahmen_verdeckt');
  const model = resultModel(lost, statusView(lost), hudRec(lost));
  assert.equal(model.cls, 'U');
  assert.equal(model.value, 'Kein Wert');
  const changing = load('running_transition');
  const t = resultModel(changing, statusView(changing), hudRec(changing));
  assert.equal(t.cls, 'T');
  assert.ok(!t.value.includes('0.62427'));
  const stopped = load('stopped');
  const end = resultModel(stopped, statusView(stopped), null);
  assert.equal(end.cls, 'X');
  assert.equal(end.word, 'Lauf beendet');
});
