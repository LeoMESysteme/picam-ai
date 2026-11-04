// Pop-ups der Laufaktionen in der Titelleiste (Spec "Aufbau der Oberflaeche"):
// Lauf starten mit Referenz, Diagnosebilder, Werteplan und Testmodus, und
// Ereignis markieren mit Text. Texte, Ablauf und POST-Koerper woertlich aus
// der alten Live-Seite; window.confirm ist durch openModal ersetzt.
import {openModal} from '../ui/modal.js';

const TEXT = {
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
  const canStart = () => !busy && !(status?.run_block && !part('override').checked);
  const refresh = () => {
    part('start').disabled = !canStart();
    onChange();
  };
  part('override').addEventListener('change', refresh);
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
      if (key !== resetKey) { resetKey = key; part('override').checked = false; }
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
          norm_schedule: schedule || null, diagnostics: part('diagnostics').checked};
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
