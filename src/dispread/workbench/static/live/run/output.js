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
// Testfreigabe ueber die Bruecke (R1/R2): wortgleich BRIDGE_RELEASE_NOTE (dispread.live.output), per Test abgeglichen.
export const BRIDGE_NOTE = 'Testfreigabe über die Brücke – nicht abgenommen, keine Messfreigabe. Ungültige und veraltete Werte werden ' +
  'ausgelassen; GSVmulti zeigt dann den letzten Wert unmarkiert weiter.';
export const BRIDGE_ACK = 'Testfreigabe: echte Werte an GSVmulti senden – nicht abgenommen, keine Messfreigabe';
export const BRIDGE_NO_ACK = 'Ohne Haken bleibt die Ausgabe gesperrt – GSVmulti erhält keine Messwerte.';
export const UART_RATE_NOTE = 'UART über Brücke trägt bei 115 200 Baud nur etwa 3–4 Werte/s: in GSVmulti höchstens 4 Hz einstellen; 10 Hz nur über Netzwerk.';
export const RELEASE_TAG = 'Testfreigabe – nicht abgenommen';
export const TEST_BLOCK = 'Testlauf erlaubt keine externe Ausgabe. Verbindungsweg auf Aus stellen.';
export const UNCONFIRMED = 'GSVmulti-Empfang unbestätigt.';
export const MARKER = 'nicht abgenommen';
// Format und Takt (Spec 2026-11-11 §3.5/§6 F3). Warnung wortgleich aus der Spec.
export const FORMAT_WARNING = 'Einkanal-Ausgabe: Bei Übergang (TRANSITION) und unlesbarer Anzeige (UNREADABLE) werden keine Zeilen gesendet. ' +
  'GSVmulti zeichnet die Lücken nicht auf; Laufzeit und Zeitachse der Aufnahme sind deshalb nicht genau.';
export const ONE_CH_SHORT = 'Einkanal: Lücken werden in GSVmulti nicht aufgezeichnet';
export const RATE_NOTE = 'In GSVmulti dieselbe Frequenz einstellen (Data Frequency).';
export const FORMATS = [['4ch', 'Vierkanal-Takt (empfohlen)'], ['1ch', 'Einkanal (nur gültige Werte)']];
export const FORMAT_DEFAULTS = {format: '4ch', rateHz: 10};
export const RATE_ERROR = 'Takt: ganze Zahl von 1 bis 10 Hz.';
export const CHECKLIST_TITLE = 'In GSVmulti';
export const CHECKLIST = [
  'Vierkanal-Session aus der Windows-App, Kanäle 8_2–8_4 ausgeblendet',
  'Configure Recording → Advanced → „Record Hidden Channels“ einschalten (Pflicht, wird nicht in der Session gespeichert)',
  'Für 8_1 Autoscale Y aus, Min/Max fest einstellen',
];
export const rateValid = (value) => {
  if (value === null || value === '' || typeof value === 'boolean') return false;
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 10;
};

export const CHOICE_KEY = 'werkbank.ausgabe-weg';
export const TOAST_DOWN = 'Verbindung zur GSVmulti-Brücke unterbrochen – lokaler Lauf läuft weiter';

const STATES = {disconnected: 'Verbindung unterbrochen – lokaler Lauf läuft weiter', bridge_connected: 'Brücke erreichbar',
  waiting: 'Warte auf Windows-Brücke', audit_failed: 'Ausgabebeleg nicht schreibbar', stopped: 'Ausgabe beendet',
  locked: 'DUT-Ausgabe gesperrt', serial_ready: 'Schnittstelle bereit', failed: 'Schnittstelle fehlgeschlagen'};
const OUTCOMES = {failed: 'fehlgeschlagen', expired: 'veraltet – nicht weitergegeben', unconfirmed: 'unbestätigt'};

export const isOff = (output) => !output || output.transport === 'off';
export const isReleased = (output) => !isOff(output) && output.release === 'test_unaccepted';
export const stateWord = (output) => STATES[output?.state] || output?.state || 'Verbindungszustand unbekannt';

// Kurzform fuer die Statusleiste: "<Weg> · <Zustand>" (Zustand ohne Erklaerzusatz).
export function shortState(output) {
  return output?.state === 'disconnected' ? 'Verbindung unterbrochen' : stateWord(output);
}

export function outputTone(output) {
  if (isOff(output)) return '';
  if (['failed', 'audit_failed'].includes(output.state)) return 'err';
  if (['disconnected', 'waiting'].includes(output.state)) return 'warn';
  if (isReleased(output)) return 'warn';
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
// Marker fuer Dock/Inspektor: UART direkt und Testfreigabe tragen "nicht abgenommen".
export const markerText = (output) => output?.transport === 'serial' ? MARKER : isReleased(output) ? RELEASE_TAG : null;
export const outputView = (output) => outputLines(output).join('\n');

// Konfiguration im Lauf, schreibgeschuetzt (config aus status.output).
export function configText(output) {
  const c = output?.config || {};
  if (output?.transport === 'serial') return `${c.port ?? '–'} · ${c.baudrate ?? '–'} Baud · Präfix ${c.prefix ?? '–'}`;
  if (output?.transport === 'tcp') return `TCP-Port ${c.tcp_port ?? '–'}`;
  if (output?.transport === 'uart') return `${c.serial_port ?? c.port ?? DEFAULTS.port} · ${c.baudrate ?? DEFAULTS.baudrate} Baud`;
  return '';
}

// Format/Takt-Teil des Koerpers; ohne fields.format bleibt der Koerper wie vor dem Vierkanal-Takt.
const formatPart = (fields) => !fields.format ? {}
  : fields.format === '4ch' ? {format: '4ch', rate_hz: Number(fields.rateHz)} : {format: '1ch'};

// POST-Koerper `output`. fields = {port, baudrate, prefix, tcpPort, ack, format, rateHz}.
export function outputBody(choice, fields = {}) {
  if (choice === 'serial') {
    // Vierkanal verlangt Praefix % (Server lehnt anderes ab).
    const prefix = fields.format === '4ch' ? '%' : fields.prefix;
    return {transport: 'serial', port: fields.port, baudrate: Number(fields.baudrate), prefix,
      acknowledge_unaccepted: fields.ack === true, ...formatPart(fields)};
  }
  // Brueckenwege: Testfreigabe nur mit gesetztem Haken, sonst bleibt das Feld weg (Ausgabe gesperrt).
  const release = fields.ack === true ? {acknowledge_unaccepted: true} : {};
  if (choice === 'tcp') return {transport: 'tcp', tcp_port: Number(fields.tcpPort), ...release, ...formatPart(fields)};
  if (choice === 'uart') return {transport: 'uart', ...release, ...formatPart(fields)};
  return {transport: 'off'};
}

// Vierkanal-Lauf? Alles ohne format=4ch ist Einkanal (alter Vertrag).
export const isFourChannel = (output) => !isOff(output) && output?.config?.format === '4ch';
const pct = (tick) => (Number.isFinite(tick?.total) && tick.total > 0 && Number.isFinite(tick?.valid)
  ? `${Math.round((100 * tick.valid) / tick.total)} %` : '–');
const rateOf = (output) => output?.tick?.rate_hz ?? output?.config?.rate_hz ?? '–';

// Zeile im Lauf: Vierkanal-Takt mit Anteil gueltig und verpassten Takten, sonst die Einkanal-Warnung (kurz).
export function tickLine(output) {
  if (isOff(output)) return null;
  if (!isFourChannel(output)) return ONE_CH_SHORT;
  const t = output.tick || {};
  const extra = [['lost', 'verloren'], ['unconfirmed', 'unbestätigt']].filter(([k]) => t[k] > 0).map(([k, w]) => ` · ${w} ${t[k]}`).join('');
  return `Vierkanal-Takt ${rateOf(output)} Hz · gültig ${pct(t)} · verpasst ${Number.isFinite(t.missed) ? t.missed : 0}${extra}`;
}
// Statusleiste, nur Vierkanal.
export const tickShort = (output) => `${rateOf(output)} Hz · ${pct(output?.tick)} gültig`;
// Bridge-Dialog, Zeile "Format".
export const formatLabel = (output) => isFourChannel(output) ? `Vierkanal-Takt ${rateOf(output)} Hz` : 'Einkanal (nur gültige Werte)';

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
    : isReleased(output) ? ` <span class="tag warn" title="${esc(output.release_note || BRIDGE_NOTE)}">${RELEASE_TAG}</span>`
    : ` <span class="tag" title="${esc(LOCK_NOTICE)}">gesperrt</span>`;
  // Testfreigabe: Marker zuerst, damit die Kuerzung der Leiste ihn nie abschneidet.
  const lead = isReleased(output) ? `${mark.trim()} ` : '';
  const fmt = isFourChannel(output) ? ` <span class="tx">· ${esc(tickShort(output))}</span>`
    : ` <span class="tag warn" data-part="one-ch" title="${esc(FORMAT_WARNING)}">Einkanal</span>`;
  return {hidden: false, cls: outputTone(output), html: `${lead}<span class="tx">${esc(way)}<b>${esc(shortState(output))}</b></span>${lead ? '' : mark}${fmt}`,
    title: [outputView(output), tickLine(output)].join('\n')};
}
