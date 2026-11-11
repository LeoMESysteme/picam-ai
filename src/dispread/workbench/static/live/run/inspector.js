// Inspektor im Lauf (Spec "Aufbau der Oberflaeche"): Wert (letzte
// Datensaetze), Ursachen (10-s-Fenster aus rejection_causes), Nachfuehrung
// (Rahmenbereiche mit Treffer) und Referenz (mit "Ablage" fuer Diagnose).
// Kein Live-Abgleich gegen die Referenz (Spec OP-1), keine erfundenen Zahlen.
import {activeRegionHint, regionDeactivatedIndices, regionDeactivatedText, regionHintIndices, regionHintText,
  trackingHintText} from '../model.js';
import {dec, esc, grp} from '../shell.js';
import {referenceText} from './result.js';
import {configText, markerText, isOff, outputLines, outputTone} from './output.js';
import {comparisonRows, planText, referenceLine} from './dock.js';

export const RUN_TABS = ['Wert', 'Ursachen', 'Nachführung', 'Referenz'];
const STATUS = {valid: ['ok', 'Freigegeben'], transition: ['warn', 'Wechselt'],
  unreadable: ['err', 'Unlesbar'], stale: ['stale', 'Veraltet']};
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const pad2 = (n) => String(n).padStart(2, '0');
const clockText = (ms) => {
  const d = new Date(ms);
  return `${pad2(d.getMinutes())}:${pad2(d.getSeconds())},${Math.floor(d.getMilliseconds() / 100)}`;
};
const sq = (tone) => `<span class="sq ${tone}"></span>`;

// Letzte Datensaetze: eine Zeile je Wechsel von Status oder Text (wie im
// Mock), mit der Zahl der Bilder in dieser Zeile. Im Testlauf wird ein
// VALID nie als Wert gefuehrt (Wahrheitsregel 2). reference = {text, stale}
// (referenceModel) beim ersten Bild der Zeile; kein Live-Abgleich (OP-1).
export function createRecordLog({max = 40, wallNow = () => Date.now()} = {}) {
  const rows = [];
  let lastSeq = null;
  return {
    rows: () => rows,
    clear() { rows.length = 0; lastSeq = null; },
    note(rec, {testRun = false, reference = null, offline = false} = {}) {
      if (!rec || rec.seq == null || rec.seq === lastSeq) return false;
      lastSeq = rec.seq;
      let status = STATUS[rec.status] ? (testRun && rec.status === 'valid' ? 'unreadable' : rec.status) : 'unreadable';
      // Verbindung verloren: nichts wird als freigegeben gefuehrt (Wahrheitsregel 1).
      if (offline && status === 'valid') status = 'stale';
      const text = status === 'valid' ? `${rec.text ?? ''}` : '';
      const top = rows[0];
      if (top && top.status === status && top.text === text) { top.frames += 1; top.lastSeq = rec.seq; return true; }
      const ref = reference && reference.text && reference.text !== '–' ? {text: reference.text, stale: Boolean(reference.stale)} : null;
      rows.unshift({at: wallNow(), status, text, unit: rec.unit || '', frames: 1, firstSeq: rec.seq, lastSeq: rec.seq, ref});
      if (rows.length > max) rows.length = max;
      return true;
    },
  };
}

export function runBadges(status) {
  const causes = status?.state === 'running' ? status?.run?.rejection_causes?.causes || [] : [];
  const flagged = regionHintIndices(activeRegionHint(status?.run?.region_hint, status?.run?.region_deactivated)).length;
  return {Ursachen: causes.length, ...(flagged ? {'Nachführung': flagged} : {})};
}
// Ursachen sind Ablehnungen (Fehlerton); der Bereichshinweis ist ein ruhiger Warnhinweis.
export const RUN_BADGE_TONE = {Ursachen: 'err-t', 'Nachführung': 'warn-t'};

// TC 2026-11-11: Rahmenbereich dauerhaft unstimmig (status.run.region_hint), im
// Lauf und nach dem Stopp. Reine Diagnose: kein Freigabeentscheid, kein Alarm.
function regionHintHTML(hint) {
  const text = regionHintText(hint);
  if (!text) return '';
  const rows = [...hint.regions].sort((a, b) => a.number - b.number).map((r) =>
    `<tr><td class="m r">${r.number}</td><td class="m r">${Array.isArray(r.centre) ? r.centre.map((v) => Math.round(v)).join(', ') : '–'}</td>` +
    `<td class="m r">${Math.round(100 * r.share)} %</td><td class="m r">${finite(r.median_px) ? `${dec(r.median_px, 2)} px` : '–'}</td></tr>`).join('');
  const limit = finite(hint.limit_px) ? `${dec(hint.limit_px, 2)} px` : '–';
  const rest = finite(hint.rest_median_px) ? `${dec(hint.rest_median_px, 2)} px` : '–';
  return `<div class="blk rhint" data-part="region-hint"><h4>${sq('warn')} Rahmenbereich unstimmig` +
    `<span>${finite(hint.frames) ? `letzte ${grp(hint.frames)} Bilder` : ''}</span></h4>` +
    `<p class="warn-t wrap">${esc(text)}</p>` +
    '<table class="grid"><thead><tr><th class="r">Nr.</th><th class="r">Mitte</th><th class="r">Anteil</th>' +
    `<th class="r">Median</th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="note">Anteil der Bilder, in denen der Bereich mehr als ${esc(limit)} von der gemeinsamen Lage abweicht ` +
    `(übrige Bereiche im Median ${esc(rest)}). Nur Diagnose: Freigabe und Grenzen bleiben unverändert.</p></div>`;
}

// TB 2026-11-11: automatisch stillgelegte Rahmenbereiche, ruhiger Info-Ton.
function regionOffHTML(list) {
  const text = regionDeactivatedText(list);
  if (!text) return '';
  const rows = [...list].sort((a, b) => a.number - b.number).map((r) =>
    `<tr><td class="m r">${r.number}</td><td class="m r">${Array.isArray(r.centre) ? r.centre.map((v) => Math.round(v)).join(', ') : '–'}</td>` +
    `<td class="m r">${Math.round(100 * r.share)} %</td><td class="m r">${finite(r.median_px) ? `${dec(r.median_px, 2)} px` : '–'}</td>` +
    `<td class="m r">${Number.isInteger(r.frame_sequence) ? grp(r.frame_sequence) : '–'}</td></tr>`).join('');
  return `<div class="blk roff" data-part="region-off"><h4>Rahmenbereich stillgelegt<span>bis Laufende</span></h4>` +
    `<p class="wrap">${esc(text)}.</p>` +
    '<table class="grid"><thead><tr><th class="r">Nr.</th><th class="r">Mitte</th><th class="r">Anteil</th>' +
    `<th class="r">Median</th><th class="r">ab Bild</th></tr></thead><tbody>${rows}</tbody></table>` +
    '<p class="note">Der Bereich wich dauerhaft allein von der gemeinsamen Lage ab. Die übrigen Bereiche führen nach; ' +
    'Mindestzahl, Streuung, Reserve und Schutzprobe sind erfüllt, Prüfgrenzen unverändert. Steht im Audit.</p></div>';
}

function wertHTML(log) {
  const rows = log.rows();
  const body = rows.map((row) => {
    const [tone, word] = STATUS[row.status];
    return `<tr><td class="m">${clockText(row.at)}</td><td class="m r">${row.status === 'valid' ? esc(row.text) : '–'}</td>` +
      `<td><span class="stc">${sq(tone)}${word}</span></td>` +
      (row.ref ? `<td class="m r${row.ref.stale ? ' struck' : ''}"${row.ref.stale ? ' title="Referenz veraltet"' : ''}>${esc(row.ref.text)}</td>`
        : '<td class="m r">–</td>') +
      `<td class="m r">${grp(row.frames)}</td></tr>`;
  }).join('');
  return '<table class="grid"><thead><tr><th title="Uhrzeit dieser Seite, nicht die Aufnahmezeit des Datensatzes">Seitenzeit</th><th class="r">Wert</th><th>Status</th><th class="r">Referenz</th>' +
    '<th class="r">Bilder</th></tr></thead>' +
    `<tbody>${body || '<tr class="pend"><td colspan="5">Keine Datensätze seit dem Laden der Seite</td></tr>'}</tbody></table>` +
    '<p class="note pad">Eine Zeile je Wechsel von Status oder Wert; Werte nur bei Freigegeben.</p>';
}

function ursachenHTML(status, result) {
  const window = status?.run?.rejection_causes;
  const now = result?.cls === 'V' ? '<p class="mut">Derzeit keine Ursache: Wert wird freigegeben.</p>'
    : `<p class="${result?.subErr ? 'err-t' : ''}">${esc(result?.sub || '–')}</p>`;
  const causes = status?.state === 'running' ? window?.causes || [] : [];
  const rows = causes.map((cause) => `<tr><td class="wrap">${esc(cause.explanation || cause.reason)}</td>` +
    `<td class="m">${esc(cause.reason)}</td><td class="m r">${Math.round(100 * cause.fraction)} %</td>` +
    `<td class="m r">${grp(cause.count)}</td></tr>`).join('');
  const frames = finite(window?.frames) ? `${grp(window.frames)} Bilder` : '';
  return `<div class="blk"><h4>Jetzt<span>${esc(result?.word || '')}</span></h4>${now}</div>` +
    `<div class="blk flush"><h4 class="pad">Letzte ${finite(window?.window_s) ? Math.round(window.window_s) : 10} s<span>${frames}</span></h4>` +
    '<table class="grid"><thead><tr><th>Ursache</th><th>Kennung</th><th class="r">Anteil</th><th class="r">Bilder</th></tr></thead>' +
    `<tbody>${rows || `<tr class="pend"><td colspan="4">${status?.state === 'running' ? 'Keine Ursachen im Fenster' : 'Lauf beendet'}</td></tr>`}</tbody></table>` +
    `${window?.limited ? '<p class="note pad">Fenster wegen hoher Bildrate begrenzt</p>' : ''}</div>`;
}

// Modus-Texte aus der alten Live-Seite (woertlich), sonst die Kennung
// (known: nur die bekannten Modi, sonst '' wie auf der alten Seite).
export function trackingModeText(mode, {known = false} = {}) {
  return mode === 'rahmenbereiche' ? 'Nachführung: Rahmenbereiche'
    : mode === 'ecc_alt' ? 'Nachführung: alt (ECC, inhaltsabhängig) – neu einrichten empfohlen'
      : mode === 'injiziert' ? 'Nachführung: injiziert' : known ? '' : mode || '–';
}

function trackingHTML(status, hud) {
  const track = hud?.track || null;
  const summary = status?.run?.summary || {};
  const score = summary.track_score || {};
  const value = (x, digits, unit = '') => (finite(x) ? `${dec(x, digits)}${unit}` : '–');
  const correcting = track?.correcting ? '<span class="teal-t">Korrektur läuft</span>' : 'ruhend';
  const hint = status?.state === 'running' ? trackingHintText(status?.run?.tracking_hint) : '';
  const deactivated = status?.run?.region_deactivated;
  const regionHint = activeRegionHint(status?.run?.region_hint, deactivated);
  const flagged = new Set(regionHintIndices(regionHint));
  const off = new Set(regionDeactivatedIndices(deactivated));
  const regions = (track?.regions || []).map((region, i) => {
    const ok = region?.ok !== false;
    const state = off.has(i) ? `${sq('pend')}<span class="mut">stillgelegt</span>`
      : flagged.has(i) ? `${sq('warn')}dauerhaft unstimmig` : `${sq(ok ? 'ok' : 'err')}${ok ? 'Treffer' : 'kein Treffer'}`;
    return `<tr${flagged.has(i) && !off.has(i) ? ' class="flag"' : ''}><td class="m r">${i + 1}</td><td class="m r">${Array.isArray(region?.c) ? region.c.map((v) => Math.round(v)).join(', ') : '–'}</td>` +
      `<td class="m r">${value(region?.peak, 2)}</td><td><span class="stc">${state}</span></td></tr>`;
  }).join('');
  const lost = Object.entries(summary.tracking_lost_reasons || {}).map(([reason, count]) =>
    `<tr><td class="wrap">${esc(status?.tracking_reasons?.[reason] || reason)}</td><td class="m r">${grp(count)}</td></tr>`).join('');
  return regionOffHTML(deactivated) + regionHintHTML(regionHint) + `<div class="blk"><h4>Spurgüte<span>${esc(trackingModeText(status?.run?.tracking?.mode ?? status?.profile?.tracking_mode))}</span></h4>` +
    `<dl class="kv2"><dt>Spur</dt><dd>${value(track?.score, 2)}</dd><dt>Versatz</dt><dd>${value(track?.shift_px, 1, ' px')}</dd>` +
    `<dt>Drehung</dt><dd>${value(track?.rotation_deg, 1, '°')}</dd><dt>Nachregistrierung</dt><dd class="t">${correcting}</dd>` +
    `<dt>Spur im Lauf</dt><dd>${finite(score.median) ? `${value(score.min, 2)} · ${value(score.median, 2)} · ${value(score.max, 2)}` : '–'}</dd></dl>` +
    `${finite(score.median) ? '<p class="note">Min · Median · Max</p>' : ''}` +
    `${hint ? `<p class="err-t">${esc(hint)}</p>` : ''}</div>` +
    '<div class="blk flush"><table class="grid"><thead><tr><th class="r">Nr.</th><th class="r">Mitte</th><th class="r">Treffer</th><th>Status</th></tr></thead>' +
    `<tbody>${regions || '<tr class="pend"><td colspan="4">Keine Rahmenbereiche im Bild</td></tr>'}</tbody></table></div>` +
    (lost ? `<div class="blk flush"><h4 class="pad">Nachführung verloren<span>${grp(summary.tracking_lost || 0)} Bilder</span></h4>` +
      `<table class="grid"><tbody>${lost}</tbody></table></div>` : '');
}

// Diagnose-Zeile aus der alten Live-Seite (woertlich).
export function diagnosticsText(s) {
  const diag = s?.diagnostics;
  return (diag?.enabled
    ? `Diagnose: ${diag.saved} Bilder, ${(diag.bytes / 1e6).toFixed(1)} MB; Queue verworfen: ${diag.dropped_queue}, ` +
      `Limit verworfen: ${diag.dropped_limit}, RAM verworfen: ${diag.dropped_memory ?? 0}, ` +
      `Markenbilder verworfen: ${diag.dropped_mark_rate ?? 0}, Schreibfehler: ${diag.write_errors}`
    : `Diagnose aus: ${diag?.reason || 'nicht gestartet'}`) +
    (s?.diagnose_kopie ? ' · Diagnose wird kopiert …' : '') +
    (diag?.first_error ? ` · ${diag.first_error} · RAM-Ablage: ${diag.staging || '—'}` : '') +
    (diag?.copied ? ' · Kopie gesichert' : '') +
    (s?.diagnostic_leftovers || []).map((item) => ` · Verbliebene RAM-Ablage: ${item.path} (` +
      `${item.bytes == null ? 'Größe unbekannt' : (item.bytes / 1e6).toFixed(1) + ' MB'})`).join('');
}

export function outputInspectorHTML(output) {
  const lines = outputLines(output);
  const tone = outputTone(output);
  const cfg = configText(output);
  return `<div class="blk" data-part="output"><h4>GSVmulti-Ausgabe<span>${isOff(output) ? '' : sq(tone || 'ok')}${markerText(output)
    ? ` <span class="tag">${esc(markerText(output))}</span>` : ''}</span></h4>` +
    lines.map((line, i) => `<p class="${i === 0 && tone ? `${tone}-t` : i ? 'note' : ''} wrap">${esc(line)}</p>`).join('') +
    (cfg ? `<dl class="kv2"><dt>Verbindung</dt><dd class="wrap">${esc(cfg)}</dd>` +
      `<dt>Abnahme</dt><dd>${esc(output.acceptance || '–')}</dd></dl>` : '') + '</div>';
}

function referenzHTML(status) {
  const reference = status?.reference || {};
  const tone = reference.restoring ? 'warn' : reference.error ? 'err' : reference.enabled ? 'ok' : 'stale';
  const n = (x) => (finite(x) ? grp(x) : '–');
  const mark = status?.last_mark;
  const latest = reference.enabled ? reference.latest : null;
  return `<div class="blk"><h4>Referenz GSV-2AS<span>${sq(tone)} ${esc(referenceLine(reference, {label: false}))}</span></h4>` +
    `<dl class="kv2"><dt>Telegramme</dt><dd>${n(reference.lines)}</dd><dt>Lesefehler</dt><dd>${n(reference.parse_errors)}</dd>` +
    `<dt>Lücken</dt><dd>${n(reference.gaps)}</dd><dt>Verworfen</dt><dd>${n(reference.dropped_oldest)}</dd>` +
    `<dt>Letzter Wert</dt><dd>${esc(referenceText(reference))}</dd>` +
    `<dt>Alter</dt><dd>${latest && finite(latest.age_s) ? `${dec(latest.age_s, 1)} s` : '–'}</dd>` +
    `<dt>Werteplan</dt><dd>${esc(planText(reference, status?.state === 'stopped'))}</dd>` +
    `<dt>Datei</dt><dd>${esc(reference.path || '–')}</dd></dl>` +
    '<p class="note">Der Referenzwert wird nur verglichen, nie zur Korrektur des gelesenen Werts benutzt.</p></div>' +
    `<div class="blk"><h4>Abgleich</h4><dl class="kv2">${comparisonRows(status).map(([label, text, cls, mono]) =>
      `<dt>${esc(label)}</dt><dd class="${cls}${mono ? '' : ' t wrap'}">${esc(text)}</dd>`).join('')}</dl></div>` +
    outputInspectorHTML(status?.output) +
    `<div class="blk"><h4>Ablage</h4><dl class="kv2"><dt>Lauf</dt><dd>${esc([status?.session_id, status?.run?.dir].filter(Boolean).join('/') || '–')}</dd></dl>` +
    `<p class="note wrap">${esc(diagnosticsText(status))}</p>` +
    `${mark ? `<p class="note wrap">${esc(`Letzte Marke (Meldezeit): ${mark.received_at_utc} · ${mark.text}`)}</p>` : ''}</div>`;
}

// Tab-Inhalt (host = Lauf-Pane des Inspektors).
export function renderRunInspector(host, status, tab, {log, hud = null, result = null} = {}) {
  let html;
  if (tab === 'Ursachen') html = ursachenHTML(status, result);
  else if (tab === 'Nachführung') html = trackingHTML(status, hud);
  else if (tab === 'Referenz') html = referenzHTML(status);
  else html = wertHTML(log);
  if (host._html !== html) { host._html = html; host.innerHTML = html; }
}
