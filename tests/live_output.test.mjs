import assert from 'node:assert/strict';
import test from 'node:test';
import {outputBody, outputItem, outputTone, outputView, loadChoice, saveChoice, SERIAL_NOTE, LOCK_NOTICE}
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
