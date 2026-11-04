// Einstieg der Live-Seite /live: Huelle aufbauen, Status abrufen, rendern.
// Entscheidungen fallen im Server (dispread.live), nie hier. Die Ansichten
// fuer Einrichtung, Lauf, Effekte und Einarbeitung kommen in eigenen
// Modulen dazu; der Viewer zeigt den MJPEG-Strom mit HUD.
import {createClient} from './api.js';
import {openPreview} from './mjpeg.js';
import {mountViewer} from './viewer/view.js';
import {enableRegionEditing, mountRegionPanel} from './viewer/regions-edit.js';
import {cameraView, stepRows} from './model.js';
import {dec, esc, mountShell, renderStatusbar, renderTitle} from './shell.js';
import {renderSteps} from './setup/steps.js';
import {focusChartModel, renderFocusChart, FOCUS_VERIFY_RATIO} from './setup/focus-chart.js';
import {exposureHTML} from './setup/exposure.js';
import {overallView, renderChecks, warningCount} from './setup/checks.js';
import {mountConfirm} from './setup/confirm.js';

const RUN_STATES = ['running', 'stopped'];
const SETUP_TABS = ['Schritt', 'Fokus', 'Prüfungen'];
const RUN_TABS = ['Wert', 'Ursachen', 'Nachführung', 'Referenz'];
const STATE_META = {idle: 'Bereit', setup_ready: 'Prüfen & Bestätigen', setup_failed: 'Abgebrochen',
  confirmed: 'Bestätigt', running: 'Lauf', stopped: 'Lauf beendet'};
const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

function setHTML(el, html) {
  if (el._html !== html) {
    el._html = html;
    el.innerHTML = html;
  }
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
      '<div class="scroll" data-part="body"><div data-part="lead"></div><div data-part="steps"></div></div>' +
      '<dl class="facts" data-part="facts"></dl>';
    host._mounted = true;
  }
  const part = (name) => host.querySelector(`[data-part="${name}"]`);
  const runPhase = RUN_STATES.includes(status.state);
  part('title').textContent = runPhase ? 'Lauf' : 'Ablauf';
  part('meta').textContent = status.state === 'setup_running' && finite(status.setup?.elapsed_s)
    ? mmss(status.setup.elapsed_s) : status.state === 'idle' ? 'Einrichtung' : '';
  setHTML(part('lead'), leadHTML(status, conn));
  renderSteps(part('steps'), runPhase ? [] : stepRows(status));
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

// Inspektor folgt dem Ablauf (Mock): Fokus waehrend der Fokussuche,
// Pruefungen ab dem Raster bis zum Vorschlag, sonst Schritt. Eine Auswahl
// des Bedieners gilt, bis der Ablauf einen anderen Tab vorschlaegt.
const CHECK_PHASES = ['raster', 'stabilitaet', 'zweites_standbild', 'gegenlesen'];
function autoSetupTab(status) {
  if (status.state !== 'setup_running') return 'Schritt';
  const running = stepRows(status).find((row) => row.state === 'running')?.key;
  if (running === 'fokus') return 'Fokus';
  if (running === 'vorschlag' || (running === 'standbilder' && CHECK_PHASES.includes(status.setup?.progress?.phase))) {
    return 'Prüfungen';
  }
  return 'Schritt';
}

function currentTab(status, ui) {
  const runPhase = RUN_STATES.includes(status.state);
  if (runPhase) {
    if (!RUN_TABS.includes(ui.tab.run)) ui.tab.run = RUN_TABS[0];
    return ui.tab.run;
  }
  const auto = autoSetupTab(status);
  const manual = ui.tab.setup;
  return manual && manual.auto === auto ? manual.tab : auto;
}

const STILL_PHASE = {mitteln: 'Standbild mitteln', zelltext: 'Zellentext', raster: 'Raster einpassen',
  stabilitaet: 'Ruhe abwarten', zweites_standbild: 'Zweites Standbild', gegenlesen: 'Gegenlesen'};

function controlsKV(controls = {}) {
  const v = (x, unit = '') => (x === undefined || x === null ? '–' : `${x}${unit}`);
  return `<dl class="kv2"><dt>focus_absolute</dt><dd>${esc(v(controls.focus_absolute))}</dd>` +
    `<dt>Belichtung</dt><dd>${esc(v(controls.exposure_time_absolute))}</dd><dt>Gain</dt><dd>${esc(v(controls.gain))}</dd>` +
    `<dt>Weißabgleich</dt><dd>${esc(v(controls.white_balance_temperature, ' K'))}</dd></dl>`;
}

// Kopf des Tabs Schritt je Zustand und laufendem Schritt (Mock-Kapitel 2–7).
function stepInfoHTML(status) {
  const setup = status.setup || {};
  if (['idle', 'setup_failed'].includes(status.state)) return intro(status);
  if (status.state === 'setup_running') {
    const row = stepRows(status).find((r) => r.state === 'running');
    const progress = setup.progress || {};
    if (row?.key === 'fokus') {
      const n = Array.isArray(setup.focus?.samples) ? setup.focus.samples.length : 0;
      return `<div class="ins"><h3>Fokus</h3><p>${n ? `Schärfe wurde an ${n} Stellen gemessen.` : 'Fokus wird gesucht …'} ` +
        'Die Kurve steht im Tab Fokus.</p></div>';
    }
    if (row?.key === 'kamera') {
      return '<div class="ins"><h3>Kamera</h3><p>Kamera wird mit festen Reglern neu gestartet. Automatik zuerst aus, dann Absolutwerte.</p></div>' +
        `<div class="blk">${controlsKV(status.camera?.source?.controls)}</div>`;
    }
    if (row?.key === 'belichtung') return exposureHTML(setup.exposure, {state: 'running'});
    if (row?.key === 'standbilder') {
      const wait = progress.phase === 'stabilitaet' ? progress.wait : null;
      const waitText = finite(wait?.elapsed_s) && finite(wait?.total_s)
        ? `${Math.floor(wait.elapsed_s)}/${Math.round(wait.total_s)} s · noch ${Math.max(0, Math.ceil(wait.total_s - wait.elapsed_s))} s` : '–';
      return '<div class="ins"><h3>Standbilder</h3><p>Zwei gemittelte Standbilder mit Ruhezeit dazwischen. ' +
        'Währenddessen darf sich nichts bewegen.</p></div>' +
        `<div class="blk"><dl class="kv2"><dt>Versuch</dt><dd>${esc(finite(progress.attempt) ? `${progress.attempt}/${progress.attempts_max}` : '–')}</dd>` +
        `<dt>Phase</dt><dd class="t">${esc(STILL_PHASE[progress.phase] || '–')}</dd><dt>Ruhe</dt><dd>${esc(waitText)}</dd></dl></div>`;
    }
    if (row?.key === 'vorschlag') return '<div class="ins"><h3>Vorschlag</h3><p>Vorschlag wird erstellt …</p></div>';
    return '<div class="ins"><h3>Einrichtung</h3><p>Einrichtung läuft …</p></div>';
  }
  if (status.state === 'setup_ready') {
    const overall = setup.overall;
    const verdict = overallView(overall);
    const why = Object.entries(setup.checks || {}).filter(([, v]) => v === overall && overall !== 'OK')
      .map(([k]) => setup.check_reasons?.[k]).filter(Boolean).join(', ');
    const cells = Array.isArray(setup.grid?.cell_boxes) ? `${setup.grid.cell_boxes.length} Zellen` : '–';
    return '<div class="ins"><h3>Prüfen &amp; Bestätigen</h3><p>Vorschlag im Bild prüfen: Viereck, Raster, Rahmenbereiche.' +
      `${verdict ? ` Gesamturteil <b class="${verdict.cls}">${esc(verdict.word)}</b>${why ? ` (${esc(why)})` : ''}.` : ''}</p>` +
      '<p class="note">Das Abtastbild (overlay_sampling) zeigt das feste Punktraster und hängt nicht von den Rahmenbereichen ab.</p></div>' +
      `<div class="blk"><dl class="kv2"><dt>Raster</dt><dd>${esc(cells)}</dd><dt>Einheit</dt><dd>mV/V</dd>` +
      `<dt>Rahmenbereiche</dt><dd>${Array.isArray(setup.regions) ? setup.regions.length : '–'}</dd></dl></div>`;
  }
  if (status.state === 'confirmed') {
    const by = status.profile?.confirmed_by;
    return `<div class="ins"><h3>Bestätigt</h3><p>${by ? `Einrichtung bestätigt von ${esc(by)}. ` : ''}Lauf über die Titelleiste starten.</p></div>`;
  }
  return '';
}

function focusPaneHTML(status) {
  const model = focusChartModel(status.setup?.focus);
  const row = stepRows(status).find((r) => r.key === 'fokus');
  const state = {running: 'läuft', done: 'abgeschlossen', failed: 'abgebrochen', pending: 'ausstehend'}[row?.state] || '';
  const best = model.best ? `${Math.round(model.best.focus)} · ${Math.round(model.best.score)}` : '–';
  const v = model.verify;
  let check = '–';
  let cls = '';
  if (v && finite(v.threshold)) {
    check = `${Math.round(v.score)} ${v.passed ? '≥' : '<'} ${Math.round(v.threshold)}` +
      (model.best.score > 0 ? ` (${Math.round((100 * v.score) / model.best.score)} %)` : '');
    cls = v.passed ? 'ok-t' : 'err-t';
  }
  const method = {climb: 'Bergsteigen', sweep: 'Vollsweep'}[model.method] || '–';
  return {state, kv: `<dt>Bestwert</dt><dd>${esc(best)}</dd><dt>Gegenprüfung</dt><dd class="${cls}">${esc(check)}</dd>` +
    `<dt>Schwelle</dt><dd>${!model.line ? '–' : model.line.ratio ? `${Math.round(FOCUS_VERIFY_RATIO * 100)} % des Bestwerts`
      : esc(String(Math.round(model.line.value)))}</dd>` +
    `<dt>Proben</dt><dd>${model.points.length}</dd><dt>Verfahren</dt><dd class="t">${esc(method)}</dd>`,
  running: row?.state === 'running'};
}

function renderInspector(host, status, ui) {
  const runPhase = RUN_STATES.includes(status.state);
  const tabs = runPhase ? RUN_TABS : SETUP_TABS;
  const key = runPhase ? 'run' : 'setup';
  const current = currentTab(status, ui);
  if (!host._mounted) {
    host.innerHTML = '<div class="pt"><span>Inspektor</span><span class="pa" data-part="meta"></span></div>' +
      '<div class="tabs" role="tablist" aria-label="Inspektor" data-part="tabs"></div>' +
      '<div class="scroll" role="tabpanel" id="inspector-panel" data-part="body">' +
      '<div data-pane="Schritt"><div data-part="info"></div><div data-part="confirm"></div><div data-part="regions"></div></div>' +
      '<div data-pane="Fokus"><div class="blk"><h4>Fokus-Suche<span data-part="focus-state"></span></h4>' +
      '<svg class="chart" role="img" aria-label="Schärfekurve"></svg></div>' +
      '<div class="blk"><dl class="kv2" data-part="focus-kv"></dl></div></div>' +
      '<div data-pane="Prüfungen"></div><div data-pane="run"></div></div>';
    host._mounted = true;
    host.querySelector('[data-part="tabs"]').addEventListener('click', (event) => {
      const button = event.target.closest('[role="tab"]');
      if (!button) return;
      if (button.dataset.scope === 'run') ui.tab.run = button.dataset.tab;
      else ui.tab.setup = {tab: button.dataset.tab, auto: autoSetupTab(ui.status())};
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
    ui.mountSetup(host);
  }
  const running = stepRows(status).find((row) => row.state === 'running');
  host.querySelector('[data-part="meta"]').textContent = status.state === 'setup_running'
    ? (running?.label || '') : (STATE_META[status.state] || '');
  const warnings = runPhase ? 0 : warningCount(status);
  setHTML(host.querySelector('[data-part="tabs"]'), tabs.map((tab) =>
    `<button type="button" role="tab" data-scope="${key}" data-tab="${esc(tab)}" aria-controls="inspector-panel" ` +
    `aria-selected="${tab === current}" tabindex="${tab === current ? 0 : -1}">${esc(tab)}` +
    `${tab === 'Prüfungen' && warnings ? ` <span class="cnt">${warnings}</span>` : ''}</button>`).join(''));
  const pane = (name) => host.querySelector(`[data-pane="${name}"]`);
  for (const el of host.querySelectorAll('[data-pane]')) {
    el.hidden = runPhase ? el.dataset.pane !== 'run' : el.dataset.pane !== current;
  }
  if (runPhase) return;
  if (current === 'Schritt') setHTML(pane('Schritt').querySelector('[data-part="info"]'), stepInfoHTML(status));
  if (current === 'Fokus') {
    const focus = focusPaneHTML(status);
    host.querySelector('[data-part="focus-state"]').textContent = focus.state;
    setHTML(host.querySelector('[data-part="focus-kv"]'), focus.kv);
    renderFocusChart(pane('Fokus').querySelector('svg.chart'), status.setup?.focus, {running: focus.running});
  }
  if (current === 'Prüfungen') renderChecks(pane('Prüfungen'), status);
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
  let status = null;
  let conn = null;
  let confirmUi = null;
  let regionPanel = null;
  // Bereichsaenderung: solange die Antwort aussteht, sind Bestaetigen und weitere Klicks gesperrt.
  const regions = enableRegionEditing(viewerUi, client, null, {onBusy: () => render()});
  const ui = {busy: false, error: null, tab: {setup: null, run: null}, render: () => render(), status: () => status,
    mountSetup(host) {
      confirmUi = mountConfirm(host.querySelector('[data-part="confirm"]'), client,
        {locked: () => regions.busy(), onChange: () => renderTitle(status, titleView(), handlers)});
      regionPanel = mountRegionPanel(host.querySelector('[data-part="regions"]'), regions);
    }};

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
    confirm: () => confirmUi?.submit(),
    // Standardwerte der alten Seite: Referenz an, Diagnosebilder aus, kein Werteplan.
    runStart: () => act('/live/run/start', {test_override: false, reference: true, norm_schedule: null, diagnostics: false}),
    stop: () => act('/live/run/stop'),
  };
  const titleView = () => ({busy: ui.busy, canConfirm: Boolean(confirmUi?.ready()) && !regions.busy(), error: ui.error});

  function render() {
    if (!status) {
      renderTitle(status, titleView(), handlers);
      return;
    }
    renderLeftDock(nodes.leftDock, status, conn);
    regions.update(status);
    renderInspector(nodes.inspector, status, ui);
    confirmUi?.update(status);
    regionPanel?.update();
    renderTitle(status, titleView(), handlers);
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
