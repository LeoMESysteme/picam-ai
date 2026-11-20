// Bestaetigen im Inspektor, Tab Schritt (Spec "Einrichtungs-Fortschritt":
// Felder wie heute; Mock-Kapitel 7, #t=50). Felder, Texte und POST-Koerper
// sind woertlich aus der alten Live-Seite uebernommen. Bestaetigen geht
// nur ueber client.post (HTTPS mit CSRF, Wahrheitsregel 5); Antworten des
// Servers erscheinen woertlich und inline (Wahrheitsregel 6). Bei neuer
// proposal_revision oder session_id beginnt die Bestaetigung von vorn.

// Gesamturteil FEHLER: Bestaetigen ist gesperrt, der Weg ist Neu einrichten (OQ-71).
export const FAILED_CONFIRM_REASON = 'Bestätigen nicht möglich: Prüfung FEHLER – neu einrichten';
// Angepasste Toleranz mit von Hand eingegebenem Wert: der Server erlaubt sie nur,
// wenn alle Standbilder in den vergleichbaren Zellen gleich gelesen wurden.
export const MANUAL_REFERENCE_NOTE = 'Referenz: von Hand eingegeben – Anzeige war während der Standbilder unverändert';
export const MANUAL_REFERENCE_FLICKER_NOTE = 'Referenz: von Hand eingegeben – Anzeige war während der Standbilder bis auf die letzte Stelle (±1) unverändert';
// Von Hand eingegebener Wert, nur die letzte Stelle sprang um 1 (setup_checks.LAST_PLACE_HINT).
export const LAST_PLACE_NOTE = 'Letzte Stelle schwankte (±1) – als Schwanken gewertet';
// Kein Standbild zeigte genau den eingegebenen Wert, alle ±1 (setup_checks.NEVER_EXACT_HINT,
// Beleg letzte_stelle_nie_exakt): kein Schwanken belegt, Gegenlesen WARNUNG.
export const NEVER_EXACT_NOTE = 'Kein Standbild zeigt genau den eingegebenen Wert (alle ±1 in der letzten Stelle)';

const cellValue = (text) => String(text ?? '').slice(1, 8).trim();

// Belege des Gegenlesens (metrics.notes, mit angepasster Toleranz auch die der Gegenprobe) als ein Satz.
export function lastPlaceText(metrics) {
  const seen = new Set();
  const notes = [...(metrics?.notes || []), ...(metrics?.tolerance?.possible ? metrics.tolerance.notes || [] : [])]
    .filter((note) => note?.code === 'letzte_stelle_schwankt')
    .filter((note) => { const key = `${note.frame}\u0000${note.read}`; if (seen.has(key)) return false; seen.add(key); return true; });
  if (!notes.length) return null;
  const details = notes.map((note) => `Standbild ${Number(note.frame) + 1}: eingegeben ${cellValue(note.reference)}, gelesen ${cellValue(note.read)}`);
  const neverExact = (metrics?.notes || []).some((note) => note?.code === 'letzte_stelle_nie_exakt');
  return `${neverExact ? NEVER_EXACT_NOTE : LAST_PLACE_NOTE} (${details.join('; ')}).`;
}

export function confirmModel(status) {
  const setup = status?.setup || {};
  const visible = status?.state === 'setup_ready';
  const metrics = setup.gegenlesen?.metrics || {};
  const tolerance = metrics.tolerance;
  const warnReasons = Object.entries(setup.checks || {})
    .filter(([, value]) => value === 'WARNUNG')
    .map(([key]) => setup.check_reasons?.[key]).filter(Boolean);
  return {
    visible,
    failed: visible && setup.overall === 'FEHLER',
    key: `${status?.session_id ?? ''}\u0000${setup.proposal_revision ?? ''}`,
    needAck: setup.overall === 'WARNUNG',
    ackReason: warnReasons.length ? warnReasons.join(', ') : null,
    tolerance: tolerance?.possible
      ? {factor: tolerance.factor,
        note: tolerance.hinweis || `Angepasste Lesetoleranz ×${tolerance.factor}: liest diese Aufstellung, erhöht aber das Risiko von Fehllesungen gegenüber der Standardtoleranz. ` +
          (tolerance.reference_kind === 'eingabe' ? 'Geprüft nur in dieser Aufstellung gegen den von Hand eingegebenen Wert.'
            : 'Geprüft nur in dieser Aufstellung gegen den Referenzwert.'),
        reference: tolerance.reference_kind === 'eingabe' && tolerance.anzeige_unveraendert?.unveraendert === true
          ? (tolerance.anzeige_unveraendert.letzte_stelle_schwankt === true ? MANUAL_REFERENCE_FLICKER_NOTE : MANUAL_REFERENCE_NOTE)
          : null}
      : null,
    block: status?.run_block && visible
      ? (tolerance?.possible
        ? 'Achtung: Mit Standardtoleranz ist der Lauf gesperrt. Die angepasste Toleranz kann gewählt werden.'
        : 'Achtung: Mit diesem Vorschlag ist der Lauf gesperrt (siehe unten). Bestätigen ist möglich, ein Lauf nur als Testlauf.')
      : null,
    runHint: visible && !status?.run_block ? status?.run_hint || null : null,
    runBlock: visible ? status?.run_block || null : null,
    hint: visible && metrics.hinweis ? `Hinweis: ${metrics.hinweis}` : null,
    lastPlace: visible ? lastPlaceText(metrics) : null,
  };
}

// Freigabe des Knopfs; der Server prueft trotzdem alles selbst.
export function fieldsReady(model, fields) {
  return Boolean(model.visible && !model.failed && String(fields.name || '').trim() && fields.format && (!model.needAck || fields.ack));
}

// POST-Koerper woertlich wie auf der alten Live-Seite ($('confirm').onclick).
export function confirmBody(status, fields) {
  return {session_id: status?.session_id, confirmed_by: fields.name,
    format_checked: Boolean(fields.format), acknowledge_warning: Boolean(fields.ack),
    use_tolerance: Boolean(fields.tolerance),
    ...(status?.setup?.proposal_revision != null ? {proposal_revision: status.setup.proposal_revision} : {})};
}

const TEMPLATE = `
  <h3>Mit Namen bestätigen</h3>
  <p class="blockmsg err-t" data-part="block" role="alert" hidden></p>
  <div class="runblock" data-part="runblock" hidden><strong>Lauf gesperrt — Leser konnte die Einrichtungsbilder nicht lesen</strong><p data-part="runblock-reason"></p></div>
  <p class="note warn-t" role="status" data-part="run-hint" hidden></p>
  <p class="mut" data-part="hint" hidden></p>
  <p class="note ref" role="status" data-part="last-place" hidden></p>
  <label class="f" for="confirm-name">Name</label>
  <input type="text" id="confirm-name" data-field="name" placeholder="Vor- und Nachname" autocomplete="off" spellcheck="false">
  <label class="ck"><input type="checkbox" data-field="format"><span>Einheit mV/V und Format geprüft</span></label>
  <label class="ck" data-part="ack" hidden><input type="checkbox" data-field="ack"><span>WARNUNG zur Kenntnis genommen<span class="mut" data-part="ack-why"></span></span></label>
  <fieldset class="outgrp" data-part="tolerance" hidden><legend>Lesetoleranz</legend>
    <div class="seg" role="radiogroup" aria-label="Lesetoleranz">
      <label><input type="radio" name="confirm-tolerance" data-field="tolerance-standard" checked><span>Standardtoleranz</span></label>
      <label><input type="radio" name="confirm-tolerance" data-field="tolerance"><span data-part="tolerance-label"></span></label>
    </div>
    <p class="note" data-part="tolerance-text"></p>
    <p class="note ref" data-part="tolerance-ref" hidden></p></fieldset>
  <div class="fa"><button type="button" class="primary" data-part="submit">Bestätigen</button></div>
  <div class="fh" data-part="state" aria-live="polite"></div>
  <div class="fh err-t" data-part="error" role="alert" hidden></div>`;

// host: leerer Container im Tab Schritt. opts.locked() = Bereichsaenderung
// laeuft (Bestaetigen gesperrt); opts.onChange() nach jeder Eingabe, damit
// die Titelleiste ihren Knopf nachzieht.
export function mountConfirm(host, client, {locked = () => false, onChange = () => {}} = {}) {
  host.classList.add('form');
  host.innerHTML = TEMPLATE;
  const q = (selector) => host.querySelector(selector);
  const field = (name) => q(`[data-field="${name}"]`);
  let status = null;
  let model = confirmModel(null);
  let sending = false;
  let error = null;
  let lastKey = null;

  const fields = () => ({name: field('name').value, format: field('format').checked, ack: field('ack').checked,
    tolerance: field('tolerance').checked});
  const ready = () => fieldsReady(model, fields()) && !sending && !locked();

  function reset() {
    field('name').value = '';
    for (const name of ['format', 'ack', 'tolerance']) field(name).checked = false;
    field('tolerance-standard').checked = true;
    error = null;
  }

  function paint() {
    const set = (part, text) => {
      const el = q(`[data-part="${part}"]`);
      el.hidden = !text;
      if (el.textContent !== (text || '')) el.textContent = text || '';
    };
    set('block', model.block);
    q('[data-part="runblock"]').hidden = !model.runBlock;
    q('[data-part="runblock-reason"]').textContent = model.runBlock || '';
    set('run-hint', model.runHint);
    set('hint', model.hint);
    set('last-place', model.lastPlace);
    q('[data-part="ack"]').hidden = !model.needAck;
    q('[data-part="ack-why"]').textContent = model.ackReason ? ` (${model.ackReason})` : '';
    q('[data-part="tolerance"]').hidden = !model.tolerance;
    q('[data-part="tolerance-label"]').textContent = model.tolerance ? `Angepasste Toleranz ×${model.tolerance.factor}` : '';
    q('[data-part="tolerance-text"]').textContent = model.tolerance ? model.tolerance.note : '';
    set('tolerance-ref', model.tolerance?.reference);
    const submit = q('[data-part="submit"]');
    submit.disabled = !ready();
    const f = fields();
    const needs = model.needAck ? 'Name und beide Haken sind nötig.' : 'Name und Haken sind nötig.';
    const text = model.failed ? FAILED_CONFIRM_REASON : locked() ? 'Rahmenbereich wird geprüft … Bestätigen ist bis zur Antwort gesperrt.'
      : sending ? 'Bestätigung wird gesendet …'
        : fieldsReady(model, f) ? 'Bereit zum Bestätigen.' : needs;
    const state = q('[data-part="state"]');
    if (state.textContent !== text) state.textContent = text;
    set('error', error);
  }

  host.addEventListener('input', () => { paint(); onChange(); });
  host.addEventListener('change', () => { paint(); onChange(); });
  host.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && event.target === field('name')) api.submit();
  });
  q('[data-part="submit"]').addEventListener('click', () => api.submit());

  const api = {
    update(next) {
      status = next;
      model = confirmModel(next);
      if (model.key !== lastKey) {
        if (lastKey !== null) reset();
        lastKey = model.key;
      }
      // Wie auf der alten Live-Seite: ohne moegliche Toleranz kein Haken.
      if (!model.tolerance) { field('tolerance').checked = false; field('tolerance-standard').checked = true; }
      if (!model.needAck) field('ack').checked = false;
      host.hidden = !model.visible;
      paint();
    },
    ready,
    async submit() {
      if (!ready()) return;
      sending = true;
      error = null;
      paint();
      onChange();
      const result = await client.post('/live/confirm', confirmBody(status, fields()));
      sending = false;
      error = result.ok ? null : result.error;
      paint();
      onChange();
    },
    // Nach Aenderung von locked() (Bereichsaenderung) neu zeichnen.
    refresh: () => paint(),
  };
  return api;
}
