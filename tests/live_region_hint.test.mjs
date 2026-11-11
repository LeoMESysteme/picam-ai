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

test('Einrichtung: Bereich des letzten Laufs ueber die Lage wiederfinden', () => {
  const previous = {session_id: 'live-x', run: 'run-01', regions: [
    {number: 6, centre: [515, 774], max_share: 0.937}, {number: 2, centre: [900, 900], max_share: 0.5}]};
  const regions = [{centre: [100, 100], size: 15}, {centre: [517, 772], size: 15}, {centre: [300, 300], size: 15}];
  assert.deepEqual(previousRegionMatches(previous, regions), [
    {number: 6, centre: [515, 774], share: 0.937, index: 1},
    {number: 2, centre: [900, 900], share: 0.5, index: -1},
  ]);
  // Gleiche Nummer, wenn der Vorschlag unveraendert ist.
  const same = Array.from({length: 8}, (_, i) => ({centre: i === 5 ? [515, 774] : [10 * i, 0], size: 15}));
  assert.equal(previousRegionMatches(previous, same)[0].index + 1, 6);
  assert.deepEqual(previousRegionMatches(null, regions), []);
  assert.deepEqual(previousRegionMatches({regions: [{number: 6, centre: [526, 774], max_share: 0.9}]}, regions)[0].index, -1);
});

test('Einrichtung: Text nennt alte und neue Nummer samt Lage', () => {
  assert.equal(previousRegionText({number: 6, centre: [515, 774], index: 4}, 'run-01'),
    'Im letzten Lauf (run-01) war Bereich 6 bei 515, 774 dauerhaft unstimmig. Hier heißt er Bereich 5: entfernen.');
  assert.equal(previousRegionText({number: 6, centre: [515, 774], index: 5}, 'run-01'),
    'Im letzten Lauf (run-01) war Bereich 6 bei 515, 774 dauerhaft unstimmig. Er heißt hier ebenfalls Bereich 6: entfernen.');
  assert.equal(previousRegionText({number: 6, centre: [515.4, 773.6], index: -1}, null),
    'Im letzten Lauf war Bereich 6 bei 515, 774 dauerhaft unstimmig. Im neuen Vorschlag liegt dort kein Bereich.');
});
