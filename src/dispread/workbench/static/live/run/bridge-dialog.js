// Dialog "Windows-Bruecke einrichten" (Plan P4.5): fuenf Schritte mit je eigenem
// Zustand (Quadrat + Wort). Werkbank-Dialogstil (.modalbg/.modal), Fokusfalle,
// Esc schliesst. Das Kopplungsangebot lebt nur im Speicher und im DOM dieses
// Dialogs: nie in Konsole oder localStorage, und weg beim Schliessen.
import {HUB_DOWN, NOT_IN_RUN, OFFER_TTL_S, PROFILE_FILENAME, STATUS_POLL_MS, TEXT, bridgeTransport, countdownText,
  createBridgeApi, fingerprintGroups, offerRemainingS, readinessRows, uartView} from './bridge-setup.js';

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), a[href], summary';

const step = (n, key, title) => `<li class="bstep" data-step="${key}"><div class="bh"><span class="sq pend" data-part="${key}-sq"></span>` +
  `<b><span class="bn">${n}</span>. ${esc(title)}</b><span class="bw" data-part="${key}-word"></span></div><div class="bb">`;

// client: Werkbank-Client (liefert das CSRF-Token des letzten Status).
export function mountBridgeDialog(client, {fetchImpl, doc = globalThis.document} = {}) {
  const api = createBridgeApi({fetchImpl, csrf: () => client.serverStatus()?.csrf || ''});
  let view = null;
  const open = (options) => {
    if (view) { view.update(options); return view; }
    view = build(options);
    return view;
  };

  function build({choice, running}) {
    const state = {choice, running: Boolean(running), hubDown: false, deadline: null, expired: false, profile: null,
      uart: null, status: null, closed: false, polls: 0};
    const uart = () => bridgeTransport(state.choice) === 'uart';
    const back = doc.createElement('div');
    back.className = 'modalbg';
    back.innerHTML = '<div class="modal bridge" role="dialog" aria-modal="true" aria-labelledby="bridge-t">' +
      '<div class="mt" id="bridge-t">Windows-Brücke einrichten</div><div class="mbody"><ol class="bsteps">' +
      `${step(1, 'app', 'Windows-App')}<p>${esc(TEXT.appNote)}</p><p class="note">${esc(TEXT.appStatus)}</p></div></li>` +
      `${step(2, 'profile', 'Pi-Verbindungsprofil')}` +
      `<div class="brow"><button type="button" data-part="profile-btn">Profil herunterladen (${esc(PROFILE_FILENAME)})</button></div>` +
      '<div data-part="profile-info" hidden><dl class="kv bkv"><dt>Anzeigename</dt><dd data-part="p-name"></dd>' +
      '<dt>Pi-ID</dt><dd class="mono" data-part="p-id"></dd><dt>Fingerabdruck (SHA-256)</dt><dd class="mono fp" data-part="p-fp"></dd></dl>' +
      `<p class="note">${esc(TEXT.profileHint)}</p></div>` +
      '<p class="msg err-t wrap" role="alert" data-part="profile-err" hidden></p></div></li>' +
      `${step(3, 'offer', 'Kopplung freigeben')}` +
      '<div class="brow"><button type="button" data-part="offer-btn">Kopplungscode erzeugen</button></div>' +
      '<div class="bcoderow" data-part="code-row" hidden></div>' +
      `<p class="note">${esc(TEXT.codeHint)}</p>` +
      '<p class="msg err-t wrap" role="alert" data-part="offer-err" hidden></p></div></li>' +
      `${step(4, 'uart', 'UART-Empfang')}` +
      '<div class="brow"><button type="button" data-part="uart-on">UART-Empfang vorbereiten</button>' +
      '<button type="button" data-part="uart-off">Beenden</button></div>' +
      `<p class="note">${esc(TEXT.uartExclusive)}</p>` +
      '<p class="note" data-part="uart-lock" hidden></p>' +
      '<p class="msg err-t wrap" role="alert" data-part="uart-err" hidden></p></div></li>' +
      `${step(5, 'ready', 'Bereitschaft')}<dl class="kv bkv" data-part="rows"></dl>` +
      '<p class="msg err-t wrap" data-part="ready-err" hidden></p></div></li>' +
      '</ol></div><div class="mf"><button type="button" class="primary" data-part="close">Schließen</button></div></div>';
    const part = (name) => back.querySelector(`[data-part="${name}"]`);
    const setStep = (key, tone, word) => {
      part(`${key}-sq`).className = `sq ${tone}`;
      part(`${key}-word`).textContent = word;
    };
    const showErr = (name, text) => { part(name).textContent = text || ''; part(name).hidden = !text; };

    const before = doc.activeElement;
    const siblings = [...doc.body.children].filter((el) => !el.hasAttribute('inert'));
    doc.body.append(back);
    for (const el of siblings) el.setAttribute('inert', '');

    let tickTimer = null;
    let pollTimer = null;
    let sequence = 0;
    const clearCode = () => {
      part('code-row').replaceChildren();
      part('code-row').hidden = true;
      state.deadline = null;
      if (tickTimer !== null) { clearInterval(tickTimer); tickTimer = null; }
    };

    const render = () => {
      back.querySelector('[data-step="uart"]').hidden = !uart();
      // Nummern folgen den sichtbaren Schritten (Netzwerk hat keinen UART-Schritt).
      [...back.querySelectorAll('.bstep:not([hidden]) .bn')].forEach((el, i) => { el.textContent = String(i + 1); });
      const locked = state.running;
      if (state.hubDown) {
        setStep('uart', 'pend', HUB_DOWN);
        setStep('ready', 'pend', HUB_DOWN);
        part('rows').replaceChildren();
        showErr('ready-err', '');
      } else if (state.status) {
        const u = uartView(state.status);
        setStep('uart', u.tone, u.word);
        showErr('uart-err', state.uartAction || u.error);
        const rows = readinessRows(state.status);
        part('rows').innerHTML = rows.map((r) => `<dt>${esc(r.label)}</dt><dd class="${r.mono ? 'mono' : ''}${r.tone === 'warn' ? ' warn-t' : ''}">` +
          `${esc(r.value)}</dd>`).join('');
        const connected = Boolean(state.status.connected);
        setStep('ready', connected ? 'ok' : 'pend', connected ? 'Verbindung steht' : 'keine Verbindung');
        showErr('ready-err', '');
      } else {
        setStep('uart', 'pend', state.uartAction ? 'Fehler' : 'unbekannt');
        showErr('uart-err', state.uartAction);
        setStep('ready', 'pend', state.statusError ? 'Fehler' : 'wird abgefragt');
        showErr('ready-err', state.statusError);
      }
      const hub = state.hubDown;
      part('uart-on').disabled = locked || hub || state.busy === 'uart';
      part('uart-off').disabled = locked || hub || state.busy === 'uart';
      part('uart-lock').hidden = !locked;
      part('uart-lock').textContent = locked ? NOT_IN_RUN : '';
      setStep('app', 'pend', 'Hinweis');
      if (state.profile) setStep('profile', 'ok', 'heruntergeladen'); else setStep('profile', 'pend', 'offen');
      if (state.deadline !== null) setStep('offer', 'run', 'Code aktiv');
      else if (state.expired) setStep('offer', 'warn', 'abgelaufen');
      else setStep('offer', 'pend', 'kein Code');
    };

    const poll = async () => {
      const mine = ++sequence;
      const result = await api.status();
      if (state.closed || mine !== sequence) return;
      if (result.ok) { state.status = result.data; state.hubDown = false; state.statusError = null; }
      else if (result.status === 503) { state.hubDown = true; state.status = null; state.statusError = null; }
      else { state.status = null; state.hubDown = false; state.statusError = result.error; }
      render();
      pollTimer = setTimeout(poll, STATUS_POLL_MS);
    };

    const showCode = (code) => {
      const row = part('code-row');
      row.innerHTML = '<code class="bcode mono" data-part="code"></code><button type="button" data-part="copy">Kopieren</button>' +
        '<span class="bcount mono" data-part="count" role="timer"></span>';
      row.querySelector('[data-part="code"]').textContent = code;
      row.hidden = false;
      row.querySelector('[data-part="copy"]').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        try {
          await globalThis.navigator.clipboard.writeText(code);
          button.textContent = 'Kopiert';
        } catch { button.textContent = 'Kopieren nicht möglich'; }
      });
    };
    const tick = () => {
      const left = offerRemainingS(state.deadline, Date.now());
      const count = part('count');
      if (count) count.textContent = countdownText(left);
      if (left <= 0) {
        clearCode();
        state.expired = true;
        part('code-row').hidden = false;
        part('code-row').innerHTML = `<span class="warn-t" data-part="expired">${esc(TEXT.expired)}</span>`;
        render();
      }
    };

    part('profile-btn').addEventListener('click', async () => {
      part('profile-btn').disabled = true;
      showErr('profile-err', '');
      const result = await api.profile();
      part('profile-btn').disabled = false;
      if (state.closed) return;
      if (!result.ok) { showErr('profile-err', result.error); return; }
      const url = URL.createObjectURL(new Blob([result.text], {type: 'application/json'}));
      const a = doc.createElement('a');
      a.href = url;
      a.download = PROFILE_FILENAME;
      doc.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      const p = result.data || {};
      state.profile = p;
      part('p-name').textContent = p.name ?? '–';
      part('p-id').textContent = p.pi_id ?? '–';
      part('p-fp').textContent = fingerprintGroups(p.certificate_sha256) || '–';
      part('profile-info').hidden = false;
      render();
    });

    part('offer-btn').addEventListener('click', async () => {
      const transport = bridgeTransport(state.choice);
      if (!transport) return;
      part('offer-btn').disabled = true;
      showErr('offer-err', '');
      const result = await api.offer(transport);
      part('offer-btn').disabled = false;
      if (state.closed) return;
      if (!result.ok) { showErr('offer-err', result.error); return; }
      const seconds = Number.isFinite(result.data.expires_in_s) ? result.data.expires_in_s : OFFER_TTL_S;
      clearCode();
      state.expired = false;
      state.deadline = Date.now() + seconds * 1000;
      showCode(String(result.data.offer));
      tickTimer = setInterval(tick, 1000);
      tick();
      render();
    });

    const uartAction = async (call) => {
      state.busy = 'uart';
      state.uartAction = null;
      render();
      const result = await call();
      state.busy = null;
      if (state.closed) return;
      if (result.ok) state.status = result.data && 'uart_state' in result.data ? result.data : state.status;
      else if (result.status === 503) state.hubDown = true;
      else state.uartAction = result.error;
      render();
    };
    part('uart-on').addEventListener('click', () => uartAction(() => api.prepare()));
    part('uart-off').addEventListener('click', () => uartAction(() => api.release()));

    const finish = () => {
      if (state.closed) return;
      state.closed = true;
      clearCode();
      clearTimeout(pollTimer);
      doc.removeEventListener('keydown', onKey, true);
      back.remove();
      for (const el of siblings) el.removeAttribute('inert');
      if (before && before.isConnected) before.focus();
      view = null;
    };
    function onKey(event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finish(); return; }
      if (event.key !== 'Tab') return;
      const items = [...back.querySelectorAll(FOCUSABLE)].filter((el) => !el.closest('[hidden]'));
      if (!items.length) return;
      const index = items.indexOf(doc.activeElement);
      const next = event.shiftKey ? (index <= 0 ? items.length - 1 : index - 1) : (index < 0 || index === items.length - 1 ? 0 : index + 1);
      event.preventDefault();
      items[next].focus();
    }
    doc.addEventListener('keydown', onKey, true);
    part('close').addEventListener('click', finish);
    render();
    poll();
    part('profile-btn').focus();
    return {
      close: finish,
      isOpen: () => !state.closed,
      update(next) {
        const before = bridgeTransport(state.choice);
        state.choice = next.choice ?? state.choice;
        // Ein Code gilt nur fuer den Transport, fuer den er erzeugt wurde.
        if (bridgeTransport(state.choice) !== before) { clearCode(); state.expired = false; }
        state.running = Boolean(next.running);
        if (!state.closed) render();
      },
    };
  }

  return {open, isOpen: () => Boolean(view?.isOpen()), close: () => view?.close()};
}
