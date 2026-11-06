// GSVmulti-Ausgabe (G2): ein Weg je Lauf. Texte der alten Bruecken-Seite
// (outputView, Sperrhinweis) woertlich, soweit sie noch passen. Kein DOM:
// node-testbar. Der Server bleibt massgeblich (normalize_output); hier nur
// Auswahl, Anzeige und die Ablehnung des Testlaufs mit Ausgabe vor dem POST.
export const PATHS = [['off', 'Aus'], ['serial', 'UART direkt'], ['uart', 'UART über Brücke'], ['tcp', 'Netzwerk über Brücke']];
export const NAMES = {serial: 'UART direkt', uart: 'UART über Brücke', tcp: 'Netzwerk über Brücke'};
export const BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600];
export const DEFAULTS = {port: '/dev/ttyAMA0', baudrate: 115200, prefix: '%', tcpPort: 5000};
export const LOCK_NOTICE = 'DUT-Ausgabe gesperrt: Windows-Abnahme fehlt. Verbindung und Diagnose sind vorbereitet; ' +
  'Messwerte werden noch nicht an GSVmulti ausgegeben.';
export const SERIAL_NOTE = 'Prototyp – nicht am Windows-PC abgenommen, keine Messfreigabe. Ungültige Werte werden ausgelassen; ' +
  'GSVmulti zeigt dann den letzten Wert unmarkiert weiter.';
export const SERIAL_ACK = 'Mir ist bewusst: nicht abgenommen, keine Messfreigabe';
export const TEST_BLOCK = 'Testlauf erlaubt keine externe Ausgabe. Verbindungsweg auf Aus stellen.';
export const UNCONFIRMED = 'GSVmulti-Empfang unbestätigt.';
export const MARKER = 'nicht abgenommen';
export const CHOICE_KEY = 'werkbank.ausgabe-weg';
export const TOAST_DOWN = 'Verbindung zur GSVmulti-Brücke unterbrochen – lokaler Lauf läuft weiter';

const STATES = {disconnected: 'Verbindung unterbrochen – lokaler Lauf läuft weiter', bridge_connected: 'Brücke erreichbar',
  waiting: 'Warte auf Windows-Brücke', audit_failed: 'Ausgabebeleg nicht schreibbar', stopped: 'Ausgabe beendet',
  locked: 'DUT-Ausgabe gesperrt', serial_ready: 'Schnittstelle bereit', failed: 'Schnittstelle fehlgeschlagen'};
const OUTCOMES = {failed: 'fehlgeschlagen', expired: 'veraltet – nicht weitergegeben', unconfirmed: 'unbestätigt'};

export const isOff = (output) => !output || output.transport === 'off';
export const stateWord = (output) => STATES[output?.state] || output?.state || 'Verbindungszustand unbekannt';

// Kurzform fuer die Statusleiste: "<Weg> · <Zustand>" (Zustand ohne Erklaerzusatz).
export function shortState(output) {
  return output?.state === 'disconnected' ? 'Verbindung unterbrochen' : stateWord(output);
}

export function outputTone(output) {
  if (isOff(output)) return '';
  if (['failed', 'audit_failed'].includes(output.state)) return 'err';
  if (['disconnected', 'waiting'].includes(output.state)) return 'warn';
  return '';
}

// Zeilen der Anzeige; Reihenfolge wie outputView der alten Seite.
export function outputLines(output) {
  if (isOff(output)) return ['Ausgabe ausgeschaltet'];
  const ack = output.last_ack;
  const frame = Number.isInteger(ack?.frame_sequence) ? ` (Bild ${ack.frame_sequence})` : '';
  const bridge = output.transport !== 'serial';
  const attempt = !ack ? null : ack.outcome === 'written'
    ? (bridge ? `Letzte COM-Weitergabe durch Brücke bestätigt${frame}.` : `Letzte Ausgabe lokal angenommen${frame}.`)
    : `Letzter ${bridge ? 'COM-Versuch' : 'Ausgabeversuch'}${frame}: ${OUTCOMES[ack.outcome] || 'Ergebnis unbekannt'}.`;
  return [`${NAMES[output.transport] || output.transport}: ${stateWord(output)}`,
    output.release_note, output.release_block, output.error, attempt,
    ack && output.ack_scope ? `Geltung der Quittung: ${output.ack_scope}` : null, UNCONFIRMED].filter(Boolean);
}
export const outputView = (output) => outputLines(output).join('\n');

// Konfiguration im Lauf, schreibgeschuetzt (config aus status.output).
export function configText(output) {
  const c = output?.config || {};
  if (output?.transport === 'serial') return `${c.port ?? '–'} · ${c.baudrate ?? '–'} Baud · Präfix ${c.prefix ?? '–'}`;
  if (output?.transport === 'tcp') return `TCP-Port ${c.tcp_port ?? '–'}`;
  if (output?.transport === 'uart') return `${c.serial_port ?? c.port ?? DEFAULTS.port} · ${c.baudrate ?? DEFAULTS.baudrate} Baud`;
  return '';
}

// POST-Koerper `output`. fields = {port, baudrate, prefix, tcpPort, ack}.
export function outputBody(choice, fields = {}) {
  if (choice === 'serial') {
    return {transport: 'serial', port: fields.port, baudrate: Number(fields.baudrate), prefix: fields.prefix,
      acknowledge_unaccepted: fields.ack === true};
  }
  if (choice === 'tcp') return {transport: 'tcp', tcp_port: Number(fields.tcpPort)};
  if (choice === 'uart') return {transport: 'uart'};
  return {transport: 'off'};
}

export function loadChoice(storage = globalThis.localStorage) {
  try {
    const value = storage?.getItem(CHOICE_KEY);
    return PATHS.some(([key]) => key === value) ? value : 'off';
  } catch { return 'off'; }
}
export function saveChoice(choice, storage = globalThis.localStorage) {
  try { storage?.setItem(CHOICE_KEY, choice); } catch { /* ohne Speicher: nur fuer diese Seite */ }
}

// Statusleiste: {hidden, cls, html, title}.
export function outputItem(output, esc = String) {
  if (isOff(output)) return {hidden: true, html: ''};
  const way = `GSVmulti: ${NAMES[output.transport] || output.transport} · `;
  const mark = output.transport === 'serial' ? ` <span class="tag">${MARKER}</span>`
    : ` <span class="tag" title="${esc(LOCK_NOTICE)}">gesperrt</span>`;
  return {hidden: false, cls: outputTone(output), html: `<span class="tx">${esc(way)}<b>${esc(shortState(output))}</b></span>${mark}`,
    title: outputView(output)};
}
