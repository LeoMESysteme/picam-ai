// Einstieg der Live-Seite /live: Huelle aufbauen, Status abrufen, rendern.
// Entscheidungen fallen im Server (dispread.live), nie hier. Die Ansichten
// fuer Einrichtung, Lauf, Effekte und Einarbeitung kommen in eigenen
// Modulen dazu; der Viewer zeigt den MJPEG-Strom mit HUD.
import {createClient} from './api.js';
import {openPreview} from './mjpeg.js';
import {mountViewer} from './viewer/view.js';
import {cameraView, stepRows} from './model.js';
import {dec, esc, mountShell, renderStatusbar, renderTitle} from './shell.js';

const RUN_STATES = ['running', 'stopped'];
const SETUP_TABS = ['Schritt', 'Fokus', 'Prüfungen'];
const RUN_TABS = ['Wert', 'Ursachen', 'Nachführung', 'Referenz'];
const STATE_META = {idle: 'Bereit', setup_ready: 'Prüfen & Bestätigen', setup_failed: 'Abgebrochen',
  confirmed: 'Bestätigt', running: 'Lauf', stopped: 'Lauf beendet'};
const SQUARE_WORD = {ok: 'erledigt', warn: 'erledigt mit Warnung', err: 'fehlgeschlagen', run: 'läuft', pend: 'ausstehend'};

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

function setHTML(el, html) {
  if (el._html !== html) {
    el._html = html;
    el.innerHTML = html;
  }
}

function duration(row) {
  if (!finite(row.elapsed_s)) return '';
  const s = row.state === 'running' ? Math.floor(row.elapsed_s) : Math.round(row.elapsed_s);
  return s < 60 ? `${s} s` : mmss(s);
}

function square(row) {
  if (row.state === 'done') return row.tone === 'warn' ? 'warn' : row.tone === 'err' ? 'err' : 'ok';
  return row.state === 'running' ? 'run' : row.state === 'failed' ? 'err' : 'pend';
}

function squareHTML(kind) {
  return `<span class="sq ${kind}" role="img" aria-label="${SQUARE_WORD[kind]}"></span>`;
}

function stepsHTML(rows) {
  return rows.map((row) => {
    const sub = row.sub.length ? `<ul class="subl">${row.sub.map((item) => {
      const kind = item.state === 'done' ? 'ok' : item.state === 'running' ? 'run' : item.state === 'failed' ? 'err' : 'pend';
      return `<li class="${item.state}" data-sub="${esc(item.key)}">${squareHTML(kind)}${esc(item.label)}` +
        `<span class="r">${esc(item.value)}</span></li>`;
    }).join('')}</ul>` : '';
    return `<div class="step ${row.state}" data-step="${esc(row.key)}" data-state="${row.state}">` +
      `${squareHTML(square(row))}<b>${esc(row.label)}</b><span class="dur">${duration(row)}</span>` +
      `${row.detail ? `<div class="sum">${esc(row.detail)}</div>` : ''}${sub}</div>`;
  }).join('');
}

function leadHTML(status, conn) {
  const view = conn?.view || {headline: '', cls: '', detail: ''};
  if (status.state === 'setup_running' && !conn?.offline) return '';
  let detail = view.detail;
  if (status.state === 'idle' && !conn?.offline && !status.error) {
    detail = status.camera?.running && !status.camera?.stalled
      ? 'Kamera liefert Bilder. Anzeige vollständig ins Bild bringen, dann <b>Einrichtung starten</b>. Dauer etwa eine Minute.'
      : esc(cameraView(status.camera || {}));
    return `<div class="lead"><h2>${esc(view.headline)}</h2><p>${detail}</p></div>`;
  }
  return `<div class="lead ${esc(view.cls)}"><h2>${esc(view.headline)}</h2>${detail ? `<p>${esc(detail)}</p>` : ''}</div>`;
}

function factsHTML(status) {
  const controls = status.camera?.source?.controls || {};
  const value = (v) => (v === undefined || v === null ? '–' : v);
  const exposure = controls.exposure_time_absolute == null ? '–'
    : `${controls.exposure_time_absolute}${controls.gain == null ? '' : ` · Gain ${controls.gain}`}`;
  const white = controls.white_balance_temperature == null ? '–' : `${controls.white_balance_temperature} K`;
  return `<dt>Sitzung</dt><dd title="${esc(status.session_id)}">${esc(value(status.session_id))}</dd>` +
    `<dt>Fokus</dt><dd>${esc(value(controls.focus_absolute))}</dd>` +
    `<dt>Belichtung</dt><dd>${esc(exposure)}</dd><dt>Weißabgleich</dt><dd>${esc(white)}</dd>`;
}

function renderLeftDock(host, status, conn) {
  if (!host._mounted) {
    host.innerHTML = '<div class="pt"><span data-part="title"></span><span class="pa mono" data-part="meta"></span></div>' +
      '<div class="scroll" data-part="body"></div><dl class="facts" data-part="facts"></dl>';
    host._mounted = true;
  }
  const part = (name) => host.querySelector(`[data-part="${name}"]`);
  const runPhase = RUN_STATES.includes(status.state);
  part('title').textContent = runPhase ? 'Lauf' : 'Ablauf';
  part('meta').textContent = status.state === 'setup_running' && finite(status.setup?.elapsed_s)
    ? mmss(status.setup.elapsed_s) : status.state === 'idle' ? 'Einrichtung' : '';
  setHTML(part('body'), leadHTML(status, conn) + (runPhase ? '' : stepsHTML(stepRows(status))));
  setHTML(part('facts'), factsHTML(status));
}

function intro(status) {
  const source = status.camera?.source || {};
  const camera = [source.model === 'logitech_streamcam' ? 'StreamCam' : source.model,
    Array.isArray(source.size) ? `${source.size[0]}×${source.size[1]}` : null].filter(Boolean).join(' · ') || '–';
  const storage = status.storage?.free_bytes == null ? (status.storage?.message || '–')
    : `${dec(status.storage.free_bytes / 1e9, 2)} GB frei`;
  return '<div class="ins"><h3>Einrichtung</h3><p>Die Einrichtung läuft selbsttätig: Fokus, Kamera, Belichtung, ' +
    'Standbilder und Vorschlag. Danach den Vorschlag prüfen und mit Namen bestätigen.</p>' +
    '<p>Während der Einrichtung Aufbau und Kamera nicht berühren.</p></div>' +
    `<div class="blk"><h4>Voraussetzungen</h4><dl class="kv2"><dt>Kamera</dt><dd>${esc(camera)}</dd>` +
    `<dt>Speicher</dt><dd>${esc(storage)}</dd></dl></div>`;
}

function renderInspector(host, status, ui) {
  const runPhase = RUN_STATES.includes(status.state);
  const tabs = runPhase ? RUN_TABS : SETUP_TABS;
  const key = runPhase ? 'run' : 'setup';
  if (!tabs.includes(ui.tab[key])) ui.tab[key] = tabs[0];
  const current = ui.tab[key];
  if (!host._mounted) {
    host.innerHTML = '<div class="pt"><span>Inspektor</span><span class="pa" data-part="meta"></span></div>' +
      '<div class="tabs" role="tablist" aria-label="Inspektor" data-part="tabs"></div>' +
      '<div class="scroll" role="tabpanel" id="inspector-panel" data-part="body"></div>';
    host._mounted = true;
    host.querySelector('[data-part="tabs"]').addEventListener('click', (event) => {
      const button = event.target.closest('[role="tab"]');
      if (!button) return;
      ui.tab[button.dataset.scope] = button.dataset.tab;
      ui.render();
    });
    host.querySelector('[data-part="tabs"]').addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      const buttons = [...host.querySelectorAll('[role="tab"]')];
      const index = buttons.indexOf(document.activeElement);
      const next = buttons[(index + (event.key === 'ArrowRight' ? 1 : buttons.length - 1)) % buttons.length];
      next?.click();
      host.querySelector(`[role="tab"][data-tab="${next?.dataset.tab}"]`)?.focus();
    });
  }
  const running = stepRows(status).find((row) => row.state === 'running');
  host.querySelector('[data-part="meta"]').textContent = status.state === 'setup_running'
    ? (running?.label || '') : (STATE_META[status.state] || '');
  setHTML(host.querySelector('[data-part="tabs"]'), tabs.map((tab) =>
    `<button type="button" role="tab" data-scope="${key}" data-tab="${esc(tab)}" aria-controls="inspector-panel" ` +
    `aria-selected="${tab === current}" tabindex="${tab === current ? 0 : -1}">${esc(tab)}</button>`).join(''));
  setHTML(host.querySelector('[data-part="body"]'),
    current === 'Schritt' && ['idle', 'setup_failed'].includes(status.state) ? intro(status) : '');
}

function renderTimeline(host) {
  if (host._mounted) return;
  host.innerHTML = '<div class="pt"><span>Zeitleiste</span><span class="pa"></span></div>';
  host._mounted = true;
}

if (typeof document !== 'undefined') {
  const root = document.getElementById('root');
  const nodes = mountShell(root);
  const viewerUi = mountViewer(nodes.viewerHost, {statusbar: nodes.statusbar});
  const client = createClient();
  let hudProc = null;
  const ui = {busy: false, error: null, tab: {setup: null, run: null}, render: () => render()};
  let status = null;
  let conn = null;

  const act = async (path, body) => {
    ui.busy = true;
    render();
    const result = await client.post(path, body);
    ui.busy = false;
    ui.error = result.ok ? null : result.error;
    render();
    return result;
  };
  const handlers = {
    setup: (cellText) => act('/live/setup', {cell_text: cellText || null}),
    // Standardwerte der alten Seite: Referenz an, Diagnosebilder aus, kein Werteplan.
    runStart: () => act('/live/run/start', {test_override: false, reference: true, norm_schedule: null, diagnostics: false}),
    stop: () => act('/live/run/stop'),
  };

  function render() {
    renderTitle(status, {busy: ui.busy, canConfirm: false, error: ui.error}, handlers);
    if (!status) return;
    renderLeftDock(nodes.leftDock, status, conn);
    renderInspector(nodes.inspector, status, ui);
    renderTimeline(nodes.timeline);
    renderStatusbar(status, hudProc);
    viewerUi.setStatus(status);
  }

  // Vorschau nur bei sichtbarer Seite: ein Hintergrund-Tab kostet den Pi keine Kodierung.
  let preview = null;
  const startPreview = () => {
    if (preview) return;
    preview = new AbortController();
    openPreview('/live/preview.mjpg', ({bitmap, hud}) => {
      hudProc = hud?.proc || null;
      viewerUi.setFrame(bitmap, hud);
    }, preview.signal, {onState: viewerUi.setStream});
  };
  const stopPreview = () => {
    preview?.abort();
    preview = null;
  };
  document.addEventListener('visibilitychange', () => (document.hidden ? stopPreview() : startPreview()));
  if (!document.hidden) startPreview();

  client.start((next) => {
    status = next;
    render();
  }, (next) => {
    conn = next;
    document.body.classList.toggle('offline', next.offline);
    if (status) renderLeftDock(nodes.leftDock, status, conn);
  });
  render();
}
