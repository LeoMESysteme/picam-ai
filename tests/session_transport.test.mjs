import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import vm from 'node:vm';

const code = readFileSync(new URL('../docs-site/assets/session-files.js', import.meta.url), 'utf8');
const sha = async bytes => Buffer.from(await webcrypto.subtle.digest('SHA-256', bytes)).toString('hex');
function transport(fetch) {
  const window = {};
  vm.runInNewContext(code, { window, document: { currentScript: { src: 'https://wiki.test/assets/session-files.js' } }, URL, fetch, crypto: webcrypto, Blob, ReadableStream, Response, DecompressionStream, Uint8Array, setTimeout });
  return window.SessionFiles;
}

test('reconstructs exact UTF8 bytes from independent checked gzip blocks', async () => {
  const original = Buffer.from('Zähler\n{"status":"valid"}\n');
  const parts = [];
  for (let start = 0; start < original.length; start += 3) {
    const raw = original.subarray(start, start + 3), packed = gzipSync(raw);
    parts.push({ path: `chunks/${start}.gz.bin`, size: packed.length, raw_size: raw.length, sha256: await sha(packed), raw_sha256: await sha(raw), packed });
  }
  const io = transport(async url => new Response(parts.find(p => String(url).endsWith(p.path)).packed));
  const file = io.file({ name: 'records.jsonl', size: original.length, parts });
  const result = await new Response(file.stream()).arrayBuffer();
  assert.deepEqual(Buffer.from(result), original);
});

test('refuses corrupt bytes before exposing any unchecked records', async () => {
  const raw = Buffer.from('original'), packed = gzipSync(raw);
  const corrupted = Buffer.from(packed); corrupted[12] ^= 1;
  const io = transport(async () => new Response(corrupted));
  const file = io.file({ name: 'records.jsonl', size: raw.length, parts: [{ path: 'chunks/a.gz.bin', size: packed.length, raw_size: raw.length, sha256: await sha(packed), raw_sha256: await sha(raw) }] });
  await assert.rejects(new Response(file.stream()).arrayBuffer(), /Prüfsumme/);
});

test('manifest paths cannot fetch outside the protected archive', () => {
  const io = transport(() => { throw new Error('must not fetch'); });
  for (const path of ['../secret', '/secret', 'https://other.test/file', 'chunks/%2e%2e/file', 'chunks/../../secret']) assert.throws(() => io.member(path));
});

test('login redirects and HTML error pages are not parsed as a catalog', async () => {
  const io = transport(async () => new Response('<html>Login</html>', { headers: { 'Content-Type': 'text/html' } }));
  await assert.rejects(io.catalog(), /Anmeldung/);
});

const explorer = readFileSync(new URL('../docs-site/assets/records-explorer/index.html', import.meta.url), 'utf8');
test('missing calendar dates never turn into January 1970', () => {
  const dashboard = readFileSync(new URL('../docs-site/assets/wiki-sessions.js', import.meta.url), 'utf8');
  const dateSource = dashboard.slice(dashboard.indexOf('const date ='), dashboard.indexOf('function el('));
  const ctx = { Intl }; vm.createContext(ctx); vm.runInContext(dateSource + '\nglobalThis.format=date;globalThis.order=chronological;', ctx);
  assert.equal(ctx.format(null), 'Zeit unbekannt');
  assert.equal(ctx.format(''), 'Zeit unbekannt');
  const rows = [{id:'unknown',started_at_utc:null},{id:'older',started_at_utc:'2026-10-23T10:00:00Z'},{id:'newer',started_at_utc:'2026-10-28T10:00:00Z'}];
  assert.deepEqual(rows.sort((a,b)=>ctx.order(a,b,true)).map(r=>r.id), ['newer','older','unknown']);
});
test('notable runs follow Tukey fences within the group and need four runs', () => {
  const dashboard = readFileSync(new URL('../docs-site/assets/wiki-sessions.js', import.meta.url), 'utf8');
  const helpers = dashboard.slice(dashboard.indexOf('const share ='), dashboard.indexOf('// Kurzname'));
  const rules = dashboard.slice(dashboard.indexOf('/* Auffälligkeiten'), dashboard.indexOf('/* Ende Auffälligkeiten */'));
  const ctx = {}; vm.createContext(ctx); vm.runInContext(helpers + rules + '\nglobalThis.notable=notableRuns;', ctx);
  const run = (id, valid, p95 = 20) => ({ id, stats: { frames: 100, counts: { valid }, processing_ms: { p95 }, rate_hz: 29.8, confidence: { median: .99 }, tracking_lost: 5 } });
  const runs = [run('a', 60), run('b', 62), run('c', 65), run('d', 66), run('e', 20, 80)];
  const found = ctx.notable(runs);
  assert.equal([...found.keys()].join(), 'e');
  assert.equal(found.get('e').map(n => n.key).sort().join(), 'p95,valid');
  // Unter vier Läufen gibt es keine Aussage über die Gruppe.
  assert.equal(ctx.notable(runs.slice(2)).size, 0);
});
const parserCode = explorer.slice(explorer.indexOf('async function parseFile('), explorer.indexOf('/* ---------------- workspace'));
const summaryCode = explorer.slice(explorer.indexOf('function summary('), explorer.indexOf('function renderCompare('));
function parser() {
  const ctx = { TextDecoder, performance, setTimeout, STATUS_BASE: ['valid', 'transition', 'unreadable', 'stale'], ST_VALID: 0, ST_UNREADABLE: 2, LOW_CONF: .5, MIN_UNREAD_S: 1,
    CONF_CLASSES: [[0, .5], [.5, 1.1]], reasonGroup: v => v,
    TRACE_KEYS: ['t_dequeue_ns','t_locate_done_ns','t_rectify_done_ns','t_read_done_ns','t_gate_done_ns','t_record_built_ns'].map(k => [k]) };
  vm.createContext(ctx); vm.runInContext(parserCode + summaryCode + '\nglobalThis.parse=parseFile;parse.summarize=summary;', ctx); return ctx.parse;
}
const row = (i, extra = {}) => ({ schema_version: 1, frame_sequence: i, status: 'valid', value: i, capture_timestamp: { value_ns: i * 1e9, base: 'v4l2_monotonic' }, result_timestamp: { value_ns: i * 1e9 + 30e6, base: 'host_monotonic' }, trace: { t_dequeue_ns: i * 1e9 + 10e6, t_record_built_ns: i * 1e9 + 20e6 }, ...extra });
async function parse(rows) { return parser()(new File([rows.map(r => JSON.stringify(r)).join('\n')], 'records.jsonl'), () => {}); }

test('synthetic/mixed bases use frame index; trace stays separately measurable', async () => {
  const data = await parse([row(5, { capture_timestamp: { value_ns: 9e9, base: 'synthetic' } }), row(9)]);
  assert.equal(data.timeBearing, false);
  assert.deepEqual(Array.from(data.t), [0, 1]);
  assert.equal(data.proc[0], 10);
  assert.equal(data.hasLat, false);
});

test('real jumps remain exact and stale raw values never become current values', async () => {
  const data = await parse([row(0, { value: 1 }), row(1, { value: 99 }), row(2, { value: 99, status: 'stale' })]);
  assert.equal(data.timeBearing, true);
  assert.deepEqual(Array.from(data.v.slice(0, 2)), [1, 99]);
  assert.ok(Number.isNaN(data.v[2]));
  assert.equal(JSON.parse(data.text[2]).value, 99);
  assert.equal(data.hasLat, false);
});

test('one frame and equal capture timestamps never fabricate a one-second rate', async () => {
  for (const rows of [[row(0)], [row(0), row(0)]]) {
    const parse = parser();
    const data = await parse(new File([rows.map(r => JSON.stringify(r)).join('\n')], 'records.jsonl'), () => {});
    const stats = parse.summarize(data);
    assert.ok(Number.isNaN(stats.rate));
    assert.ok(Number.isNaN(stats.dropPerMin));
  }
});

test('missing trace marks do not attribute a combined interval to the next stage', async () => {
  const data = await parse([row(0, { trace: { t_dequeue_ns: 0, t_locate_done_ns: 5e6,
    t_rectify_done_ns: null, t_read_done_ns: 15e6, t_gate_done_ns: 20e6, t_record_built_ns: 25e6 } })]);
  assert.equal(data.steps[0][0], 5);
  assert.ok(Number.isNaN(data.steps[1][0]));
  assert.ok(Number.isNaN(data.steps[2][0]));
  assert.equal(data.steps[3][0], 5);
  assert.equal(data.steps[4][0], 5);
  assert.equal(data.proc[0], 25);
});

test('loading progress changes the transform without writing a layout width', async () => {
  const nodes = new Map();
  const barStyle = new Proxy({}, { set(target, key, value) {
    assert.notEqual(key, 'width', 'progress must not animate layout');
    target[key] = value; return true;
  } });
  const ctx = { FILES: { A: null, B: null }, VIEW: 'A',
    $: id => { if (!nodes.has(id)) nodes.set(id, { style: id === 'loadBar' ? barStyle : {} }); return nodes.get(id); },
    mb: String, nf: String, setView() {}, toastHide() {},
    parseFile: async (file, progress) => { progress(25, 1); return { n: 1 }; } };
  vm.createContext(ctx);
  const source = explorer.slice(explorer.indexOf('let loading=false;'), explorer.indexOf('async function parseFile('));
  vm.runInContext(source + '\nglobalThis.openFile=loadFile;', ctx);
  await ctx.openFile({ name: 'records.jsonl', size: 100 });
  assert.equal(barStyle.transform, 'scaleX(0.25)');
});
