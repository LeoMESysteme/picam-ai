// Gemeinsamer Statusvertrag fuer Node und Browser; keine Laufzeitabhaengigkeiten.
const fail = (path, expected) => { throw new TypeError(`${path}: erwartet ${expected}`); };
const object = (v, p) => {
  if (v === null || typeof v !== 'object' || Array.isArray(v)) fail(p, 'Objekt');
};
const string = (v, p) => { if (typeof v !== 'string') fail(p, 'String'); };
const boolean = (v, p) => { if (typeof v !== 'boolean') fail(p, 'Boolean'); };
const number = (v, p) => { if (typeof v !== 'number' || !Number.isFinite(v)) fail(p, 'endliche Zahl'); };
const percentage = (v, p) => { number(v, p); if (v < 0 || v > 100) fail(p, 'Zahl von 0 bis 100'); };
const nonnegative = (v, p) => { number(v, p); if (v < 0) fail(p, 'Zahl >= 0'); };
const integer = (v, p) => { nonnegative(v, p); if (!Number.isInteger(v)) fail(p, 'Ganzzahl >= 0'); };
const positive = (v, p) => { integer(v, p); if (v === 0) fail(p, 'positive Ganzzahl'); };
const nullable = check => (v, p) => { if (v !== null) check(v, p); };
const choice = (...values) => (v, p) => { if (!values.includes(v)) fail(p, values.join('|')); };
const array = check => (v, p) => {
  if (!Array.isArray(v)) fail(p, 'Array');
  v.forEach((item, i) => check(item, `${p}[${i}]`));
};
const tuple = (...checks) => (v, p) => {
  if (!Array.isArray(v) || v.length !== checks.length) fail(p, `Tupel mit ${checks.length} Eintraegen`);
  checks.forEach((check, i) => check(v[i], `${p}[${i}]`));
};
const fields = schema => (v, p) => {
  object(v, p);
  for (const [key, check] of Object.entries(schema)) {
    if (!Object.hasOwn(v, key)) fail(`${p}.${key}`, 'Pflichtfeld');
    check(v[key], `${p}.${key}`);
  }
};
const dictionary = check => (v, p) => {
  object(v, p);
  for (const [key, item] of Object.entries(v)) check(item, `${p}.${key}`);
};
const optional = (v, key, check, p) => { if (Object.hasOwn(v, key)) check(v[key], `${p}.${key}`); };
const checkStatus = choice('OK', 'WARNUNG', 'FEHLER', 'NICHT_GEPRUEFT');
const valueStatus = choice('valid', 'transition', 'unreadable', 'stale');
const point = tuple(number, number);
const timestamp = fields({ value_ns: integer, base: string, semantics: string, uncertainty_ns: nullable(integer) });
const focus = fields({
  method: choice('climb', 'sweep'), samples: array(tuple(number, number)),
  verify: nullable(fields({ score: number, threshold: number })),
  roi: nullable(tuple(integer, integer, positive, positive)),
});
const exposure = fields({
  target: number, band: tuple(number, number),
  rounds: array(fields({ level: nullable(number), controls: object })),
});
const progress = fields({
  steps: array(fields({
    key: choice('fokus', 'kamera', 'belichtung', 'standbilder', 'vorschlag'),
    state: choice('pending', 'running', 'done', 'failed'), elapsed_s: nullable(nonnegative),
  })),
  attempt: positive, attempts_max: positive,
  phase: nullable(choice('mitteln', 'zelltext', 'raster', 'stabilitaet', 'zweites_standbild', 'gegenlesen')),
  wait: nullable(fields({ elapsed_s: nonnegative, total_s: nonnegative })),
});
function setup(v, p) {
  fields({ focus, exposure, progress, step: nullable(string), elapsed_s: nullable(nonnegative),
    grid: nullable(fields({ target_size: point, cell_boxes: array(tuple(number, number, number, number)),
                            quad: tuple(point, point, point, point), source: string })),
  })(v, p);
  if (v.progress.steps.length !== 5 || new Set(v.progress.steps.map(s => s.key)).size !== 5) {
    fail(`${p}.progress.steps`, 'fuenf unterschiedliche Schritte');
  }
  const checksLive = dictionary(fields({ status: checkStatus, reason: nullable(string) }));
  if (!Object.hasOwn(v, 'overall')) fields({ checks_live: checksLive })(v, p);
  else {
    fields({
      overall: checkStatus, checks: dictionary(checkStatus), overlays: array(string),
      proposal_revision: string, regions: array(fields({ centre: point, size: positive })),
      auswahl: choice('automatisch', 'manuell'), centre_results: array(fields({
        requested_centre: point, centre: nullable(point), used_centre: nullable(point),
        ok: boolean, reason: nullable(string),
      })),
    })(v, p);
    optional(v, 'checks_live', checksLive, p);
  }
  optional(v, 'message', string, p);
  optional(v, 'diagnostics_error', string, p);
  optional(v, 'check_reasons', dictionary(string), p);
  optional(v, 'gegenlesen', fields({ status: checkStatus, metrics: object }), p);
}
const latest = fields({
  frame_sequence: integer, status: valueStatus, value: nullable(number), unit: string,
  raw_text: string, reject_reasons: array(string), frames_confirmed: integer,
  confirmation_span_ns: nullable(integer), capture_timestamp: timestamp,
});
const hint = fields({
  kind: choice('anzeige_bewegt', 'rahmen_verdeckt', 'unbekannt'), since_s: nonnegative,
  shift_px: nullable(number), rotation_deg: nullable(number), region_shift_px: nullable(number),
});
const causes = fields({
  window_s: number, frames: integer, limited: boolean,
  causes: array(fields({ reason: string, count: integer, fraction: number })),
});
function output(v, p) {
  fields({ transport: choice('off', 'serial', 'uart', 'tcp'), state: string })(v, p);
  if (v.transport === 'off') {
    choice('off')(v.state, `${p}.state`);
    return;
  }
  fields({
    state: choice('waiting', 'bridge_connected', 'disconnected', 'audit_failed', 'stopped', 'serial_ready', 'failed'),
    config: object, error: nullable(string), release_block: nullable(string),
    last_ack: nullable(object), ack_scope: string, acceptance: choice('fehlt'),
  })(v, p);
  if (v.transport === 'serial') fields({ release_note: string })(v, p);
}
function run(v, p) {
  fields({
    latest: nullable(latest), summary: object,
    counts: fields({ valid: integer, transition: integer, unreadable: integer, stale: integer }),
    recent: array(tuple(nonnegative, choice('v', 't', 'u', 's'), nullable(number))),
    recent_now_ms: nonnegative, dir: string, latest_age_s: nullable(nonnegative), guess: nullable(object),
    started_at_utc: string, elapsed_s: nonnegative, ended_at_utc: nullable(string),
    tracking: object, tracking_hint: nullable(hint), rejection_causes: causes,
  })(v, p);
  optional(v, 'output', object, p);
}
function referenceEval(v, p) {
  fields({ state: choice('running', 'done', 'error') })(v, p);
  if (v.state === 'done') {
    fields({ misreads: integer, compared_valid: integer, undecided_valid: integer, uncovered_valid: integer })(v, p);
  } else if (v.state === 'error') fields({ error: string })(v, p);
}
const root = fields({
  state: choice('idle', 'setup_running', 'setup_failed', 'setup_ready', 'confirmed', 'running', 'stopped', 'error'),
  step: nullable(string), error: nullable(string), simulate: boolean,
  camera: fields({ running: boolean, stalled: boolean, error: nullable(string), frames: integer,
                   gaps: integer, source: object, last_start: nullable(object) }),
  storage: fields({ free_bytes: nullable(nonnegative), reserve_bytes: nonnegative,
                    level: choice('ok', 'warn', 'error'), message: string }),
  system: fields({ cpu_percent: nullable(percentage), cpu_window_s: nonnegative }),
  release_notice: string, session_id: nullable(string), setup: nullable(setup), profile: nullable(object),
  run_block: nullable(string), test_run: nullable(object), reader_tolerance: nullable(object), run: nullable(run),
  diagnostics: fields({ enabled: boolean }), diagnose_kopie: boolean,
  diagnostic_leftovers: array(fields({ path: string, bytes: nullable(nonnegative) })),
  last_mark: nullable(object), reference: fields({ enabled: boolean,
    latest: nullable(fields({ cell_text: string, raw: string, value: number, age_s: nonnegative })),
    schedule_step: nullable(fields({ index: integer, factor: number, since_s: nonnegative })),
  }), reference_eval: nullable(referenceEval),
});

/** Throws TypeError with a field path if required status fields have a wrong shape. */
export function assertStatusShape(status) {
  root(status, 'status');
  optional(status, 'output', output, 'status');
  optional(status, 'csrf', string, 'status');
  optional(status, 'tracking_reasons', dictionary(string), 'status');
  optional(status, 'cause_texts', dictionary(string), 'status');
}
