/* Reine Geometrieprüfung für die Zielbox-Umrechnung in dataset.js.
 *
 * `DatasetCollection.toOriginalBox` ist die einzige aus dataset.js exportierte
 * Funktion - bewusst so klein gehalten, weil sie die einzige Stelle ist, an
 * der eine falsche Umrechnung eine falsche Zielbox in einer gespeicherten
 * Probe erzeugen würde (Konzept: Browser-Skalierung/Letterboxing nie als
 * Originalkoordinaten übernehmen). Ausgeführt gegen den echten
 * Auslieferungsstand der Datei, kein Nachbau in diesem Test.
 *
 * Aufruf: node tests/dataset_client.test.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { toOriginalBox, clampSelectionToImage, chooseInitialGroup } = require(
  path.join(here, '..', 'src', 'dispread', 'workbench', 'static', 'dataset.js'),
);

// Gleiches Seitenverhältnis: keine Letterboxing-Ränder, reiner Skalierungsfaktor 2.
{
  const box = toOriginalBox(
    { x: 50, y: 30, w: 100, h: 60 },
    { width: 500, height: 300 },
    { width: 1000, height: 600 },
  );
  assert.deepEqual(box, { x: 100, y: 60, w: 200, h: 120 });
}

// Echtes Letterboxing: schmaleres sichtbares Fenster als das Originalbild,
// oben/unten je 50px Rand.
{
  const box = toOriginalBox(
    { x: 0, y: 50, w: 50, h: 50 },
    { width: 400, height: 300 },
    { width: 1000, height: 500 },
  );
  assert.deepEqual(box, { x: 0, y: 0, w: 125, h: 125 });
}

// Seitliches Letterboxing (hochformatiges Original in breitem Fenster).
{
  const box = toOriginalBox(
    { x: 100, y: 0, w: 50, h: 100 },
    { width: 300, height: 400 },
    { width: 300, height: 800 },
  );
  // originalAspect=0.375 < visibleAspect=0.75 -> Hoehe fuellt, seitlicher Rand.
  // renderedHeight=400, renderedWidth=400*0.375=150, offsetX=(300-150)/2=75.
  assert.deepEqual(box, { x: (100 - 75) * 2, y: 0, w: 50 * 2, h: 100 * 2 });
}

// Device-Pixel-Ratio darf keine Rolle spielen: dieselbe CSS-Pixel-Eingabe
// liefert dasselbe Ergebnis unabhaengig von window.devicePixelRatio, weil
// toOriginalBox ausschliesslich mit CSS-Pixel-Groessen rechnet.
{
  const args = [
    { x: 50, y: 30, w: 100, h: 60 },
    { width: 500, height: 300 },
    { width: 1000, height: 600 },
  ];
  const withoutDpr = toOriginalBox(...args);
  globalThis.devicePixelRatio = 3;
  const withDpr = toOriginalBox(...args);
  delete globalThis.devicePixelRatio;
  assert.deepEqual(withoutDpr, withDpr);
}

// clampSelectionToImage darf eine Auswahl, die in den Letterboxing-Rand
// hineingezogen wurde, nicht ausserhalb des sichtbaren Bildes lassen.
{
  const clamped = clampSelectionToImage(
    { x: -10, y: 40, w: 30, h: 30 },
    { width: 400, height: 300 },
    { width: 1000, height: 500 },
  );
  assert.ok(clamped.x >= 0);
}

// chooseInitialGroup: Schritt 2 der Sammelmodus-Oberflaeche darf nur bei
// genau einer vorhandenen Situation automatisch uebersprungen werden - bei
// keiner oder mehreren muss der Bediener bewusst waehlen (docs/status.md,
// "Sammelmodus-UX vereinfacht").
{
  assert.equal(chooseInitialGroup({}), null);
  assert.equal(chooseInitialGroup(undefined), null);
}
{
  const chosen = chooseInitialGroup({ g1: { change_note: 'erste Situation' } });
  assert.deepEqual(chosen, { group_id: 'g1', change_note: 'erste Situation' });
}
{
  const chosen = chooseInitialGroup({
    g1: { change_note: 'erste Situation' },
    g2: { change_note: 'zweite Situation' },
  });
  assert.equal(chosen, null);
}

// Struktur-Regression: "als Vertreter markieren" (#dataset-representative)
// stand vorher als Kind von #dataset-editor im Markup. afterSave() setzt
// #dataset-editor.hidden=true, BEVOR es #dataset-representative.hidden=false
// setzt - ein verstecktes Vorfahrenelement blendet ein Kind aber unabhaengig
// von dessen eigenem hidden-Attribut aus (Nutzerfund: der Knopf existierte
// im DOM und die Logik lief, war aber nie sichtbar). Diese Prüfung liest das
// echte Markup und stellt sicher, dass #dataset-representative NICHT
// innerhalb von #dataset-editor verschachtelt ist, ohne dafuer einen vollen
// DOM/jsdom in diesem Testharness zu brauchen (siehe OQ-21: Browsertests
// dieser Umgebung sind eingeschraenkt).
{
  const htmlPath = path.join(here, '..', 'src', 'dispread', 'workbench', 'static', 'index.html');
  const html = readFileSync(htmlPath, 'utf8');
  const editorStart = html.indexOf('id="dataset-editor"');
  assert.ok(editorStart >= 0, '#dataset-editor nicht im Markup gefunden');
  const openTagStart = html.lastIndexOf('<div', editorStart);
  let depth = 0;
  let cursor = openTagStart;
  let editorEnd = -1;
  const tagRe = /<div\b|<\/div>/g;
  tagRe.lastIndex = openTagStart;
  let match;
  while ((match = tagRe.exec(html))) {
    if (match[0] === '<div') depth += 1;
    else depth -= 1;
    if (depth === 0) {
      editorEnd = match.index + match[0].length;
      break;
    }
  }
  assert.ok(editorEnd > openTagStart, '#dataset-editor: schliessendes </div> nicht gefunden');
  const editorMarkup = html.slice(openTagStart, editorEnd);
  assert.ok(
    !editorMarkup.includes('id="dataset-representative"'),
    '#dataset-representative darf nicht innerhalb von #dataset-editor verschachtelt sein - sonst bleibt es unsichtbar, sobald der Editor nach dem Speichern versteckt wird',
  );
}

console.log('dataset_client.test.mjs: alle Pruefungen bestanden');
