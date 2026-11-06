// Fokuskurve im Inspektor-Tab Fokus (Spec "Einrichtungs-Fortschritt und
// Fokuskurve", Mock-Kapitel 2, #t=10). Punkte kommen aus
// status.setup.focus.samples in Messreihenfolge, der Bestwert ist markiert.
// Die Schwellenlinie steht bei verify.threshold vom Server; fehlt verify
// (Suche laeuft noch oder die Gegenpruefung brach mit Fehler ab), steht sie
// bei 85 % des Maximums (live/setup.py FOCUS_VERIFY_RATIO). Ein
// Gegenpruefungswert wird nie erfunden.
import {esc} from '../shell.js';

// Spiegel von live/setup.py FOCUS_VERIFY_RATIO; der Status traegt nur den Schwellwert.
export const FOCUS_VERIFY_RATIO = 0.85;
const W = 330;
const H = 170;
const X0 = 38;
const X1 = W - 14;
const Y0 = 22;
const Y1 = H - 28;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const round = (value) => Math.round(value);

export function focusChartModel(focus) {
  const samples = (Array.isArray(focus?.samples) ? focus.samples : [])
    .filter((sample) => Array.isArray(sample) && finite(sample[0]) && finite(sample[1]));
  const points = samples.map(([f, s], i) => ({order: i + 1, focus: f, score: s, best: false}));
  const best = points.reduce((top, p) => (!top || p.score > top.score ? p : top), null);
  if (best) best.best = true;
  const v = focus?.verify;
  const verify = best && v && finite(v.score)
    ? {focus: best.focus, score: v.score, threshold: finite(v.threshold) ? v.threshold : null,
      passed: finite(v.threshold) ? v.score >= v.threshold : null}
    : null;
  let line = null;
  const ratioLabel = (value) => `${Math.round(FOCUS_VERIFY_RATIO * 100)} % = ${round(value)}`;
  if (v && finite(v.threshold)) {
    // Schwelle vom Server: "85 %" nur, wenn sie nachweislich 85 % des Probenmaximums ist.
    const derived = best && best.score > 0 && Math.abs(v.threshold / best.score - FOCUS_VERIFY_RATIO) < 1e-3;
    line = {value: v.threshold, source: 'verify', ratio: Boolean(derived),
      label: derived ? ratioLabel(v.threshold) : `Schwelle ${round(v.threshold)}`};
  } else if (best) {
    const value = FOCUS_VERIFY_RATIO * best.score;
    line = {value, source: 'maximum', ratio: true, label: ratioLabel(value)};
  }
  return {method: focus?.method || null, points, best, latest: points.at(-1) || null, verify, line};
}

function niceStep(span, maxTicks) {
  const raw = span / maxTicks;
  const power = 10 ** Math.floor(Math.log10(raw || 1));
  for (const k of [1, 2, 2.5, 5, 10]) if (k * power >= raw) return k * power;
  return 10 * power;
}

function xDomain(points) {
  if (!points.length) return [0, 100];
  let lo = Math.min(...points.map((p) => p.focus));
  let hi = Math.max(...points.map((p) => p.focus));
  if (hi - lo < 8) {
    const mid = (lo + hi) / 2;
    lo = mid - 4;
    hi = mid + 4;
  }
  return [lo, hi];
}

// Inhalt des <svg> (ohne Huelle); fuer node --test und renderFocusChart.
export function focusChartInner(focus, {running = false} = {}) {
  const model = focusChartModel(focus);
  const {points, best, latest, verify, line} = model;
  let g = '';
  if (!points.length) {
    return `<text class="cap" x="${W / 2}" y="${H / 2}" text-anchor="middle">Fokussuche: noch keine Probe</text>`;
  }
  const [fx0, fx1] = xDomain(points);
  const top = Math.max(...points.map((p) => p.score), verify?.score || 0, line?.value || 0) * 1.08;
  const yStep = niceStep(top, 4);
  const yMax = Math.ceil(top / yStep) * yStep;
  const x = (f) => X0 + ((f - fx0) / (fx1 - fx0)) * (X1 - X0);
  const y = (s) => Y1 - (s / yMax) * (Y1 - Y0);
  const px = (v) => v.toFixed(1);

  for (let s = 0; s <= yMax + 1e-9; s += yStep) {
    g += `<path class="gl" d="M${X0} ${px(y(s))}H${X1}"/><text x="${X0 - 6}" y="${px(y(s) + 3.5)}" text-anchor="end">${round(s)}</text>`;
  }
  const xStep = [1, 2, 4, 5, 8, 10, 20, 25, 50, 100, 200, 250, 500].find((k) => (fx1 - fx0) / k <= 5) || 1000;
  for (let f = Math.ceil(fx0 / xStep) * xStep; f <= fx1 + 1e-9; f += xStep) {
    g += `<text x="${px(x(f))}" y="${H - 14}" text-anchor="middle">${round(f)}</text>`;
  }
  g += `<text class="cap" x="${X1}" y="${H - 2}" text-anchor="end">focus_absolute</text>` +
    `<text class="cap" x="4" y="10">Schärfe</text>`;
  if (line) {
    const {label} = line;
    const ly = y(line.value);
    // Beschriftung an das Ende der Linie, an dem keine Probe in ihrer Naehe liegt.
    const LABEL_W = 74;
    const free = ([left, below]) => !points.some((p) => {
      const px0 = x(p.focus), py0 = y(p.score);
      const inX = left ? px0 <= X0 + LABEL_W : px0 >= X1 - LABEL_W;
      return inX && py0 > (below ? ly : ly - 16) - 4 && py0 < (below ? ly + 16 : ly) + 4;
    });
    const [left, below] = [[false, true], [true, true], [false, false], [true, false]].find(free) || [false, true];
    g += `<path class="thr" data-part="threshold" data-source="${line.source}" data-value="${round(line.value)}" ` +
      `d="M${X0} ${px(ly)}H${X1}"/><text class="thr-t" x="${left ? X0 + 4 : X1}" y="${px(below ? ly + 12 : ly - 5)}"` +
      `${left ? '' : ' text-anchor="end"'}>${esc(label)}</text>`;
  }
  const curve = [...points].sort((a, b) => a.focus - b.focus);
  if (curve.length > 1) {
    g += `<polyline class="curve" points="${curve.map((p) => `${px(x(p.focus))},${px(y(p.score))}`).join(' ')}"/>`;
  }
  if (running && latest) g += `<path class="now" d="M${px(x(latest.focus))} ${Y0 - 2}V${Y1}"/>`;
  for (const p of points) {
    g += `<rect class="smp${p.best ? ' best' : ''}${p === latest ? ' last' : ''}" data-sample="${p.order}"` +
      `${p.best ? ' data-best="true"' : ''} x="${px(x(p.focus) - 3)}" y="${px(y(p.score) - 3)}" width="6" height="6">` +
      `<title>Probe ${p.order} · focus_absolute ${round(p.focus)} · Schärfe ${round(p.score)}</title></rect>`;
  }
  if (verify) {
    g += `<rect class="ver${verify.passed === false ? ' fail' : ''}" data-part="verify" x="${px(x(verify.focus) - 3.5)}" ` +
      `y="${px(y(verify.score) - 3.5)}" width="7" height="7"><title>Gegenprüfung · Schärfe ${round(verify.score)}</title></rect>`;
  }
  if (best) {
    const right = x(best.focus) > (X0 + X1) / 2;
    g += `<text class="bt" x="${px(x(best.focus) + (right ? -9 : 9))}" y="${px(Math.max(Y0 + 2, y(best.score) - 7))}"` +
      `${right ? ' text-anchor="end"' : ''}>${round(best.focus)} → ${round(best.score)}</text>`;
  }
  return g;
}

export function focusChartSVG(focus, opts) {
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Schärfekurve">${focusChartInner(focus, opts)}</svg>`;
}

// svg: vorhandenes <svg class="chart">; zeichnet nur bei Aenderung neu.
export function renderFocusChart(svg, focus, opts = {}) {
  if (svg.getAttribute('viewBox') !== `0 0 ${W} ${H}`) svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const inner = focusChartInner(focus, opts);
  if (svg._inner !== inner) {
    svg._inner = inner;
    svg.innerHTML = inner;
  }
}
