import test from 'node:test';
import assert from 'node:assert/strict';
import {createViewer} from '../src/dispread/workbench/static/live/viewer/view.js';
import {readFileSync} from 'node:fs';
import {cellQuads, drawHud, hitTest, homography, readoutTag} from '../src/dispread/workbench/static/live/viewer/hud.js';
import {LEGEND_ROWS, legendRows} from '../src/dispread/workbench/static/live/viewer/legend.js';

// Leser-Raster wie im Live-Status (Szene running_valid): entzerrte Pixel.
const GRID = JSON.parse(readFileSync(new URL('./fixtures/live/scene-running_valid.json', import.meta.url), 'utf8')).setup.grid;
// Mitte einer Rasterzelle im Kamerabild.
const cellCentre = (i) => {
  const [x, y, w, h] = GRID.cell_boxes[i];
  return homography(QUAD).map((x + w / 2) / GRID.target_size[0], (y + h / 2) / GRID.target_size[1]);
};

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

  // Mitte von Zelle 8 des Leser-Rasters.
  const cell = hitTest(hud(), cellCentre(8), {scale: 0.5, grid: GRID});
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
  const cell = hitTest(bare, cellCentre(8), {scale: 0.5, grid: GRID});
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

test('cell boxes come from the reader grid and land inside the quad', () => {
  const boxes = cellQuads(QUAD, GRID);
  assert.equal(boxes.length, 16);
  const inside = (p) => {
    let c = false;
    for (let i = 0, j = 3; i < 4; j = i++) {
      const [xi, yi] = QUAD[i], [xj, yj] = QUAD[j];
      if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  for (const box of boxes) for (const p of box) assert.ok(inside([p[0] - Math.sign(p[0] - 1100) * 0.01, p[1] - 0.01]) || inside(p), `${p}`);
  // Zelle 0 beginnt 18 von 160 entzerrten Pixeln unter der Oberkante.
  const top = homography(QUAD).map(0, 0);
  assert.ok(boxes[0][0][1] > top[1] + 5, `Oberkante ${boxes[0][0][1]} nicht unter ${top[1]}`);
  // Der Rasterrand (top 18) ist kein Zelltreffer.
  const [, , , h] = GRID.cell_boxes[0];
  assert.ok(h < 160);
  assert.equal(hitTest(hud(), homography(QUAD).map(12.5 / 400, 5 / 160), {scale: 0.5, grid: GRID}), null);
});

test('without a reader grid there are no cell boxes and no cell hits', () => {
  assert.deepEqual(cellQuads(QUAD, null), []);
  assert.equal(hitTest(hud(), cellCentre(8), {scale: 0.5}), null);
  assert.equal(hitTest(hud(), cellCentre(8), {scale: 0.5, grid: {target_size: [400, 160], cell_boxes: []}}), null);
  const labels = legendRows({grid: false}).map(([, label]) => label).join(' | ');
  assert.ok(!/Raster|Zelle/.test(labels), labels);
  assert.ok(legendRows({grid: true}).some(([, label]) => label.startsWith('Raster')));
  assert.ok(!LEGEND_ROWS.some(([, label]) => label.includes('Fehlerort')));
});

test('a released value turns Veraltet while no new frame arrives', () => {
  const tag = readoutTag(hud(), {frameAgeS: 0.6});
  assert.equal(tag.word, 'Veraltet');
  assert.ok(!/\d\.\d/.test(tag.value), tag.value);
  assert.equal(readoutTag(hud(), {frameAgeS: 0.3}).word, 'Freigegeben');
});

test('viewer redraws at the value age limit and keeps the frame size on a broken HUD', () => {
  let t = 0;
  const pending = [];
  const timers = {setTimeout: (fn, ms) => { pending.push({fn, at: t + ms}); return pending.length; }, clearTimeout: () => {}};
  let draws = 0;
  const viewer = createViewer(fakeCanvas(), {dpr: 1, now: () => t, timers, schedule: (fn) => { draws += 1; fn(); }});
  viewer.setFrame({width: 960, height: 540}, hud());
  const words = [];
  viewer.addPainter((ctx, view) => words.push(readoutTag(viewer.hud(), {frameAgeS: view.frameAgeS})?.word));
  // Timer an der 0,5-s-Grenze (0,5 − 0,04 s) und an der 1,5-s-Bildgrenze.
  const due = pending.map((p) => p.at).sort((a, b) => a - b);
  assert.ok(due.some((ms) => ms >= 460 && ms <= 470), `${due}`);
  assert.ok(due.some((ms) => ms >= 1500 && ms <= 1510), `${due}`);
  t = 470;
  const before = draws;
  pending.find((p) => p.at >= 460 && p.at <= 470).fn();
  assert.ok(draws > before);
  assert.equal(words[words.length - 1], 'Veraltet');
  assert.equal(viewer.tagWord(), 'Veraltet');
  // Ein Teil ohne lesbares X-Hud bleibt im Kamerabild-Raum (1920 breit).
  viewer.fit();
  const wide = viewer.imageToScreen([1920, 0])[0] - viewer.imageToScreen([0, 0])[0];
  viewer.setFrame({width: 960, height: 540}, null);
  viewer.fit();
  assert.ok(Math.abs(viewer.imageToScreen([1920, 0])[0] - viewer.imageToScreen([0, 0])[0] - wide) < 1e-9);
});

test('click handlers compose: the first one returning true consumes the click', () => {
  const viewer = createViewer(fakeCanvas(), {dpr: 1, schedule: () => {}});
  viewer.setFrame({width: 960, height: 540}, hud());
  const calls = [];
  const removeA = viewer.addClickHandler((point) => { calls.push(['a', Math.round(point[0])]); return false; });
  viewer.addClickHandler(() => { calls.push(['b']); return true; });
  viewer.addClickHandler(() => { calls.push(['c']); return true; });
  const screen = viewer.imageToScreen([1485, 658]);
  viewer.click(screen);
  assert.deepEqual(calls, [['a', 1485], ['b']]);
  assert.equal(viewer.pinned(), null, 'verbrauchter Klick heftet nicht an');
  removeA();
  calls.length = 0;
  viewer.click(screen);
  assert.deepEqual(calls, [['b']]);
  const removePainter = viewer.addPainter(() => {});
  assert.equal(typeof removePainter, 'function');
});
