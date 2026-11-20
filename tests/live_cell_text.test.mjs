// Wert der Anzeige von Hand: Browser-Normalisierung = Server-Normalisierung.
// Die Faelle in fixtures/cell_text_cases.json prueft auch tests/test_gsv2as_cell_text.py.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { normalizeCellText, spokenCells } from '../src/dispread/workbench/static/live/setup/cell-text.js';

const cases = JSON.parse(readFileSync(new URL('./fixtures/cell_text_cases.json', import.meta.url)));

for (const [raw, expected] of cases.accept) {
  test(`nimmt ${JSON.stringify(raw)} als ${JSON.stringify(expected)}`, () => {
    assert.deepEqual(normalizeCellText(raw), { ok: true, text: expected });
  });
}
for (const raw of cases.reject) {
  test(`lehnt ${JSON.stringify(raw)} ab`, () => {
    const result = normalizeCellText(raw);
    assert.equal(result.ok, false);
    assert.equal(typeof result.error, 'string');
    assert.ok(result.error.length > 10);
  });
}
test('Meldungen nennen den Grund', () => {
  assert.match(normalizeCellText('-0,4678').error, /Minuszeichen/);
  assert.match(normalizeCellText('0.4.678').error, /Mehr als ein Dezimalpunkt/);
  assert.match(normalizeCellText('12.34567').error, /7 Ziffern/);
  assert.match(normalizeCellText('+0.4??? ').error, /höchstens 2 Zellen mit \?/);
  assert.match(normalizeCellText('0,4678 V').error, /Zeichen „V“/);
  assert.equal(normalizeCellText(0.4678).ok, false);
});
test('Vorlesetext nennt Leerzellen und schwankende Ziffern', () => {
  assert.equal(spokenCells('+ 0.467? '), '+, Leerzelle, 0, Punkt, 4, 6, 7, schwankend');
});

test('Dialoglage bleibt im Fenster, Andockstellen und Merken ohne Speicher', async () => {
  const { clampPosition, dockPosition, loadPosition, savePosition, POSITION_KEY } =
    await import('../src/dispread/workbench/static/live/setup/cell-text.js');
  const size = { width: 500, height: 400 };
  const view = { vw: 1440, vh: 900 };
  assert.deepEqual(clampPosition({ left: -50, top: 2000 }, size, view), { left: 0, top: 500 });
  assert.deepEqual(clampPosition({ left: 2000, top: -1 }, size, view), { left: 940, top: 0 });
  // Groesser als das Fenster: linke obere Ecke bleibt sichtbar.
  assert.deepEqual(clampPosition({ left: 30, top: 30 }, { width: 600, height: 1000 }, { vw: 360, vh: 740 }), { left: 0, top: 0 });
  assert.deepEqual(dockPosition('links', size, view), { left: 16, top: 250 });
  assert.deepEqual(dockPosition('rechts', size, view), { left: 924, top: 250 });
  assert.deepEqual(dockPosition('unten', size, view), { left: 470, top: 484 });
  assert.deepEqual(dockPosition('mitte', size, view), { left: 470, top: 250 });
  const map = new Map();
  const store = { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, v), removeItem: (k) => map.delete(k) };
  savePosition({ left: 12, top: 34 }, store);
  assert.equal(map.get(POSITION_KEY), '{"left":12,"top":34}');
  assert.deepEqual(loadPosition(store), { left: 12, top: 34 });
  map.set(POSITION_KEY, 'kaputt');
  assert.equal(loadPosition(store), null);
  const broken = { getItem() { throw new Error('gesperrt'); }, setItem() { throw new Error('gesperrt'); } };
  assert.equal(loadPosition(broken), null);
  savePosition({ left: 1, top: 2 }, broken);
  assert.equal(loadPosition(null), null);
});
