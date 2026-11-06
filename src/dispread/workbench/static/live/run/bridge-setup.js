// Windows-Bruecke einrichten: Logik ohne DOM (node-testbar). Texte und Zustandswoerter
// des Dialogs; Serverrueckmeldungen erscheinen woertlich. Kein Geheimnis wird hier
// gespeichert oder protokolliert.
export const PROFILE_FILENAME = 'pi.dispread';
export const OFFER_TTL_S = 300;
export const STATUS_POLL_MS = 2000;
export const HUB_DOWN = 'Brückendienst auf dem Pi nicht aktiv';
export const NOT_IN_RUN = 'Im Lauf nicht änderbar.';
export const TEXT = {
  appNote: 'Die Windows-App wird auf dem GSVmulti-PC installiert.',
  appStatus: 'Interner Testbuild – beim Entwickler anfragen.',
  profileHint: 'In der Windows-App muss derselbe Fingerabdruck erscheinen.',
  codeHint: 'Code nur in die Windows-App eingeben. Einmal gültig, 5 Minuten.',
  expired: 'Abgelaufen – neuen Code erzeugen',
  uartExclusive: 'UART direkt und der Brücken-UART nutzen denselben Port und nie gleichzeitig.',
};

const UART_STATES = {unprepared: ['nicht vorbereitet', 'pend'], opening: ['wird geöffnet', 'run'],
  listening: ['wartet auf Windows-App', 'ok'], failed: ['fehlgeschlagen', 'err'], stopped: ['beendet', 'pend']};

// Ausgabewahl der Werkbank -> Transport der Kopplung.
export const bridgeTransport = (choice) => ({tcp: 'network', uart: 'uart'}[choice] || null);
export const offerBody = (transport) => ({transport});
export const prepareBody = () => ({transport: 'uart'});

export function countdownText(seconds) {
  const s = Number.isFinite(seconds) ? Math.max(0, Math.ceil(seconds)) : 0;
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
export const offerRemainingS = (deadlineMs, nowMs) => Math.max(0, Math.ceil((deadlineMs - nowMs) / 1000));

export function fingerprintGroups(value) {
  const clean = String(value ?? '').replace(/[^0-9a-zA-Z]/g, '');
  return clean.match(/.{1,4}/g)?.join(' ') ?? '';
}

// Fehlertext des Servers woertlich: {"error": ...} oder Klartext.
export function requestError(status, text) {
  try {
    const data = JSON.parse(text);
    if (data && typeof data.error === 'string' && data.error) return data.error;
  } catch { /* Klartext */ }
  return String(text ?? '').trim() || `HTTP ${status}`;
}

export function uartView(status) {
  const [word, tone] = UART_STATES[status?.uart_state] || ['unbekannt', 'pend'];
  return {word, tone, error: status?.uart_error || null};
}

// Zeilen der Bereitschaft. Ein verbundener Client heisst nur Verbindung.
export function readinessRows(status) {
  if (!status) return [];
  const via = {network: 'Netzwerk', uart: 'UART'}[status.transport];
  const rows = [
    {label: 'Pi-Kennung', value: String(status.pi_id ?? '–'), mono: true},
    {label: 'Windows-App', value: status.connected ? `verbunden${via ? ` über ${via}` : ''}` : 'nicht verbunden',
      tone: status.connected ? 'ok' : 'pend'},
  ];
  if (status.release_block) rows.push({label: 'Ausgabe', value: String(status.release_block), tone: 'warn'});
  return rows;
}

// Fetch-Schicht: GET/POST/DELETE mit CSRF des letzten Werkbank-Status.
export function createBridgeApi({fetchImpl = (...a) => fetch(...a), csrf = () => ''} = {}) {
  const call = async (method, path, body) => {
    let response;
    try {
      response = await fetchImpl(path, {method, headers: {'X-CSRF-Token': csrf(),
        ...(body ? {'Content-Type': 'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined});
    } catch {
      return {ok: false, status: 0, error: 'Keine Verbindung zur Werkbank.', response: null};
    }
    return {ok: response.ok, status: response.status, response};
  };
  const json = async (method, path, body) => {
    const r = await call(method, path, body);
    if (!r.response) return r;
    const text = await r.response.text();
    if (!r.ok) return {ok: false, status: r.status, error: requestError(r.status, text)};
    try { return {ok: true, status: r.status, data: JSON.parse(text)}; } catch { return {ok: true, status: r.status, data: {}}; }
  };
  return {
    status: () => json('GET', '/live/bridge/status'),
    offer: (transport) => json('POST', '/live/bridge/offers', offerBody(transport)),
    prepare: () => json('POST', '/live/bridge/prepare', prepareBody()),
    release: () => json('DELETE', '/live/bridge/prepare'),
    async profile() {
      const r = await call('GET', '/live/bridge/profile');
      if (!r.response) return r;
      if (!r.ok) return {ok: false, status: r.status, error: requestError(r.status, await r.response.text())};
      const text = await r.response.text();
      let data = null;
      try { data = JSON.parse(text); } catch { return {ok: false, status: r.status, error: 'Profil nicht lesbar.'}; }
      return {ok: true, status: r.status, text, data};
    },
  };
}
