// Huelle der Live-Seite (Mock-Kapitel 1): Titelleiste, Dock links, Viewer,
// Zeitleiste, Ergebnis und Inspektor rechts, Statusleiste. Die Huelle kennt
// nur Layout und Kontextaktionen; Inhalte rendern die Ansichten in die
// zurueckgegebenen Knoten.
import {cameraView} from './model.js';

const ICONS = `<svg class="sprite" aria-hidden="true" focusable="false"><defs>
<symbol id="i-chev" viewBox="0 0 16 16"><path d="M6 3.5l4.5 4.5L6 12.5"/></symbol>
<symbol id="i-down" viewBox="0 0 10 10"><path d="M2.5 3.8L5 6.3l2.5-2.5"/></symbol>
<symbol id="i-run" viewBox="0 0 16 16"><path d="M5 3.5v9l7-4.5z"/></symbol>
<symbol id="i-stop" viewBox="0 0 16 16"><rect x="4" y="4" width="8" height="8"/></symbol>
<symbol id="i-flag" viewBox="0 0 16 16"><path d="M4 14V2.5M4 3h8l-1.8 3L12 9H4"/></symbol>
<symbol id="i-redo" viewBox="0 0 16 16"><path d="M12.5 4.5v3h-3"/><path d="M12.3 7.3A5 5 0 1 0 13 10"/></symbol>
<symbol id="i-zm" viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14M5 7h4"/></symbol>
<symbol id="i-zp" viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14M5 7h4M7 5v4"/></symbol>
<symbol id="i-fit" viewBox="0 0 16 16"><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/></symbol>
<symbol id="i-lay" viewBox="0 0 16 16"><path d="M8 2.5l5.5 3-5.5 3-5.5-3zM2.5 8.2l5.5 3 5.5-3M2.5 10.8l5.5 3 5.5-3"/></symbol>
<symbol id="i-lg" viewBox="0 0 16 16"><path d="M6 4.5h7.5M6 8h7.5M6 11.5h7.5"/><rect x="2.5" y="3.5" width="2" height="2"/><rect x="2.5" y="7" width="2" height="2"/><rect x="2.5" y="10.5" width="2" height="2"/></symbol>
</defs></svg>`;

const TEMPLATE = `${ICONS}
<div class="app">
  <header class="titlebar">
    <span class="brand">picam-ai Werkbank</span>
    <span class="vsep"></span>
    <nav class="crumbs" aria-label="Ablauf"><span data-crumb="setup">Einrichtung</span><svg class="i" aria-hidden="true"><use href="#i-chev"/></svg><span data-crumb="run">Lauf</span></nav>
    <span class="vsep"></span>
    <span class="device">GSV-2AS · Displaytech 161A</span>
    <span class="testband" role="alert" hidden>TESTLAUF – Werte nicht freigegeben</span>
    <div class="hdr-act"></div>
  </header>
  <aside class="dock ldock" aria-label="Ablauf"></aside>
  <main class="center">
    <section class="viewer-host" aria-label="Bildansicht"></section>
    <section class="strip" aria-label="Zeitleiste"></section>
  </main>
  <aside class="dock rdock" aria-label="Inspektor">
    <section class="judge" aria-label="Ergebnis" aria-live="polite" hidden></section>
    <div class="inspector"></div>
  </aside>
  <footer class="statusbar">
    <span class="it" data-item="camera"></span>
    <span class="it" data-item="preview">Vorschau <b data-slot="preview-fps">–</b><span data-slot="preview-note"></span></span>
    <span class="it" data-item="frames"></span>
    <span class="it" data-item="gaps"></span>
    <span class="it" data-item="latency"></span>
    <span class="it" data-item="storage"></span>
    <span class="it" data-item="reference"></span>
    <span class="it" data-item="tolerance" hidden></span>
    <span class="it notice" data-item="notice" hidden></span>
    <span class="it last" data-item="session"></span>
  </footer>
</div>`;

// Feldtext aus static/live.html (woertlich).
const CELL_TEXT_LABEL = 'Zellentext Zellen 0–8 – empfohlen: leer lassen (dann liest die Werkbank den Wert vom GSV-2AS). ' +
  'Bei Eingabe schwankende Ziffern mit ? markieren, z. B. „+0.4678?“';

let shell = null;

export const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const NNBSP = ' ';
export const grp = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
export const dec = (x, digits) => x.toFixed(digits).replace('.', ',');
const icon = (name) => `<svg class="i" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

function setHTML(el, html) {
  if (el._html !== html) {
    el._html = html;
    el.innerHTML = html;
  }
}

export function mountShell(root) {
  root.innerHTML = TEMPLATE;
  const q = (selector) => root.querySelector(selector);
  const items = Object.fromEntries([...root.querySelectorAll('.statusbar [data-item]')]
    .map((el) => [el.dataset.item, el]));
  shell = {root, crumbs: {setup: q('[data-crumb="setup"]'), run: q('[data-crumb="run"]')},
    testband: q('.testband'), titleActions: q('.hdr-act'), items, handlers: {}, signature: null};
  // Pop-up der Kontextaktion schliesst bei Klick daneben und mit Esc.
  root.ownerDocument.addEventListener('pointerdown', (event) => {
    const pop = shell?.titleActions.querySelector('.popover');
    if (pop && !pop.hidden && !event.target.closest?.('.popover, [data-popover-toggle]')) togglePopover(false);
  });
  return {
    titleActions: shell.titleActions,
    leftDock: q('.ldock'),
    viewerHost: q('.viewer-host'),
    resultHost: q('.judge'),
    inspector: q('.inspector'),
    timeline: q('.strip'),
    statusbar: q('.statusbar'),
  };
}

function togglePopover(open) {
  const pop = shell.titleActions.querySelector('.popover');
  const toggle = shell.titleActions.querySelector('[data-popover-toggle]');
  if (!pop || !toggle) return;
  pop.hidden = !open;
  toggle.setAttribute('aria-expanded', String(open));
  if (open) pop.querySelector('input')?.focus();
}

// Kontextaktionen je Zustand (Spec "Aufbau der Oberflaeche"). Fehlt ein
// Handler, bleibt der Knopf sichtbar, aber gesperrt.
function titleActions(status, view, handlers) {
  const state = status?.state;
  const busy = Boolean(view.busy);
  const actions = [];
  if (view.error) actions.push({kind: 'note', cls: 'err-t', text: view.error, alert: true});
  if (['idle', 'setup_failed', 'stopped'].includes(state)) {
    actions.push({kind: 'setup', label: state === 'stopped' ? 'Neu einrichten' : 'Einrichtung starten',
      icon: state === 'stopped' ? 'redo' : 'run', disabled: busy || !handlers.setup});
  } else if (state === 'setup_running') {
    actions.push({kind: 'note', text: 'Bestätigen erst nach dem Vorschlag'},
      {kind: 'button', name: 'confirm', label: 'Bestätigen', cls: 'primary', disabled: true, title: 'Erst nach dem Vorschlag'});
  } else if (state === 'setup_ready') {
    const ready = Boolean(view.canConfirm && handlers.confirm) && !busy;
    actions.push({kind: 'button', name: 'confirm', label: 'Bestätigen', cls: 'primary', disabled: !ready,
      title: ready ? '' : 'Name und Haken im Inspektor'});
  } else if (state === 'confirmed') {
    const by = status.profile?.confirmed_by;
    if (by) actions.push({kind: 'note', text: `Einrichtung bestätigt · ${by}`});
    // view.canStart (Pop-up): gesperrt bei Lesesperre ohne Testmodus-Haken.
    const canStart = view.canStart ?? !status.run_block;
    actions.push({kind: 'run', name: 'runStart', toggle: 'runOptions', label: 'Lauf starten', icon: 'run', cls: 'primary',
      disabled: busy || !handlers.runStart || !canStart, toggleDisabled: busy || !handlers.runOptions,
      expanded: Boolean(view.runOptionsOpen), title: status.run_block && !canStart ? status.run_block : ''});
  } else if (state === 'running') {
    actions.push({kind: 'button', name: 'mark', label: 'Ereignis markieren', icon: 'flag', popup: true,
      expanded: Boolean(view.markOpen), disabled: busy || !handlers.mark},
      {kind: 'button', name: 'stop', label: 'Lauf stoppen', icon: 'stop', cls: 'danger', disabled: busy || !handlers.stop});
  }
  return actions;
}

function actionHTML(action, index) {
  if (action.kind === 'note') {
    return `<span class="hdr-note ${action.cls || ''}"${action.alert ? ' role="alert"' : ''}>${esc(action.text)}</span>`;
  }
  if (action.kind === 'setup') {
    return `<div class="split"><button type="button" class="primary" data-action="${index}">${icon(action.icon)}${esc(action.label)}</button>` +
      `<button type="button" class="primary" data-popover-toggle aria-haspopup="dialog" aria-expanded="false" aria-label="Zellentext angeben" title="Zellentext (optional)">${icon('down')}</button></div>` +
      `<div class="popover" role="dialog" aria-label="Zellentext" hidden><label for="cell-text">${esc(CELL_TEXT_LABEL)}</label>` +
      `<input type="text" id="cell-text" class="mono" maxlength="9" autocomplete="off" spellcheck="false"></div>`;
  }
  if (action.kind === 'run') {
    return `<div class="split"><button type="button" class="primary" data-action="${index}">${icon(action.icon)}${esc(action.label)}</button>` +
      `<button type="button" class="primary" data-action-toggle="${index}" aria-haspopup="dialog" aria-expanded="false" ` +
      `aria-label="Laufoptionen" title="Referenz, Diagnosebilder, Werteplan, Testmodus">${icon('down')}</button></div>`;
  }
  const popup = action.popup ? ' aria-haspopup="dialog" aria-expanded="false"' : '';
  return `<button type="button" class="${action.cls || ''}" data-action="${index}"${popup}>${action.icon ? icon(action.icon) : ''}${esc(action.label)}</button>`;
}

export function renderTitle(status, view = {}, handlers = {}) {
  if (!shell) throw new Error('mountShell zuerst');
  shell.handlers = handlers;
  const state = status?.state;
  const runPhase = state === 'running' || state === 'stopped';
  for (const [key, el] of Object.entries(shell.crumbs)) {
    const current = (key === 'run') === runPhase;
    if (current) el.setAttribute('aria-current', 'step'); else el.removeAttribute('aria-current');
    el.classList.toggle('past', key === 'setup' && runPhase);
  }
  shell.testband.hidden = !status?.test_run;
  const actions = titleActions(status, view, handlers);
  const signature = JSON.stringify(actions.map(({kind, name, label, cls, text}) => [kind, name, label, cls, text]));
  if (signature !== shell.signature) {
    shell.signature = signature;
    shell.titleActions.innerHTML = actions.map(actionHTML).join('');
    shell.titleActions.querySelectorAll('[data-action]').forEach((button) => {
      const action = actions[Number(button.dataset.action)];
      button.onclick = () => {
        if (action.kind === 'setup') {
          const value = shell.titleActions.querySelector('#cell-text')?.value ?? '';
          togglePopover(false);
          shell.handlers.setup?.(value);
        } else {
          shell.handlers[action.name]?.(button);
        }
      };
    });
    shell.titleActions.querySelectorAll('[data-action-toggle]').forEach((button) => {
      const action = actions[Number(button.dataset.actionToggle)];
      button.onclick = () => shell.handlers[action.toggle]?.(button);
    });
    const toggle = shell.titleActions.querySelector('[data-popover-toggle]');
    if (toggle) {
      toggle.onclick = () => togglePopover(toggle.getAttribute('aria-expanded') !== 'true');
      shell.titleActions.querySelector('.popover').onkeydown = (event) => {
        if (event.key === 'Escape') { togglePopover(false); toggle.focus(); }
        if (event.key === 'Enter') shell.titleActions.querySelector('[data-action]')?.click();
      };
    }
  }
  // Sperren und Hinweise ohne Neuaufbau nachziehen (Fokus und Eingabe bleiben).
  shell.titleActions.querySelectorAll('[data-action]').forEach((button) => {
    const action = actions[Number(button.dataset.action)];
    button.disabled = Boolean(action.disabled);
    if (action.title) button.title = action.title; else button.removeAttribute('title');
    if (action.popup) button.setAttribute('aria-expanded', String(Boolean(action.expanded)));
  });
  shell.titleActions.querySelectorAll('[data-action-toggle]').forEach((button) => {
    const action = actions[Number(button.dataset.actionToggle)];
    button.disabled = Boolean(action.toggleDisabled);
    button.setAttribute('aria-expanded', String(Boolean(action.expanded)));
  });
  const toggle = shell.titleActions.querySelector('[data-popover-toggle]');
  if (toggle) toggle.disabled = Boolean(actions.find((a) => a.kind === 'setup')?.disabled);
}

function storageItem(storage) {
  if (!storage || storage.free_bytes == null) {
    const message = storage?.message || 'Speicherplatz nicht verfuegbar';
    return {cls: 'err', html: `<span class="sq err"></span>SD <b class="t">${esc(message)}</b>`, title: message};
  }
  const free = `${dec(storage.free_bytes / 1e9, 2)} GB`;
  const prefix = storage.level === 'error' ? 'Speicher knapp: ' : storage.level === 'warn' ? 'Warnung: unter 5 GB frei. ' : '';
  const level = storage.level === 'ok' ? '' : storage.level === 'warn' ? 'warn' : 'err';
  return {cls: level, html: `${level ? `<span class="sq ${level}"></span>` : ''}SD <b>${free}</b> frei`,
    title: `${prefix}SD-Speicher: ${free} frei`};
}

function referenceItem(reference) {
  // Texte aus static/live.js (woertlich).
  if (reference?.restoring) return {cls: 'warn', html: '<span class="sq warn"></span>Werte werden zurückgestellt …', title: ''};
  if (reference?.error) return {cls: 'err', html: `<span class="sq err"></span>${esc(reference.error)}`, title: reference.error};
  if (reference?.enabled) {
    return {cls: '', html: `<span class="sq ok"></span>Referenz <b>${grp(reference.lines ?? 0)}</b> Telegramme`,
      title: `Referenz: ${reference.lines} Telegramme`};
  }
  const text = `ohne Referenz: ${reference?.reason || 'nicht gestartet'}`;
  return {cls: '', html: `<span class="sq stale"></span>${esc(text)}`, title: text};
}

function setItem(el, {html, cls = '', title = '', hidden = false}) {
  el.hidden = hidden;
  if (hidden) return;
  setHTML(el, html);
  el.classList.toggle('warn', cls === 'warn');
  el.classList.toggle('err', cls === 'err');
  if (title) el.title = title; else el.removeAttribute('title');
}

// hudProc = X-Hud.proc ({fps, latency_ms, skipped_recent}) des zuletzt
// gezeigten Bilds oder null. Die gemessene Vorschau-Rate traegt der Viewer
// in [data-slot="preview-fps"] ein (Aufgabe 7); X-Hud.preview.fps ist nur
// die Soll-Rate des Servers.
export function renderStatusbar(status, hudProc = null) {
  if (!shell) throw new Error('mountShell zuerst');
  const {items} = shell;
  const camera = status?.camera || {};
  const source = camera.source || {};
  const name = source.model === 'logitech_streamcam' ? 'StreamCam' : (source.model || 'Kamera');
  let cam;
  if (camera.stalled) cam = {cls: 'err', html: `<span class="sq err"></span><b class="t">${esc(name)}</b> · kein Bild`};
  else if (camera.running) {
    const size = Array.isArray(source.size) ? ` · ${source.size[0]}×${source.size[1]}` : '';
    const fps = finite(source.fps) ? ` · ${source.fps} fps` : '';
    cam = {cls: '', html: `<span class="sq ok"></span><b class="t">${esc(name)}</b>${size}${fps}`};
  } else cam = {cls: 'err', html: `<span class="sq err"></span><b class="t">${esc(name)}</b> · aus`};
  setItem(items.camera, {...cam, title: cameraView(camera)});
  setItem(items.frames, {html: `Bilder <b>${finite(camera.frames) ? grp(camera.frames) : '–'}</b>`});
  setItem(items.gaps, {html: `Lücken <b>${finite(camera.gaps) ? grp(camera.gaps) : '–'}</b>`,
    cls: camera.gaps > 0 ? 'warn' : ''});
  setItem(items.latency, {html: `Latenz <b>${finite(hudProc?.latency_ms) ? `${Math.round(hudProc.latency_ms)} ms` : '–'}</b>`});
  setItem(items.storage, storageItem(status?.storage));
  setItem(items.reference, referenceItem(status?.reference));
  const tolerance = status?.reader_tolerance;
  setItem(items.tolerance, {hidden: !tolerance, cls: 'warn',
    html: `<span class="sq warn"></span>Lesetoleranz <b>×${esc(tolerance?.factor)}</b> nicht validiert`,
    title: tolerance ? `Angepasste Lesetoleranz ×${tolerance.factor}: Werte nur in dieser Aufstellung gegen Referenz geprüft, nicht validiert.` : ''});
  const notice = status?.release_notice;
  setItem(items.notice, {hidden: !notice, html: `<span>${esc(notice)}</span>`, title: notice || ''});
  setItem(items.session, {html: `Sitzung <b>${esc(status?.session_id || '–')}</b>`});
}
