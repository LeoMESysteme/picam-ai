// Zeitleiste der Einrichtung (Spec "Aufbau der Oberflaeche": Zeitleiste
// Einrichtung = Schritte; Mock-Kapitel 2 und 6, #t=10 und #t=46):
// Schrittspur aus setup.progress.steps[].elapsed_s, Fokusproben als Striche,
// Abspielkopf beim aktuellen Stand. Keine Uhrzeiten, nur Sekunden seit dem
// Start der Einrichtung.
//
// Gemessen sind nur die Dauern der Schritte. Noch nicht begonnene Schritte
// (und Pruefen & Bestaetigen) stehen mit einer geplanten Breite (NOMINAL_S,
// Mock-Zeitachse) da; sie ist reine Gestaltung, nie eine Zeitangabe. Die
// Fokusproben tragen im Status keine Zeit: ihre Striche zeigen Zahl und
// Reihenfolge, gleichmaessig ueber den gemessenen Teil des Fokusschritts.
import {stepRows} from '../model.js';

// Geplante Breiten in Sekunden (Mock: Fokus 14, Kamera 2, Belichtung 4,
// Standbilder 27 mit Ruhezeit, Vorschlag 3, Bestaetigen als Rest).
export const NOMINAL_S = {fokus: 14, kamera: 2, belichtung: 4, standbilder: 27, vorschlag: 3, bestaetigen: 6};
const STATES = ['setup_running', 'setup_ready', 'setup_failed', 'confirmed'];
const SHORT = {bestaetigen: 'Bestätigen'};
const PAD = 12;
// Farben = Spec-Tokens bzw. Mock-Toene der Schrittspur (Canvas kennt keine CSS-Variablen).
const COL = {
  done: ['#2a3a2d', '#a9d8b3'], running: ['#26344a', '#dfe8f6'], pending: ['#23221f', '#958f85'],
  failed: ['#3a2320', '#ffb4a9'], fill: '#35507a', failFill: '#6a3129', sel: '#86aee8', tx: '#ebe7e0', tx3: '#958f85',
};
const SANS = '"Segoe UI","Noto Sans",sans-serif';
const MONO = '"Noto Sans Mono",monospace';
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

// {segments: [{key, label, state, t0, t1, fill}], probes: [s], playhead, span} oder null.
export function setupTimelineModel(status) {
  if (!STATES.includes(status?.state)) return null;
  const steps = status.setup?.progress?.steps;
  if (!Array.isArray(steps) || !steps.length) return null;
  const segments = [];
  let t = 0;
  let playhead = 0;
  for (const row of stepRows(status)) {
    const nominal = NOMINAL_S[row.key] ?? 3;
    const measured = finite(row.elapsed_s) ? Math.max(0, row.elapsed_s) : null;
    let duration = nominal;
    let fill = t;
    if (row.state === 'done' && row.key !== 'bestaetigen') {
      duration = measured ?? nominal;
      fill = t + duration;
      playhead = fill;
    } else if (row.state === 'failed') {
      duration = measured ?? 0;
      fill = t + duration;
      playhead = fill;
    } else if (row.state === 'running' && row.key !== 'bestaetigen') {
      duration = Math.max(measured ?? 0, nominal);
      fill = t + (measured ?? 0);
      playhead = fill;
    } else if (row.key === 'bestaetigen' && row.state !== 'pending') {
      // Pruefen & Bestaetigen: Zeit wird nicht gemessen; der Kopf steht an seinem Anfang.
      playhead = t;
    }
    segments.push({key: row.key, label: SHORT[row.key] || row.label, state: row.state, t0: t, t1: t + duration, fill});
    t += duration;
  }
  const focus = segments.find((s) => s.key === 'fokus');
  const samples = Array.isArray(status.setup.focus?.samples) ? status.setup.focus.samples : [];
  const measuredFocus = focus ? focus.fill - focus.t0 : 0;
  const probes = focus && measuredFocus > 0
    ? samples.map((_, i) => focus.t0 + (measuredFocus * (i + 0.5)) / samples.length) : [];
  return {segments, probes, playhead, span: Math.max(t, 1)};
}

// ctx in CSS-px; Hoehen wie im Mock (Zeichenflaeche ~91 px).
export function paintSetupTimeline(ctx, model, {W, H}) {
  if (!model) return;
  const x = (s) => PAD + (s / model.span) * (W - 2 * PAD);
  const top = 22, h = Math.min(22, Math.max(14, H - 69));
  const tickY = top + h + 4;
  const axisY = Math.min(H - 25, tickY + 14);
  ctx.textBaseline = 'alphabetic';
  ctx.textAlign = 'left';
  ctx.fillStyle = COL.tx3;
  ctx.font = `11.5px ${SANS}`;
  ctx.fillText('Fokusproben', PAD, 14);
  for (const seg of model.segments) {
    const x0 = x(seg.t0), x1 = x(seg.t1);
    const [bg, fg] = COL[seg.state] || COL.pending;
    ctx.fillStyle = bg;
    ctx.fillRect(x0 + 1, top, Math.max(1, x1 - x0 - 2), h);
    if (seg.state === 'running' && seg.fill > seg.t0) {
      ctx.fillStyle = COL.fill;
      ctx.fillRect(x0 + 1, top, Math.max(1, x(seg.fill) - x0 - 1), h);
    }
    ctx.font = `12px ${SANS}`;
    // Beschriftung nur, wenn sie ganz in den Abschnitt passt.
    if (ctx.measureText(seg.label).width < x1 - x0 - 10) {
      ctx.fillStyle = fg;
      ctx.fillText(seg.label, x0 + 6, top + h / 2 + 4);
    }
  }
  ctx.fillStyle = COL.sel;
  for (const t of model.probes) ctx.fillRect(Math.round(x(t)), tickY, 1, 6);
  ctx.fillStyle = COL.tx3;
  ctx.font = `11px ${MONO}`;
  for (let s = 0; s <= model.span; s += 10) {
    const ax = Math.round(x(s));
    ctx.fillRect(ax, axisY, 1, 4);
    if (ax + 34 < W) ctx.fillText(mmss(s), ax + 3, axisY + 14);
  }
  const hx = Math.round(x(Math.min(model.playhead, model.span))) + 0.5;
  ctx.strokeStyle = COL.tx;
  ctx.lineWidth = 1;
  // Unter der Beschriftungszeile beginnen, damit die Kappe nie den Text kreuzt.
  ctx.beginPath();
  ctx.moveTo(hx, top - 5);
  ctx.lineTo(hx, axisY - 2);
  ctx.stroke();
  ctx.fillStyle = COL.tx;
  ctx.fillRect(hx - 3.5, top - 6, 7, 3);
}

// Zeichnet auf die Canvas der Zeitleiste (Groesse aus dem Layout, dpr-scharf).
export function drawSetupTimeline(canvas, status) {
  if (!canvas || typeof canvas.getContext !== 'function') return;
  const rect = canvas.getBoundingClientRect();
  const W = Math.round(rect.width), H = Math.round(rect.height);
  if (!W || !H) return;
  const dpr = globalThis.devicePixelRatio || 1;
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  paintSetupTimeline(ctx, setupTimelineModel(status), {W, H});
}
