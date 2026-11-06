// Zeitleiste des Laufs (Spec "Lauf", Mock-Kapitel 8): Statusband je
// 250-ms-Eimer, darueber die Wertspur nur aus freigegebenen Werten als
// Stufen, Ereignismarken. Rechter Rand = jetzt; ein Stillstand zeigt seine
// Luecke bis jetzt (Ruling R7), ein junger Lauf waechst von links.
//
// Achse: Client-Millisekunden (now(), standardmaessig performance.now()).
// seed(recent, recentNowMs) legt run.recent ueber recent_now_ms auf diese
// Achse; push und mark nehmen Client-Millisekunden.

export const BUCKET_MS = 250;
export const VIEW_MS = 40_000; // sichtbar (Spec: 40 s, scrollend)
export const KEEP_MS = 60_000; // so weit reicht run.recent
const CODES = {v: 'v', t: 't', u: 'u', s: 's', valid: 'v', transition: 't', unreadable: 'u', stale: 's'};
const RANK = {v: 0, t: 1, u: 2, s: 3};
const EPS_MS = 1;
// Farben = Spec-Tokens (Canvas kennt keine CSS-Variablen).
const COL = {v: '#55c46e', t: '#e5a535', u: '#ee5b4d', s: '#8f8a82', tx: '#ebe7e0', tx2: '#bab4aa', tx3: '#958f85', dock: '#1c1b19',
  grid: '#2a2825', axis: '#7e786f', sel: '#86aee8', err: '#ee5b4d'};
const MONO = '"Noto Sans Mono",monospace';
const SANS = '"Segoe UI","Noto Sans",sans-serif';
const PAD = 12;

const finite = (x) => typeof x === 'number' && Number.isFinite(x);

// Wertspur: Laeufe aneinandergrenzender v-Eimer werden zu Treppen
// ([[t, wert], ...]); ein Wertwechsel ist ein senkrechter Sprung an der
// Eimergrenze. Jeder andere Status und jede Luecke beendet die Spur dort.
// Werte nicht freigegebener Eimer erscheinen nie (Wahrheitsregel 3).
export function valueTrace(buckets, bucketMs = BUCKET_MS) {
  const runs = [];
  let run = null;
  let level = null;
  let end = null;
  const close = () => {
    if (run) { run.push([end, level]); runs.push(run); }
    run = null;
  };
  for (const [t, code, value] of buckets) {
    if (code !== 'v' || !finite(value)) { close(); continue; }
    if (run && Math.abs(t - end) <= EPS_MS) {
      if (value !== level) { run.push([t, level], [t, value]); level = value; }
    } else {
      close();
      run = [[t, value]];
      level = value;
    }
    end = t + bucketMs;
  }
  close();
  return runs;
}

// Geometrie fuer eine Breite in CSS-px. Fenster endet bei jetzt bzw. bei
// aeltestem Eimer + 40 s, solange der Lauf juenger ist.
export function layoutTimeline(buckets, marks, {nowMs, width, view = VIEW_MS, bucketMs = BUCKET_MS} = {}) {
  const oldest = buckets.length ? buckets[0][0] : nowMs;
  const t1 = Math.max(nowMs, oldest + view);
  const t0 = t1 - view;
  const span = Math.max(1, width - 2 * PAD);
  const pxPerMs = span / view;
  const x = (t) => PAD + (t - t0) * pxPerMs;
  const visible = buckets.filter(([t]) => t + bucketMs > t0 && t < t1);
  const bands = [];
  for (const [t, code] of visible) {
    const x0 = Math.max(PAD, x(t));
    const x1 = Math.min(PAD + span, x(t + bucketMs));
    const last = bands.at(-1);
    // Gleiche, aneinandergrenzende Eimer zu einem Rechteck zusammenfassen.
    if (last && last.code === code && Math.abs(last.x1 - x0) < 0.01) last.x1 = x1;
    else bands.push({code, x0, x1});
  }
  const trace = valueTrace(visible, bucketMs);
  const values = trace.flat().map(([, v]) => v);
  let lo = Math.min(0, ...values);
  let hi = Math.max(0, ...values);
  if (hi === lo) hi = lo + 1;
  const head = (hi - lo) * 0.12;
  const scale = {lo: lo < 0 ? lo - head : lo, hi: hi > 0 ? hi + head : hi, top: hi, bottom: lo};
  return {t0, t1, nowMs, pxPerMs, x, bands, trace, scale,
    marks: marks.filter((m) => m.t >= t0 && m.t <= t1).map((m) => ({...m, x: x(m.t)}))};
}

// Beschriftung einer Ereignismarke: rechts der Linie, sonst links; nie ueber
// den Rand und nie ueber eine Wertbeschriftung (boxes: {x0, x1, y0, y1}).
export const MARK_LABEL_Y = [2, 14];
export function placeMarkLabel(mx, width, W, boxes = []) {
  const [y0, y1] = MARK_LABEL_Y;
  const right = {x: mx + 4, align: 'left', x0: mx + 4, x1: mx + 4 + width};
  const left = {x: mx - 4, align: 'right', x0: mx - 4 - width, x1: mx - 4};
  const inside = (c) => c.x0 >= 0 && c.x1 <= W - PAD;
  const free = (c) => !boxes.some((b) => b.y0 < y1 && b.y1 > y0 && b.x0 < c.x1 && b.x1 > c.x0);
  return [right, left].find((c) => inside(c) && free(c)) || [right, left].find(inside) || left;
}

const pad2 = (n) => String(n).padStart(2, '0');
function clock(ms) {
  const d = new Date(ms);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}
const fmt = (v) => String(Math.round(v * 1e5) / 1e5);

export function createTimeline(canvas, {now = () => performance.now(), wallNow = () => Date.now(), view = VIEW_MS} = {}) {
  let buckets = [];
  let marks = [];
  let frozen = null;
  let frozenWall = null;
  let unit = '';
  let running = true;
  const current = () => (frozen === null ? now() : frozen);
  const prune = () => {
    const limit = current() - KEEP_MS;
    while (buckets.length && buckets[0][0] + BUCKET_MS <= limit) buckets.shift();
    marks = marks.filter((m) => m.t >= limit);
  };

  const api = {
    // run.recent ([[t_ms, code, wert], ...]) auf die Client-Achse legen;
    // recent_now_ms ist "jetzt" auf der Achse von recent.
    seed(recent, recentNowMs = null) {
      if (!Array.isArray(recent)) return;
      const rows = recent.filter((row) => Array.isArray(row) && finite(row[0]) && CODES[row[1]]);
      const anchor = finite(recentNowMs) ? recentNowMs
        : rows.length ? rows.at(-1)[0] + BUCKET_MS : 0;
      const offset = current() - anchor;
      buckets = rows.map(([t, code, value]) => [t + offset, CODES[code], finite(value) ? value : null]);
      prune();
      api.draw();
    },
    // Einzelnes Bild (Client-ms): schlechtester Status je Eimer, letzter freigegebener Wert.
    push(tMs, status, value) {
      const code = CODES[status] || 'u';
      const last = buckets.at(-1);
      let start = last ? last[0] + Math.floor((tMs - last[0]) / BUCKET_MS) * BUCKET_MS
        : Math.floor(tMs / BUCKET_MS) * BUCKET_MS;
      if (last && start < last[0]) start = last[0]; // nie rueckwaerts einsortieren
      const released = code === 'v' && finite(value) ? value : null;
      if (last && Math.abs(start - last[0]) <= EPS_MS) {
        if (RANK[code] > RANK[last[1]]) last[1] = code;
        if (released !== null) last[2] = released;
      } else {
        buckets.push([start, code, released]);
      }
      prune();
    },
    mark(tMs, label, kind = 'mark') {
      marks.push({t: tMs, label: String(label ?? ''), kind});
      prune();
      api.draw();
    },
    clear() { buckets = []; marks = []; frozen = frozenWall = null; running = true; api.draw(); },
    // Laufende: Zeit anhalten (rechter Rand und Uhrzeiten der Achse bleiben stehen).
    freeze(on) {
      if (on && frozen === null) { frozen = now(); frozenWall = wallNow(); }
      if (!on) frozen = frozenWall = null;
      running = !on;
    },
    setUnit(next) { unit = next || ''; },
    buckets: () => buckets.map((b) => [...b]),
    layout: (width) => layoutTimeline(buckets, marks, {nowMs: current(), width, view}),
    draw() {
      if (!canvas || typeof canvas.getContext !== 'function') return;
      const rect = canvas.getBoundingClientRect();
      const W = Math.round(rect.width);
      const H = Math.round(rect.height);
      if (!W || !H) return;
      const dpr = globalThis.devicePixelRatio || 1;
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const wall = (t) => (frozenWall ?? wallNow()) - (current() - t);
      paint(ctx, api.layout(W), {W, H, unit, running, wall});
    },
  };
  if (canvas) canvas.timeline = api;
  return api;
}

function paint(ctx, layout, {W, H, unit, running, wall}) {
  const {x, bands, trace, scale, marks, t0, t1} = layout;
  // Hoehen wie im Mock (Zeichenflaeche ~91 px): Marken oben, Wertspur, Band, Achse.
  const by = Math.max(40, H - 33);
  const bh = 12;
  const ty0 = 25; // unter der Zeile der Markenbeschriftung
  const ty1 = by - 6;
  const y = (v) => ty1 - ((v - scale.lo) / (scale.hi - scale.lo)) * (ty1 - ty0);
  ctx.lineWidth = 1;
  // Nulllinie und Oberkante der Werte, beschriftet rechts.
  ctx.strokeStyle = COL.grid;
  ctx.beginPath();
  const levels = [...new Set([0, scale.top, scale.bottom])];
  for (const v of levels) {
    const yy = Math.round(y(v)) + 0.5;
    ctx.moveTo(PAD, yy);
    ctx.lineTo(W - PAD, yy);
  }
  ctx.stroke();
  ctx.textBaseline = 'alphabetic';
  // Wertbeschriftung rechts; gezeichnet wird sie zuletzt auf Dock-Grund,
  // damit Marken und Spur sie nicht kreuzen. Laege sie auf der Jetzt-Linie
  // (Lauf fuellt das Fenster), rueckt sie links davor, statt die Linie zu unterbrechen.
  ctx.font = `10.5px ${MONO}`;
  const nowX = running && layout.nowMs <= t1 ? Math.round(x(layout.nowMs)) + 0.5 : null;
  const valueLabels = levels.map((v) => {
    const text = v === 0 ? '0' : `${fmt(v)}${unit ? ` ${unit}` : ''}`;
    const ly = Math.round(y(v)) - 3;
    const w = ctx.measureText(text).width;
    let right = W - PAD;
    if (nowX !== null && nowX >= right - w - 6 && nowX <= right + 3) right = Math.floor(nowX - 6);
    return {text, ly, right, x0: right - w - 3, x1: right, y0: ly - 9, y1: ly + 2};
  });
  // Statusband.
  for (const band of bands) {
    ctx.fillStyle = COL[band.code];
    ctx.fillRect(band.x0, by, Math.max(1, band.x1 - band.x0), bh);
  }
  // Wertspur: Stufen, nie geglaettet, nur freigegebene Werte.
  ctx.strokeStyle = COL.tx;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (const run of trace) {
    run.forEach(([t, v], i) => {
      const px = Math.min(W - PAD, Math.max(PAD, x(t)));
      if (i === 0) ctx.moveTo(px, y(v)); else ctx.lineTo(px, y(v));
    });
  }
  ctx.stroke();
  ctx.lineWidth = 1;
  // Ereignismarken.
  ctx.font = `11px ${SANS}`;
  for (const m of marks) {
    const mx = Math.round(m.x) + 0.5;
    const color = m.kind === 'stoerung' ? COL.err : m.kind === 'plan' ? COL.tx2 : COL.sel;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(mx, 2);
    ctx.lineTo(mx, by + bh);
    ctx.stroke();
    ctx.fillStyle = color;
    const label = m.label.length > 28 ? `${m.label.slice(0, 27)}…` : m.label;
    const place = placeMarkLabel(mx, ctx.measureText(label).width, W, valueLabels);
    ctx.textAlign = place.align;
    ctx.fillText(label, place.x, 12);
    ctx.textAlign = 'left';
  }
  // Zeitachse (Uhrzeit des Clients) alle 5 s.
  ctx.fillStyle = COL.tx3;
  ctx.font = `11px ${MONO}`;
  const shift = wall(t0) - t0; // Client-Achse -> Uhrzeit; Striche auf vollen 5 s der Uhr
  for (let w = Math.ceil(wall(t0) / 5000) * 5000; w - shift <= t1; w += 5000) {
    const t = w - shift;
    const tx = Math.round(x(t));
    ctx.fillRect(tx, by + bh + 2, 1, 4);
    if (tx + 60 < W) ctx.fillText(clock(wall(t)), tx + 3, by + bh + 15);
  }
  if (nowX !== null) {
    ctx.strokeStyle = COL.tx;
    ctx.beginPath();
    ctx.moveTo(nowX, ty0 - 4);
    ctx.lineTo(nowX, by + bh + 2);
    ctx.stroke();
  }
  ctx.font = `10.5px ${MONO}`;
  ctx.textAlign = 'right';
  for (const label of valueLabels) {
    ctx.fillStyle = COL.dock;
    ctx.fillRect(label.x0, label.y0, label.x1 - label.x0, label.y1 - label.y0);
    ctx.fillStyle = COL.axis;
    ctx.fillText(label.text, label.right, label.ly);
  }
  ctx.textAlign = 'left';
}
