import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import type { Page } from '@playwright/test';

export function sessionFixture() {
  const bodies = new Map<string, { body: Buffer | string; contentType: string }>();
  const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
  function run(id: string, day: string, processing: number[], testRun = false, synthetic = false) {
    const rows = processing.map((ms, i) => ({ schema_version: 1, frame_sequence: i, status: i === 3 ? 'unreadable' : 'valid',
      value: i === 3 ? null : i + 1, unit: 'mV/V', confidence: .9, capture_timestamp: { value_ns: i * 1e9, base: synthetic ? 'synthetic' : 'v4l2_monotonic' },
      result_timestamp: { value_ns: i * 1e9 + 10e6, base: 'host_monotonic' },
      trace: { t_dequeue_ns: i * 1e9, t_record_built_ns: i * 1e9 + ms * 1e6 }, reject_reasons: i === 3 ? ['tracking_lost'] : [], component_versions: { dispread: day } }));
    const raw = Buffer.from(rows.map(r => JSON.stringify(r)).join('\n') + '\n'), packed = gzipSync(raw);
    const path = 'chunks/' + id.replace('/', '-') + '.gz.bin';
    const files = [{ name: 'records.jsonl', size: raw.length, parts: [{ path, size: packed.length, sha256: hash(packed), raw_size: raw.length, raw_sha256: hash(raw) }] }];
    const manifest = 'runs/' + id.replace('/', '-') + '/manifest.json';
    bodies.set(path, { body: packed, contentType: 'application/octet-stream' });
    bodies.set(manifest, { body: JSON.stringify({ schema: 'session-files/1', id, files }), contentType: 'application/json' });
    const median = processing.length === 2 ? 6 : processing.length === 4 ? 35 : 100;
    return { id, group: testRun ? 'tests' : 'regular', device_id: 'GSV-2AS', unit: 'mV/V', test_run: testRun,
      warnings: testRun ? ['Testlauf, keine Messfreigabe'] : [], started_at_utc: `2026-10-${day}T10:00:00+00:00`, ended_at_utc: `2026-10-${day}T10:01:00+00:00`,
      config: { tolerance: 1, confirm_frames: 2 }, versions: { dispread: day }, manifest, files,
      stats: { frames: rows.length, invalid_lines: 0, counts: { valid: Math.min(3, rows.length), unreadable: rows.length === 4 ? 1 : 0 }, processing_ms: { n: rows.length, mean: median, median, p95: processing.length === 2 ? 9.6 : processing.length === 4 ? 48.5 : 100 },
        confidence: { n: Math.min(3, rows.length), median: .9, mean: .9, p95: .9 }, value: { n: Math.min(3, rows.length), median: rows.length === 2 ? 1.5 : 2 },
        duration_s: synthetic ? null : rows.length - 1, rate_hz: synthetic ? null : rows.length / (rows.length - 1), tracking_lost: 0 } };
  }
  const runs = [run('live-a/run-01', '23', [2, 10]), run('live-b/run-01', '28', [20, 30, 40, 50]), run('live-test/run-01', '28', [100], true, true)];
  const equal = { shares: { valid: .875, unreadable: .125, transition: 0, stale: 0 }, processing_median_ms: 20.5, processing_p95_ms: 29.05, confidence_median: .9, rate_hz: 5 / 3, tracking_per_1000: 0 };
  const weighted = { ...equal, shares: { valid: 5 / 6, unreadable: 1 / 6, transition: 0, stale: 0 }, processing_median_ms: 25, processing_p95_ms: 47.5, rate_hz: 1.5 };
  const groups = [{ id: 'regular', label: 'GSV-2AS · mV/V · streng', config: {}, test_run: false, session_count: 2, frames: 6, run_equal: equal, frame_weighted: weighted },
    { id: 'tests', label: 'GSV-2AS · Testlauf', config: {}, test_run: true, session_count: 1, frames: 1, run_equal: { ...equal, processing_median_ms: 100 }, frame_weighted: { ...weighted, processing_median_ms: 100 } }];
  const catalog = { schema: 'sessions/1', stats_version: 'sessions-stats/1', generated_at: '2026-10-28T11:00:00+00:00', runs, groups, errors: [] };
  bodies.set('catalog.json', { body: JSON.stringify(catalog), contentType: 'application/json' });
  return { bodies, catalog };
}

export async function mockSessionArchive(page: Page) {
  const fixture = sessionFixture();
  await page.route('**/assets/sessions/**', async route => {
    const key = new URL(route.request().url()).pathname.split('/assets/sessions/')[1];
    const entry = fixture.bodies.get(key);
    if (entry) await route.fulfill({ status: 200, ...entry }); else await route.fulfill({ status: 404, body: 'missing' });
  });
  return fixture;
}
