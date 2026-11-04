// Bilder des Uebungslaufs: setzt scenario.frame().bitmapSource aus dem
// Standbild still.jpg zusammen (Zeichnung aus dem Mock mock.src.html:
// synthetisches LCD in 5×7-Punkten auf plate.jpg, Hand von rechts, Stoss,
// Schaerfe und Helligkeit). still.jpg und plate.jpg werden einmal per
// createImageBitmap dekodiert und danach wiederverwendet; zusammengesetzte
// Bilder liegen in einem kleinen Zwischenspeicher (Canvas, kein close()).
//
// Koordinaten wie im Mock: Standbild 1440×810. Gezeichnet wird in 960×540
// (Breite des echten Vorschau-JPEGs); der Viewer zieht es auf hud.w × hud.h.

const SRC_W = 1440, SRC_H = 810;
const OUT_W = 960, OUT_H = 540;
const SCALE = OUT_W / SRC_W;
const CACHE_MAX = 16;
// Mock: Anzeige-Viereck und Lage der Glasplatte im Standbild.
const QUAD = [[608, 383], [1027, 383], [1033, 435], [610, 443]];
const PLATE_AT = [598, 370];
const DOT = {u0: 0.5 / 6, du: 1 / 6, w: 0.80 / 6, v0: 0.168, dv: 0.1095, h: 0.092};
// 5×7-Zeichen (HD44780 A00, Teilmenge des Mocks).
const FONT = {'0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
  '2': '01110100010000100010001000100011111', '3': '11111000100010000010000011000101110',
  '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
  '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
  '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
  '+': '00000001000010011111001000010000000', '-': '00000000000000011111000000000000000',
  '.': '00000000000000000000000000110001100', 'm': '00000000001101010101101011000110001',
  'V': '10001100011000110001100010101000100', '/': '00000000010001000100010001000000000',
  ' ': '00000000000000000000000000000000000', '?': '01110100010000100010001000000000100'};

const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const eo = (k) => 1 - (1 - clamp(k, 0, 1)) ** 3;
const q = (x, step) => Math.round(x / step) * step;

function homog(quad) {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = quad;
  const dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3, dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
  let g = 0, h = 0;
  if (Math.abs(dx3) > 1e-9 || Math.abs(dy3) > 1e-9) {
    const den = dx1 * dy2 - dx2 * dy1;
    g = (dx3 * dy2 - dx2 * dy3) / den;
    h = (dx1 * dy3 - dx3 * dy1) / den;
  }
  const a = x1 - x0 + g * x1, b = x3 - x0 + h * x3, c = x0, d = y1 - y0 + g * y1, e = y3 - y0 + h * y3, f = y0;
  return (u, v) => { const w = g * u + h * v + 1; return [(a * u + b * v + c) / w, (d * u + e * v + f) / w]; };
}
const MAP = homog(QUAD);

// Mock drawLCD: unbeleuchtete Punkte schwach, Zeichen dunkel; im Wechsel
// verblassen alte Punkte, neue dunkeln nach (k = Fortschritt 0..1).
function drawLCD(c, text, from, k) {
  const quadAt = (u0, v0, u1, v1) => {
    const p = [MAP(u0, v0), MAP(u1, v0), MAP(u1, v1), MAP(u0, v1)];
    c.moveTo(p[0][0], p[0][1]);
    for (let i = 1; i < 4; i++) c.lineTo(p[i][0], p[i][1]);
    c.closePath();
  };
  const layer = (select, color) => {
    c.beginPath();
    for (let ci = 0; ci < 16; ci++) {
      for (let row = 0; row < 7; row++) {
        for (let j = 0; j < 5; j++) {
          if (!select(ci, row, j)) continue;
          const u = (ci + DOT.u0 + j * DOT.du) / 16, v = DOT.v0 + row * DOT.dv;
          quadAt(u - DOT.w / 32, v - DOT.h / 2, u + DOT.w / 32, v + DOT.h / 2);
        }
      }
    }
    c.fillStyle = color;
    c.fill();
  };
  const on = (ch, row, j) => (FONT[ch] || FONT[' '])[row * 5 + j] === '1';
  const changed = new Set();
  if (from) for (let i = 0; i < 16; i++) if (from[i] !== text[i]) changed.add(i);
  layer(() => true, 'rgba(52,78,44,0.07)');
  layer((ci, row, j) => !changed.has(ci) && on(text[ci], row, j), 'rgba(40,58,48,0.9)');
  if (changed.size) {
    layer((ci, row, j) => changed.has(ci) && on(from[ci], row, j) && !on(text[ci], row, j), `rgba(40,58,48,${0.9 * (1 - k)})`);
    layer((ci, row, j) => changed.has(ci) && on(text[ci], row, j) && !on(from[ci], row, j), `rgba(40,58,48,${0.9 * eo(k)})`);
    layer((ci, row, j) => changed.has(ci) && on(text[ci], row, j) && on(from[ci], row, j), 'rgba(40,58,48,0.9)');
  }
}

// Mock HAND: unscharfe Hand nah vor dem Objektiv, von rechts.
const HAND_X = 920, HAND_Y = 140;
function makeHand(doc) {
  const canvas = doc.createElement('canvas');
  canvas.width = 560;
  canvas.height = 640;
  const c = canvas.getContext('2d');
  c.translate(-HAND_X, -HAND_Y);
  const F = [[1105, 305, 122, 34, -0.2], [1093, 386, 124, 35, -0.04], [1097, 466, 120, 34, 0.07], [1112, 542, 102, 31, 0.22], [1150, 628, 92, 36, 0.7]];
  const shape = (dx, dy) => {
    c.beginPath(); c.ellipse(1250 + dx, 435 + dy, 150, 225, 0, 0, 7); c.fill();
    for (const [x, y, rx, ry, a] of F) { c.beginPath(); c.ellipse(x + dx, y + dy, rx, ry, a, 0, 7); c.fill(); }
  };
  c.filter = 'blur(20px)'; c.fillStyle = 'rgba(18,14,10,.5)'; shape(-26, 20);
  c.filter = 'blur(8px)';
  const g = c.createLinearGradient(980, 0, 1400, 0);
  g.addColorStop(0, '#c8977c'); g.addColorStop(0.45, '#d5a68b'); g.addColorStop(1, '#a77560');
  c.fillStyle = g; shape(0, 0);
  c.filter = 'blur(7px)'; c.strokeStyle = 'rgba(120,78,60,.55)'; c.lineWidth = 5;
  for (const [x, y, rx, ry, a] of F.slice(0, 4)) { c.beginPath(); c.ellipse(x, y, rx, ry, a, Math.PI * 0.6, Math.PI * 1.4); c.stroke(); }
  return canvas;
}

async function decode(url, fetchImpl) {
  const response = await fetchImpl(url);
  if (!response.ok) throw new Error(`Übungsbild ${url}: HTTP ${response.status}`);
  return globalThis.createImageBitmap(await response.blob());
}

// base: URL-Basis der Bilder (Verzeichnis von practice/). Rueckgabe
// {ready: Promise, get(bitmapSource) -> Canvas|null}.
export function createFrameComposer({doc = globalThis.document, base = new URL('./', import.meta.url).href,
  fetchImpl = (...args) => fetch(...args)} = {}) {
  const images = {still: null, plate: null, hand: null};
  const cache = new Map();
  const ready = Promise.all([decode(new URL('still.jpg', base).href, fetchImpl), decode(new URL('plate.jpg', base).href, fetchImpl)])
    .then(([still, plate]) => { images.still = still; images.plate = plate; images.hand = makeHand(doc); });

  function compose(src, key) {
    const canvas = doc.createElement('canvas');
    canvas.width = OUT_W;
    canvas.height = OUT_H;
    const c = canvas.getContext('2d');
    c.fillStyle = '#0d0c0b';
    c.fillRect(0, 0, OUT_W, OUT_H);
    c.scale(SCALE, SCALE);
    const filter = [src.blur > 0.05 ? `blur(${(src.blur * SCALE).toFixed(2)}px)` : '',
      Math.abs(src.bright - 1) > 0.004 ? `brightness(${src.bright.toFixed(3)})` : ''].filter(Boolean).join(' ');
    if (filter) c.filter = filter;
    if (src.bump) {
      c.translate(720, 405);
      c.rotate((src.bump * 0.8 * Math.PI) / 180);
      c.translate(-720 + 10 * src.bump, -405 - 9 * src.bump);
    }
    c.drawImage(images.still, 0, 0, SRC_W, SRC_H);
    c.drawImage(images.plate, PLATE_AT[0], PLATE_AT[1]);
    drawLCD(c, src.lcd.text, src.lcd.from, src.lcd.k);
    if (src.hand > 0) {
      c.globalAlpha = Math.min(1, src.hand * 1.15);
      c.drawImage(images.hand, HAND_X + (1 - src.hand) * 320, HAND_Y);
      c.globalAlpha = 1;
    }
    cache.set(key, canvas);
    while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
    return canvas;
  }

  return {
    ready,
    get(src) {
      if (!images.still || !src) return null;
      // Stufen statt jedes Zwischenwerts: wenige Bilder, gleicher Eindruck.
      const norm = {lcd: {text: src.lcd?.text || '', from: src.lcd?.from || null, k: src.lcd?.from ? q(src.lcd.k ?? 1, 0.5) : 1},
        hand: q(src.hand || 0, 0.25), bump: q(src.bump || 0, 0.5), blur: q(src.blur || 0, 0.5), bright: q(src.bright ?? 1, 0.02)};
      const key = JSON.stringify(norm);
      const hit = cache.get(key);
      if (hit) {
        cache.delete(key);
        cache.set(key, hit);
        return hit;
      }
      return compose(norm, key);
    },
  };
}
