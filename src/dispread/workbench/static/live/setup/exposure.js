// Belichtung im Inspektor (Spec "Einrichtungs-Fortschritt", Mock-Kapitel 4,
// #t=21): Pegel p80 als Balken im Band mit Ziel, dazu die Runden mit
// Belichtung, Gain und Weissabgleich aus status.setup.exposure.
import {EXPOSURE_MAX_ROUNDS} from '../model.js';
import {esc} from '../shell.js';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const W = 330;
const L = 8;
const R = W - 12;
const X = (v) => L + (Math.min(255, Math.max(0, v)) / 255) * (R - L);
const px = (v) => v.toFixed(1);
const show = (value, unit = '') => (value === undefined || value === null ? '–' : `${value}${unit}`);

function gauge(level, band, target) {
  let g = `<svg class="gauge chart" viewBox="0 0 ${W} 54" role="img" aria-label="Pegel p80${finite(level) ? ` ${Math.round(level)}` : ''}">` +
    `<rect class="track" x="${L}" y="14" width="${R - L}" height="12"/>`;
  if (band) g += `<rect class="band" x="${px(X(band[0]))}" y="14" width="${px(X(band[1]) - X(band[0]))}" height="12"/>`;
  if (finite(target)) g += `<path class="target" d="M${px(X(target))} 10V30"/>`;
  if (finite(level)) {
    const inside = band ? level >= band[0] && level <= band[1] : false;
    g += `<rect class="lvl${inside ? ' in' : ''}" x="${L}" y="17" width="${px(X(level) - L)}" height="6"/>` +
      `<path class="cur" d="M${px(X(level))} 8V32"/>` +
      `<text class="lv" x="${px(X(level) + 4)}" y="9">p80 ${Math.round(level)}</text>`;
  }
  g += `<text x="${L}" y="46">0</text>`;
  if (band) {
    g += `<text x="${px(X(band[0]))}" y="46" text-anchor="middle">${band[0]}</text>` +
      `<text x="${px(X(band[1]))}" y="46" text-anchor="middle">${band[1]}</text>`;
  }
  return `${g}<text x="${R}" y="46" text-anchor="end">255</text></svg>`;
}

// state: Zustand des Schritts belichtung (running|done|failed|pending).
export function exposureHTML(exposure, {state = 'done'} = {}) {
  const rounds = Array.isArray(exposure?.rounds) ? exposure.rounds : [];
  const band = Array.isArray(exposure?.band) && exposure.band.length === 2 ? exposure.band : null;
  const target = exposure?.target;
  const last = rounds.at(-1) || null;
  const level = finite(last?.level) ? last.level : null;
  const current = state === 'running' ? Math.min(rounds.length + 1, EXPOSURE_MAX_ROUNDS) : rounds.length;
  const intro = band && finite(target)
    ? `Helligkeit im Glasbereich (p80) soll im Band ${band[0]}–${band[1]} liegen, Ziel ${target}.`
    : 'Helligkeit im Glasbereich (p80).';
  const status = level === null ? (finite(target) ? `Ziel p80 ${target} · erste Messung läuft` : 'erste Messung läuft') : '';
  const controls = last?.controls || {};
  let html = `<div class="ins"><h3>Belichtung</h3><p>${esc(intro)}</p>${gauge(level, band, target)}` +
    (status ? `<p class="mut">${esc(status)}</p>` : '') + '</div>' +
    `<div class="blk"><dl class="kv2"><dt>Runde</dt><dd>${current}/${EXPOSURE_MAX_ROUNDS}</dd>` +
    `<dt>Belichtung</dt><dd>${esc(show(controls.exposure_time_absolute))}</dd>` +
    `<dt>Gain</dt><dd>${esc(show(controls.gain))}</dd>` +
    `<dt>Weißabgleich</dt><dd>${esc(show(controls.white_balance_temperature, ' K'))}</dd></dl></div>`;
  if (rounds.length > 1) {
    html += '<div class="blk flush"><table class="grid"><thead><tr><th>Runde</th><th class="r">p80</th>' +
      '<th class="r">Belichtung</th><th class="r">Gain</th><th class="r">Weißabgleich</th></tr></thead><tbody>' +
      rounds.map((round, i) => `<tr><td class="m">${i + 1}</td><td class="m r">${finite(round.level) ? Math.round(round.level) : '–'}</td>` +
        `<td class="m r">${esc(show(round.controls?.exposure_time_absolute))}</td><td class="m r">${esc(show(round.controls?.gain))}</td>` +
        `<td class="m r">${esc(show(round.controls?.white_balance_temperature, ' K'))}</td></tr>`).join('') +
      '</tbody></table></div>';
  }
  return html;
}

export function renderExposure(host, exposure, opts) {
  const html = exposureHTML(exposure, opts);
  if (host._html !== html) {
    host._html = html;
    host.innerHTML = html;
  }
}
