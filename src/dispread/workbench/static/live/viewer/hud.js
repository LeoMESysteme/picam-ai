// HUD des Viewers: zeichnet Anzeige-Viereck, Zellenraster, unsichere Zellen,
// Rahmenbereiche und das Wert-Etikett aus dem X-Hud des gerade gezeigten
// MJPEG-Teils, mit 1-px-Linien im Bildschirmraum (bei jedem Zoom scharf).
// Alle Zahlen in Etikett und Markierungs-Info kommen aus dem HUD; Konfidenz
// heisst "Spur" oder "Treffer", nie Wahrscheinlichkeit.
// Koordinaten im HUD sind Kamerabild-Pixel (hud.w × hud.h, 1920×1080).

export const LAYERS = [
  ['anzeige', 'Anzeige'], ['raster', 'Raster'], ['zellen', 'Zellen'],
  ['rahmen', 'Rahmenbereiche'], ['fokus', 'Fokus-ROI'], ['etikett', 'Wert-Etikett'],
];
export const ALL_LAYERS = new Set(LAYERS.map(([key]) => key));

// Farben = Spec-Tokens (Canvas kennt keine CSS-Variablen).
export const COL = {ok: '#55c46e', warn: '#e5a535', err: '#ee5b4d', stale: '#8f8a82', sel: '#86aee8',
  teal: '#30c6b7', mag: '#d65ccf', tx: '#ebe7e0'};
const STATUS = {
  valid: ['Freigegeben', 'ok'], transition: ['Wechselt', 'warn'],
  unreadable: ['Unlesbar', 'err'], stale: ['Veraltet', 'stale'],
};
// Displaytech 161A: 16 Zeichen × 1 Zeile; das HUD traegt kein Raster, nur das
// Viereck. Die Zellen sind deshalb 16 gleiche Teile des Vierecks.
export const CELLS = 16;
// Suchradius des Rahmen-Trackers (FrameTrackingConfig.search_radius_px). Der
// Laufstart verlangt die Standardkonfiguration, das HUD traegt ihn nicht;
// er bestimmt nur die gezeichnete Fenstergroesse, nie einen Infotext.
export const SEARCH_RADIUS_PX = 12;
const CORNERS = ['oben links', 'oben rechts', 'unten rechts', 'unten links'];
const SANS = '"Segoe UI","Noto Sans",sans-serif';
const MONO = '"Noto Sans Mono",monospace';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const dec = (x, digits) => x.toFixed(digits).replace('.', ',').replace(/^-/, '−');
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);

function validQuad(quad) {
  return Array.isArray(quad) && quad.length === 4 && quad.every((p) => Array.isArray(p) && finite(p[0]) && finite(p[1]));
}

// Projektive Abbildung Einheitsquadrat <-> Viereck (Ecken oben links,
// oben rechts, unten rechts, unten links).
export function homography(q) {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = q;
  const dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3;
  const dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
  let g = 0, h = 0;
  if (Math.abs(dx3) > 1e-9 || Math.abs(dy3) > 1e-9) {
    const den = dx1 * dy2 - dx2 * dy1;
    g = (dx3 * dy2 - dx2 * dy3) / den;
    h = (dx1 * dy3 - dx3 * dy1) / den;
  }
  const a = x1 - x0 + g * x1, b = x3 - x0 + h * x3, c = x0;
  const d = y1 - y0 + g * y1, e = y3 - y0 + h * y3, f = y0;
  const A = e - f * h, B = c * h - b, C = b * f - c * e, D = f * g - d, E = a - c * g, F = c * d - a * f;
  const G = d * h - e * g, H = b * g - a * h, I = a * e - b * d;
  return {
    map: (u, v) => { const w = g * u + h * v + 1; return [(a * u + b * v + c) / w, (d * u + e * v + f) / w]; },
    inv: (x, y) => { const w = G * x + H * y + I; return [(A * x + B * y + C) / w, (D * x + E * y + F) / w]; },
  };
}

const layerOn = (layers, key) => !layers || layers.has(key);
const cellsOf = (hud) => (Array.isArray(hud?.cells) ? hud.cells : []);
const regionsOf = (hud) => (Array.isArray(hud?.track?.regions) ? hud.track.regions
  .filter((r) => Array.isArray(r?.c) && finite(r.c[0]) && finite(r.c[1])) : []);

// Wert-Etikett (Wahrheitsregel 1): ein Wert aelter als 0,5 s oder ein Bild
// ohne Nachfolger seit 1,5 s ist Veraltet, nie Freigegeben. Eine
// Leser-Vermutung erscheint hier nie.
export function readoutTag(hud, {frameAgeS = 0} = {}) {
  const rec = hud?.rec;
  if (!rec) return null;
  let status = STATUS[rec.status] ? rec.status : 'unreadable';
  const fresh = finite(rec.age_s) && rec.age_s <= 0.5;
  if ((status === 'valid' && !fresh) || frameAgeS > 1.5) status = 'stale';
  const [word, tone] = STATUS[status];
  const value = status === 'valid' ? `${rec.text} ${rec.unit || ''}`.trim()
    : status === 'transition' ? 'Wert wechselt' : status === 'stale' ? 'veraltet' : 'kein Wert';
  const score = hud.track?.score;
  return {value, word, tone, spur: finite(score) ? `Spur ${dec(score, 2)}` : null};
}

// Markierungs-Info fuer eine Markierung, aus dem aktuellen HUD neu gebaut
// (angeheftete Infos laufen so mit jedem Bild mit).
export function markerInfo(hud, kind, index) {
  let title, rows = [], hint = null, tone = 'sel';
  if (kind === 'region') {
    const region = hud?.track?.regions?.[index];
    if (!region || !Array.isArray(region.c)) return null;
    title = `Rahmenbereich ${index + 1}`;
    tone = region.ok ? 'mag' : 'err';
    rows.push(['Suchfenster-Mitte', `${Math.round(region.c[0])}, ${Math.round(region.c[1])}`]);
    if (finite(region.peak)) rows.push(['Treffer', dec(region.peak, 2)]);
    if (finite(region.s)) rows.push(['Größe', `${region.s} px`]);
    if (!region.ok) {
      rows.push(['Zustand', 'kein Treffer']);
      hint = 'Kein Treffer im Suchfenster – verdeckt oder verschoben';
    } else {
      hint = 'Mitte des Suchfensters, nicht der Fundort des Treffers';
    }
  } else if (kind === 'cell') {
    const cell = cellsOf(hud).find((c) => c?.i === index);
    title = `Zelle ${index}`;
    if (cell) {
      if (typeof cell.best === 'string') rows.push(['Bestwert', cell.best === ' ' ? 'Leer' : cell.best]);
      if (finite(cell.margin)) rows.push(['Abstand', dec(cell.margin, 2)]);
      if (cell.uncertain) {
        rows.push(['Zustand', 'unsicher']);
        tone = 'warn';
        hint = 'Abstand unter null: Zeichen nicht eindeutig';
      }
    } else {
      hint = 'Für diese Zelle meldet der Leser nichts';
    }
  } else if (kind === 'corner') {
    const quad = hud?.track?.quad;
    if (!validQuad(quad) || !quad[index]) return null;
    title = `Anzeige-Ecke ${CORNERS[index]}`;
    rows.push(['Lage', `${dec(quad[index][0], 1)}, ${dec(quad[index][1], 1)}`]);
  } else {
    return null;
  }
  const info = [title, ...rows.map(([k, v]) => `${k} ${v}`)].join(' · ');
  return {kind, index, title, rows, hint, tone, info};
}

// Trifft [x, y] (Kamerabild-Pixel) eine Markierung? scale = Bildschirm-px je
// Bildpixel, damit kleine Ziele bei kleinem Zoom treffbar bleiben.
export function hitTest(hud, [x, y], {scale = 1, layers} = {}) {
  if (!hud?.track) return null;
  if (layerOn(layers, 'rahmen')) {
    const regions = hud.track.regions || [];
    for (let i = 0; i < regions.length; i += 1) {
      const r = regions[i];
      if (!Array.isArray(r?.c)) continue;
      const half = Math.max((finite(r.s) ? r.s : 15) / 2, 8 / scale);
      if (Math.abs(x - r.c[0]) <= half && Math.abs(y - r.c[1]) <= half) return markerInfo(hud, 'region', i);
    }
  }
  const quad = hud.track.quad;
  if (!validQuad(quad)) return null;
  if (layerOn(layers, 'anzeige')) {
    for (let i = 0; i < 4; i += 1) {
      if (Math.hypot(quad[i][0] - x, quad[i][1] - y) * scale < 9) return markerInfo(hud, 'corner', i);
    }
  }
  if (layerOn(layers, 'zellen') || layerOn(layers, 'raster') || layerOn(layers, 'anzeige')) {
    const [u, v] = homography(quad).inv(x, y);
    if (u >= 0 && u < 1 && v >= 0 && v <= 1) return markerInfo(hud, 'cell', Math.floor(u * CELLS));
  }
  return null;
}

// Kante auf Geraetepixel legen: 1-px-Linien bleiben bei jedem Zoom scharf.
function crisp(v, width, dpr) {
  const w = width * dpr;
  return (Math.round(v * dpr - w / 2) + w / 2) / dpr;
}

function poly(ctx, points, toS) {
  ctx.beginPath();
  points.forEach((p, i) => {
    const [a, b] = toS(p);
    if (i) ctx.lineTo(a, b); else ctx.moveTo(a, b);
  });
  ctx.closePath();
}

function strokeHalo(ctx, color, width) {
  ctx.lineWidth = width + 2.5;
  ctx.strokeStyle = 'rgba(0,0,0,.55)';
  ctx.stroke();
  ctx.lineWidth = width;
  ctx.strokeStyle = color;
  ctx.stroke();
}

function screenRect(ctx, [cx, cy], half, width, dpr) {
  const x0 = crisp(cx - half, width, dpr), y0 = crisp(cy - half, width, dpr);
  const x1 = crisp(cx + half, width, dpr), y1 = crisp(cy + half, width, dpr);
  ctx.beginPath();
  ctx.rect(x0, y0, x1 - x0, y1 - y0);
  return [x1, y0];
}

function badge(ctx, x, y, text, color) {
  ctx.font = `600 11px ${MONO}`;
  const w = ctx.measureText(text).width + 8;
  ctx.fillStyle = color;
  ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), 15);
  ctx.fillStyle = '#111';
  ctx.fillText(text, Math.round(x) + 4, Math.round(y) + 11);
}

function drawTag(ctx, tag, quad, view) {
  const toS = view.imageToScreen;
  const parts = [[tag.value, 'value'], [tag.word, 'word']];
  if (tag.spur) parts.push([tag.spur, 'spur']);
  const fontOf = (kind) => (kind === 'word' ? `600 12px ${SANS}` : `500 12px ${MONO}`);
  const width = parts.reduce((sum, [text, kind]) => {
    ctx.font = fontOf(kind);
    return sum + ctx.measureText(text).width + (kind === 'word' ? 28 : 16);
  }, 0);
  const color = COL[tag.tone];
  let tx, ty;
  if (quad) {
    // Fuehrungslinie von der Unterkante (8 % ab links) zum Etikett.
    const qa = toS(quad[3]), qb = toS(quad[2]);
    const ax = qa[0] + (qb[0] - qa[0]) * 0.08, ay = qa[1] + (qb[1] - qa[1]) * 0.08;
    tx = clamp(ax + 18, 6, view.width - width - 6);
    ty = clamp(ay + 26, 6, view.height - 30);
    ctx.beginPath();
    ctx.moveTo(Math.round(ax) + 0.5, Math.round(ay) + 0.5);
    ctx.lineTo(Math.round(ax) + 0.5, Math.round(ty) + 10.5);
    ctx.lineTo(Math.round(tx), Math.round(ty) + 10.5);
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(235,231,224,.7)';
    ctx.stroke();
    ctx.fillStyle = COL.tx;
    ctx.fillRect(Math.round(ax) - 1.5, Math.round(ay) - 1.5, 4, 4);
  } else {
    // Ohne Viereck (Nachfuehrung verloren) unter dem Quellen-Chip.
    tx = 10;
    ty = 42;
  }
  tx = Math.round(tx);
  ty = Math.round(ty);
  ctx.fillStyle = 'rgba(18,17,16,.93)';
  ctx.fillRect(tx, ty, Math.round(width), 21);
  ctx.lineWidth = 1;
  ctx.strokeStyle = color;
  ctx.strokeRect(tx + 0.5, ty + 0.5, Math.round(width) - 1, 20);
  let x = tx + 8;
  for (const [text, kind] of parts) {
    ctx.font = fontOf(kind);
    if (kind === 'word') {
      ctx.fillStyle = color;
      ctx.fillRect(x, ty + 6, 9, 9);
      x += 14;
      ctx.fillStyle = COL.tx;
    } else {
      ctx.fillStyle = kind === 'value' ? (tag.tone === 'stale' ? COL.stale : '#fff') : '#b9b4aa';
    }
    ctx.fillText(text, x, ty + 15);
    x += ctx.measureText(text).width + (kind === 'word' ? 14 : 16);
  }
}

// view: {imageToScreen([x, y]) -> [sx, sy] (CSS-px), width, height, scale,
// dpr, hover: {kind, index} | null, frameAgeS}. ctx steht auf CSS-px
// (setTransform(dpr, 0, 0, dpr, 0, 0)).
export function drawHud(ctx, hud, view, layers = ALL_LAYERS) {
  if (!hud) return;
  const toS = view.imageToScreen;
  const dpr = view.dpr || 1;
  const hover = view.hover || null;
  const track = hud.track || null;
  const tag = readoutTag(hud, {frameAgeS: view.frameAgeS || 0});
  const quad = validQuad(track?.quad) ? track.quad : null;
  ctx.save();
  ctx.lineJoin = 'miter';
  ctx.setLineDash([]);
  const quadColor = track?.correcting ? COL.teal : tag ? COL[tag.tone] : COL.sel;

  if (quad) {
    const H = homography(quad);
    if (layerOn(layers, 'raster')) {
      ctx.beginPath();
      for (let i = 1; i < CELLS; i += 1) {
        const a = toS(H.map(i / CELLS, 0)), b = toS(H.map(i / CELLS, 1));
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
      }
      ctx.lineWidth = 1;
      ctx.strokeStyle = tag ? 'rgba(235,231,224,.18)' : 'rgba(134,174,232,.38)';
      ctx.stroke();
    }
    const cellQuad = (i) => [H.map(i / CELLS, 0), H.map((i + 1) / CELLS, 0), H.map((i + 1) / CELLS, 1), H.map(i / CELLS, 1)];
    if (layerOn(layers, 'zellen')) {
      for (const cell of cellsOf(hud)) {
        if (!cell?.uncertain || !(cell.i >= 0 && cell.i < CELLS)) continue;
        poly(ctx, cellQuad(cell.i), toS);
        ctx.fillStyle = 'rgba(229,165,53,.20)';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = COL.warn;
        ctx.stroke();
      }
    }
    if (hover?.kind === 'cell' && hover.index >= 0 && hover.index < CELLS) {
      poly(ctx, cellQuad(hover.index), toS);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
      const [a, b] = toS(H.map((hover.index + 0.5) / CELLS, 0));
      ctx.font = `600 11px ${MONO}`;
      const label = String(hover.index);
      const w = ctx.measureText(label).width + 8;
      badge(ctx, a - w / 2, b - 19, label, '#fff');
    }
    if (layerOn(layers, 'anzeige')) {
      poly(ctx, quad, toS);
      strokeHalo(ctx, quadColor, 1.5);
      ctx.fillStyle = quadColor;
      quad.forEach((p, i) => {
        const [a, b] = toS(p);
        const size = hover?.kind === 'corner' && hover.index === i ? 8 : 6;
        ctx.fillRect(Math.round(a) - size / 2, Math.round(b) - size / 2, size, size);
      });
    }
  }

  if (track && layerOn(layers, 'rahmen')) {
    const regions = track.regions || [];
    regions.forEach((region, i) => {
      if (!Array.isArray(region?.c) || !finite(region.c[0]) || !finite(region.c[1])) return;
      const centre = toS(region.c);
      const half = (finite(region.s) ? region.s : 15) / 2;
      const lost = !region.ok;
      const hovered = hover?.kind === 'region' && hover.index === i;
      const color = lost ? COL.err : COL.mag;
      // Suchfenster nur am verlorenen oder gezeigten Bereich, sonst bleibt das Bild ruhig.
      if (lost || hovered) {
        screenRect(ctx, centre, (half + SEARCH_RADIUS_PX) * view.scale, 1, dpr);
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1;
        ctx.strokeStyle = lost ? 'rgba(238,91,77,.55)' : 'rgba(214,92,207,.6)';
        ctx.stroke();
        ctx.setLineDash([]);
      }
      const width = hovered ? 2 : 1;
      const corner = screenRect(ctx, centre, Math.max(half * view.scale, 3), width, dpr);
      if (lost) {
        ctx.fillStyle = 'rgba(238,91,77,.22)';
        ctx.fill();
      }
      strokeHalo(ctx, color, width);
      if (hovered) badge(ctx, corner[0] + 3, corner[1] - 1, String(i + 1), color);
    });
  }

  if (tag && layerOn(layers, 'etikett')) drawTag(ctx, tag, quad, view);
  ctx.restore();
}
