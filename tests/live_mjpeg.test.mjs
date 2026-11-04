import test from 'node:test';
import assert from 'node:assert/strict';
import {openPreview, parseParts} from '../src/dispread/workbench/static/live/mjpeg.js';

const enc = new TextEncoder();

function part(seq, body, hud = {seq}) {
  const head = enc.encode('--frame\r\nContent-Type: image/jpeg\r\n' +
    `Content-Length: ${body.length}\r\nX-Frame-Sequence: ${seq}\r\nX-Capture-Ns: ${seq * 1000}\r\n` +
    `X-Hud: ${JSON.stringify(hud)}\r\n\r\n`);
  return concat(head, body, enc.encode('\r\n'));
}

function concat(...arrays) {
  const out = new Uint8Array(arrays.reduce((n, a) => n + a.length, 0));
  let at = 0;
  for (const a of arrays) { out.set(a, at); at += a.length; }
  return out;
}

async function* chunked(bytes, cuts) {
  let from = 0;
  for (const cut of [...cuts, bytes.length]) {
    yield bytes.slice(from, cut);
    from = cut;
  }
}

async function collect(iterable) {
  const out = [];
  for await (const item of iterable) out.push(item);
  return out;
}

test('parseParts splits parts across chunk boundaries', async () => {
  // Der erste Rumpf enthaelt selbst eine Grenzzeile: Content-Length muss gelten.
  const first = concat(Uint8Array.from([0xff, 0xd8, 1, 2, 3]), enc.encode('\r\n--frame\r\n'), Uint8Array.from([0xff, 0xd9]));
  const second = Uint8Array.from({length: 1500}, (_, i) => (i * 37) & 0xff);
  const stream = concat(part(51234, first), part(51235, second, {seq: 51235, w: 1920}));
  // Sieben Schnitte: mitten in Grenze, Kopfzeile, Leerzeile, Rumpf und CRLF.
  const cuts = [3, 20, 61, stream.length - second.length - 140, stream.length - second.length - 3,
    stream.length - 900, stream.length - 1];
  assert.equal(cuts.length, 7);
  const parts = await collect(parseParts(chunked(stream, cuts), 'frame'));
  assert.equal(parts.length, 2);
  assert.equal(parts[0].headers.get('x-frame-sequence'), '51234');
  assert.equal(parts[1].headers.get('x-frame-sequence'), '51235');
  assert.equal(parts[0].body.length, first.length);
  assert.equal(parts[1].body.length, 1500);
  assert.deepEqual([...parts[0].body], [...first]);
  assert.deepEqual([...parts[1].body], [...second]);
  assert.deepEqual(JSON.parse(parts[1].headers.get('x-hud')), {seq: 51235, w: 1920});
  assert.equal(parts[0].headers.get('content-type'), 'image/jpeg');
});

test('parseParts survives one byte per chunk and a trailing partial part', async () => {
  const body = Uint8Array.from([9, 8, 7, 6]);
  const stream = concat(part(7, body), part(8, body).slice(0, 30));
  const cuts = Array.from({length: stream.length - 1}, (_, i) => i + 1);
  const parts = await collect(parseParts(chunked(stream, cuts), 'frame'));
  assert.equal(parts.length, 1);
  assert.deepEqual([...parts[0].body], [9, 8, 7, 6]);
});

test('openPreview reconnects with backoff 0.5 to 5 s and resets after a frame', async () => {
  const sleeps = [];
  const controller = new AbortController();
  let calls = 0;
  const frames = [];
  const goodBody = part(5, Uint8Array.from([1, 2]));
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 7) {
      return {ok: true, headers: new Map([['content-type', 'multipart/x-mixed-replace; boundary=frame']]),
        body: chunked(goodBody, [10])};
    }
    if (calls >= 9) controller.abort();
    throw new Error('weg');
  };
  await openPreview('/live/preview.mjpg', (frame) => frames.push(frame), controller.signal, {
    fetchImpl,
    decode: async (bytes) => ({width: 960, bytes: bytes.length}),
    sleep: async (ms) => { sleeps.push(ms); },
  });
  assert.deepEqual(sleeps, [500, 1000, 2000, 4000, 5000, 5000, 500, 1000]);
  assert.equal(frames.length, 1);
  assert.equal(frames[0].hud.seq, 5);
  assert.equal(frames[0].seq, 5);
  assert.equal(frames[0].bitmap.bytes, 2);
});

test('openPreview passes a null HUD when the header is broken', async () => {
  const controller = new AbortController();
  const raw = concat(enc.encode('--frame\r\nContent-Length: 1\r\nX-Frame-Sequence: 3\r\nX-Hud: {kaputt\r\n\r\n'),
    Uint8Array.from([1]), enc.encode('\r\n'));
  const frames = [];
  await openPreview('/x', (frame) => { frames.push(frame); controller.abort(); }, controller.signal, {
    fetchImpl: async () => ({ok: true, headers: new Map([['content-type', 'multipart/x-mixed-replace; boundary=frame']]),
      body: chunked(raw, [4])}),
    decode: async () => ({width: 960}),
    sleep: async () => {},
  });
  assert.equal(frames.length, 1);
  assert.equal(frames[0].hud, null);
});
