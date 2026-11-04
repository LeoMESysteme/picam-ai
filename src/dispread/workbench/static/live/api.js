// Statusabruf und Bedienschritte der Live-Seite. Der Client entscheidet
// nichts: er holt /live/status alle 500 ms, meldet Verbindung und Status
// weiter und reicht POSTs mit dem CSRF-Token des letzten Status durch.
import {connectionLost, connectionView} from './model.js';

const POLL_MS = 500;
// Ein haengender Abruf darf den Takt nicht bis zum TCP-Timeout anhalten.
const STATUS_TIMEOUT_MS = 3000;
const NETWORK_ERROR = 'Aktion nicht bestätigt – Verbindung prüfen und erneut versuchen.';

// Fehler der Anzeige-Callbacks sichtbar machen (Konsole, pageerror), ohne
// sie als Verbindungsverlust zu deuten.
function surfaceError(error) {
  if (typeof globalThis.reportError === 'function') globalThis.reportError(error);
  else setTimeout(() => { throw error; });
}

export function createClient({fetchImpl = (...args) => fetch(...args), now = () => performance.now(),
  timers = globalThis, onError = surfaceError} = {}) {
  let lastStatus = null;
  let lastOkMs = null;
  let httpStatus = null;
  let fullReceived = false;
  let trackingReasons = null;
  let csrf = '';
  let sequence = 0;
  let running = false;
  let pollTimer = null;
  let connectionTimer = null;
  let onStatus = null;
  let onConnection = null;

  const connection = () => {
    const t = now();
    return {offline: connectionLost(lastOkMs, t, httpStatus), httpStatus, lastOkMs,
      ageMs: lastOkMs === null ? null : t - lastOkMs, view: connectionView(lastStatus, lastOkMs, t, httpStatus)};
  };
  const deliver = (callback, value) => {
    try { callback?.(value); } catch (error) { onError(error); }
  };
  const report = () => { if (running) deliver(onConnection, connection()); };

  const refresh = async () => {
    const mine = ++sequence;
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    let timer = null;
    const timeout = new Promise((_resolve, reject) => {
      timer = timers.setTimeout(() => {
        controller?.abort();
        reject(new Error('Statusabruf ohne Antwort'));
      }, STATUS_TIMEOUT_MS);
    });
    timeout.catch(() => {});
    let received = null;
    try {
      // Einmal den vollen Status (deutsche Gruende), danach nur den kleinen.
      const response = await Promise.race([
        fetchImpl(fullReceived ? '/live/status' : '/live/status?full=1', {signal: controller?.signal}), timeout]);
      if (mine !== sequence) return;
      httpStatus = response.status;
      if (response.ok) {
        const status = await Promise.race([response.json(), timeout]);
        if (mine !== sequence) return;
        fullReceived = true;
        if (status.tracking_reasons) trackingReasons = status.tracking_reasons;
        status.tracking_reasons = trackingReasons;
        if (typeof status.csrf === 'string') csrf = status.csrf;
        lastStatus = status;
        lastOkMs = now();
        received = status;
      }
    } catch {
      if (mine === sequence) httpStatus = null;
    } finally {
      timers.clearTimeout(timer);
    }
    if (mine !== sequence) return;
    // Ausserhalb des Abruf-try: ein Fehler beim Rendern ist kein Verbindungsverlust.
    if (received && running) deliver(onStatus, received);
    report();
  };

  const tick = async () => {
    try { await refresh(); } finally {
      if (running) pollTimer = timers.setTimeout(tick, POLL_MS);
    }
  };

  return {
    start(statusCallback, connectionCallback) {
      if (running) return;
      running = true;
      onStatus = statusCallback;
      onConnection = connectionCallback;
      // Haengt ein Abruf, kippt die Verbindung trotzdem nach 1,5 s auf verloren.
      connectionTimer = timers.setInterval(report, POLL_MS);
      tick();
    },
    async post(path, body) {
      let response;
      try {
        response = await fetchImpl(path, {method: 'POST', headers: {'Content-Type': 'application/json',
          'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
      } catch {
        return {ok: false, error: NETWORK_ERROR};
      }
      let text = '';
      let data = {};
      try {
        text = await response.text();
        data = JSON.parse(text);
      } catch { /* Antwort ohne JSON, z. B. "CSRF rejected" */ }
      if (response.ok) {
        if (running) refresh();
        return {ok: true, error: null};
      }
      // Rueckmeldungen des Servers erscheinen woertlich (Wahrheitsregel 6).
      const error = (data && typeof data.error === 'string' && data.error) || text.trim() ||
        response.statusText || `HTTP ${response.status}`;
      return {ok: false, error};
    },
    stop() {
      running = false;
      sequence++;
      if (pollTimer !== null) timers.clearTimeout(pollTimer);
      if (connectionTimer !== null) timers.clearInterval(connectionTimer);
      pollTimer = connectionTimer = null;
    },
  };
}
