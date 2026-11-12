// Dock links im Lauf (Spec "Aufbau der Oberflaeche"/"Lauf", Mock-Kapitel 8):
// Laufdaten, Statusanteile je Bild (run.counts), Referenz und Werteplan; nach
// dem Stopp die Zusammenfassung mit Endgrund und Ablage. Fehllesungen gegen
// die Referenz erst nach Laufende (Spec OP-1), vorher "Abgleich nach Laufende".
import {dec, esc, grp} from '../shell.js';
import {FORMAT_WARNING, configText, isFourChannel, markerText, isOff, outputLines, outputTone, tickLine} from './output.js';

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

// Abgleich gegen die Referenz (Spec OP-1): im Lauf nur "Abgleich nach
// Laufende"; danach aus reference_eval: laeuft, fertig mit Zahlen, Fehler
// woertlich. Zeilen [Bezeichnung, Text, Klasse, mono].
export function comparisonRows(status) {
  const label = 'Fehllesungen gegen Referenz';
  if (status?.state !== 'stopped') return [[label, 'Abgleich nach Laufende', 'mut', false]];
  const result = status?.reference_eval;
  if (result?.state === 'running') return [[label, 'Abgleich läuft …', 'mut', false]];
  if (result?.state === 'error') return [[label, result.error || '–', 'err-t', false]];
  if (result?.state !== 'done') return [[label, '–', 'mut', true]];
  const n = (x) => (finite(x) ? grp(x) : '–');
  return [[label, n(result.misreads), result.misreads === 0 ? 'ok-t' : 'err-t', true],
    ['Verglichen', n(result.compared_valid), '', true],
    ['Nicht entscheidbar (Wechsel)', n(result.undecided_valid), '', true],
    ['Ohne Referenz', n(result.uncovered_valid), '', true]];
}

const pad2 = (x) => String(x).padStart(2, '0');
// Uhrzeit des Laufstarts im Browser (Ortszeit) aus started_at_utc.
export function clockOf(utc) {
  const d = new Date(utc);
  return Number.isNaN(d.getTime()) ? '–' : `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}
export function hms(seconds) {
  if (!finite(seconds)) return '–';
  const s = Math.floor(seconds);
  return `${pad2(Math.floor(s / 3600))}:${pad2(Math.floor((s % 3600) / 60))}:${pad2(s % 60)}`;
}

// Werteplan mit laufendem Schritt (reference.schedule_step, index ab 0).
export function planText(reference, stopped = false) {
  const step = reference?.schedule_step;
  const plan = scheduleText(reference?.norm_schedule);
  // Nach dem Stopp ist der letzte Schritt Verlauf, kein laufender Werteplan.
  if (stopped && step) return `zuletzt Schritt ${step.index + 1} · Faktor ${step.factor}`;
  return step ? `set norm ${step.factor} (Schritt ${step.index + 1})` : plan;
}

// label = false: hinter einer Bezeichnung "Referenz" ohne doppelten Vorsatz.
export function referenceLine(reference, {label = true} = {}) {
  // Texte aus der alten Live-Seite (woertlich).
  if (reference?.restoring) return 'Werte werden zurückgestellt …';
  if (reference?.error) return reference.error;
  if (reference?.enabled) {
    return `${label ? 'Referenz: ' : ''}${finite(reference.lines) ? grp(reference.lines) : '–'} Telegramme`;
  }
  return `ohne Referenz: ${reference?.reason || 'nicht gestartet'}`;
}

// Ausgabezeile im Dock (nur bei Ausgabe ausser Aus); Text wie outputView.
export function outputDockHTML(output) {
  if (isOff(output)) return '';
  const tone = outputTone(output);
  const lines = outputLines(output);
  const cfg = configText(output);
  return `<div class="sect" data-part="output"><div class="pt flat">GSVmulti-Ausgabe` +
    `${markerText(output) && output.transport === 'serial' ? `<span class="pa"><span class="tag">${esc(markerText(output))}</span></span>` : ''}</div>` +
    (output.transport !== 'serial' && markerText(output) ? `<p><span class="tag">${esc(markerText(output))}</span></p>` : '') +
    `<p class="${tone ? `${tone}-t ` : ''}wrap"><b>${esc(lines[0])}</b></p>` +
    (isFourChannel(output) ? `<p class="wrap" data-part="tick">${esc(tickLine(output))}</p>`
      : `<p class="warn-t wrap" data-part="one-ch" title="${esc(FORMAT_WARNING)}">${esc(tickLine(output))}</p>`) +
    lines.slice(1).map((line) => `<p class="note wrap">${esc(line)}</p>`).join('') +
    (cfg ? `<p class="note mono">${esc(cfg)}</p>` : '') +
    (['uart', 'tcp'].includes(output.transport) ? '<p class="brow"><button type="button" class="ghost" data-act="bridge-setup">Brücke anzeigen…</button></p>' : '') + '</div>';
}

export function runDockHTML(status, {resultCls = 'X'} = {}) {
  const run = status?.run || {};
  const summary = run.summary || {};
  const counts = run.counts || {};
  const total = STATUS_ROWS.reduce((sum, [key]) => sum + (finite(counts[key]) ? counts[key] : 0), 0);
  const stopped = status?.state === 'stopped';
  const elapsed = finite(run.elapsed_s) ? run.elapsed_s : null;
  const head = stopped
    ? `<div class="endbox"><b>Lauf beendet</b>${summary.end_reason
      ? `<span>Endgrund <span class="mono">${esc(summary.end_reason)}</span></span>` : ''}` +
      `${status?.error ? `<span class="err-t">${esc(status.error)}</span>` : ''}</div>`
    : `<div class="runhead"><span class="sq ${CLS_TONE[resultCls] || 'stale'}"></span><b>${status?.test_run ? 'Testlauf läuft' : 'Lauf läuft'}</b>` +
      `<span class="mut mono">${esc(hms(elapsed))}</span></div>`;
  const facts = `<dl class="kv"><dt>Gestartet</dt><dd>${esc(clockOf(run.started_at_utc))}</dd>` +
    `<dt>Dauer</dt><dd>${esc(hms(elapsed))}</dd><dt>Bilder</dt><dd>${num(summary.frames_read)}</dd>` +
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
  const reference = status?.reference || {};
  const comparison = `<div class="sect kvf">` +
    comparisonRows(status).map(([label, text, cls, mono]) =>
      `<div><span>${esc(label)}</span><b class="${cls}${mono ? '' : ' t'}">${esc(text)}</b></div>`).join('') +
    `<div><span>Referenz</span><b class="t">${esc(referenceLine(reference, {label: false}))}</b></div>` +
    `<div><span>Werteplan</span><b>${esc(planText(reference, stopped))}</b></div></div>`;
  const storage = stopped
    ? `<div class="sect"><dl class="kv"><dt>Ablage</dt><dd class="wrap">${esc([status?.session_id, run.dir].filter(Boolean).join('/') || '–')}</dd></dl></div>`
    : '';
  return head + facts +
    `<div class="sect"><div class="pt flat">Status<span class="pa">Anteil</span></div><table class="stt">${rows}</table>` +
    `<div class="share" aria-hidden="true">${share}</div></div>` + comparison + outputDockHTML(status?.output) + storage;
}
