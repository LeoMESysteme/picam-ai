import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';
import { assertStatusShape } from './live_status_shape.mjs';

const dir = new URL('./fixtures/live/', import.meta.url);
const load = name => JSON.parse(readFileSync(new URL(`scene-${name}.json`, dir)));
const scenes = readdirSync(dir).filter(name => /^scene-.*\.json$/.test(name));
test('cause_texts is optional and accepts only an object of strings', () => {
  const status = load('idle');
  delete status.cause_texts;
  assert.doesNotThrow(() => assertStatusShape(status));
  for (const texts of [{}, { no_value: 'Kein lesbarer Wert', kontrast: 'Kontrast zu gering' }]) {
    status.cause_texts = texts;
    assert.doesNotThrow(() => assertStatusShape(status));
  }
  for (const texts of [null, [], 'Text', 1, true, { no_value: 1 }, { no_value: null },
    { no_value: {} }, { no_value: [] }, { no_value: 'Text', kontrast: false }]) {
    status.cause_texts = texts;
    assert.throws(() => assertStatusShape(status), TypeError);
  }
});
test('setup grid accepts reader boxes or null and rejects malformed or missing geometry', () => {
  const status = load('setup_ready_warnung');
  const grid = { target_size: [400, 160], cell_boxes: [[0, 18, 25, 142]], source: 'dot_lattice',
    quad: [[810, 511], [1369, 511], [1377, 580], [814, 591]] };
  status.setup.grid = grid;
  assert.doesNotThrow(() => assertStatusShape(status));
  status.setup.grid = null;
  assert.doesNotThrow(() => assertStatusShape(status));
  for (const broken of [undefined, [], {},
    { ...grid, target_size: [400] }, { ...grid, target_size: [400, '160'] },
    { ...grid, cell_boxes: {} }, { ...grid, cell_boxes: [[0, 18, 25]] },
    { ...grid, cell_boxes: [[0, 18, 25, Infinity]] },
    { ...grid, cell_boxes: [[0, '18', 25, 142]] }, { ...grid, source: 1 },
    { target_size: grid.target_size, cell_boxes: grid.cell_boxes },
    { target_size: grid.target_size, cell_boxes: grid.cell_boxes, source: grid.source },
    ...[null, {}, [], grid.quad.slice(0, 3), [...grid.quad, [1, 2]],
      [[810], ...grid.quad.slice(1)], [[810, 511, 0], ...grid.quad.slice(1)],
      [['810', 511], ...grid.quad.slice(1)], [[810, Infinity], ...grid.quad.slice(1)],
      [[NaN, 511], ...grid.quad.slice(1)]].map(quad => ({ ...grid, quad })),
  ]) {
    status.setup.grid = broken;
    assert.throws(() => assertStatusShape(status), TypeError);
  }
  delete status.setup.grid;
  assert.throws(() => assertStatusShape(status), TypeError);
});
test('all committed scenes exist', () => assert.equal(scenes.length, 11));
for (const name of scenes) {
  test(`${name}: complete contract`, () => {
    const status = JSON.parse(readFileSync(new URL(name, dir)));
    assert.deepEqual(status.output, { transport: 'off', state: 'off' });
    assert.doesNotThrow(() => assertStatusShape(status));
  });
}
const cases = [
  ['idle', 'state', 42], ['idle', 'camera.stalled', 'false'],
  ['idle', 'storage.free_bytes', '4200'], ['idle', 'simulate', 0],
  ['setup_focus', 'setup.focus.method', 'auto'],
  ['setup_focus', 'setup.focus.samples.0.1', '630'],
  ['setup_focus_done', 'setup.focus.verify.score', '624'],
  ['setup_focus_done', 'setup.focus.verify.threshold', NaN],
  ['setup_standbilder', 'setup.exposure.target', '130'],
  ['setup_standbilder', 'setup.exposure.band', [115]],
  ['setup_standbilder', 'setup.progress.steps.0.state', 'finished'],
  ['setup_standbilder', 'setup.progress.steps.0.elapsed_s', '21'],
  ['setup_standbilder', 'setup.progress.phase', 'unknown'],
  ['setup_standbilder', 'setup.progress.wait.total_s', '15'],
  ['setup_standbilder', 'setup.progress.attempt', 0],
  ['setup_standbilder', 'setup.checks_live.kontrast.status', 'GOOD'],
  ['setup_ready_warnung', 'setup.checks.raster', false],
  ['setup_ready_warnung', 'setup.regions.0.centre', [1]],
  ['setup_ready_warnung', 'setup.proposal_revision', 1],
  ['running_valid', 'run.counts.valid', NaN],
  ['running_valid', 'run.counts.stale', -1],
  ['running_valid', 'run.recent.0', [0, 'v']],
  ['running_valid', 'run.recent.0.1', 'x'],
  ['running_valid', 'run.recent.0.2', '0.62'],
  ['running_valid', 'run.recent_now_ms', '60000'],
  ['running_valid', 'run.latest.status', 'maybe'],
  ['running_valid', 'run.latest.capture_timestamp.base', 1],
  ['running_valid', 'run.latest_age_s', '0.04'],
  ['running_anzeige_bewegt', 'run.tracking_hint.since_s', '3'],
];
for (const [scene, path, wrong] of cases) {
  for (const missing of [true, false]) {
    // Tuple members are checked by their length/type; do not make sparse arrays.
    if (missing && /\.\d+$/.test(path)) continue;
    if (missing && path === 'setup.checks.raster') continue; // Pruefnamen sind ein offenes Woerterbuch.
    test(`${scene}: ${missing ? 'missing' : 'invalid'} ${path}`, () => {
      const status = load(scene);
      const parts = path.split('.');
      let parent = status;
      for (const key of parts.slice(0, -1)) parent = parent[key];
      if (missing) delete parent[parts.at(-1)];
      else parent[parts.at(-1)] = wrong;
      assert.throws(() => assertStatusShape(status), TypeError);
    });
  }
}
test('existing root fields are required and additions are allowed', () => {
  const status = load('idle');
  for (const key of Object.keys(status)) {
    if (key === 'output') continue;
    const broken = { ...status };
    delete broken[key];
    assert.throws(() => assertStatusShape(broken), TypeError, key);
  }
  assert.doesNotThrow(() => assertStatusShape({ ...status, future_addition: {} }));
});

test('exposure rounds and nullable data use the real contract', () => {
  const status = load('setup_standbilder');
  status.setup.exposure.rounds = [{ level: 124, controls: { gain: 10 } }, { level: null, controls: {} }];
  assert.doesNotThrow(() => assertStatusShape(status));
  status.setup.exposure.rounds[0].level = '124';
  assert.throws(() => assertStatusShape(status), TypeError);
  delete status.setup.exposure.rounds[0].level;
  assert.throws(() => assertStatusShape(status), TypeError);
  status.setup.exposure.rounds[0] = { level: 124, controls: [] };
  assert.throws(() => assertStatusShape(status), TypeError);
});

const r19Status = () => {
  const status = load('running_valid');
  Object.assign(status.run, { started_at_utc: '2026-11-04T12:00:00+00:00', elapsed_s: 60, ended_at_utc: null });
  Object.assign(status.reference, {
    latest: { cell_text: '+ 0.62427', raw: '+00.62427 mV/V', value: .62427, age_s: .1 },
    schedule_step: { index: 1, factor: 2, since_s: 12 },
  });
  status.reference_eval = null;
  return status;
};
for (const [path, wrong] of [
  ['run.started_at_utc', 42], ['run.elapsed_s', -1], ['run.ended_at_utc', false],
  ['reference.latest.cell_text', 1], ['reference.latest.raw', null],
  ['reference.latest.value', '0.62427'], ['reference.latest.age_s', -1],
  ['reference.schedule_step.index', .5], ['reference.schedule_step.factor', '2'],
  ['reference.schedule_step.since_s', -1], ['reference_eval', {}],
]) {
  test(`run additions reject missing or invalid ${path}`, () => {
    for (const missing of [true, false]) {
      const status = r19Status();
      const keys = path.split('.');
      const parent = keys.slice(0, -1).reduce((obj, key) => obj[key], status);
      if (missing) delete parent[keys.at(-1)];
      else parent[keys.at(-1)] = wrong;
      assert.throws(() => assertStatusShape(status), TypeError);
    }
  });
}
test('reference evaluation accepts running, complete counts or error, rejecting incomplete results', () => {
  const status = r19Status();
  for (const result of [null, { state: 'running' },
    { state: 'done', misreads: 0, compared_valid: 2, undecided_valid: 1, uncovered_valid: 0 },
    { state: 'error', error: 'Abgleich abgelehnt: Testlauf' },
  ]) {
    status.reference_eval = result;
    assert.doesNotThrow(() => assertStatusShape(status));
  }
  for (const result of [{ state: 'unknown' }, { state: 'done', misreads: 0 }, { state: 'error' },
    { state: 'done', misreads: -1, compared_valid: 2, undecided_valid: 1, uncovered_valid: 0 },
    { state: 'done', misreads: 0, compared_valid: '2', undecided_valid: 1, uncovered_valid: 0 },
  ]) {
    status.reference_eval = result;
    assert.throws(() => assertStatusShape(status), TypeError);
  }
});
test('reference latest and schedule can be null', () => {
  const status = r19Status();
  status.reference.latest = status.reference.schedule_step = null;
  assert.doesNotThrow(() => assertStatusShape(status));
});

test('output requires a known transport and complete enabled status', () => {
  const status = load('idle');
  delete status.output;
  assert.doesNotThrow(() => assertStatusShape(status));
  for (const transport of ['serial', 'uart', 'tcp']) {
    status.output = { transport, state: transport === 'serial' ? 'serial_ready' : 'waiting',
      config: { transport }, error: null, release_block: null, last_ack: null };
    assert.doesNotThrow(() => assertStatusShape(status));
    delete status.output.last_ack;
    status.output.last_driver_ack = null;
    assert.doesNotThrow(() => assertStatusShape(status));
    for (const key of ['state', 'config', 'error', 'release_block', 'last_driver_ack']) {
      const valid = status.output;
      status.output = { ...valid };
      delete status.output[key];
      assert.throws(() => assertStatusShape(status), TypeError);
      status.output = valid;
    }
  }
  for (const output of [undefined, null, [], {}, { transport: 'off', state: 'waiting' },
    { transport: 'unknown', state: 'off' }, { transport: 'serial', state: 'serial_ready' },
    { transport: 'tcp', state: 'invented', config: {}, error: null, release_block: null, last_ack: null }]) {
    status.output = output;
    assert.throws(() => assertStatusShape(status), TypeError);
  }
  status.output = { transport: 'off', state: 'off' };
  assert.doesNotThrow(() => assertStatusShape(status));
});
