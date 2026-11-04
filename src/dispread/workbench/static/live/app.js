// Einstieg der Live-Seite /live: Huelle aufbauen, Status abrufen, rendern.
// Entscheidungen fallen im Server (dispread.live), nie hier. Die Ansichten
// fuer Einrichtung, Lauf, Effekte und Einarbeitung kommen in eigenen
// Modulen dazu; der Viewer zeigt den MJPEG-Strom mit HUD.
import {createClient} from './api.js';
import {openPreview} from './mjpeg.js';
import {mountViewer} from './viewer/view.js';
import {enableRegionEditing, mountRegionPanel} from './viewer/regions-edit.js';
import {cameraView, statusView, stepRows} from './model.js';
import {dec, esc, mountShell, renderStatusbar, renderTitle} from './shell.js';
import {renderSteps} from './setup/steps.js';
import {focusChartModel, renderFocusChart, FOCUS_VERIFY_RATIO} from './setup/focus-chart.js';
import {exposureHTML} from './setup/exposure.js';
import {overallView, renderChecks, warningCount} from './setup/checks.js';
import {mountConfirm} from './setup/confirm.js';
import {renderResult} from './run/result.js';
import {runDockHTML, runTitle} from './run/dock.js';
import {RUN_TABS, createRecordLog, renderRunInspector, runBadges} from './run/inspector.js';
import {createTimeline} from './run/timeline.js';
import {mountMarkPopover, mountStartPopover} from './run/start-popover.js';

const RUN_STATES = ['running', 'stopped'];
const SETUP_TABS = ['Schritt', 'Fokus', 'Prüfungen'];
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

function renderLeftDock(host, status, conn, run = {}) {
  if (!host._mounted) {
    host.innerHTML = '<div class="pt"><span data-part="title"></span><span class="pa mono" data-part="meta"></span></div>' +
      '<div class="scroll" data-part="body"><div data-part="lead"></div><div data-part="steps"></div>' +
      '<div data-part="run" hidden></div></div>' +
      '<dl class="facts" data-part="facts"></dl>';
    host._mounted = true;
  }
  const part = (name) => host.querySelector(`[data-part="${name}"]`);
  const runPhase = RUN_STATES.includes(status.state);
  part('title').textContent = runPhase ? runTitle(status) : 'Ablauf';
  part('meta').textContent = runPhase ? (status.state === 'running' ? 'läuft' : 'beendet')
    : status.state === 'setup_running' && finite(status.setup?.elapsed_s)
      ? mmss(status.setup.elapsed_s) : status.state === 'idle' ? 'Einrichtung' : '';
  // Im Lauf traegt die Ergebnisanzeige rechts den Zustand; links stehen Laufdaten.
  part('lead').hidden = runPhase && !conn?.offline;
  setHTML(part('lead'), leadHTML(status, conn));
  part('steps').hidden = runPhase;
  renderSteps(part('steps'), runPhase ? [] : stepRows(status));
  part('run').hidden = !runPhase;
  if (runPhase) setHTML(part('run'), runDockHTML(status, {resultCls: run.resultCls}));
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
    ? (running?.label || '') : runPhase ? runTitle(status) : (STATE_META[status.state] || '');
  const warnings = runPhase ? 0 : warningCount(status);
  const badges = runPhase ? runBadges(status) : {};
  setHTML(host.querySelector('[data-part="tabs"]'), tabs.map((tab) =>
    `<button type="button" role="tab" data-scope="${key}" data-tab="${esc(tab)}" aria-controls="inspector-panel" ` +
    `aria-selected="${tab === current}" tabindex="${tab === current ? 0 : -1}">${esc(tab)}` +
    `${tab === 'Prüfungen' && warnings ? ` <span class="cnt">${warnings}</span>` : ''}` +
    `${badges[tab] ? ` <span class="cnt err-t">${badges[tab]}</span>` : ''}</button>`).join(''));
  const pane = (name) => host.querySelector(`[data-pane="${name}"]`);
  for (const el of host.querySelectorAll('[data-pane]')) {
    el.hidden = runPhase ? el.dataset.pane !== 'run' : el.dataset.pane !== current;
  }
  if (runPhase) {
    renderRunInspector(pane('run'), status, current, ui.runContext());
    return;
  }
  if (current === 'Schritt') setHTML(pane('Schritt').querySelector('[data-part="info"]'), stepInfoHTML(status));
  if (current === 'Fokus') {
    const focus = focusPaneHTML(status);
    host.querySelector('[data-part="focus-state"]').textContent = focus.state;
    setHTML(host.querySelector('[data-part="focus-kv"]'), focus.kv);
    renderFocusChart(pane('Fokus').querySelector('svg.chart'), status.setup?.focus, {running: focus.running});
  }
  if (current === 'Prüfungen') renderChecks(pane('Prüfungen'), status);
}

const LEGEND = [['ok', 'Freigegeben'], ['warn', 'Wechselt'], ['err', 'Unlesbar'], ['stale', 'Veraltet']]
  .map(([tone, word]) => `<span><span class="sq ${tone}"></span>${word}</span>`).join('') +
  '<span><svg width="16" height="8" aria-hidden="true"><path d="M0 6h6V2h10" stroke="#ebe7e0" fill="none" stroke-width="1.5"/></svg>Wert</span>';

function mountTimeline(host) {
  host.innerHTML = '<div class="pt"><span data-part="title">Zeitleiste</span><span class="pa slg" data-part="legend"></span></div>' +
    '<canvas class="stripc" role="img" aria-label="Statusband und Wertspur der letzten 40 s" hidden></canvas>';
  return {title: host.querySelector('[data-part="title"]'), legend: host.querySelector('[data-part="legend"]'),
    canvas: host.querySelector('canvas')};
}

function renderTimelineChrome(parts, status) {
  const runPhase = RUN_STATES.includes(status.state);
  parts.canvas.hidden = !runPhase;
  parts.title.textContent = !runPhase ? 'Zeitleiste'
    : status.state === 'running' ? `Zeitleiste · ${runTitle(status)} · letzte 40 s` : `Zeitleiste · ${runTitle(status)}`;
  setHTML(parts.legend, runPhase ? LEGEND : '');
}

const HINT_LABEL = {anzeige_bewegt: 'Anzeige bewegt', rahmen_verdeckt: 'Rahmen verdeckt', unbekannt: 'Nachführung unsicher'};

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
  let hud = null;
  const timelineParts = mountTimeline(nodes.timeline);
  const timeline = createTimeline(timelineParts.canvas);
  const log = createRecordLog();
  let runKey = null;
  let resultModel = null;
  let runDirty = false;
  // mark: undefined = dieser Lauf noch ungesehen (Neuladen), sonst Kennung der letzten Marke.
  const seen = {mark: undefined, hint: null, stalled: false};
  // Bereichsaenderung: solange die Antwort aussteht, sind Bestaetigen und weitere Klicks gesperrt.
  const regions = enableRegionEditing(viewerUi, client, null, {onBusy: () => render()});
  const ui = {busy: false, error: null, tab: {setup: null, run: null}, render: () => render(), status: () => status,
    runContext: () => ({log, hud, result: resultModel}),
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
    // Optionen und Bestaetigungen im Pop-up (Referenz, Diagnosebilder, Werteplan, Testmodus).
    runStart: () => startPop.start(),
    runOptions: (button) => startPop.toggle(button),
    mark: (button) => markPop.toggle(button),
    stop: () => act('/live/run/stop'),
  };
  const titleView = () => ({busy: ui.busy, canConfirm: Boolean(confirmUi?.ready()) && !regions.busy(), error: ui.error,
    canStart: startPop.canStart(), runOptionsOpen: startPop.isOpen(), markOpen: markPop.isOpen()});
  const titlebar = nodes.titleActions.closest('.titlebar');
  const startPop = mountStartPopover(titlebar, client, {onStart: (body) => act('/live/run/start', body),
    onChange: () => renderTitle(status, titleView(), handlers)});
  const markPop = mountMarkPopover(titlebar, client);

  // Ergebnis: Statuswort nach derselben Regel wie das HUD-Etikett (Bildalter laeuft mit).
  const renderRun = () => {
    if (!status) return;
    const frameAgeS = viewerUi.viewer.frameAgeS();
    resultModel = renderResult(nodes.resultHost, statusView(status), status, hud?.rec || null,
      {frameAgeS, offline: Boolean(conn?.offline), track: hud?.track || null});
  };

  // Zeitleiste: run.recent ist massgeblich und wird je Statusabruf neu angelegt;
  // Ereignismarken (Bediener, Stoerungen) legt der Client auf seine Achse.
  function updateTimeline(next) {
    const key = RUN_STATES.includes(next.state) ? `${next.session_id}|${next.run?.dir}` : null;
    if (key !== runKey) {
      runKey = key;
      timeline.clear();
      log.clear();
      Object.assign(seen, {mark: undefined, hint: null, stalled: false});
    }
    if (!key) return;
    const nowMs = performance.now();
    const back = (seconds) => nowMs - Math.min(60, Math.max(0, seconds)) * 1000;
    timeline.freeze(next.state === 'stopped');
    timeline.setUnit(next.run?.latest?.unit);
    if (next.state === 'running' || timeline.buckets().length === 0) timeline.seed(next.run?.recent, next.run?.recent_now_ms);
    const mark = next.last_mark;
    const markKey = mark ? `${mark.number ?? ''}|${mark.received_at_utc}|${mark.text}` : null;
    if (markKey && markKey !== seen.mark) {
      // Neu waehrend des Zusehens: seit dem letzten Abruf gesetzt. Nach dem
      // Neuladen aus der Meldezeit (Uhren von Pi und Browser koennen abweichen).
      const age = seen.mark === undefined ? (Date.now() - Date.parse(mark.received_at_utc)) / 1000 : 0.25;
      timeline.mark(back(Number.isFinite(age) ? age : 0), mark.text, 'mark');
    }
    seen.mark = markKey;
    const hint = next.state === 'running' ? next.run?.tracking_hint?.kind || null : null;
    if (hint && hint !== seen.hint) timeline.mark(back(next.run.tracking_hint.since_s || 0), HINT_LABEL[hint] || hint, 'stoerung');
    seen.hint = hint;
    const stalled = next.state === 'running' && Boolean(next.camera?.stalled);
    if (stalled && !seen.stalled) timeline.mark(nowMs, 'Stillstand', 'stoerung');
    seen.stalled = stalled;
  }

  function render() {
    if (!status) {
      renderTitle(status, titleView(), handlers);
      return;
    }
    startPop.update(status);
    markPop.update(status);
    renderRun();
    renderLeftDock(nodes.leftDock, status, conn, {resultCls: resultModel?.cls});
    regions.update(status);
    renderInspector(nodes.inspector, status, ui);
    confirmUi?.update(status);
    regionPanel?.update();
    renderTitle(status, titleView(), handlers);
    renderTimelineChrome(timelineParts, status);
    updateTimeline(status);
    timeline.draw();
    renderStatusbar(status, hudProc);
    viewerUi.setStatus(status);
  }

  // Vorschau nur bei sichtbarer Seite: ein Hintergrund-Tab kostet den Pi keine Kodierung.
  let preview = null;
  const startPreview = () => {
    if (preview) return;
    preview = new AbortController();
    openPreview('/live/preview.mjpg', ({bitmap, hud: frameHud}) => {
      hudProc = frameHud?.proc || null;
      hud = frameHud || null;
      viewerUi.setFrame(bitmap, frameHud);
      if (status?.state === 'running' && log.note(hud?.rec, {testRun: Boolean(status.test_run)})) runDirty = true;
    }, preview.signal, {onState: viewerUi.setStream});
  };
  const stopPreview = () => {
    preview?.abort();
    preview = null;
  };
  document.addEventListener('visibilitychange', () => (document.hidden ? stopPreview() : startPreview()));
  if (!document.hidden) startPreview();

  // Ruhiger Takt fuer Ergebnis und Datensaetze
  // zwischen den Statusabrufen (Bild- und Wertalter zaehlen weiter).
  setInterval(() => {
    if (!status || !RUN_STATES.includes(status.state) || document.hidden) return;
    renderRun();
    if (runDirty || ui.tab.run === 'Nachführung') {
      runDirty = false;
      renderInspector(nodes.inspector, status, ui);
    }
  }, 200);
  // Mitlaufen des rechten Rands (20 px/s bei 1440 px): 10 Bilder je Sekunde, nur im laufenden Lauf.
  setInterval(() => {
    if (status?.state === 'running' && !document.hidden) timeline.draw();
  }, 100);
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => timeline.draw()).observe(timelineParts.canvas);

  client.start((next) => {
    status = next;
    render();
  }, (next) => {
    conn = next;
    document.body.classList.toggle('offline', next.offline);
    if (status) {
      renderRun();
      renderLeftDock(nodes.leftDock, status, conn, {resultCls: resultModel?.cls});
    }
  });
  render();
}
