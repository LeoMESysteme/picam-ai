// Pruefungen im Inspektor (Spec "Einrichtungs-Fortschritt": Raster mit
// Pruefung | Status | Hinweis, Mock-Kapitel 5, #t=30). Vor dem Vorschlag
// kommen die Zeilen aus setup.checks_live (report-Haken von assist_measure),
// danach aus setup.checks mit setup.check_reasons. Reihenfolge wie vom Server.
import {esc} from '../shell.js';
import {dotHTML} from './steps.js';

// Anzeigenamen der Pruefschluessel (live/setup.py setup_checks), Woerter wie im Mock.
const CHECK_LABELS = {kontrast: 'Kontrast', kanten: 'Kanten', rahmen: 'Rahmen', glanz: 'Glanz',
  belichtung: 'Belichtung', aufloesung: 'Auflösung', raster: 'Raster', stabilitaet: 'Stabilität',
  rasterversatz: 'Rasterversatz', gegenlesen: 'Gegenlesen', displayfehler: 'Displayfehler',
  nachfuehrung: 'Nachführung'};
const WORDS = {OK: ['OK', 'ok'], WARNUNG: ['WARNUNG', 'warn'], FEHLER: ['FEHLER', 'err']};
// "nicht geprüft" wie static/live.js (status ?? 'nicht geprüft').
const UNCHECKED = ['nicht geprüft', 'pend'];

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const label = (key) => CHECK_LABELS[key] || key;

function row(key, status, hint) {
  const [word, tone] = WORDS[status] || UNCHECKED;
  return {key, label: label(key), status: status || null, word, tone, hint: hint || ''};
}

export function checkRows(status) {
  const setup = status?.setup || {};
  let rows;
  if (setup.checks && typeof setup.checks === 'object') {
    const reasons = setup.check_reasons || {};
    rows = Object.entries(setup.checks).map(([key, value]) => row(key, value, reasons[key]));
  } else {
    rows = Object.entries(setup.checks_live || {}).map(([key, check]) => row(key, check?.status, check?.reason));
  }
  // Die Ruhezeit laeuft, bevor assist_measure Stabilitaet meldet: als laufende Zeile zeigen.
  const progress = setup.progress;
  if (status?.state === 'setup_running' && progress?.phase === 'stabilitaet' && !rows.some((r) => r.key === 'stabilitaet')) {
    const wait = progress.wait;
    const hint = finite(wait?.elapsed_s) && finite(wait?.total_s)
      ? `noch ${Math.max(0, Math.ceil(wait.total_s - wait.elapsed_s))} s` : '';
    rows.push({key: 'stabilitaet', label: label('stabilitaet'), status: null, word: 'läuft', tone: 'run', hint});
  }
  return rows;
}

export function warningCount(status) {
  return checkRows(status).filter((r) => r.tone === 'warn' || r.tone === 'err').length;
}

// Gesamturteil: nur OK/WARNUNG/FEHLER tragen Statusfarben. NICHT_GEPRUEFT oder
// ein unbekanntes Urteil erscheint grau (ausstehend), nie im Freigabe-Gruen.
export function overallView(overall) {
  if (!overall) return null;
  const known = WORDS[overall];
  if (known) return {word: known[0], square: known[1], cls: `${known[1]}-t`};
  return {word: overall === 'NICHT_GEPRUEFT' ? UNCHECKED[0] : String(overall), square: 'stale', cls: 'mut'};
}

export function checksSummary(status) {
  const rows = checkRows(status);
  const n = (tone) => rows.filter((r) => r.tone === tone).length;
  const parts = [`${n('ok')} OK`, `${n('warn')} Warnung`];
  if (n('err')) parts.push(`${n('err')} Fehler`);
  if (n('pend') + n('run')) parts.push(`${n('pend') + n('run')} offen`);
  const overall = status?.setup?.overall || null;
  const text = !overall ? 'Erst nach dem Vorschlag'
    : overall === 'WARNUNG' ? '– bestätigen möglich, Warnung zur Kenntnis nehmen' : '';
  return {overall, counts: parts.join(' · '), text};
}

export function checksHTML(status) {
  const rows = checkRows(status);
  const body = rows.length ? rows.map((r) =>
    `<tr class="${r.tone === 'pend' ? 'pend' : ''}" data-check="${esc(r.key)}"><td>${esc(r.label)}</td>` +
    `<td><span class="stc">${dotHTML(r.tone)}<span class="${r.tone === 'warn' ? 'warn-t' : r.tone === 'err' ? 'err-t' : ''}">${esc(r.word)}</span></span></td>` +
    `<td class="${r.tone === 'warn' ? 'warn-t' : r.tone === 'err' ? 'err-t' : 'mut'} wrap">${esc(r.hint)}</td></tr>`).join('')
    : '<tr class="pend"><td colspan="3">Noch keine Prüfung gemeldet</td></tr>';
  const summary = checksSummary(status);
  const view = overallView(summary.overall);
  const verdict = view
    ? `<div class="verdict" data-overall="${esc(summary.overall)}">${dotHTML(view.square)}<b class="${view.cls}">${esc(view.word)}</b>` +
      `${summary.text ? `<span class="mut">${esc(summary.text)}</span>` : ''}</div>`
    : `<span class="mut">${esc(summary.text)}</span>`;
  return '<div class="blk flush"><table class="grid"><thead><tr><th>Prüfung</th><th class="st">Status</th><th>Hinweis</th></tr></thead>' +
    `<tbody>${body}</tbody></table></div>` +
    `<div class="blk"><h4>Gesamturteil<span>${esc(summary.counts)}</span></h4>${verdict}</div>`;
}

// host: Container im Tab Pruefungen.
export function renderChecks(host, status) {
  const html = checksHTML(status);
  if (host._html !== html) {
    host._html = html;
    host.innerHTML = html;
  }
}
