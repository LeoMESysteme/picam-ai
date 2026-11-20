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
