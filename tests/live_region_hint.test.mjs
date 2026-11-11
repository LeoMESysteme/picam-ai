// TC 2026-11-11: Bedienhinweis "Rahmenbereich dauerhaft unstimmig" (reine Diagnose).
import test from 'node:test';
import assert from 'node:assert/strict';
import {regionHintIndices, regionHintShort, regionHintText} from '../src/dispread/workbench/static/live/model.js';
import {renderRunInspector, runBadges} from '../src/dispread/workbench/static/live/run/inspector.js';
import {drawHud} from '../src/dispread/workbench/static/live/viewer/hud.js';
import {previousRegionMatches, previousRegionText} from '../src/dispread/workbench/static/live/viewer/regions-edit.js';

const HINT = {regions: [{number: 6, index: 5, centre: [515, 774], share: 0.917, median_px: 1.332, frames: 205}],
  rest_median_px: 0.175, frames: 210, limit_px: 0.65};
const TWO = {...HINT, regions: [HINT.regions[0], {number: 5, index: 4, centre: [319, 415], share: 0.4, median_px: 0.7, frames: 170}]};

test('Hinweistext wie freigegeben, 1-basierte Nummer und gerundeter Anteil', () => {
  assert.equal(regionHintText(HINT), 'Rahmenbereich 6 ist dauerhaft unstimmig (92 % der Bilder). ' +
    'Werte bleiben geschützt; es gehen nur Werte verloren. Nach dem Lauf neu einrichten und Bereich 6 entfernen.');
  assert.equal(regionHintShort(HINT), 'Bereich 6 unstimmig');
  assert.deepEqual(regionHintIndices(HINT), [5]);
});

test('Mehrere Bereiche nach Nummer, Anteile in derselben Reihenfolge', () => {
  assert.equal(regionHintText(TWO), 'Rahmenbereiche 5 und 6 sind dauerhaft unstimmig (40 % und 92 % der Bilder). ' +
    'Werte bleiben geschützt; es gehen nur Werte verloren. Nach dem Lauf neu einrichten und Bereiche 5 und 6 entfernen.');
  assert.equal(regionHintShort(TWO), 'Bereiche 5 und 6 unstimmig');
  assert.deepEqual(regionHintIndices(TWO), [4, 5]);
});

test('Ohne oder mit kaputtem Hinweis kein Text und nichts markiert', () => {
  for (const bad of [null, undefined, {}, {regions: []}, {regions: [{number: 'x', index: 1, share: 0.5}]},
    {regions: [{number: 2, index: -1, share: 0.5}]}, {regions: [{number: 2, index: 1, share: NaN}]}]) {
    assert.equal(regionHintText(bad), '');
    assert.equal(regionHintShort(bad), '');
    assert.deepEqual(regionHintIndices(bad), []);
  }
});

function host() {
  return {innerHTML: '', _html: undefined};
}

test('Inspektor Nachfuehrung: ruhiger Hinweisblock und markierte Tabellenzeile', () => {
  const status = {state: 'running', run: {region_hint: HINT, summary: {}, tracking: {mode: 'rahmenbereiche'}}};
  const hud = {track: {regions: Array.from({length: 8}, (_, i) => ({c: [100 + i, 200], s: 15, peak: 0.9, ok: true}))}};
  const pane = host();
  renderRunInspector(pane, status, 'Nachführung', {log: {rows: () => []}, hud});
  assert.match(pane.innerHTML, /data-part="region-hint"/);
  assert.match(pane.innerHTML, /class="warn-t[^"]*">Rahmenbereich 6 ist dauerhaft unstimmig \(92 % der Bilder\)/);
  assert.doesNotMatch(pane.innerHTML, /err-t">Rahmenbereich/);
  assert.match(pane.innerHTML, /<tr class="flag"><td class="m r">6<\/td>/);
  assert.match(pane.innerHTML, /dauerhaft unstimmig/);
  // Nach dem Stopp bleibt der Hinweis stehen (Bediener richtet danach neu ein).
  const stopped = host();
  renderRunInspector(stopped, {...status, state: 'stopped'}, 'Nachführung', {log: {rows: () => []}, hud});
  assert.match(stopped.innerHTML, /data-part="region-hint"/);
  const none = host();
  renderRunInspector(none, {...status, run: {...status.run, region_hint: null}}, 'Nachführung', {log: {rows: () => []}, hud});
  assert.doesNotMatch(none.innerHTML, /region-hint/);
});

test('Tab-Abzeichen Nachfuehrung nur mit Hinweis', () => {
  assert.equal(runBadges({state: 'running', run: {region_hint: HINT}})['Nachführung'], 1);
  assert.equal(runBadges({state: 'running', run: {region_hint: TWO}})['Nachführung'], 2);
  assert.equal(runBadges({state: 'running', run: {region_hint: null}})['Nachführung'], undefined);
});

function recordingContext() {
  const strokes = [];
  const texts = [];
  const target = {strokes, texts, strokeStyle: null};
  return new Proxy(target, {
    get(t, key) {
      if (key in t) return t[key];
      if (key === 'measureText') return (text) => ({width: String(text).length * 7});
      if (key === 'fillText') return (text) => texts.push(String(text));
      if (key === 'stroke') return () => strokes.push(t.strokeStyle);
      return () => {};
    },
    set(t, key, value) { t[key] = value; return true; },
  });
}

test('HUD markiert den auffaelligen Bereich in Warnfarbe mit Nummer', () => {
  const hud = {track: {regions: Array.from({length: 8}, (_, i) => ({c: [100 + 30 * i, 200], s: 15, peak: 0.9, ok: true}))}};
  const view = {imageToScreen: (p) => p, scale: 1, dpr: 1, width: 800, height: 600};
  const plain = recordingContext();
  drawHud(plain, hud, view, new Set(['rahmen']));
  assert.ok(!plain.strokes.includes('#e5a535'));
  assert.ok(!plain.texts.includes('6'));
  const marked = recordingContext();
  drawHud(marked, hud, {...view, flagged: [5]}, new Set(['rahmen']));
  assert.ok(marked.strokes.includes('#e5a535'));
  assert.ok(marked.texts.includes('6'));
});

const PREV = (regions, quad) => ({session_id: 'live-x', run: 'run-01', quad, regions});
const QUAD = [[810, 511], [1369, 511], [1377, 580], [814, 591]];
const mk = (number, x, y, share = 0.9, marks = 3) => ({number, centre: [x, y], max_share: share, flagged_evaluations: marks});

test('Einrichtung: nur ein Bereich nahe einer dauerhaft unstimmigen Stelle gibt einen Hinweis', () => {
  const previous = PREV([mk(6, 515, 774, 0.937), mk(2, 900, 900, 0.5)], QUAD);
  const regions = [{centre: [100, 100], size: 15}, {centre: [517, 772], size: 15}, {centre: [300, 300], size: 15}];
  // Stelle ohne Bereich im neuen Vorschlag: stumm.
  assert.deepEqual(previousRegionMatches(previous, regions, QUAD),
    [{number: 6, centre: [515, 774], share: 0.937, index: 1}]);
  assert.deepEqual(previousRegionMatches(null, regions), []);
  assert.deepEqual(previousRegionMatches(PREV([mk(6, 526, 774)], QUAD), regions, QUAD), []);
});

test('Einrichtung: dauerhaft heisst Anteil >= 0,30 und mehrfach markiert', () => {
  const regions = [{centre: [10, 10], size: 15}];
  const hit = (share, marks) => previousRegionMatches(PREV([mk(1, 10, 10, share, marks)], QUAD), regions, QUAD).length;
  assert.equal(hit(0.30, 2), 1);
  assert.equal(hit(0.29, 5), 0);
  assert.equal(hit(0.90, 1), 0);
  const old = {number: 1, centre: [10, 10], max_share: 0.9};  // altes Statusformat ohne Zaehler
  assert.equal(previousRegionMatches(PREV([old], QUAD), regions, QUAD).length, 0);
});

test('Einrichtung: neue Aufstellung vergleicht keine alten Positionen', () => {
  const previous = PREV([mk(1, 10, 10)], QUAD);
  const regions = [{centre: [10, 10], size: 15}];
  const near = QUAD.map(([x, y]) => [x + 5, y - 4]);
  const far = QUAD.map(([x, y]) => [x + 60, y + 40]);
  assert.equal(previousRegionMatches(previous, regions, near).length, 1);
  assert.deepEqual(previousRegionMatches(previous, regions, far), []);
  // Ohne bekanntes Viereck wird nicht geraten: vergleichen wie bisher.
  assert.equal(previousRegionMatches(previous, regions, null).length, 1);
});

test('Einrichtung: hoechstens drei Hinweise, die staerksten zuerst', () => {
  const previous = PREV([mk(1, 0, 0, 0.4), mk(2, 50, 0, 0.9), mk(3, 100, 0, 0.5), mk(4, 150, 0, 0.7), mk(5, 200, 0, 0.35)], QUAD);
  const regions = [0, 50, 100, 150, 200].map((x) => ({centre: [x, 0], size: 15}));
  assert.deepEqual(previousRegionMatches(previous, regions, QUAD).map((m) => m.index), [1, 3, 2]);
});

test('Einrichtung: Hinweistext nennt neue Nummer und Anteil', () => {
  assert.equal(previousRegionText({number: 6, centre: [515, 774], share: 0.937, index: 4}),
    'Bereich 5 liegt an einer Stelle, die im letzten Lauf dauerhaft unstimmig war (94 %). ' +
    'Die Einrichtung wählt solche Stellen künftig selbst ab; bei Bedarf hier entfernen.');
});
