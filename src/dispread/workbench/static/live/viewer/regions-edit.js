// Rahmenbereiche bearbeiten (Spec "Viewer": nur setup_ready, Bildquelle
// Live oder Standbild; Mock-Kapitel 6, #t=46). Klick auf freien Rahmen fuegt
// einen Bereich hinzu, Klick auf einen Bereich entfernt ihn. Vertrag wie
// static/live.js: POST /live/setup/regions {proposal_revision, add, remove}.
// Die Rueckmeldung je Klick kommt aus centre_results der Antwort und steht
// als Etikett am Klickpunkt. Solange eine Anfrage laeuft, sind Bestaetigen
// und weitere Aenderungen gesperrt. Die Koordinateneingabe x,y im Inspektor
// (mountRegionPanel) bleibt der Tastaturweg.
import {drawHud} from './hud.js';

// Gruende woertlich aus static/live.js; status.tracking_reasons (fields.py) gewinnt.
export const REGION_REASONS = {im_zeichenbereich: 'im Zeichenbereich', ausserhalb_rahmenband: 'außerhalb des Rahmenbands',
  am_bildrand: 'am Bildrand', zu_wenig_struktur: 'zu wenig zweidimensionale Struktur',
  mehrdeutig: 'mehrdeutige Struktur', zu_nah: 'zu nah an einem anderen Bereich',
  zweitbild_peak_zu_niedrig: 'Rahmenbereich im Zweitbild nicht deutlich genug wiedergefunden',
  zweitbild_mehrdeutig: 'Rahmenbereich im Zweitbild nicht eindeutig wiedergefunden',
  zweitbild_suchrand: 'Rahmenbereich im Zweitbild am Rand des Suchbereichs',
  zweitbild_am_bildrand: 'Rahmenbereich im Zweitbild zu nah am Bildrand',
  zweitbild_lage_abweichend: 'Rahmenbereich im Zweitbild an anderer Position wiedergefunden'};
const COORDINATES = /^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$/;
const COORDINATE_ERROR = 'Koordinaten als x,y eingeben, zum Beispiel 320,240.';
const BUSY_TEXT = 'Rahmenbereich wird geprüft …';
// Woertlich aus static/live.js (editRegions, catch-Zweig).
export const REGION_NETWORK_ERROR = 'Bereichsänderung nicht bestätigt – Verbindung prüfen und erneut versuchen.';
// Wie live.js nach erfolgreichem POST auf refresh() wartet: Sperre bis zum
// Status mit neuer proposal_revision, hoechstens so lange.
const REVISION_WAIT_MS = 3000;
// Mindest-Trefferflaeche am Bildschirm, damit 15-px-Bereiche auch eingepasst klickbar bleiben.
const MIN_HIT_PX = 6;
const FEEDBACK_MS = 4000;
const SOURCES = ['live', 'still'];

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

export function reasonText(reason, trackingReasons) {
  return trackingReasons?.[reason] || REGION_REASONS[reason] || reason;
}

// Zeile wie static/live.js #region-results.
export function resultText(result, trackingReasons) {
  const requested = result.requested_centre || result.centre;
  const used = result.used_centre === undefined ? result.centre : result.used_centre;
  return `${requested.join(',')} (verwendet: ${used ? used.join(',') : 'kein Mittelpunkt'}): ` +
    `${result.ok ? 'geeignet' : reasonText(result.reason, trackingReasons)}`;
}

// Index des Bereichs unter dem Bildpunkt (Pruefung wie static/live.js, aber
// mindestens MIN_HIT_PX Bildschirmpixel breit), sonst -1. scale = CSS-px je Bildpixel.
export function regionAt(regions, [x, y], scale = 1) {
  return (regions || []).findIndex((region) => {
    if (!Array.isArray(region?.centre)) return false;
    const half = Math.max((finite(region.size) ? region.size : 15) / 2, MIN_HIT_PX / (scale || 1));
    return Math.abs(x - region.centre[0]) <= half && Math.abs(y - region.centre[1]) <= half;
  });
}

// Etikett nach der Antwort: {ok, text}. edit = {add, remove}; result = client.post(...).
export function editFeedback(edit, result, trackingReasons) {
  if (!result.ok) return {ok: false, text: result.network ? REGION_NETWORK_ERROR : result.error};
  if (!edit.add.length) return {ok: true, text: `Rahmenbereich ${edit.remove[0] + 1} entfernt`};
  const results = Array.isArray(result.data?.centre_results) ? result.data.centre_results : [];
  // centre_results: erst die behaltenen, dann die neuen Punkte (proposal_from_regions).
  const at = results.length - edit.add.length;
  const mine = at >= 0 ? results[at] : null;
  if (!mine) return {ok: true, text: 'Bereichsänderung übernommen'};
  if (!mine.ok) return {ok: false, text: `${reasonText(mine.reason, trackingReasons)} – nicht geeignet`};
  const number = results.slice(0, at + 1).filter((r) => r.ok).length;
  return {ok: true, text: `Rahmenbereich ${number} hinzugefügt – geeignet`};
}

// mounted = Rueckgabe von mountViewer ({viewer, canvas}). Rueckgabe:
// {update(status), busy(), editable(), edit(add, remove, point), onChange(fn)}.
export function enableRegionEditing(mounted, client, status = null, {onBusy = () => {}} = {}) {
  const viewer = mounted.viewer;
  const canvas = mounted.canvas;
  const stage = canvas.parentElement;
  const label = stage.ownerDocument.createElement('div');
  label.className = 'vfb';
  label.setAttribute('role', 'status');
  label.setAttribute('aria-live', 'polite');
  label.hidden = true;
  stage.append(label);
  const listeners = new Set();
  let current = status;
  let busy = false;
  let hover = -1;
  let feedback = null; // {point, text, tone}
  let hideTimer = null;
  let panelText = null; // {text, tone} fuer den Inspektor

  const setup = () => current?.setup || {};
  const regions = () => (Array.isArray(setup().regions) ? setup().regions : []);
  const shown = () => current?.state === 'setup_ready' && SOURCES.includes(viewer.source());
  const editable = () => shown() && setup().proposal_revision != null;
  const notify = () => { for (const fn of listeners) fn(); };

  function frameSize() {
    const hud = viewer.hud();
    if (finite(hud?.w) && finite(hud?.h)) return [hud.w, hud.h];
    const size = current?.camera?.source?.size;
    return Array.isArray(size) && size.length === 2 ? size : null;
  }

  function showFeedback(point, text, tone, sticky = false) {
    clearTimeout(hideTimer);
    feedback = point ? {point, text, tone} : null;
    panelText = {text, tone};
    if (!sticky) {
      hideTimer = setTimeout(() => {
        feedback = null;
        viewer.redraw();
      }, FEEDBACK_MS);
    }
    viewer.redraw();
    notify();
  }

  // Sperre loesen: nach Fehlern sofort, nach Erfolg erst mit dem Status der
  // neuen Revision (update) oder nach REVISION_WAIT_MS.
  let waitFor = null; // {revision, timer}
  // quiet: aus update() heraus; der Aufrufer rendert ohnehin weiter.
  function release(quiet = false) {
    if (waitFor) clearTimeout(waitFor.timer);
    waitFor = null;
    busy = false;
    if (!quiet) onBusy(false);
    notify();
  }

  async function edit(add, remove, point = null) {
    if (busy || current?.state !== 'setup_ready') return false;
    const revision = setup().proposal_revision;
    busy = true;
    onBusy(true);
    showFeedback(point, BUSY_TEXT, 'pend', true);
    const result = await client.post('/live/setup/regions', {proposal_revision: revision, add, remove});
    const answer = editFeedback({add, remove}, result, current?.tracking_reasons);
    showFeedback(point, answer.text, answer.ok ? 'ok' : 'err');
    if (result.ok && current?.state === 'setup_ready' && setup().proposal_revision === revision) {
      waitFor = {revision, timer: setTimeout(() => release(), REVISION_WAIT_MS)};
      notify();
    } else {
      release();
    }
    return result.ok;
  }

  viewer.addClickHandler((point) => {
    if (!editable()) return false;
    // Waehrend einer Anfrage ist jeder weitere Klick wirkungslos.
    if (busy) return true;
    const [x, y] = point.map(Math.floor);
    const size = frameSize();
    if (x < 0 || y < 0 || (size && (x >= size[0] || y >= size[1]))) return true;
    const index = regionAt(regions(), [x, y], viewer.viewState().scale);
    edit(index < 0 ? [[x, y]] : [], index < 0 ? [] : [index], [x, y]);
    return true;
  });

  // Bereiche des Vorschlags im Bild; der gezeigte traegt seine Nummer.
  viewer.addPainter((ctx, view) => {
    stage.classList.toggle('editing', editable());
    stage.classList.toggle('on-region', editable() && hover >= 0);
    if (shown() && viewer.layers().has('rahmen')) {
      const track = {regions: regions().filter((r) => Array.isArray(r?.centre))
        .map((r) => ({c: r.centre, s: r.size, ok: true}))};
      drawHud(ctx, {track}, {...view, hover: hover >= 0 ? {kind: 'region', index: hover} : null}, new Set(['rahmen']));
    }
    if (!feedback?.point || !shown()) {
      label.hidden = true;
      return;
    }
    const [sx, sy] = view.imageToScreen([feedback.point[0] + 0.5, feedback.point[1] + 0.5]);
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = feedback.tone === 'err' ? '#ee5b4d' : feedback.tone === 'ok' ? '#d65ccf' : '#86aee8';
    ctx.beginPath();
    ctx.moveTo(sx - 6, sy - 6); ctx.lineTo(sx + 6, sy + 6);
    ctx.moveTo(sx + 6, sy - 6); ctx.lineTo(sx - 6, sy + 6);
    ctx.stroke();
    if (label.textContent !== feedback.text) label.textContent = feedback.text;
    label.className = `vfb ${feedback.tone}`;
    label.hidden = false;
    const w = label.offsetWidth;
    const left = sx + 10 + w > view.width - 6 ? sx - 10 - w : sx + 10;
    label.style.left = `${Math.round(Math.max(4, left))}px`;
    label.style.top = `${Math.round(Math.min(sy + 8, view.height - 28))}px`;
  });

  const local = (event) => {
    const rect = canvas.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  };
  canvas.addEventListener('pointermove', (event) => {
    const next = editable() ? regionAt(regions(), viewer.screenToImage(local(event)), viewer.viewState().scale) : -1;
    if (next !== hover) {
      hover = next;
      viewer.redraw();
    }
  });
  canvas.addEventListener('pointerleave', () => {
    if (hover >= 0) {
      hover = -1;
      viewer.redraw();
    }
  });

  return {
    update(next) {
      const before = JSON.stringify([current?.state, current?.setup?.proposal_revision, current?.setup?.regions]);
      current = next;
      if (waitFor && (next?.state !== 'setup_ready' || next?.setup?.proposal_revision !== waitFor.revision)) release(true);
      if (JSON.stringify([next?.state, next?.setup?.proposal_revision, next?.setup?.regions]) !== before) {
        if (hover >= regions().length) hover = -1;
        viewer.redraw();
        notify();
      }
    },
    busy: () => busy,
    editable,
    edit,
    // Letzte Rueckmeldung fuer den Inspektor ({text, tone} oder null).
    message: () => panelText,
    onChange(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    status: () => current,
  };
}

// Tastaturweg und Liste im Inspektor (Tab Schritt): Koordinaten x,y,
// Bereiche mit Entfernen, Auswahl und Pruefergebnisse (Texte aus live.js/live.html).
export function mountRegionPanel(host, editor) {
  host.classList.add('blk');
  host.innerHTML = `
    <h4>Rahmenbereiche<span data-part="count"></span></h4>
    <p class="note">Im Bild: Klick auf den Rahmen fügt einen Bereich hinzu, Klick auf einen Bereich entfernt ihn.
      Nur feste Rahmenstruktur auswählen, nie Zeichen, Kabel, Tisch oder Hintergrund.</p>
    <label class="f" for="region-coordinates">Quellbild-Koordinaten x,y</label>
    <div class="inrow"><input type="text" id="region-coordinates" class="mono" placeholder="z. B. 320,240" autocomplete="off" spellcheck="false">
      <button type="button" data-part="add">Bereich hinzufügen</button></div>
    <p class="msg" data-part="msg" role="status" aria-live="polite" hidden></p>
    <p class="mut selection" data-part="selection"></p>
    <details class="fold"><summary>Bereiche einzeln<span class="mut" data-part="list-count"></span></summary>
      <ul class="rlist" data-part="region-list"></ul></details>
    <details class="fold results" data-part="results" hidden><summary>Prüfergebnisse<span class="mut" data-part="results-count"></span></summary>
      <ul data-part="results-list"></ul></details>`;
  const q = (selector) => host.querySelector(selector);
  const input = q('#region-coordinates');
  const addButton = q('[data-part="add"]');
  let listKey = null;
  let localError = null;

  function addFromText() {
    const text = input.value.trim();
    if (!COORDINATES.test(text)) {
      localError = COORDINATE_ERROR;
      paint();
      return;
    }
    localError = null;
    const point = text.split(',').map(Number);
    editor.edit([point], [], point.map(Math.floor));
  }
  addButton.addEventListener('click', addFromText);
  input.addEventListener('keydown', (event) => { if (event.key === 'Enter') addFromText(); });
  input.addEventListener('input', () => { if (localError) { localError = null; paint(); } });
  q('[data-part="region-list"]').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-index]');
    if (!button || button.disabled) return;
    const status = editor.status();
    const index = Number(button.dataset.index);
    editor.edit([], [index], status?.setup?.regions?.[index]?.centre || null);
  });

  function paint() {
    const status = editor.status();
    const setup = status?.setup || {};
    const regions = Array.isArray(setup.regions) ? setup.regions : [];
    const editable = status?.state === 'setup_ready' && setup.proposal_revision != null;
    const busy = editor.busy();
    host.hidden = !editable;
    q('[data-part="count"]').textContent = String(regions.length);
    addButton.disabled = !editable || busy;
    input.disabled = !editable;
    q('[data-part="selection"]').textContent = `Auswahl: ${setup.auswahl || 'automatisch'}`;
    // Liste nur bei neuer Revision neu bauen: fokussierte Entfernen-Knoepfe bleiben.
    const key = JSON.stringify([setup.proposal_revision, regions]);
    const list = q('[data-part="region-list"]');
    if (key !== listKey) {
      listKey = key;
      list.innerHTML = regions.map((region, index) =>
        `<li><span class="n">${index + 1}</span><span class="c">${region.centre.join(', ')}</span>` +
        `<button type="button" class="ghost" data-index="${index}" aria-label="Bereich ${index + 1} entfernen (${region.centre.join(', ')})">Entfernen</button></li>`).join('');
    }
    for (const button of list.querySelectorAll('button')) button.disabled = !editable || busy;
    const message = localError ? {text: localError, tone: 'err'} : editor.message();
    const msg = q('[data-part="msg"]');
    msg.hidden = !message;
    msg.textContent = message?.text || '';
    msg.className = `msg ${message?.tone === 'err' ? 'err-t' : message?.tone === 'pend' ? 'sel-t' : 'mut'}`;
    const results = Array.isArray(setup.centre_results) ? setup.centre_results : [];
    q('[data-part="results"]').hidden = !results.length;
    q('[data-part="list-count"]').textContent = ` · ${regions.length}`;
    const rejected = results.filter((result) => !result.ok).length;
    q('[data-part="results-count"]').textContent = ` · ${results.length}${rejected ? ` · ${rejected} nicht geeignet` : ''}`;
    const html = results.map((result) =>
      `<li class="${result.ok ? '' : 'err-t'}">${escapeText(resultText(result, status?.tracking_reasons))}</li>`).join('');
    const target = q('[data-part="results-list"]');
    if (target._html !== html) { target._html = html; target.innerHTML = html; }
  }
  editor.onChange(paint);
  return {update: paint};
}

const escapeText = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
