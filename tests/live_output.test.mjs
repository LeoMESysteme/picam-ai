import assert from 'node:assert/strict';
import test from 'node:test';
import {outputBody, outputItem, outputTone, outputView, loadChoice, saveChoice, SERIAL_NOTE, LOCK_NOTICE, BRIDGE_NOTE, markerText}
  from '../src/dispread/workbench/static/live/run/output.js';

const bridge = (transport, state, extra = {}) => ({transport, state, config: {}, error: null,
  release_block: LOCK_NOTICE, last_ack: null, ack_scope: 'COM driver write, not GSVmulti reception', acceptance: 'fehlt', ...extra});
const serial = (state, extra = {}) => ({transport: 'serial', state, config: {port: '/dev/ttyAMA0', baudrate: 115200, prefix: '%'},
  error: null, release_block: null, release_note: SERIAL_NOTE, last_ack: null, ack_scope: 'lokale Annahme', acceptance: 'fehlt', ...extra});

test('aus: eine Zeile, kein Empfangshinweis', () => {
  assert.equal(outputView({transport: 'off', state: 'off'}), 'Ausgabe ausgeschaltet');
  assert.equal(outputView(null), 'Ausgabe ausgeschaltet');
  assert.equal(outputItem({transport: 'off', state: 'off'}).hidden, true);
});

test('Bruecke: Zustandstexte, Sperre und unbestaetigter Empfang', () => {
  const view = outputView(bridge('uart', 'disconnected'));
  assert.equal(view.split('\n')[0], 'UART über Brücke: Verbindung unterbrochen – lokaler Lauf läuft weiter');
  assert.match(view, /DUT-Ausgabe gesperrt: Windows-Abnahme fehlt/);
  assert.ok(view.endsWith('GSVmulti-Empfang unbestätigt.'));
  assert.equal(outputView(bridge('tcp', 'waiting')).split('\n')[0], 'Netzwerk über Brücke: Warte auf Windows-Brücke');
  assert.match(outputView(bridge('tcp', 'bridge_connected')), /^Netzwerk über Brücke: Brücke erreichbar/);
  assert.match(outputView(bridge('tcp', 'audit_failed', {error: 'Platte voll'})), /Ausgabebeleg nicht schreibbar\n.*\nPlatte voll\n/);
  assert.match(outputView(bridge('uart', 'stopped')), /Ausgabe beendet/);
});

test('Quittung: Bruecke bestaetigt nur die COM-Weitergabe', () => {
  const ack = (outcome) => bridge('uart', 'bridge_connected', {last_ack: {outcome, frame_sequence: 7}});
  assert.match(outputView(ack('written')), /Letzte COM-Weitergabe durch Brücke bestätigt \(Bild 7\)\./);
  assert.match(outputView(ack('expired')), /Letzter COM-Versuch \(Bild 7\): veraltet – nicht weitergegeben\./);
  assert.match(outputView(ack('failed')), /fehlgeschlagen/);
  assert.match(outputView(ack('unconfirmed')), /unbestätigt\./);
  assert.match(outputView(ack('written')), /Geltung der Quittung: COM driver write, not GSVmulti reception/);
});

test('seriell: Hinweis woertlich, Marker, Fehler', () => {
  const view = outputView(serial('serial_ready'));
  assert.equal(view.split('\n')[0], 'UART direkt: Schnittstelle bereit');
  assert.ok(view.includes(SERIAL_NOTE));
  assert.match(outputView(serial('failed', {error: 'Port weg'})), /Schnittstelle fehlgeschlagen\n.*\nPort weg\n/);
  assert.match(outputItem(serial('serial_ready')).html, /nicht abgenommen/);
  assert.doesNotMatch(outputItem(bridge('uart', 'waiting')).html, /nicht abgenommen/);
});

test('Statusleiste: Ton und Text', () => {
  assert.equal(outputItem(bridge('uart', 'disconnected')).cls, 'warn');
  assert.equal(outputItem(bridge('tcp', 'waiting')).cls, 'warn');
  assert.equal(outputTone(serial('failed')), 'err');
  assert.equal(outputTone(bridge('tcp', 'audit_failed')), 'err');
  assert.equal(outputTone(bridge('tcp', 'bridge_connected')), '');
  assert.match(outputItem(bridge('tcp', 'waiting')).html, /GSVmulti: Netzwerk über Brücke · <b>Warte auf Windows-Brücke<\/b>/);
});

test('POST-Koerper je Weg', () => {
  assert.deepEqual(outputBody('off'), {transport: 'off'});
  assert.deepEqual(outputBody('uart'), {transport: 'uart'});
  assert.deepEqual(outputBody('tcp', {tcpPort: '5001'}), {transport: 'tcp', tcp_port: 5001});
  assert.deepEqual(outputBody('serial', {port: '/dev/ttyAMA0', baudrate: '115200', prefix: '%', ack: true}),
    {transport: 'serial', port: '/dev/ttyAMA0', baudrate: 115200, prefix: '%', acknowledge_unaccepted: true});
  assert.equal(outputBody('serial', {port: 'p', baudrate: '9600', prefix: '%'}).acknowledge_unaccepted, false);
});

test('Wahl wird gemerkt, kaputter Speicher stoert nicht', () => {
  const store = {m: {}, getItem(k) { return this.m[k] ?? null; }, setItem(k, v) { this.m[k] = v; }};
  assert.equal(loadChoice(store), 'off');
  saveChoice('tcp', store);
  assert.equal(loadChoice(store), 'tcp');
  store.m['werkbank.ausgabe-weg'] = 'quatsch';
  assert.equal(loadChoice(store), 'off');
  const broken = {getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); }};
  assert.equal(loadChoice(broken), 'off');
  saveChoice('uart', broken);
});

const released = (transport, state, extra = {}) => bridge(transport, state, {release: 'test_unaccepted', release_block: null,
  release_note: BRIDGE_NOTE, ...extra});

test('Testfreigabe: Hinweis woertlich, Marker, Warn-Ton, keine Sperrzeile', () => {
  const view = outputView(released('tcp', 'bridge_connected'));
  assert.ok(view.includes(BRIDGE_NOTE));
  assert.doesNotMatch(view, /DUT-Ausgabe gesperrt/);
  assert.equal(outputTone(released('tcp', 'bridge_connected')), 'warn');
  assert.equal(outputTone(released('uart', 'audit_failed')), 'err');
  const item = outputItem(released('uart', 'waiting'));
  assert.match(item.html, /Testfreigabe – nicht abgenommen/);
  assert.doesNotMatch(item.html, />gesperrt</);
  assert.equal(markerText(released('tcp', 'waiting')), 'Testfreigabe – nicht abgenommen');
  assert.equal(markerText(bridge('tcp', 'waiting')), null);
  assert.match(outputItem(bridge('tcp', 'waiting')).html, />gesperrt</);
});

test('Testfreigabe: POST-Koerper nur mit Haken', () => {
  assert.deepEqual(outputBody('uart', {ack: true}), {transport: 'uart', acknowledge_unaccepted: true});
  assert.deepEqual(outputBody('tcp', {tcpPort: '5001', ack: true}), {transport: 'tcp', tcp_port: 5001, acknowledge_unaccepted: true});
  assert.deepEqual(outputBody('uart', {ack: false}), {transport: 'uart'});
  assert.deepEqual(outputBody('off', {ack: true}), {transport: 'off'});
});

// --- U1: Vierkanal-Takt ---
import {FORMAT_WARNING, ONE_CH_SHORT, RATE_NOTE, FORMAT_DEFAULTS, rateValid, tickLine, tickShort, formatLabel, outputBody as ob}
  from '../src/dispread/workbench/static/live/run/output.js';

test('Format: Vorgaben, Warnung woertlich, Takt 1-10 ganzzahlig', () => {
  assert.deepEqual(FORMAT_DEFAULTS, {format: '4ch', rateHz: 10});
  assert.match(FORMAT_WARNING, /^Einkanal-Ausgabe: Bei Übergang \(TRANSITION\) und unlesbarer Anzeige \(UNREADABLE\) werden keine Zeilen gesendet\. GSVmulti zeichnet die Lücken nicht auf; Laufzeit und Zeitachse der Aufnahme sind deshalb nicht genau\.$/);
  assert.equal(RATE_NOTE, 'In GSVmulti dieselbe Frequenz einstellen (Data Frequency).');
  for (const ok of [1, 4, 10, '7']) assert.equal(rateValid(ok), true);
  for (const bad of [0, 11, 2.5, '', 'x', null, NaN]) assert.equal(rateValid(bad), false);
});

test('outputBody: Format und Takt je Weg', () => {
  assert.deepEqual(ob('tcp', {tcpPort: 5000, format: '4ch', rateHz: '5'}), {transport: 'tcp', tcp_port: 5000, format: '4ch', rate_hz: 5});
  assert.deepEqual(ob('uart', {format: '1ch', rateHz: 5, ack: true}), {transport: 'uart', acknowledge_unaccepted: true, format: '1ch'});
  assert.deepEqual(ob('serial', {port: '/dev/ttyAMA0', baudrate: 115200, prefix: 'x', ack: true, format: '4ch', rateHz: 10}),
    {transport: 'serial', port: '/dev/ttyAMA0', baudrate: 115200, prefix: '%', acknowledge_unaccepted: true, format: '4ch', rate_hz: 10});
  assert.deepEqual(ob('off', {format: '4ch', rateHz: 10}), {transport: 'off'});
});

test('Taktzeile im Lauf', () => {
  const out = (tick, format = '4ch') => ({transport: 'serial', state: 'serial_ready', config: {format, rate_hz: 10}, tick});
  assert.equal(tickLine(out({rate_hz: 10, total: 200, valid: 150, missed: 3})), 'Vierkanal-Takt 10 Hz · gültig 75 % · verpasst 3');
  assert.equal(tickLine(out({rate_hz: 10, total: 0, valid: 0, missed: 0})), 'Vierkanal-Takt 10 Hz · gültig – · verpasst 0');
  assert.equal(tickLine(out({rate_hz: 10, total: 100, valid: 99, missed: 0, lost: 4, unconfirmed: 2})),
    'Vierkanal-Takt 10 Hz · gültig 99 % · verpasst 0 · verloren 4 · unbestätigt 2');
  assert.equal(tickLine(out(undefined)), 'Vierkanal-Takt 10 Hz · gültig – · verpasst 0');
  assert.equal(tickLine(out(null, '1ch')), ONE_CH_SHORT);
  assert.equal(tickLine({transport: 'tcp', state: 'waiting', config: {}}), ONE_CH_SHORT);
  assert.equal(tickLine({transport: 'off', state: 'off'}), null);
  assert.equal(tickShort(out({total: 200, valid: 150, missed: 3})), '10 Hz · 75 % gültig');
  assert.equal(formatLabel(out(null)), 'Vierkanal-Takt 10 Hz');
  assert.equal(formatLabel(out(null, '1ch')), 'Einkanal (nur gültige Werte)');
});
