// Uebungslauf (Spec "Einarbeitung"): ein clientseitiges Szenario im Format
// von /live/status. Es ist das Zeitachsen-Modell des freigegebenen Mocks
// (mock.src.html: CH, CHECKS, VCH, EP), wartet aber an den Bedienstellen
// auf den Bediener: Einrichtung starten, Bestaetigen (Name Pflicht), Lauf
// starten, Dialog, Lauf stoppen. Kein DOM, kein Netz: node-testbar.
//
// createScenario({clock}) -> {status(), frame(), act(path, body), chapter}
// * status(): Status wie /live/status, oder null waehrend des simulierten
//   Verbindungsverlusts (Mock EP.conn) - der Client wertet das wie einen
//   ausbleibenden Abruf.
// * frame(): {bitmapSource, hud} fuer den Viewer, null bei Stillstand.
//   bitmapSource beschreibt das Bild (Standbild, LCD-Text, Hand, Schaerfe);
//   practice/frames.js setzt es aus still.jpg zusammen.
// * act(path, body): dieselben Bedienschritte wie die POST-Routen, mit den
//   Servertexten woertlich (live/service.py, live_api.py). Nie ein Netzweg.
//
// Die Geometrie stammt aus der echten Sitzung live-20261030T133635Z wie die
// Fixtures des Testservers (tests/live_ui_server.py), in Kamerapixeln
// 1920×1080. Das Standbild hat 1440×810 (Mock-Koordinaten = Kamera × 3/4).
// Werte, Zeiten und Treffer sind simuliert und keine Messbelege.

export const CHAPTERS = ['Bereit', 'Fokus', 'Kamera', 'Belichtung', 'Standbilder', 'Vorschlag',
  'Prüfen & Bestätigen', 'Lauf', 'Lauf beendet'];

// ---- Mock-Zeitachse (Sekunden, Mock-Uhr u; Einrichtung beginnt bei u = 3) ----
const U0 = 3;
const STEP_SPANS = [['fokus', 3, 17], ['kamera', 17, 19], ['belichtung', 19, 23], ['standbilder', 23, 43], ['vorschlag', 43, 47]];
const U_READY = 47;
const PT0 = 3.6, PDT = 1.25; // Fokusproben
const U_VERIFY = PT0 + 9 * PDT + 0.8;
const U_EXPOSED = 21.8;
const U_GRID = 43;
// Mock CHECKS: Schluessel, fertig bei u, Ergebnis, Hinweis.
const CHECKS = [['kontrast', 27.4, 'OK', null], ['kanten', 27.8, 'OK', null], ['rahmen', 28.2, 'OK', null],
  ['glanz', 28.6, 'OK', null], ['belichtung', 29.0, 'OK', 'p80 124'], ['aufloesung', 29.4, 'OK', '26 px je Zelle'],
  ['raster', 29.9, 'WARNUNG', 'Raster am Rand knapp'], ['stabilitaet', 36.5, 'OK', '15 s ohne Änderung'],
  ['rasterversatz', 39.0, 'OK', '0,04 Punktspalten'], ['gegenlesen', 40.5, 'OK', 'beide Standbilder gelesen'],
  ['displayfehler', 43.8, 'OK', null], ['nachfuehrung', 44.6, 'OK', null]];
// Mock comp(): die 15 s Ruhe sind auf 8 s verkuerzt; Dauern zeigen Produktzeit.
const comp = (u) => clamp((u - 28.5) / 8, 0, 1) * 7;
const pt = (u) => u + comp(u);

// ---- Lauf (r = Sekunden seit Laufstart), Mock VCH/TRD/EP ----
const VCH = [[0, '+0.62427'], [3.0, '+0.62428'], [3.8, '+0.62427'], [6.4, '+0.62428'], [6.9, '+0.62427'], [9.0, '+1.24855'],
  [11.5, '+1.24856'], [12.2, '+1.24855'], [19.6, '+1.24854'], [20.3, '+1.24855'], [27.0, '+1.24856'], [27.5, '+1.24855'],
  [31.8, '+1.24854'], [32.4, '+1.24855']];
const TRD = (r0) => (r0 === 9.0 ? 0.4 : 0.2);
const EP = {hand: [14.0, 17.6], handIn: 13.6, handOut: 17.0, corr: [17.0, 18.6], stall: [21.0, 25.0], conn: [28.0, 31.0], bump: 35.0};
const NORM_STEP_R = 9.0;
const FPS = 15;
const SEQ0 = 51234;
const CAP0_NS = 1_730_000_000_000;
const FRAME_NS = 66_666_667;

// ---- Geometrie und Werte der echten Einrichtung (wie tests/live_ui_server.py) ----
const QUAD = [[810, 511], [1369, 511], [1377, 580], [814, 591]];
const REGION_CENTRES = [[873, 385], [915, 737], [1256, 422], [1485, 658], [829, 411], [822, 737],
  [1310, 437], [1457, 635], [877, 459], [858, 742], [1291, 391], [1321, 707]];
const RIGHT_REGIONS = new Set([3, 6, 7, 11]); // die Hand kommt von rechts (Mock 8a)
const FOCUS_SAMPLES = [[48, 630.3558194010419], [56, 273.53271242939513], [40, 201.1113182858314],
  [42, 301.5480297000838], [44, 442.0887939597047], [46, 542.9752734088474],
  [50, 607.4170064667126], [52, 525.0128897387846], [54, 391.07734162279286]];
const FOCUS_VERIFY = {score: 624.465370104453, threshold: 535.8024464908856};
const GRID = {target_size: [400, 160], cell_boxes: Array.from({length: 16}, (_, i) => [25 * i, 18, 25, 142]),
  quad: QUAD, source: 'dot_lattice'};
const CONTROLS = {focus_absolute: 48, exposure_time_absolute: 300, white_balance_temperature: 4742, gain: 10};
const SOURCE = {model: 'logitech_streamcam', usb_id: '046d:0893', size: [1920, 1080], fourcc: 'YUYV', fps: 30, device: 'Übung'};
const REGION_SIZE = 15;
const ADDED_SIZE = 5;
// Messbereich der Fokussuche am Geraet: immer das mittlere Drittel (live/setup.py measurement_roi_pixels).
const FOCUS_ROI = [640, 360, 640, 360];
// Simulierte Last wie im Mock, falls die Werkbank keine meldet.
const SYSTEM = {cpu_percent: 38.0, cpu_window_s: 1.0};
// Wie live_cause (workbench/fields.py) fuer die beiden Gruende, die das Szenario erzeugt.
const CAUSE_EXPLANATION = {'anzeige_wechselt': 'Wert wechselt',
  'tracking_lost:rahmen_unstimmig': 'Rahmenbereiche verdeckt oder verschoben - Kamera und Sicht pruefen'};

export const STILL_URL = 'practice/still.jpg';
export const SAMPLING_URL = 'practice/sampling.jpg';

function clamp(x, lo, hi) { return x < lo ? lo : x > hi ? hi : x; }
const lerp = (a, b, k) => a + (b - a) * k;
const eo = (k) => 1 - (1 - clamp(k, 0, 1)) ** 3;
const eio = (k) => { const x = clamp(k, 0, 1); return x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2; };
const round1 = (x) => Math.round(x * 10) / 10;
const inR = (x, [a, b]) => x >= a && x < b;
const copy = (value) => JSON.parse(JSON.stringify(value));
export const lcdLine = (value) => `${value} mV/V`.padEnd(16, ' ');

// Mock focusAt: Fokusstellung der Kamera waehrend der Suche.
function focusAt(u) {
  let f = 52;
  for (let i = 0; i < FOCUS_SAMPLES.length; i++) {
    const t0 = PT0 + i * PDT;
    if (u >= t0) f = lerp(i ? FOCUS_SAMPLES[i - 1][0] : 52, FOCUS_SAMPLES[i][0], eio((u - t0) / 0.5));
  }
  const tv = PT0 + 9 * PDT;
  if (u >= tv) f = lerp(FOCUS_SAMPLES[8][0], 48, eio((u - tv) / 0.5));
  return u >= 17 ? 48 : f;
}
const p80At = (u) => (u < 19.6 ? 96 : lerp(96, 124, eo((u - 19.6) / 2.2)));

function dispVal(r) {
  let v = VCH[0][1];
  for (const [a, b] of VCH) if (r >= a) v = b;
  return v;
}
function transAt(r) {
  for (let i = 1; i < VCH.length; i++) {
    const [a, b] = VCH[i];
    const d = TRD(a);
    if (r >= a && r < a + d) return {from: VCH[i - 1][1], to: b, k: (r - a) / d};
  }
  return null;
}
// Status je Bild: U Anzeige bewegt > U Rahmen verdeckt > S Stillstand > T Wechsel > V.
function recAt(r) {
  if (r >= EP.bump) return {st: 'u', kind: 'anzeige_bewegt'};
  if (inR(r, EP.hand)) return {st: 'u', kind: 'rahmen_verdeckt'};
  if (r >= EP.stall[0] + 0.5 && r < EP.stall[1]) return {st: 's'};
  const tr = transAt(r);
  if (tr) return {st: 't', text: tr.from, tr};
  return {st: 'v', text: dispVal(r)};
}
const hasFrame = (r) => !inR(r, EP.stall) && !inR(r, EP.conn);
const STATUS_WORD = {v: 'valid', t: 'transition', u: 'unreadable', s: 'stale'};
const REASONS_OF = {u: ['tracking_lost:rahmen_unstimmig'], t: ['anzeige_wechselt'], s: ['no_value'], v: []};

// Mock trackedQuad: waehrend der Hand driftet das Viereck, die Korrektur holt es zurueck.
function trackedQuad(r) {
  let dx = 0, dy = 0;
  if (r >= EP.hand[0] && r < EP.corr[1]) {
    const k = eo((r - EP.hand[0]) / 1.2);
    dx = -6.5 * k; dy = 4.8 * k;
    if (r >= EP.corr[0]) { const c = eio((r - EP.corr[0]) / 1.2); dx *= 1 - c; dy *= 1 - c; }
  }
  // Mock rechnet in Standbild-Pixeln (3/4 der Kamera).
  return QUAD.map(([x, y]) => [round1(x + dx * 4 / 3), round1(y + dy * 4 / 3)]);
}
function regionPeak(i, r) {
  let m = 0.93 + 0.02 * Math.sin(i * 1.7 + r * 0.9);
  if (RIGHT_REGIONS.has(i)) {
    const occ = clamp((r - EP.handIn) / 0.4, 0, 1) * (1 - clamp((r - EP.handOut) / 0.6, 0, 1));
    m = lerp(m, 0.16 + 0.06 * Math.sin(i + r * 3), occ);
  }
  if (r >= EP.bump) m = lerp(m, 0.11 + 0.05 * Math.sin(i * 2 + r * 2), clamp((r - EP.bump) / 0.3, 0, 1));
  return Math.round(m * 100) / 100;
}

function utc(ms) { return new Date(ms).toISOString().replace('.000Z', '+00:00').replace(/\.\d+Z$/, '+00:00'); }
function stamp(ms) { return new Date(ms).toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z'); }

const ok = (data = {ok: true}) => ({ok: true, error: null, data});
const fail = (error) => ({ok: false, error, data: {error}});

import {LOCK_NOTICE, SERIAL_NOTE} from '../run/output.js';

export function createScenario({clock = () => globalThis.performance.now(), wall = () => Date.now(), base = null} = {}) {
  // phase: idle | setup | failed | ready | confirmed | run | stopped
  let phase = 'idle';
  let phaseAt = clock();
  let sessionId = `uebung-${stamp(wall())}`;
  let regions = REGION_CENTRES.map((c) => ({centre: c.slice(), size: REGION_SIZE}));
  let revisionNo = 1;
  let auswahl = 'automatisch';
  let centreResults = [];
  let profile = null;
  let runOpts = null;
  let outputChoice = null;
  let runStartedWall = null;
  let stopR = null;
  let lastMark = null;
  let setupEndElapsed = null;
  // Abbruch: Mock-Uhr der Einrichtung beim Abbruch (bleibt danach stehen).
  let cancelU = null;

  const seconds = () => (clock() - phaseAt) / 1000;
  const enter = (next) => { phase = next; phaseAt = clock(); };
  const revision = () => `uebung-r${revisionNo}`;
  // Mock-Uhr der Einrichtung; nach dem Vorschlag steht sie bei U_READY.
  const setupU = () => (phase === 'setup' ? Math.min(U0 + seconds(), U_READY)
    : phase === 'idle' ? 0 : phase === 'failed' ? cancelU : U_READY);
  const runR = () => (phase === 'run' ? seconds() : phase === 'stopped' ? stopR : 0);
  const nowR = () => (phase === 'run' ? seconds() : phase === 'stopped' ? stopR + seconds() : 0);

  function advance() {
    if (phase === 'setup' && U0 + seconds() >= U_READY) {
      const overshoot = U0 + seconds() - U_READY;
      phase = 'ready';
      phaseAt = clock() - overshoot * 1000;
    }
  }

  function chapter() {
    advance();
    if (phase === 'idle' || phase === 'failed') return CHAPTERS[0];
    if (phase === 'setup') {
      const u = setupU();
      const index = STEP_SPANS.findIndex(([, a, b]) => u >= a && u < b);
      return CHAPTERS[1 + Math.max(0, index)];
    }
    if (phase === 'ready' || phase === 'confirmed') return CHAPTERS[6];
    return phase === 'run' ? CHAPTERS[7] : CHAPTERS[8];
  }

  function checkStates() {
    const nachfuehrung = regions.length ? 'OK' : 'FEHLER';
    return Object.fromEntries(CHECKS.map(([key, , status]) => [key, key === 'nachfuehrung' ? nachfuehrung : status]));
  }

  function setupBlock() {
    const u = setupU();
    const failed = phase === 'failed';
    const ready = !['idle', 'setup', 'failed'].includes(phase);
    const steps = STEP_SPANS.map(([key, a, b]) => {
      let state = u >= b ? 'done' : u >= a ? 'running' : 'pending';
      if (failed && state === 'running') state = 'failed';
      return {key, state, elapsed_s: state === 'done' ? round1(pt(b) - pt(a))
        : state === 'running' || state === 'failed' ? round1(pt(u) - pt(a)) : null};
    });
    const running = steps.find((s) => s.state === 'running' || s.state === 'failed');
    let progressPhase = null;
    let wait = null;
    if (running?.key === 'standbilder') {
      progressPhase = u < 25.4 ? 'mitteln' : u < 26.4 ? 'zelltext' : u < 28.5 ? 'raster' : u < 36.5 ? 'stabilitaet'
        : u < 38.6 ? 'zweites_standbild' : 'gegenlesen';
      if (progressPhase === 'stabilitaet') wait = {elapsed_s: round1(clamp((u - 28.5) * 15 / 8, 0, 15)), total_s: 15};
    }
    const samples = FOCUS_SAMPLES.filter((_, i) => u >= PT0 + i * PDT + 0.9).map((s) => s.slice());
    const checks = checkStates();
    const live = Object.fromEntries(CHECKS.filter(([, done]) => u >= done)
      .map(([key, , , reason]) => [key, {status: checks[key], reason}]));
    const setup = {
      grid: u >= U_GRID ? copy(GRID) : null,
      step: running?.key || (ready ? 'vorschlag' : null),
      elapsed_s: ready || failed ? setupEndElapsed : round1(pt(u) - pt(U0)),
      focus: {method: 'climb', roi: [...FOCUS_ROI], samples, verify: u >= U_VERIFY ? {...FOCUS_VERIFY} : null},
      exposure: {target: 130, band: [115, 150], rounds: u >= U_EXPOSED ? [{level: 124.0, controls: {...CONTROLS}}] : []},
      progress: {steps, attempt: 1, attempts_max: 3, phase: progressPhase, wait},
      checks_live: live,
    };
    if (!ready) return setup;
    const reasons = Object.fromEntries(CHECKS.filter(([, , , reason]) => reason).map(([key, , , reason]) => [key, reason]));
    if (!regions.length) reasons.nachfuehrung = 'zu wenige geeignete Rahmenbereiche';
    const order = {OK: 0, WARNUNG: 1, FEHLER: 2};
    return {...setup, overall: Object.values(checks).reduce((a, b) => (order[b] > order[a] ? b : a), 'OK'),
      checks, check_reasons: reasons, overlays: ['overlay_source', 'overlay_sampling'],
      proposal_revision: revision(), regions: copy(regions), auswahl, centre_results: copy(centreResults)};
  }

  // ---- Lauf: Datensaetze je Bild (15 fps), Zaehler, Zeitleiste ----
  const frameIndex = (r) => Math.floor(r * FPS + 1e-9);
  function recordAt(k) {
    const r = k / FPS;
    const rec = recAt(r);
    return {k, r, ...rec};
  }
  function lastFrame(r) {
    // Letztes Bild bis r (im Stillstand und Verbindungsverlust: das letzte davor).
    let k = frameIndex(r);
    while (k > 0 && !hasFrame(k / FPS)) k--;
    return recordAt(k);
  }
  function countsUntil(r) {
    const counts = {valid: 0, transition: 0, unreadable: 0, stale: 0};
    const last = frameIndex(r);
    for (let k = 0; k <= last; k++) {
      const rec = recAt(k / FPS);
      if (rec.st === 's' || hasFrame(k / FPS)) counts[STATUS_WORD[rec.st]]++;
    }
    return counts;
  }
  function recent(r) {
    const rows = [];
    const startMs = Math.max(0, Math.floor((r - 60) * 4) * 250);
    const endMs = Math.floor(r * 1000);
    const rank = {v: 0, t: 1, u: 2, s: 3};
    for (let t = startMs; t + 250 <= endMs + 250 && t <= endMs; t += 250) {
      let worst = null;
      let value = null;
      for (let k = Math.ceil((t / 1000) * FPS); k / FPS < (t + 250) / 1000 && k / FPS <= r; k++) {
        const rec = recAt(k / FPS);
        if (rec.st !== 's' && !hasFrame(k / FPS)) continue;
        if (!worst || rank[rec.st] > rank[worst]) worst = rec.st;
        if (rec.st === 'v') value = Number(rec.text);
      }
      if (worst) rows.push([t, worst, worst === 'v' ? value : null]);
    }
    return rows;
  }
  function latestRecord(rec) {
    const valid = rec.st === 'v';
    return {frame_sequence: SEQ0 + rec.k, status: STATUS_WORD[rec.st], value: valid ? Number(rec.text) : null, unit: 'mV/V',
      raw_text: rec.text || '', reject_reasons: REASONS_OF[rec.st].slice(), frames_confirmed: valid ? 3 : 0,
      confirmation_span_ns: valid ? 2 * FRAME_NS : null,
      capture_timestamp: {value_ns: CAP0_NS + rec.k * FRAME_NS, base: 'synthetic', semantics: 'unknown', uncertainty_ns: null}};
  }
  function hintAt(r) {
    if (phase !== 'run') return null;
    if (r >= EP.bump) return {kind: 'anzeige_bewegt', since_s: round1(r - EP.bump), shift_px: 14, rotation_deg: 0.8, region_shift_px: 16};
    if (inR(r, EP.hand)) return {kind: 'rahmen_verdeckt', since_s: round1(r - EP.hand[0]), shift_px: null, rotation_deg: null, region_shift_px: null};
    return null;
  }
  function causesAt(r) {
    const from = frameIndex(Math.max(0, r - 10));
    const to = frameIndex(r);
    const tally = new Map();
    let frames = 0;
    for (let k = from; k <= to; k++) {
      if (!hasFrame(k / FPS)) continue;
      frames++;
      const rec = recAt(k / FPS);
      const reason = REASONS_OF[rec.st][0];
      if (reason) tally.set(reason, (tally.get(reason) || 0) + 1);
    }
    const causes = [...tally].sort((a, b) => b[1] - a[1]).map(([reason, count]) => ({reason, count,
      fraction: frames ? Math.round((count / frames) * 1000) / 1000 : 0, cell: null, explanation: CAUSE_EXPLANATION[reason]}));
    return {window_s: 10.0, frames, limited: false, causes};
  }
  function runBlock() {
    const r = runR();
    const counts = countsUntil(r);
    const last = lastFrame(r);
    const frames = Object.values(counts).reduce((a, b) => a + b, 0);
    const hint = hintAt(r);
    const hands = (r >= EP.hand[0] ? 1 : 0) + (r >= EP.bump ? 1 : 0);
    return {
      started_at_utc: utc(runStartedWall), elapsed_s: round1(r), ended_at_utc: stopR === null ? null : utc(runStartedWall + stopR * 1000),
      latest: latestRecord(last),
      summary: {marks: lastMark?.number || 0, by_status: {valid: counts.valid, transition: counts.transition, unreadable: counts.unreadable},
        transition_display_changing: counts.transition, frames_read: frames, tolerance_frames: 0, frames_skipped: 0,
        frame_gaps: 0, frame_gaps_owner_total: 0, audit_errors: 0, tracking_lost: counts.unreadable,
        tracking_coarse_retries: 0, tracking_coarse_accepted: r >= EP.corr[0] ? 1 : 0, tracking_lost_reasons: {},
        tracking_hints: {count: hands, by_kind: {anzeige_bewegt: r >= EP.bump ? 1 : 0, rahmen_verdeckt: r >= EP.hand[0] ? 1 : 0, unbekannt: 0},
          max_shift_px: r >= EP.bump ? 14 : null},
        track_score: {min: r >= EP.hand[0] ? 0.11 : 0.91, median: 0.93, max: 0.95, n: frames},
        camera_error: null, end_reason: stopR === null ? null : 'bediener'},
      counts,
      recent: recent(r),
      recent_now_ms: Math.floor(r * 1000),
      dir: 'run-01',
      latest_age_s: round1(Math.max(0.04, nowR() - last.r)),
      guess: null,
      tracking: {mode: 'frame_local', profile_mode: 'frame_local', version: 1, regions: regions.length},
      tracking_hint: hint,
      rejection_causes: causesAt(r),
    };
  }
  function referenceBlock() {
    if (!runOpts?.reference || (phase !== 'run' && phase !== 'stopped')) {
      return {enabled: false, reason: 'kein Referenzlauf', latest: null, schedule_step: null};
    }
    const r = runR();
    const text = dispVal(r);
    const step = runOpts.norm_schedule
      ? (r < NORM_STEP_R ? {index: 0, factor: 1.0, since_s: round1(nowR())} : {index: 1, factor: 2.0, since_s: round1(nowR() - NORM_STEP_R)})
      : null;
    return {enabled: true, reason: null, lines: Math.floor(r * 10),
      latest: {cell_text: lcdLine(text).slice(0, 9).trimEnd(), raw: `${text[0]}0${text.slice(1)} mV/V`, value: Number(text),
        age_s: round1(Math.min(nowR() - r, 60) + 0.1)},
      schedule_step: step};
  }

  function status() {
    advance();
    const r = nowR();
    const running = phase === 'run';
    if (running && inR(r, EP.conn)) return null;
    const stalled = running && r >= EP.stall[0] + 1 && r < EP.stall[1];
    const u = setupU();
    const runPhase = phase === 'run' || phase === 'stopped';
    const frames = runPhase ? SEQ0 + frameIndex(runR()) : 1 + Math.floor((clock() / 1000) * FPS) % 100000;
    const camera = {running: true, stalled, error: stalled ? `Streamstillstand: kein Bild seit ${(r - EP.stall[0]).toFixed(1)} s` : null,
      frames, gaps: 0, source: {...SOURCE, controls: {...CONTROLS, focus_absolute: phase === 'setup' ? Math.round(focusAt(u)) : 48}},
      last_start: null};
    const state = {idle: 'idle', setup: 'setup_running', failed: 'setup_failed', ready: 'setup_ready', confirmed: 'confirmed',
      run: 'running', stopped: 'stopped'}[phase];
    const result = {
      state, step: null, error: phase === 'failed' ? 'Einrichtung abgebrochen' : null, simulate: true, camera,
      storage: base?.storage ? copy(base.storage) : {free_bytes: 18_400_000_000, reserve_bytes: 2_000_000_000, level: 'ok', message: '18.40 GB frei'},
      system: Number.isFinite(base?.system?.cpu_window_s) ? copy(base.system) : {...SYSTEM},
      release_notice: typeof base?.release_notice === 'string' ? base.release_notice : '',
      session_id: sessionId,
      setup: phase === 'idle' ? null : setupBlock(),
      profile: profile ? {...profile} : null,
      run_block: null, test_run: null, reader_tolerance: null,
      run: runPhase ? runBlock() : null,
      diagnostics: {enabled: Boolean(runOpts?.diagnostics && runPhase), reason: runOpts?.diagnostics ? null : 'kein Diagnoselauf'},
      diagnose_kopie: false, diagnostic_leftovers: [],
      last_mark: lastMark ? {...lastMark} : null,
      reference: referenceBlock(),
      reference_eval: phase === 'stopped' && runOpts?.reference
        ? {state: 'done', misreads: 0, compared_valid: countsUntil(stopR).valid, undecided_valid: 0, uncovered_valid: 0} : null,
      // Der Uebungslauf gibt nie etwas aus: der gewaehlte Weg wird nur im Status
      // nachgestellt (einheitlicher Ausgabestatus), ohne Netz und ohne Schnittstelle.
      output: practiceOutput(),
    };
    return result;
  }

  function practiceOutput() {
    const out = outputChoice;
    if (!out) return {transport: 'off', state: 'off'};
    const serial = out.transport === 'serial';
    const {acknowledge_unaccepted: _ack, transport: _t, ...config} = out;
    return {transport: out.transport, state: phase === 'stopped' ? 'stopped' : serial ? 'serial_ready' : 'waiting',
      config: serial || out.transport === 'tcp' ? config : {port: '/dev/ttyAMA0', baudrate: 115200},
      error: null, release_block: serial ? null : LOCK_NOTICE, last_ack: null, acceptance: 'fehlt',
      ack_scope: 'Übungslauf: simuliert, nichts gesendet', ...(serial ? {release_note: SERIAL_NOTE} : {})};
  }

  // ---- Bild und HUD ----
  function frame() {
    advance();
    const r = nowR();
    const running = phase === 'run';
    if (running && !hasFrame(r)) return null;
    const u = setupU();
    const runPhase = phase === 'run' || phase === 'stopped';
    const blur = phase === 'setup' && u < 17 ? Math.min(Math.abs(focusAt(u) - 48) * 0.36, 4.2) : 0;
    const bright = phase !== 'setup' ? 1 : u < 17 ? 0.86 : u < 22.5 ? lerp(0.8, 1, clamp((p80At(u) - 96) / 28, 0, 1)) : 1;
    let lcd = {text: lcdLine('+0.62427'), from: null, k: 1};
    let hand = 0;
    let bump = 0;
    if (runPhase) {
      const rr = runR();
      const tr = running ? transAt(rr) : null;
      lcd = tr ? {text: lcdLine(tr.to), from: lcdLine(tr.from), k: tr.k} : {text: lcdLine(dispVal(rr)), from: null, k: 1};
      if (running && rr >= EP.handIn && rr < EP.handOut + 0.4) hand = rr < EP.handOut ? eo((rr - EP.handIn) / 0.4) : 1 - eo((rr - EP.handOut) / 0.4);
      if (rr >= EP.bump) bump = eo((rr - EP.bump) / 0.18);
    }
    const bitmapSource = {url: STILL_URL, lcd, hand, bump, blur, bright};
    const seq = runPhase ? SEQ0 + frameIndex(runR()) : 1 + Math.floor((clock() / 1000) * FPS);
    const hud = {seq, cap_ns: CAP0_NS + seq * FRAME_NS, w: 1920, h: 1080, rec: null, track: null, cells: null, proc: null,
      preview: {fps: 15, throttled: null}};
    if (running) {
      const rr = runR();
      const rec = recordAt(frameIndex(rr));
      const lost = rec.st === 'u';
      hud.rec = {seq: SEQ0 + rec.k, status: STATUS_WORD[rec.st], text: rec.text || '', unit: 'mV/V', reasons: REASONS_OF[rec.st].slice(),
        age_s: 0.04};
      hud.track = {quad: rr >= EP.bump ? copy(QUAD) : trackedQuad(rr), score: lost ? (rr >= EP.bump ? 0.11 : 0.43) : 0.93,
        shift_px: 0.4, rotation_deg: 0.0, reason: lost ? 'rahmen_unstimmig' : null, correcting: inR(rr, EP.corr),
        regions: regions.map((reg, i) => {
          const peak = regionPeak(i, rr);
          return {c: reg.centre.slice(), s: reg.size, peak, ok: peak >= 0.5};
        })};
      const text = (rec.st === 't' ? lcdLine(rec.tr.from) : lcdLine(dispVal(rr)));
      hud.cells = [...text].map((best, i) => ({i, best, margin: rec.st === 't' && text[i] !== lcdLine(rec.tr.to)[i] ? -0.12 : 0.41,
        uncertain: rec.st === 't' && text[i] !== lcdLine(rec.tr.to)[i]}));
      hud.proc = {fps: 14.8, latency_ms: 38, skipped_recent: 0.0};
    }
    return {bitmapSource, hud};
  }

  // ---- Bedienschritte ----
  function act(path, body = {}) {
    advance();
    const data = body && typeof body === 'object' ? body : {};
    if (path === '/live/setup') {
      if (phase === 'run') return fail('Lauf zuerst beenden');
      if (phase === 'setup') return fail('Einrichtung laeuft bereits');
      sessionId = `uebung-${stamp(wall())}`;
      regions = REGION_CENTRES.map((c) => ({centre: c.slice(), size: REGION_SIZE}));
      revisionNo = 1;
      auswahl = 'automatisch';
      centreResults = [];
      profile = null;
      runOpts = null;
      outputChoice = null;
      stopR = null;
      lastMark = null;
      cancelU = null;
      setupEndElapsed = round1(pt(U_READY) - pt(U0));
      enter('setup');
      return ok();
    }
    if (path === '/live/setup/cancel') {
      // Wie live/service.py cancel_setup: nur waehrend der Einrichtung.
      if (phase !== 'setup') return fail('Keine Einrichtung laeuft');
      cancelU = setupU();
      setupEndElapsed = round1(pt(cancelU) - pt(U0));
      enter('failed');
      return ok();
    }
    if (path === '/live/setup/regions') {
      if (phase !== 'ready') return fail('Kein aktueller Vorschlag zum Bearbeiten');
      if (data.proposal_revision !== revision()) return fail('Vorschlag hat sich geaendert');
      const add = data.add, remove = data.remove;
      if (!Array.isArray(add) || !Array.isArray(remove) || !(add.length || remove.length)) {
        return fail('Bereichsaenderung braucht Listen add und remove mit mindestens einer Aenderung');
      }
      if (remove.some((i) => !Number.isInteger(i) || i < 0 || i >= regions.length) || new Set(remove).size !== remove.length) {
        return fail('Ungueltiger oder doppelter Bereichsindex');
      }
      for (const p of add) {
        if (!Array.isArray(p) || p.length !== 2 || !p.every((v) => typeof v === 'number' && Number.isFinite(v))) {
          return fail('Bereich braucht zwei endliche Pixelkoordinaten');
        }
        if (!(p[0] >= 0 && p[0] < 1920 && p[1] >= 0 && p[1] < 1080)) return fail('Bereichskoordinaten liegen ausserhalb des Quellbilds');
      }
      const kept = regions.filter((_, i) => !remove.includes(i));
      // Wie proposal_from_regions: erst die behaltenen, dann die neuen Punkte.
      const results = kept.map((reg) => ({requested_centre: reg.centre, centre: reg.centre, used_centre: reg.centre, ok: true, reason: null}));
      for (const p of add) {
        const inside = insideQuad(p);
        results.push({requested_centre: p, centre: p, used_centre: inside ? null : p, ok: !inside, reason: inside ? 'im_zeichenbereich' : null});
        if (!inside) kept.push({centre: p.slice(), size: ADDED_SIZE});
      }
      regions = kept;
      revisionNo++;
      auswahl = 'manuell';
      centreResults = results;
      return ok({proposal_revision: revision(), centre_results: copy(results)});
    }
    if (path === '/live/confirm') {
      if (phase !== 'ready') return fail('Kein Vorschlag zum Bestaetigen');
      // Im Uebungslauf zuerst der Name: er ist die Bedienstelle.
      if (!String(data.confirmed_by ?? '').trim()) return fail('Name des Bestaetigenden fehlt');
      if (data.session_id !== sessionId) return fail('Vorschlag hat sich geaendert — bitte neu pruefen');
      if (data.proposal_revision !== revision()) return fail('Vorschlag hat sich geaendert - Rahmenbereiche bitte neu pruefen');
      if (!data.format_checked) return fail('Einheit mV/V und Format gsv2as_v1 muessen geprueft sein');
      const overall = setupBlock().overall;
      if (overall === 'FEHLER') return fail('Einrichtung meldet FEHLER - nicht bestaetigbar');
      if (overall === 'WARNUNG' && !data.acknowledge_warning) return fail('Einrichtung meldet WARNUNG - ausdruecklich zur Kenntnis nehmen');
      profile = {confirmed_by: String(data.confirmed_by).trim(), confirmed_at_utc: utc(wall()),
        warning_acknowledged: overall === 'WARNUNG', tracking_mode: 'rahmenbereiche'};
      enter('confirmed');
      return ok();
    }
    if (path === '/live/run/start') {
      if (phase === 'run') return fail('Lauf laeuft bereits');
      if (phase !== 'confirmed') return fail('Erst einrichten und bestaetigen');
      if (data.norm_schedule && data.reference === false) return fail('Werteplan braucht Referenzaufzeichnung');
      runOpts = {reference: data.reference !== false, norm_schedule: data.norm_schedule || null, diagnostics: Boolean(data.diagnostics)};
      outputChoice = data.output?.transport && data.output.transport !== 'off' ? data.output : null;
      runStartedWall = wall();
      stopR = null;
      lastMark = null;
      enter('run');
      return ok();
    }
    if (path === '/live/run/mark') {
      if (phase !== 'run') return fail('kein Lauf aktiv');
      const text = data.text;
      if (typeof text !== 'string' || !text.trim() || text.length > 200) return fail('Ereignismarke braucht 1 bis 200 Zeichen');
      lastMark = {text, zeit: 'meldezeit_bediener', number: (lastMark?.number || 0) + 1, received_at_utc: new Date(wall()).toISOString()};
      return ok();
    }
    if (path === '/live/run/stop') {
      if (phase !== 'run') return fail('kein Lauf aktiv');
      stopR = seconds();
      enter('stopped');
      return ok();
    }
    if (path === '/live/camera/start') return ok();
    return fail(`Im Übungslauf nicht vorgesehen: ${path}`);
  }

  return {
    status,
    frame,
    act: async (path, body) => act(path, body),
    get chapter() { return chapter(); },
    // Sekunden seit Laufstart (Tests, Auftraege des Uebungslaufs).
    runSeconds: () => nowR(),
    phase: () => { advance(); return phase; },
  };
}

function insideQuad([x, y]) {
  let inside = false;
  for (let i = 0, j = QUAD.length - 1; i < QUAD.length; j = i++) {
    const [xi, yi] = QUAD[i], [xj, yj] = QUAD[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
