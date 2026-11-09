import assert from 'node:assert/strict';
import test from 'node:test';
import {PROFILE_FILENAME, bridgeTransport, countdownText, fingerprintGroups, fingerprintLines, offerBody, offerRemainingS,
  prepareBody, readinessRows, requestError, uartView} from '../src/dispread/workbench/static/live/run/bridge-setup.js';

test('Countdown 5:00 bis 0:00, nie negativ', () => {
  assert.equal(countdownText(300), '5:00');
  assert.equal(countdownText(61), '1:01');
  assert.equal(countdownText(9.2), '0:10');
  assert.equal(countdownText(0), '0:00');
  assert.equal(countdownText(-3), '0:00');
  assert.equal(countdownText(NaN), '0:00');
});

test('Restzeit aus Ablaufzeitpunkt, aufgerundet', () => {
  assert.equal(offerRemainingS(10_000 + 300_000, 10_000), 300);
  assert.equal(offerRemainingS(10_000 + 300_000, 10_000 + 299_100), 1);
  assert.equal(offerRemainingS(10_000, 20_000), 0);
});

test('Fingerabdruck in Vierergruppen, Trennzeichen entfernt', () => {
  assert.equal(fingerprintGroups('ab12cd34ef56'), 'ab12 cd34 ef56');
  assert.equal(fingerprintGroups('AB:12:CD:34:EF'), 'ab12 cd34 ef');
  assert.equal(fingerprintGroups(''), '');
  assert.equal(fingerprintGroups(null), '');
});

test('Transport passend zur Ausgabewahl, Koerper exakt', () => {
  assert.equal(bridgeTransport('tcp'), 'network');
  assert.equal(bridgeTransport('uart'), 'uart');
  assert.equal(bridgeTransport('off'), null);
  assert.equal(bridgeTransport('serial'), null);
  assert.deepEqual(offerBody('network'), {transport: 'network'});
  assert.deepEqual(prepareBody(), {transport: 'uart'});
  assert.equal(PROFILE_FILENAME, 'pi.dispread');
});

test('Serverfehler woertlich aus JSON oder Text', () => {
  assert.equal(requestError(409, '{"error":"UART unavailable or occupied; release its owner first"}'),
    'UART unavailable or occupied; release its owner first');
  assert.equal(requestError(503, 'Bridge hub unavailable'), 'Bridge hub unavailable');
  assert.equal(requestError(500, ''), 'HTTP 500');
});

test('UART-Zustandswoerter und Fehlertext', () => {
  assert.equal(uartView({uart_state: 'unprepared'}).word, 'nicht vorbereitet');
  assert.equal(uartView({uart_state: 'listening'}).tone, 'ok');
  assert.equal(uartView({uart_state: 'failed', uart_error: 'busy'}).error, 'busy');
  assert.equal(uartView({uart_state: 'failed'}).tone, 'err');
  assert.equal(uartView(null).word, 'unbekannt');
});

test('Bereitschaft: Verbindung heisst nie Freigabe, Sperre woertlich', () => {
  const rows = readinessRows({pi_id: 'pi-1', connected: true, transport: 'network', release_block: 'DUT-Ausgabe gesperrt: X'});
  assert.deepEqual(rows.map((r) => r.label), ['Pi-Kennung', 'Windows-App', 'Ausgabe']);
  assert.equal(rows[0].value, 'pi-1');
  assert.equal(rows[1].value, 'verbunden über Netzwerk');
  assert.equal(rows[2].value, 'DUT-Ausgabe gesperrt: X');
  assert.equal(readinessRows({pi_id: 'p', connected: true, transport: 'uart', release_block: ''})[1].value, 'verbunden über UART');
  const off = readinessRows({pi_id: 'p', connected: false, transport: null, release_block: ''});
  assert.equal(off[1].value, 'nicht verbunden');
  assert.equal(off.length, 2, 'ohne Sperrtext keine Ausgabezeile');
  assert.ok(!JSON.stringify(rows).match(/bereit zur Messung|Messfreigabe/));
  assert.deepEqual(readinessRows(null), []);
});

test('Fingerabdruck: Kleinbuchstaben, vier Gruppen je Zeile, nie gekuerzt', () => {
  const hex = ('0123456789ABCDEF'.repeat(4));
  const lines = fingerprintLines(hex);
  assert.equal(lines.length, 4);
  for (const line of lines) assert.equal(line, '0123 4567 89ab cdef');
  assert.equal(lines.join('').replace(/ /g, ''), hex.toLowerCase());
  assert.deepEqual(fingerprintLines('AB:12:CD:34:EF:56:78:90:11'), ['ab12 cd34 ef56 7890', '11']);
  assert.deepEqual(fingerprintLines(null), []);
});

test('Bereitschaft: Testfreigabe ersetzt den Sperrtext', () => {
  const rows = readinessRows({pi_id: 'p', connected: true, transport: 'network', release: 'test_unaccepted', release_block: null});
  assert.deepEqual(rows[2], {label: 'Ausgabe', value: 'Testfreigabe – nicht abgenommen', tone: 'warn'});
});
