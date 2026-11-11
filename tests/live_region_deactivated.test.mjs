// TB 2026-11-11: automatisch stillgelegte Rahmenbereiche, ruhiger Info-Ton.
import test from 'node:test';
import assert from 'node:assert/strict';
import {activeRegionHint, regionDeactivatedIndices, regionDeactivatedText, regionHintText}
  from '../src/dispread/workbench/static/live/model.js';
import {renderRunInspector, runBadges} from '../src/dispread/workbench/static/live/run/inspector.js';
import {drawHud} from '../src/dispread/workbench/static/live/viewer/hud.js';

const OFF = [{number: 6, index: 5, centre: [515, 774], share: 0.911, median_px: 1.31, frame_sequence: 1213,
  rest_median_px: 0.169}];
const HINT = {regions: [{number: 6, index: 5, centre: [515, 774], share: 0.917, median_px: 1.332, frames: 205},
  {number: 1, index: 0, centre: [320, 416], share: 0.45, median_px: 0.6, frames: 170}],
rest_median_px: 0.175, frames: 210, limit_px: 0.65};

test('Text "Bereich N automatisch stillgelegt (x % unstimmig)", 1-basiert, sortiert', () => {
  assert.equal(regionDeactivatedText(OFF), 'Bereich 6 automatisch stillgelegt (91 % unstimmig)');
  const two = [...OFF, {number: 1, index: 0, centre: [320, 416], share: 0.5, median_px: 0.7, frame_sequence: 2100}];
  assert.equal(regionDeactivatedText(two), 'Bereiche 1 und 6 automatisch stillgelegt (50 % und 91 % unstimmig)');
  assert.deepEqual(regionDeactivatedIndices(two), [0, 5]);
  for (const bad of [null, undefined, [], [{number: 'x', index: 1, share: 0.5}], [{number: 2, index: -1, share: 1}]]) {
    assert.equal(regionDeactivatedText(bad), '');
    assert.deepEqual(regionDeactivatedIndices(bad), []);
  }
});

test('Kein "entfernen" fuer stillgelegte Bereiche', () => {
  const rest = activeRegionHint(HINT, OFF);
  assert.deepEqual(rest.regions.map((r) => r.index), [0]);
  assert.doesNotMatch(regionHintText(rest), /Bereich 6/);
  assert.equal(activeRegionHint({...HINT, regions: [HINT.regions[0]]}, OFF), null);
  assert.equal(activeRegionHint(HINT, []), HINT);
  assert.equal(runBadges({state: 'running', run: {region_hint: HINT, region_deactivated: OFF}})['Nachführung'], 1);
});

test('Inspektor Nachfuehrung: Info-Block ohne Warn-/Fehlerton, Zeile "stillgelegt"', () => {
  const status = {state: 'running', run: {region_hint: null, region_deactivated: OFF, summary: {},
    tracking: {mode: 'rahmenbereiche'}}};
  const hud = {track: {regions: Array.from({length: 8}, (_, i) => ({c: [100 + i, 200], s: 15, peak: i === 5 ? 0 : 0.9,
    ok: i !== 5}))}};
  const pane = {innerHTML: ''};
  renderRunInspector(pane, status, 'Nachführung', {log: {rows: () => []}, hud});
  const html = pane.innerHTML;
  assert.match(html, /data-part="region-off"/);
  assert.match(html, /Bereich 6 automatisch stillgelegt \(91 % unstimmig\)/);
  const block = html.slice(html.indexOf('data-part="region-off"'), html.indexOf('</div>', html.indexOf('data-part="region-off"')));
  assert.doesNotMatch(block, /warn-t|err-t|sq warn|sq err/);
  assert.match(html, /<tr><td class="m r">6<\/td><td class="m r">105, 200<\/td><td class="m r">0,00<\/td><td><span class="stc"><span class="sq pend"><\/span><span class="mut">stillgelegt<\/span>/);
  assert.doesNotMatch(html, /data-part="region-hint"/);
  const none = {innerHTML: ''};
  renderRunInspector(none, {...status, run: {...status.run, region_deactivated: []}}, 'Nachführung',
    {log: {rows: () => []}, hud});
  assert.doesNotMatch(none.innerHTML, /region-off/);
});

function recordingContext() {
  const strokes = [];
  const target = {strokes, strokeStyle: null};
  return new Proxy(target, {
    get(t, key) {
      if (key in t) return t[key];
      if (key === 'measureText') return (text) => ({width: String(text).length * 7});
      if (key === 'stroke') return () => strokes.push(t.strokeStyle);
      return () => {};
    },
    set(t, key, value) { t[key] = value; return true; },
  });
}

test('HUD: stillgelegter Bereich wird nicht als Verlust (rot) gezeichnet', () => {
  const view = {imageToScreen: (p) => p, scale: 1, dpr: 1, width: 800, height: 600};
  const regions = Array.from({length: 4}, (_, i) => ({c: [100 + 30 * i, 200], s: 15, peak: 0.9, ok: true}));
  const lost = recordingContext();
  drawHud(lost, {track: {regions: regions.map((r, i) => (i === 2 ? {...r, ok: false, peak: 0} : r))}}, view, new Set(['rahmen']));
  const off = recordingContext();
  drawHud(off, {track: {regions: regions.map((r, i) => (i === 2 ? {...r, ok: false, peak: 0, off: true} : r))}}, view,
    new Set(['rahmen']));
  assert.ok(lost.strokes.some((s) => String(s).includes('238,91,77') || s === '#ee5b4d'));
  assert.ok(!off.strokes.some((s) => String(s).includes('238,91,77') || s === '#ee5b4d'));
  assert.ok(off.strokes.length < lost.strokes.length);
});
