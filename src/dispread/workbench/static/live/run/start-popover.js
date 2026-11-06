// Pop-ups der Laufaktionen in der Titelleiste (Spec "Aufbau der Oberflaeche"):
// Lauf starten mit Referenz, Diagnosebilder, Werteplan und Testmodus, und
// Ereignis markieren mit Text. Texte, Ablauf und POST-Koerper woertlich aus
// der alten Live-Seite; window.confirm ist durch openModal ersetzt.
import {openModal} from '../ui/modal.js';
import {BAUDRATES, DEFAULTS, LOCK_NOTICE, NAMES, PATHS, SERIAL_ACK, SERIAL_NOTE, TEST_BLOCK, configText,
  loadChoice, outputBody, saveChoice} from './output.js';

const TEXT = {
  serialAck: 'Bitte zuerst den Haken „Mir ist bewusst“ setzen: UART direkt ist nicht abgenommen.',
  blockTitle: 'Lauf gesperrt — Leser konnte die Einrichtungsbilder nicht lesen',
  testSummary: 'Testmodus (nur zu Testzwecken)',
  testLabel: 'Lesesperre übergehen – Testlauf, Werte sind nicht freigegeben und nicht für Messungen zu verwenden',
  reference: 'Referenz vom GSV-2AS mitschreiben',
  diagnostics: 'Diagnosebilder aufzeichnen (fuer Fehlersuche, bis 600 MB RAM und SD je Lauf; zum Sparen von SD-Platz standardmaessig aus)',
  plan: 'Werteplan (set norm), z. B. 1:20,2:20,0.5:20',
  planPlaceholder: 'optional: Faktor:Sekunden',
  planNote: 'schreibt in den RAM des GSV-2AS (laut Messung 2026-10 EEnow = 0 an diesem Gerät, kein EEPROM-Verschleiss; nicht live geprüft)',
  planNeedsReference: 'Werteplan braucht Referenzaufzeichnung',
  testTitle: 'TESTLAUF starten?',
  testText: 'Die Lesesperre wird übergangen. Angezeigte Vermutungen und Werte sind nicht freigegeben und dürfen nicht für Messungen verwendet werden. Der Lauf wird als Testlauf gekennzeichnet (TESTLAUF.json).',
  planTitle: 'Werteplan anwenden?',
  planText: 'Der Plan schreibt in den RAM des GSV-2AS. Beim Stoppen werden die Ausgangswerte zurückgestellt und geprüft. Gerät verbunden lassen.',
  outputGroup: 'GSVmulti-Ausgabe',
  markLabel: 'Ereignis (Meldezeit des Bedieners):',
};

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// Gemeinsames Verhalten: Klick daneben und Esc schliessen, Fokus zurueck auf den Ausloeser.
function popoverShell(host, {label, cls}) {
  const el = host.ownerDocument.createElement('div');
  el.className = `popover ${cls}`;
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-label', label);
  el.hidden = true;
  host.append(el);
  let anchor = null;
  const api = {
    el,
    isOpen: () => !el.hidden,
    open(trigger = null) {
      anchor = trigger || anchor;
      el.hidden = false;
      anchor?.setAttribute('aria-expanded', 'true');
      el.querySelector('input:not([type=checkbox]), input, button')?.focus();
    },
    close({focus = false} = {}) {
      if (el.hidden) return;
      el.hidden = true;
      anchor?.setAttribute('aria-expanded', 'false');
      if (focus && anchor?.isConnected) anchor.focus();
    },
    toggle(trigger) { if (el.hidden) api.open(trigger); else api.close(); },
  };
  el.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.stopPropagation(); api.close({focus: true}); }
  });
  host.ownerDocument.addEventListener('pointerdown', (event) => {
    if (!el.hidden && !el.contains(event.target) && !(anchor && anchor.contains(event.target))) api.close();
  });
  return api;
}

// host: Titelleiste (Pop-up rechts darunter). onStart(body) sendet den Start;
// ohne onStart geht der POST direkt ueber client. confirm = openModal.
export function mountStartPopover(host, client, {onStart = null, confirm = openModal, onChange = () => {}} = {}) {
  const pop = popoverShell(host, {label: 'Laufoptionen', cls: 'runpop'});
  pop.el.innerHTML =
    `<div class="runblock" data-part="block" hidden><strong>${esc(TEXT.blockTitle)}</strong><p data-part="block-reason"></p></div>` +
    `<label class="ck"><input type="checkbox" data-part="reference" checked> ${esc(TEXT.reference)}</label>` +
    `<label class="ck"><input type="checkbox" data-part="diagnostics"> ${esc(TEXT.diagnostics)}</label>` +
    `<label class="f" for="norm-schedule">${esc(TEXT.plan)}</label>` +
    `<input type="text" id="norm-schedule" class="mono" data-part="plan" placeholder="${esc(TEXT.planPlaceholder)}" autocomplete="off" spellcheck="false">` +
    `<p class="note">${esc(TEXT.planNote)}</p>` +
    `<fieldset class="outgrp" data-part="output"><legend>${esc(TEXT.outputGroup)}</legend>` +
    `<div class="seg" role="radiogroup" aria-label="${esc(TEXT.outputGroup)}">${PATHS.map(([key, label]) =>
      `<label><input type="radio" name="output-path" value="${key}" data-part="path-${key}"><span>${esc(label)}</span></label>`).join('')}</div>` +
    '<div data-part="out-serial" hidden>' +
    '<label class="f" for="out-port">Port</label><input type="text" id="out-port" class="mono" data-part="out-port" autocomplete="off" spellcheck="false">' +
    '<label class="f" for="out-baud">Baudrate</label><select id="out-baud" class="mono" data-part="out-baud">' +
    BAUDRATES.map((b) => `<option value="${b}">${b}</option>`).join('') + '</select>' +
    '<label class="f" for="out-prefix">Präfix</label><input type="text" id="out-prefix" class="mono" maxlength="1" data-part="out-prefix" autocomplete="off" spellcheck="false">' +
    `<p class="note err-t" data-part="out-note">${esc(SERIAL_NOTE)}</p>` +
    `<label class="ck"><input type="checkbox" data-part="out-ack"> ${esc(SERIAL_ACK)}</label></div>` +
    '<div data-part="out-tcpbox" hidden><label class="f" for="out-tcp">TCP-Port</label>' +
    '<input type="number" id="out-tcp" class="mono" min="1" max="65535" data-part="out-tcp"></div>' +
    `<p class="note warn-t" data-part="out-lock" hidden>${esc(LOCK_NOTICE)}</p>` +
    '<p class="note" data-part="out-ro" hidden></p></fieldset>' +
    `<details class="fold" data-part="test" hidden><summary>${esc(TEXT.testSummary)}</summary>` +
    `<label class="ck"><input type="checkbox" data-part="override"> ${esc(TEXT.testLabel)}</label></details>` +
    '<p class="msg err-t" role="alert" data-part="error" hidden></p>' +
    '<div class="fa"><button type="button" class="primary" data-part="start">Lauf starten</button></div>';
  const part = (name) => pop.el.querySelector(`[data-part="${name}"]`);
  let status = null;
  let resetKey = null;
  let busy = false;
  const showError = (text) => {
    part('error').textContent = text || '';
    part('error').hidden = !text;
  };
  const running = () => status?.state === 'running' && status?.output;
  const choice = () => PATHS.map(([key]) => key).find((key) => part(`path-${key}`).checked) || 'off';
  const showOutput = () => {
    const mode = choice();
    part('out-serial').hidden = mode !== 'serial';
    part('out-tcpbox').hidden = mode !== 'tcp';
    part('out-lock').hidden = !['uart', 'tcp'].includes(mode);
  };
  const setChoice = (key) => { part(`path-${key}`).checked = true; showOutput(); };
  part('out-port').value = DEFAULTS.port;
  part('out-baud').value = String(DEFAULTS.baudrate);
  part('out-prefix').value = DEFAULTS.prefix;
  part('out-tcp').value = String(DEFAULTS.tcpPort);
  setChoice(loadChoice());
  const canStart = () => !busy && !(status?.run_block && !part('override').checked) &&
    !(choice() === 'serial' && !part('out-ack').checked);
  const refresh = () => {
    part('start').disabled = !canStart();
    onChange();
  };
  // Testmodus bietet keine Ausgabe an: Auswahl und Felder gesperrt, gezeigt als "Aus"
  // (der gespeicherte Weg kommt beim Abwaehlen zurueck; der Start bleibt abgelehnt).
  let beforeTest = null;
  const syncTest = () => {
    const test = part('override').checked && !running();
    if (test && beforeTest === null) { beforeTest = choice(); setChoice('off'); }
    else if (!test && beforeTest !== null) { setChoice(beforeTest); beforeTest = null; }
    for (const el of part('output').querySelectorAll('input, select')) el.disabled = test || Boolean(running());
  };
  part('override').addEventListener('change', () => { showError(''); syncTest(); refresh(); });
  part('out-ack').addEventListener('change', () => { showError(''); refresh(); });
  for (const [key] of PATHS) {
    part(`path-${key}`).addEventListener('change', () => { saveChoice(key); showOutput(); showError(''); refresh(); });
  }
  part('plan').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); api.start(); }
  });
  part('start').addEventListener('click', () => api.start());
  for (const name of ['reference', 'plan']) part(name).addEventListener('input', () => showError(''));

  const api = {
    ...pop,
    canStart,
    update(next) {
      status = next;
      // Jeder neue Vorschlag bzw. jede neue Sitzung verlangt einen neuen Testmodus-Haken.
      const key = `${next?.session_id}|${next?.setup?.proposal_revision ?? ''}`;
      if (key !== resetKey) { resetKey = key; part('override').checked = false; part('out-ack').checked = false; }
      // Im Lauf schreibgeschuetzt und aus status.output.config vorbelegt.
      const live = running();
      for (const el of part('output').querySelectorAll('input, select')) el.disabled = Boolean(live);
      part('out-ro').hidden = !live;
      syncTest();
      if (live) {
        const out = status.output;
        setChoice(out.transport);
        const c = out.config || {};
        if (out.transport === 'serial') {
          part('out-port').value = c.port ?? DEFAULTS.port;
          part('out-baud').value = String(c.baudrate ?? DEFAULTS.baudrate);
          part('out-prefix').value = c.prefix ?? DEFAULTS.prefix;
        } else if (out.transport === 'tcp') part('out-tcp').value = String(c.tcp_port ?? DEFAULTS.tcpPort);
        part('out-ro').textContent = out.transport === 'off' ? 'Im Lauf nicht änderbar.'
          : `${NAMES[out.transport]}: ${configText(out)} · im Lauf nicht änderbar.`;
      }
      part('block').hidden = !next?.run_block;
      part('block-reason').textContent = next?.run_block || '';
      part('test').hidden = !next?.run_block;
      if (!next?.run_block) part('override').checked = false;
      part('diagnostics').disabled = next?.state === 'running';
      if (next?.state !== 'confirmed') pop.close();
      refresh();
    },
    // Ablauf wie run-start der alten Live-Seite: Sperre, Testlauf-Dialog, Werteplan-Pruefung und -Dialog.
    async start() {
      if (busy) return null;
      const override = Boolean(status?.run_block && part('override').checked);
      if (status?.run_block && !override) return null;
      const mode = choice();
      if (mode === 'serial' && !part('out-ack').checked) {
        showError(TEXT.serialAck);
        pop.open();
        return null;
      }
      if (override && mode !== 'off') {
        showError(TEST_BLOCK);
        pop.open();
        return null;
      }
      busy = true;
      refresh();
      try {
        if (override && await confirm({title: TEXT.testTitle, text: TEXT.testText, tone: 'err', actions: [
          {label: 'Abbrechen', value: false, escape: true}, {label: 'Testlauf starten', value: true, primary: true}]}) !== true) return null;
        // Jeder Testlauf braucht einen neuen Haken.
        if (override) part('override').checked = false;
        const schedule = part('plan').value.trim();
        if (schedule && !part('reference').checked) {
          showError(TEXT.planNeedsReference);
          pop.open();
          return null;
        }
        if (schedule && await confirm({title: TEXT.planTitle, text: TEXT.planText, tone: 'warn', actions: [
          {label: 'Abbrechen', value: false, escape: true}, {label: 'Werteplan anwenden', value: true, primary: true}]}) !== true) return null;
        showError('');
        pop.close();
        const body = {test_override: override, reference: part('reference').checked,
          norm_schedule: schedule || null, diagnostics: part('diagnostics').checked,
          output: outputBody(mode, {port: part('out-port').value, baudrate: part('out-baud').value,
            prefix: part('out-prefix').value, tcpPort: part('out-tcp').value, ack: part('out-ack').checked})};
        part('out-ack').checked = false;
        return onStart ? await onStart(body) : await client.post('/live/run/start', body);
      } finally {
        busy = false;
        refresh();
      }
    },
  };
  return api;
}

// Ereignis markieren: Text 1–200 Zeichen (session.mark), Meldezeit setzt der Server.
export function mountMarkPopover(host, client, {onMarked = () => {}, onError = () => {}} = {}) {
  const pop = popoverShell(host, {label: 'Ereignis markieren', cls: 'markpop'});
  pop.el.innerHTML = `<label class="f" for="mark-text">${esc(TEXT.markLabel)}</label>` +
    '<div class="inrow"><input type="text" id="mark-text" maxlength="200" autocomplete="off" data-part="text">' +
    '<button type="button" class="primary" data-part="send">Marke setzen</button></div>' +
    '<p class="msg err-t" role="alert" data-part="error" hidden></p>' +
    '<p class="note" data-part="last" role="status"></p>';
  const part = (name) => pop.el.querySelector(`[data-part="${name}"]`);
  let busy = false;
  const send = async () => {
    const text = part('text').value;
    // Wie die alte Seite: auch ein leerer Text geht an den Server, dessen Antwort steht woertlich da.
    if (busy) return;
    busy = true;
    part('send').disabled = true;
    const result = await client.post('/live/run/mark', {text});
    busy = false;
    part('send').disabled = false;
    part('error').hidden = result.ok;
    part('error').textContent = result.ok ? '' : result.error;
    if (result.ok) {
      part('text').value = '';
      pop.close({focus: true});
      onMarked(text);
    } else onError(result.error);
  };
  part('send').addEventListener('click', send);
  part('text').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); send(); }
  });
  return {
    ...pop,
    update(status) {
      const mark = status?.last_mark;
      part('last').textContent = mark ? `Letzte Marke (Meldezeit): ${mark.received_at_utc} · ${mark.text}` : '';
      if (status?.state !== 'running') pop.close();
    },
  };
}
