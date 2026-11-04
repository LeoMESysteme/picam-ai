// Statusabruf und Bedienschritte der Live-Seite. Der Client entscheidet
// nichts: er holt /live/status alle 500 ms, meldet Verbindung und Status
// weiter und reicht POSTs mit dem CSRF-Token des letzten Status durch.
//
// Eine Quelle fuer Status und Aktionen, umschaltbar (useSource): "server"
// oder ein Uebungs-Szenario (practice/scenario.js). Im Szenario-Modus kommen
// Status und Antworten aus scenario.status()/act(); fetch wird fuer POST nie
// aufgerufen (Wahrheitsregel 5: der Uebungslauf sendet nie). Der echte
// Status wird weiter gelesen (nur GET) und an onServerStatus gemeldet, damit
// die Seite den Uebungslauf beenden kann, wenn an der Werkbank etwas startet.
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
  // Lesegruende (fields.py LIVE_CAUSE_TEXT), sobald der volle Status sie traegt.
  let causeTexts = null;
  let csrf = '';
  let sequence = 0;
  let running = false;
  let pollTimer = null;
  let connectionTimer = null;
  let onStatus = null;
  let onConnection = null;
  let onServerStatus = null;
  // 'server' oder ein Szenario {status(), act(path, body)}.
  let source = 'server';
  let practice = {lastStatus: null, lastOkMs: null};

  const connection = () => {
    const t = now();
    const [status, okMs, code] = source === 'server' ? [lastStatus, lastOkMs, httpStatus]
      : [practice.lastStatus, practice.lastOkMs, 200];
    return {offline: connectionLost(okMs, t, code), httpStatus: code, lastOkMs: okMs,
      ageMs: okMs === null ? null : t - okMs, view: connectionView(status, okMs, t, code), practice: source !== 'server'};
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
        if (status.cause_texts) causeTexts = status.cause_texts;
        if (causeTexts) status.cause_texts = causeTexts;
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
    if (received && running) deliver(source === 'server' ? onStatus : onServerStatus, received);
    if (source === 'server') report();
  };

  // Uebungslauf: Status aus dem Szenario. null = simulierter Verbindungsverlust
  // (wie ein ausbleibender Abruf: kein neuer Stand, die Verbindung kippt nach 1,5 s).
  const scenarioTick = () => {
    if (source === 'server' || !running) return;
    let next = null;
    try { next = source.status(); } catch (error) { onError(error); }
    if (next) {
      next.tracking_reasons = trackingReasons;
      if (causeTexts) next.cause_texts = causeTexts;
      practice = {lastStatus: next, lastOkMs: now()};
      deliver(onStatus, next);
    }
    report();
  };

  const tick = async () => {
    scenarioTick();
    try { await refresh(); } finally {
      if (running) pollTimer = timers.setTimeout(tick, POLL_MS);
    }
  };

  return {
    // options.onServerStatus(status): echter Status, solange ein Szenario die Quelle ist.
    start(statusCallback, connectionCallback, options = {}) {
      if (running) return;
      running = true;
      onStatus = statusCallback;
      onConnection = connectionCallback;
      onServerStatus = options.onServerStatus || null;
      // Haengt ein Abruf, kippt die Verbindung trotzdem nach 1,5 s auf verloren.
      connectionTimer = timers.setInterval(report, POLL_MS);
      tick();
    },
    // "server" oder ein Szenario. Der Wechsel liefert sofort den Stand der neuen Quelle.
    useSource(next) {
      const scenario = next && next !== 'server' && typeof next.status === 'function' && typeof next.act === 'function';
      if (next && next !== 'server' && !scenario) throw new TypeError('Quelle: "server" oder ein Szenario mit status() und act()');
      source = scenario ? next : 'server';
      practice = {lastStatus: null, lastOkMs: null};
      if (!running) return;
      if (scenario) scenarioTick();
      else {
        // Den letzten echten Stand sofort zeigen, dann frisch abrufen.
        if (lastStatus) deliver(onStatus, lastStatus);
        report();
        refresh();
      }
    },
    source: () => source,
    // Echter Status des letzten erfolgreichen Abrufs (auch im Uebungslauf).
    serverStatus: () => lastStatus,
    async post(path, body) {
      if (source !== 'server') {
        const scenario = source;
        let answer;
        try { answer = await scenario.act(path, body || {}); } catch (error) {
          onError(error);
          answer = {ok: false, error: String(error?.message || error)};
        }
        const ok = Boolean(answer?.ok);
        const error = ok ? null : (answer?.error || 'Übungslauf: Aktion abgelehnt');
        const data = answer?.data ?? (ok ? {ok: true} : {error});
        if (source === scenario) scenarioTick();
        return {ok, error, data};
      }
      let response;
      try {
        response = await fetchImpl(path, {method: 'POST', headers: {'Content-Type': 'application/json',
          'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
      } catch {
        // network: die Anfrage kam nie an; Aufrufer duerfen ihren eigenen Wortlaut nehmen.
        return {ok: false, error: NETWORK_ERROR, network: true};
      }
      let text = '';
      let data = {};
      try {
        text = await response.text();
        data = JSON.parse(text);
      } catch { /* Antwort ohne JSON, z. B. "CSRF rejected" */ }
      // data = Antwortkoerper (z. B. centre_results der Bereichsaenderung).
      if (response.ok) {
        if (running) refresh();
        return {ok: true, error: null, data};
      }
      // Rueckmeldungen des Servers erscheinen woertlich (Wahrheitsregel 6).
      const error = (data && typeof data.error === 'string' && data.error) || text.trim() ||
        response.statusText || `HTTP ${response.status}`;
      return {ok: false, error, data};
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
