// Bestaetigen im Inspektor, Tab Schritt (Spec "Einrichtungs-Fortschritt":
// Felder wie heute; Mock-Kapitel 7, #t=50). Felder, Texte und POST-Koerper
// sind woertlich aus der alten Live-Seite uebernommen. Bestaetigen geht
// nur ueber client.post (HTTPS mit CSRF, Wahrheitsregel 5); Antworten des
// Servers erscheinen woertlich und inline (Wahrheitsregel 6). Bei neuer
// proposal_revision oder session_id beginnt die Bestaetigung von vorn.

// Gesamturteil FEHLER: Bestaetigen ist gesperrt, der Weg ist Neu einrichten (OQ-71).
export const FAILED_CONFIRM_REASON = 'Bestätigen nicht möglich: Prüfung FEHLER – neu einrichten';

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
      ? `Angepasste Toleranz ×${tolerance.factor} verwenden – Lesung nur in dieser Aufstellung gegen den Referenzwert geprüft, nicht validiert`
      : null,
    block: status?.run_block && visible
      ? (tolerance?.possible
        ? 'Achtung: Der strikte Lauf ist gesperrt. Angepasste Toleranz kann ausdrücklich gewählt werden; sonst ist nur ein Testlauf möglich.'
        : 'Achtung: Mit diesem Vorschlag ist der Lauf gesperrt (siehe unten). Bestätigen ist möglich, ein Lauf nur als Testlauf.')
      : null,
    runBlock: visible ? status?.run_block || null : null,
    hint: visible && metrics.hinweis ? `Hinweis: ${metrics.hinweis}` : null,
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
  <p class="mut" data-part="hint" hidden></p>
  <label class="f" for="confirm-name">Name</label>
  <input type="text" id="confirm-name" data-field="name" placeholder="Vor- und Nachname" autocomplete="off" spellcheck="false">
  <label class="ck"><input type="checkbox" data-field="format"><span>Einheit mV/V und Format geprüft</span></label>
  <label class="ck" data-part="ack" hidden><input type="checkbox" data-field="ack"><span>WARNUNG zur Kenntnis genommen<span class="mut" data-part="ack-why"></span></span></label>
  <label class="ck" data-part="tolerance" hidden><input type="checkbox" data-field="tolerance"><span data-part="tolerance-text"></span></label>
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
    set('hint', model.hint);
    q('[data-part="ack"]').hidden = !model.needAck;
    q('[data-part="ack-why"]').textContent = model.ackReason ? ` (${model.ackReason})` : '';
    q('[data-part="tolerance"]').hidden = !model.tolerance;
    q('[data-part="tolerance-text"]').textContent = model.tolerance || '';
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
      if (!model.tolerance) field('tolerance').checked = false;
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
