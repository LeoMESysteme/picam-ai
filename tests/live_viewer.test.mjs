import test from 'node:test';
import assert from 'node:assert/strict';
import {createViewer} from '../src/dispread/workbench/static/live/viewer/view.js';
import {drawHud, hitTest, homography, readoutTag} from '../src/dispread/workbench/static/live/viewer/hud.js';
import {LEGEND_ROWS} from '../src/dispread/workbench/static/live/viewer/legend.js';

// Zeichenkontext-Attrappe: nimmt jeden Aufruf an und merkt sich Texte.
function fakeContext() {
  const texts = [];
  const ctx = new Proxy({texts}, {
    get(target, key) {
      if (key in target) return target[key];
      if (key === 'measureText') return (text) => ({width: String(text).length * 7});
      if (key === 'fillText') return (text) => texts.push(String(text));
      if (key === 'createPattern' || key === 'createLinearGradient') return () => ({addColorStop() {}});
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
  return ctx;
}

function fakeCanvas(width = 800, height = 450) {
  const ctx = fakeContext();
  return {clientWidth: width, clientHeight: height, width: 0, height: 0, dataset: {}, ctx,
    getContext: () => ctx, addEventListener() {}, getBoundingClientRect: () => ({left: 0, top: 0, width, height})};
}

const QUAD = [[810, 511], [1369, 511], [1377, 580], [814, 591]];
const REGIONS = [[873, 385], [915, 737], [1256, 422], [1485, 658], [829, 411]];

function hud(over = {}) {
  return {
    seq: 51234, cap_ns: 1, w: 1920, h: 1080,
    rec: {seq: 51233, status: 'valid', text: '+0.62427', unit: 'mV/V', reasons: [], age_s: 0.04},
    track: {quad: QUAD, score: 0.93, shift_px: 0.4, rotation_deg: 0, reason: null, correcting: false,
      regions: REGIONS.map((c, i) => ({c, s: 15, peak: i === 1 ? 0.3 : 0.92, ok: i !== 1}))},
    cells: Array.from({length: 16}, (_, i) => ({i, best: '+ 0.62427 mV/V  '[i], margin: i === 8 ? 0.41 : 0.12,
      uncertain: i === 8 ? true : false})),
    proc: {fps: 14.8, latency_ms: 46, skipped_recent: 0.02},
    preview: {fps: 15, throttled: null},
    ...over,
  };
}

test('screenToImage∘imageToScreen is identity for zoom 0.25…8 and dpr 1,2', () => {
  for (const dpr of [1, 2]) {
    const viewer = createViewer(fakeCanvas(), {dpr, schedule: () => {}});
    viewer.setFrame({width: 960, height: 540}, hud());
    for (const zoom of [0.25, 0.5, 1, 1.7, 3, 8]) {
      viewer.oneToOne();
      viewer.zoomBy(zoom, [400, 225]);
      assert.ok(Math.abs(viewer.zoom() - zoom) < 1e-9, `zoom ${viewer.zoom()} != ${zoom}`);
      for (const point of [[0, 0], [873.25, 385.5], [1919, 1079], [-40, 2000]]) {
        const back = viewer.screenToImage(viewer.imageToScreen(point));
        assert.ok(Math.abs(back[0] - point[0]) <= 0.01 && Math.abs(back[1] - point[1]) <= 0.01,
          `dpr ${dpr} zoom ${zoom}: ${point} -> ${back}`);
      }
      for (const screen of [[0, 0], [399.5, 224.25], [800, 450]]) {
        const back = viewer.imageToScreen(viewer.screenToImage(screen));
        assert.ok(Math.hypot(back[0] - screen[0], back[1] - screen[1]) <= 0.01);
      }
    }
  }
});

test('zoomBy keeps the image point under the pointer and 1:1 is one image pixel per device pixel', () => {
  const viewer = createViewer(fakeCanvas(), {dpr: 2, schedule: () => {}});
  viewer.setFrame({width: 960, height: 540}, hud());
  const pointer = [612, 140];
  const before = viewer.screenToImage(pointer);
  viewer.zoomBy(2.5, pointer);
  const after = viewer.screenToImage(pointer);
  assert.ok(Math.hypot(after[0] - before[0], after[1] - before[1]) < 1e-6);
  viewer.oneToOne();
  assert.equal(viewer.zoom(), 1);
  const [a, b] = [viewer.imageToScreen([100, 100]), viewer.imageToScreen([101, 100])];
  assert.ok(Math.abs((b[0] - a[0]) * 2 - 1) < 1e-9, 'ein Bildpunkt = ein Gerätepixel');
  viewer.fit();
  // Einpassen zeigt das ganze Kamerabild (1920×1080) im Fenster.
  const [x0, y0] = viewer.imageToScreen([0, 0]);
  const [x1, y1] = viewer.imageToScreen([1920, 1080]);
  assert.ok(x0 >= 0 && y0 >= 0 && x1 <= 800 && y1 <= 450);
  assert.ok(Math.abs((x1 - x0) - 800) < 20 || Math.abs((y1 - y0) - 450) < 20);
});

test('hitTest finds region 3 and cell 8', () => {
  const region = hitTest(hud(), [1486, 657], {scale: 0.5});
  assert.equal(region.kind, 'region');
  assert.equal(region.index, 3);
  assert.match(region.info, /^Rahmenbereich 4 · /);
  assert.match(region.info, /Suchfenster-Mitte 1485, 658/);
  assert.match(region.info, /Treffer 0,92/);
  assert.ok(!region.info.includes('%'));

  const lost = hitTest(hud(), [915, 737], {scale: 0.5});
  assert.equal(lost.index, 1);
  assert.match(lost.info, /kein Treffer/);

  // Mitte von Zelle 8 im Viereck (16 gleiche Zellen, projektiv).
  const cell = hitTest(hud(), homography(QUAD).map(8.5 / 16, 0.5), {scale: 0.5});
  assert.equal(cell.kind, 'cell');
  assert.equal(cell.index, 8);
  assert.match(cell.info, /^Zelle 8 · /);
  assert.ok(cell.info.includes('Abstand 0,41'), cell.info);
  assert.ok(cell.info.includes('unsicher'));
  assert.ok(cell.info.includes('Bestwert 7'));
  assert.ok(!cell.info.includes('%'));
  assert.ok(!/Wahrscheinlichkeit|Sicherheit/.test(cell.info));
  assert.equal(hitTest(hud(), [100, 100], {scale: 0.5}), null);
});

test('hitTest only reports numbers the HUD carries', () => {
  const bare = hud({cells: [{i: 8, best: '7', margin: null, uncertain: false}]});
  const cell = hitTest(bare, homography(QUAD).map(8.5 / 16, 0.5), {scale: 0.5});
  assert.equal(cell.index, 8);
  assert.ok(!cell.info.includes('Abstand'), cell.info);
  // Ausgeblendete Ebenen sind nicht treffbar; ohne Lauf gibt es nichts.
  assert.equal(hitTest(hud(), [1486, 657], {scale: 0.5, layers: new Set(['anzeige'])}), null);
  assert.equal(hitTest(hud({track: null, cells: null, rec: null}), [1486, 657], {scale: 0.5}), null);
  const corner = hitTest(hud(), [1369.5, 511.5], {scale: 0.5});
  assert.equal(corner.kind, 'corner');
  assert.match(corner.info, /Anzeige-Ecke oben rechts · Lage 1369,0, 511,0/);
});

test('readout tag never shows a stale value as released', () => {
  assert.deepEqual(readoutTag(hud()), {value: '+0.62427 mV/V', word: 'Freigegeben', tone: 'ok', spur: 'Spur 0,93'});
  const old = readoutTag(hud({rec: {...hud().rec, age_s: 0.9}}));
  assert.equal(old.word, 'Veraltet');
  assert.ok(!old.value.includes('0.62427'));
  assert.equal(readoutTag(hud(), {frameAgeS: 1.6}).word, 'Veraltet');
  const unreadable = readoutTag(hud({rec: {...hud().rec, status: 'unreadable'}}));
  assert.equal(unreadable.value, 'kein Wert');
  assert.equal(unreadable.word, 'Unlesbar');
  assert.equal(readoutTag(hud({rec: {...hud().rec, status: 'transition'}})).value, 'Wert wechselt');
  assert.equal(readoutTag(hud({rec: null})), null);
});

test('drawHud draws every layer without throwing and labels the tag', () => {
  const canvas = fakeCanvas();
  const viewer = createViewer(canvas, {dpr: 1, schedule: () => {}});
  viewer.setFrame({width: 960, height: 540}, hud());
  const ctx = fakeContext();
  drawHud(ctx, hud(), viewer.viewState(), new Set(['anzeige', 'raster', 'zellen', 'rahmen', 'etikett']));
  assert.ok(ctx.texts.includes('+0.62427 mV/V'));
  assert.ok(ctx.texts.includes('Freigegeben'));
  assert.ok(ctx.texts.includes('Spur 0,93'));
  const empty = fakeContext();
  drawHud(empty, hud({track: null, cells: null, rec: null}), viewer.viewState(), new Set(['anzeige']));
  drawHud(empty, null, viewer.viewState(), new Set());
  assert.deepEqual(empty.texts, []);
});

test('legend explains every marker without probability wording', () => {
  const labels = LEGEND_ROWS.map(([, label]) => label).join(' | ');
  for (const word of ['Rahmenbereich mit Treffer', 'Rahmenbereich ohne Treffer', 'Suchfenster', 'Unsichere Zelle',
    'Korrektur läuft', 'Wert-Etikett']) assert.ok(labels.includes(word), word);
  assert.ok(!/Wahrscheinlichkeit|%/.test(labels));
});
