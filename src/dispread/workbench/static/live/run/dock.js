// Dock links im Lauf (Spec "Aufbau der Oberflaeche"/"Lauf", Mock-Kapitel 8):
// Laufdaten, Statusanteile je Bild (run.counts), Referenz und Werteplan; nach
// dem Stopp die Zusammenfassung mit Endgrund und Ablage. Fehllesungen gegen
// die Referenz erst nach Laufende (Spec OP-1), vorher "Abgleich nach Laufende".
import {dec, esc, grp} from '../shell.js';

export const STATUS_ROWS = [
  ['valid', 'ok', 'Freigegeben', 'VALID'], ['transition', 'warn', 'Wechselt', 'TRANSITION'],
  ['unreadable', 'err', 'Unlesbar', 'UNREADABLE'], ['stale', 'stale', 'Veraltet', 'STALE'],
];
const CLS_TONE = {V: 'ok', T: 'warn', U: 'err', S: 'stale', X: 'stale'};
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const num = (x) => (finite(x) ? grp(x) : '–');

// "run-01" -> "Lauf 01"
export function runTitle(status) {
  const match = /^run-(\d+)$/.exec(status?.run?.dir || '');
  return match ? `Lauf ${match[1]}` : 'Lauf';
}

export function scheduleText(schedule) {
  if (!Array.isArray(schedule) || !schedule.length) return 'kein';
  return schedule.map(([factor, seconds]) => `${factor}:${seconds}`).join(', ');
}

// Fehllesungen: erst nach Laufende, aus der bestehenden Auswertung, falls
// der Status sie traegt (reference_eval); sonst ehrlich "–".
export function misreadText(status) {
  if (status?.state !== 'stopped') return {text: 'Abgleich nach Laufende', cls: 'mut', mono: false};
  const misreads = status?.reference_eval?.misreads;
  if (!finite(misreads)) {
    return {text: '–', cls: 'mut', mono: true, title: 'Auswertung (reference_eval) liegt im Status nicht vor'};
  }
  return {text: grp(misreads), cls: misreads === 0 ? 'ok-t' : 'err-t', mono: true};
}

export function referenceLine(reference) {
  // Texte aus static/live.js (woertlich).
  if (reference?.restoring) return 'Werte werden zurückgestellt …';
  if (reference?.error) return reference.error;
  if (reference?.enabled) return `Referenz: ${reference.lines} Telegramme`;
  return `ohne Referenz: ${reference?.reason || 'nicht gestartet'}`;
}

export function runDockHTML(status, {resultCls = 'X'} = {}) {
  const run = status?.run || {};
  const summary = run.summary || {};
  const counts = run.counts || {};
  const total = STATUS_ROWS.reduce((sum, [key]) => sum + (finite(counts[key]) ? counts[key] : 0), 0);
  const stopped = status?.state === 'stopped';
  const head = stopped
    ? `<div class="endbox"><b>Lauf beendet</b>${summary.end_reason
      ? `<span>Endgrund <span class="mono">${esc(summary.end_reason)}</span></span>` : ''}` +
      `${status?.error ? `<span class="err-t">${esc(status.error)}</span>` : ''}</div>`
    : `<div class="runhead"><span class="sq ${CLS_TONE[resultCls] || 'stale'}"></span><b>${status?.test_run ? 'Testlauf läuft' : 'Lauf läuft'}</b>` +
      `<span class="mut mono">${esc(run.dir || '')}</span></div>`;
  const facts = `<dl class="kv"><dt>Bilder</dt><dd>${num(summary.frames_read)}</dd>` +
    `<dt>Lücken</dt><dd>${num(summary.frame_gaps)}</dd><dt>Übersprungen</dt><dd>${num(summary.frames_skipped)}</dd>` +
    `<dt>Datensätze</dt><dd>${num(total)}</dd><dt>Marken</dt><dd>${num(summary.marks)}</dd></dl>`;
  const rows = STATUS_ROWS.map(([key, tone, word, code]) => {
    const n = finite(counts[key]) ? counts[key] : 0;
    return `<tr data-status="${key}"><td><span class="sq ${tone}"></span></td><td>${word}<span class="code">${code}</span></td>` +
      `<td class="n">${grp(n)}</td><td class="p">${total ? `${dec((100 * n) / total, 1)} %` : '–'}</td></tr>`;
  }).join('');
  const share = total ? STATUS_ROWS.map(([key, tone]) => {
    const n = finite(counts[key]) ? counts[key] : 0;
    return n ? `<i class="${tone}" style="width:${((100 * n) / total).toFixed(3)}%"></i>` : '';
  }).join('') : '';
  const misread = misreadText(status);
  const reference = status?.reference || {};
  const compared = status?.reference_eval?.compared_valid;
  const comparison = `<div class="sect kvf">` +
    `<div><span>Fehllesungen gegen Referenz</span><b class="${misread.cls}${misread.mono ? '' : ' t'}"` +
    `${misread.title ? ` title="${esc(misread.title)}"` : ''}>${esc(misread.text)}</b></div>` +
    (stopped && finite(compared) ? `<div><span>Verglichen</span><b>${grp(compared)}</b></div>` : '') +
    `<div><span>Referenz</span><b class="t">${esc(referenceLine(reference))}</b></div>` +
    `<div><span>Werteplan</span><b>${esc(scheduleText(reference.norm_schedule))}</b></div></div>`;
  const storage = stopped
    ? `<div class="sect"><dl class="kv"><dt>Ablage</dt><dd class="wrap">${esc([status?.session_id, run.dir].filter(Boolean).join('/') || '–')}</dd></dl></div>`
    : '';
  return head + facts +
    `<div class="sect"><div class="pt flat">Status<span class="pa">Anteil</span></div><table class="stt">${rows}</table>` +
    `<div class="share" aria-hidden="true">${share}</div></div>` + comparison + storage;
}
