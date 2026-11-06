// Reine Ableitungen fuer die Live-Seite: aus /live/status (und dem X-Hud des
// Vorschaustroms) wird, was die Oberflaeche zeigt. Kein DOM, keine Zeit, kein
// Netz, damit alles unter node --test laeuft. Entscheidungen fallen im Server
// (dispread.live), nie hier.
//
// statusView, connectionView, cameraView, recordView und trackingHintText sind
// inhaltsgleich aus der alten Live-Seite uebernommen (Spec "Technik"); connectionLost
// ist nur die herausgezogene Bedingung von connectionView.

export function cameraView(camera) {
  // Serverzahl "seit 5.3 s" erscheint mit Dezimalkomma wie alle Zahlen der Seite.
  if (camera.stalled) return (camera.error || 'Streamstillstand: kein neues Kamerabild').replace(/(\d)\.(\d)/g, '$1,$2');
  return camera.running ? `Kamera läuft, ${camera.frames} Bilder, ${camera.gaps} Lücken`
    : `Kamera aus: ${camera.error || '—'}`;
}

export function statusView(status, {sinceS = 0} = {}) {
  if (status.reference?.restoring) {
    return {headline: 'Werte werden zurückgestellt …', cls: 'transition', detail: 'Gerät verbunden lassen.'};
  }
  const view = recordView(status, sinceS);
  if (status.reader_tolerance && view.cls === 'valid') {
    view.detail = `erweiterte Toleranz ×${status.reader_tolerance.factor} – nicht validiert · ${view.detail}`;
  }
  if (status.test_run && status.state === 'running') {
    view.headline = `TESTLAUF · ${view.headline}`;
    // Vermutung nur zum aktuellen, verworfenen Bild: nie neben STALE oder VALID.
    const guess = status.run?.guess;
    if (guess && view.cls !== 'stale' && view.cls !== 'valid') {
      view.detail += `\nLeser-Vermutung (verworfen, nicht freigegeben): ${guess.text}` +
        `\nunsichere Zellen: ${guess.uncertain.length ? guess.uncertain.join(', ') : 'keine'}`;
    }
  }
  return view;
}

function recordView(status, sinceS = 0) {
  const run = status.run && status.run.latest;
  if (run) {
    // Ohne HUD laeuft das Alter ab Eingang des Status weiter (Wahrheitsregel 1).
    const age = Number.isFinite(status.run.latest_age_s) ? status.run.latest_age_s + Math.max(0, sinceS) : status.run.latest_age_s;
    const fresh = typeof age === 'number' && Number.isFinite(age) && age <= 0.5;
    const reasons = run.reject_reasons.map((reason) => {
      const key = reason.startsWith('tracking_lost:') ? reason.slice('tracking_lost:'.length) : reason;
      const label = status.tracking_reasons?.[key] || status.run.rejection_causes?.causes
        ?.find((cause) => cause.reason === reason)?.explanation;
      return label ? `${label} (${reason})` : reason;
    }).join(', ');
    if (status.test_run && run.status === 'valid' && fresh && status.state === 'running') {
      return {headline: 'UNREADABLE', cls: 'unreadable', detail: 'Testlauf: keine Wertfreigabe'};
    }
    if (status.state === 'running' && run.status === 'valid' && fresh) {
      return {headline: `${run.raw_text} ${run.unit}`, cls: 'valid', detail: `Bild ${run.frame_sequence}`};
    }
    const cls = !fresh || run.status === 'valid' ? 'stale' : run.status;
    if (run.reject_reasons[0]?.startsWith('tracking_lost:')) {
      return {headline: cls.toUpperCase(), cls,
        detail: (status.state === 'running' && trackingHintText(status.run.tracking_hint)) ||
          `Anzeige verloren — Kamera bewegt? Neu einrichten (${reasons})`};
    }
    if (cls === 'transition' && run.reject_reasons[0] === 'anzeige_wechselt') {
      // Traegt der Grund schon die Erklaerung "Wert wechselt" (live_cause), nicht doppelt klammern.
      return {headline: 'TRANSITION', cls, detail: reasons.startsWith('Wert wechselt') ? reasons : `Wert wechselt (${reasons})`};
    }
    return {headline: cls.toUpperCase(), cls, detail: status.error || reasons};
  }
  if (status.run_block && ['setup_ready', 'confirmed', 'stopped'].includes(status.state)) {
    return {headline: 'Lauf gesperrt', cls: 'error', detail: status.run_block};
  }
  const setup = status.setup || {};
  const elapsed = typeof setup.elapsed_s === 'number' && Number.isFinite(setup.elapsed_s)
    ? ` (${setup.elapsed_s.toFixed(1)} s)` : '';
  const labels = {
    idle: 'Bereit zur Einrichtung', setup_running: `Einrichtung läuft: ${setup.step || ''}${elapsed}`,
    setup_ready: 'Vorschlag prüfen und bestätigen', setup_failed: 'Einrichtung abgebrochen',
    confirmed: 'Bestätigt – Lauf starten', running: 'Lauf startet …', stopped: 'Lauf beendet',
  };
  return {headline: labels[status.state] || status.state, cls: status.error ? 'error' : '', detail: status.error || setup.message || ''};
}

export function trackingHintText(hint) {
  if (hint?.kind === 'anzeige_bewegt' && Number.isFinite(hint.shift_px) && Number.isFinite(hint.rotation_deg)) {
    const shift = Math.round(hint.shift_px).toLocaleString('de-DE');
    const rotation = Math.abs(hint.rotation_deg).toLocaleString('de-DE', {
      minimumFractionDigits: 1, maximumFractionDigits: 1});
    return `Anzeige hat sich bewegt (ca. ${shift} px (Ecken), ${rotation} Grad) – Werte werden nicht freigegeben. Bitte neu einrichten.`;
  }
  if (hint?.kind === 'rahmen_verdeckt') {
    return 'Rahmen verdeckt? Hand oder Gegenstand vom Rahmen nehmen. Werte werden nicht freigegeben.';
  }
  if (hint?.kind === 'unbekannt') {
    return 'Anzeige nicht sicher wiedergefunden. Bitte Sicht auf den Rahmen prüfen und bei Bedarf neu einrichten. Werte werden nicht freigegeben.';
  }
  return '';
}

export function connectionLost(lastOkMs, nowMs, httpStatus) {
  return httpStatus === null || httpStatus < 200 || httpStatus >= 300 ||
    lastOkMs === null || nowMs - lastOkMs > 1500;
}

export function connectionView(status, lastOkMs, nowMs, httpStatus) {
  if (connectionLost(lastOkMs, nowMs, httpStatus)) {
    return {headline: 'STALE', cls: 'stale', detail: httpStatus === 401
      ? 'Anmeldung abgelaufen' : 'Verbindung zur Werkbank verloren'};
  }
  return statusView(status);
}

// ---------------------------------------------------------------------------
// Zustandseffekte (Spec "Zustandseffekte"): genau einer, nach Vorrang
// Verbindung verloren > Streamstillstand > Unlesbar/verloren > Korrektur > Wechselt.
// conn beschreibt die Verbindungen des Clients: {offline} aus dem Statusabruf
// (connectionLost), {frameAgeS} = Sekunden seit dem letzten Bild des
// Vorschaustroms und {hud} = X-Hud dieses Bilds (Geometrie fuer Ecken/Bereiche).
// ---------------------------------------------------------------------------
const NO_EFFECT = Object.freeze({kind: null, corners: [], regions: []});
const ALL_CORNERS = [0, 1, 2, 3];
const effect = (kind, corners = [], regions = []) => ({kind, corners, regions});

function freshLatest(status) {
  const age = status?.run?.latest_age_s;
  return typeof age === 'number' && Number.isFinite(age) && age <= 0.5;
}

function nearestCorners(quad, centres) {
  const corners = new Set();
  for (const [x, y] of centres) {
    let best = 0;
    quad.forEach(([qx, qy], i) => {
      if (Math.hypot(qx - x, qy - y) < Math.hypot(quad[best][0] - x, quad[best][1] - y)) best = i;
    });
    corners.add(best);
  }
  return [...corners].sort((a, b) => a - b);
}

export function effectState(status, conn = {}) {
  if (conn?.offline) return effect('offline');
  const frameAge = conn?.frameAgeS;
  if (status?.camera?.stalled || (typeof frameAge === 'number' && frameAge > 1.5)) return effect('stalled');
  if (status?.state !== 'running') return {...NO_EFFECT};
  const latest = status.run?.latest;
  const fresh = freshLatest(status);
  const hint = status.run?.tracking_hint?.kind || null;
  const lost = fresh && (latest?.reject_reasons || []).some(reason => reason.startsWith('tracking_lost:'));
  // Im Testlauf schreibt der Server nur VALID-Datensaetze auf UNREADABLE um
  // (erster Grund testlauf_keine_freigabe, live/session.py); das ist keine Stoerung.
  // Echt unlesbare Bilder behalten ihre eigenen Gruende und zeigen den Effekt.
  const unreadable = fresh && latest?.status === 'unreadable' &&
    !(latest.reject_reasons || []).includes('testlauf_keine_freigabe');
  const track = conn?.hud?.track || null;
  if (hint || lost || unreadable) {
    const regions = (track?.regions || []).flatMap((region, i) => (region && region.ok === false ? [i] : []));
    const quad = Array.isArray(track?.quad) && track.quad.length === 4 ? track.quad : null;
    let corners = [];
    if (hint === 'anzeige_bewegt' || hint === 'unbekannt') corners = [...ALL_CORNERS];
    else if (regions.length && quad) corners = nearestCorners(quad, regions.map(i => track.regions[i].c));
    else if (hint || lost) corners = [...ALL_CORNERS];
    return effect('error', corners, regions);
  }
  if (track?.correcting) return effect('correcting');
  if (fresh && latest?.status === 'transition') return effect('transition');
  return {...NO_EFFECT};
}

// ---------------------------------------------------------------------------
// Einrichtungs-Fortschritt (Spec "Einrichtungs-Fortschritt und Fokuskurve").
// Schluessel kommen aus status.setup.progress.steps (live/service.py
// SETUP_STEPS), Phasen aus live/setup.py (on_phase-Reihenfolge).
// ---------------------------------------------------------------------------
const STEP_LABELS = {fokus: 'Fokus', kamera: 'Kamera', belichtung: 'Belichtung',
  standbilder: 'Standbilder', vorschlag: 'Vorschlag'};
const PHASES = [['mitteln', 'Mitteln'], ['zelltext', 'Zellentext'], ['raster', 'Raster'],
  ['stabilitaet', 'Stabilität'], ['zweites_standbild', 'Zweites Standbild'], ['gegenlesen', 'Gegenlesen']];
// Spiegel von live/setup.py EXPOSURE_MAX_ROUNDS; der Status traegt die Obergrenze nicht.
export const EXPOSURE_MAX_ROUNDS = 4;
const CONFIRMED_STATES = ['confirmed', 'running', 'stopped'];

const finite = value => typeof value === 'number' && Number.isFinite(value);
const round = value => Math.round(value);
const phaseLabel = key => PHASES.find(([k]) => k === key)?.[1] || key;

function waitText(wait) {
  if (!finite(wait?.elapsed_s) || !finite(wait?.total_s)) return '';
  return `${Math.floor(wait.elapsed_s)}/${round(wait.total_s)} s`;
}

function focusParts(setup, state) {
  const focus = setup.focus || {};
  const samples = Array.isArray(focus.samples) ? focus.samples : [];
  const best = samples.reduce((top, sample) => (!top || sample[1] > top[1] ? sample : top), null);
  const verify = focus.verify || null;
  let detail = '';
  if (state === 'done') detail = best ? `Bestwert ${best[0]} · Schärfe ${round(best[1])}` : '';
  else if (state === 'running') detail = samples.length
    ? `Schärfe an ${samples.length} Stellen gemessen${focus.method === 'sweep' ? ' · Vollsuche' : ''}`
    : 'Fokus wird gesucht …';
  else if (state === 'failed') detail = samples.length ? `Abgebrochen nach ${samples.length} Proben` : 'Abgebrochen';
  if (!['running', 'failed'].includes(state) || !samples.length) return {detail, sub: []};
  const passed = verify && finite(verify.score) && finite(verify.threshold) && verify.score >= verify.threshold;
  const verifyValue = verify && finite(verify.score) && finite(verify.threshold)
    ? `${round(verify.score)} ${passed ? '≥' : '<'} ${round(verify.threshold)}` +
      (best && best[1] > 0 ? ` (${round(100 * verify.score / best[1])} %)` : '') : '';
  return {detail, sub: [
    {key: 'proben', label: `Probe ${samples.length}`, state: verify ? 'done' : state,
      value: `focus_absolute ${samples.at(-1)[0]}`},
    {key: 'gegenpruefung', label: 'Gegenprüfung ≥ 85 %',
      state: verify ? (passed ? 'done' : 'failed') : 'pending', value: verifyValue},
  ]};
}

function exposureDetail(setup, state) {
  const exposure = setup.exposure || {};
  const rounds = Array.isArray(exposure.rounds) ? exposure.rounds : [];
  const band = Array.isArray(exposure.band) ? exposure.band : null;
  const level = finite(rounds.at(-1)?.level) ? rounds.at(-1).level : null;
  const target = exposure.target;
  if (state === 'running') {
    const current = Math.min(rounds.length + 1, EXPOSURE_MAX_ROUNDS);
    return `${level === null ? `Ziel p80 ${target}` : `p80 ${round(level)} → Ziel ${target}`} · Runde ${current}/${EXPOSURE_MAX_ROUNDS}`;
  }
  if (state === 'done' && level !== null && band) {
    const inside = level >= band[0] && level <= band[1];
    return `p80 ${round(level)} ${inside ? 'im Band' : 'außerhalb'} ${band[0]}–${band[1]} · Runde ${rounds.length}/${EXPOSURE_MAX_ROUNDS}`;
  }
  if (state === 'failed') return 'Abgebrochen';
  return '';
}

function stillParts(progress, state) {
  const attempt = finite(progress?.attempt) && finite(progress?.attempts_max)
    ? `Versuch ${progress.attempt}/${progress.attempts_max}` : '';
  const phase = progress?.phase || null;
  const wait = phase === 'stabilitaet' ? progress?.wait : null;
  let detail = '';
  if (state === 'done') detail = ['Zwei Standbilder', attempt].filter(Boolean).join(' · ');
  else if (state === 'running') {
    const remaining = finite(wait?.elapsed_s) && finite(wait?.total_s)
      ? `, noch ${Math.max(0, Math.ceil(wait.total_s - wait.elapsed_s))} s` : '';
    detail = [attempt, phase ? `${phaseLabel(phase)}${remaining}` : ''].filter(Boolean).join(' · ');
  } else if (state === 'failed') {
    detail = [phase ? `Abgebrochen bei ${phaseLabel(phase)}` : 'Abgebrochen', attempt].filter(Boolean).join(' · ');
  }
  if (!['running', 'failed'].includes(state)) return {detail, sub: []};
  const current = PHASES.findIndex(([key]) => key === phase);
  const sub = PHASES.map(([key, label], i) => ({key, label,
    state: current < 0 || i > current ? 'pending' : i < current ? 'done' : state,
    value: key === 'stabilitaet' && i === current ? waitText(wait) : ''}));
  // Nur die Ruhezeit hat einen gemessenen Anteil; andere Phasen haben keine Dauer im Status.
  const fraction = state === 'running' && finite(wait?.elapsed_s) && finite(wait?.total_s) && wait.total_s > 0
    ? Math.min(1, Math.max(0, wait.elapsed_s / wait.total_s)) : null;
  return {detail, sub, progress: fraction};
}

function proposalParts(setup, state) {
  const overall = setup.overall || null;
  if (state === 'running') return {detail: 'Vorschlag wird erstellt …', tone: null};
  if (state === 'failed') return {detail: 'Abgebrochen', tone: 'err'};
  if (state !== 'done') return {detail: '', tone: null};
  return {detail: overall ? `Gesamturteil ${overall}` : 'Vorschlag liegt vor',
    tone: overall === 'WARNUNG' ? 'warn' : overall === 'FEHLER' ? 'err' : null};
}

export function stepRows(status) {
  const setup = status?.setup || {};
  const progress = setup.progress || null;
  const failed = status?.state === 'setup_failed';
  let steps = Array.isArray(progress?.steps) && progress.steps.length
    ? progress.steps.map(({key, state, elapsed_s}) => ({key, state, elapsed_s: finite(elapsed_s) ? elapsed_s : null}))
    : Object.keys(STEP_LABELS).map(key => ({key, state: 'pending', elapsed_s: null}));
  if (!progress && status?.state === 'setup_running') {
    steps = steps.map(step => (step.key === setup.step ? {...step, state: 'running'} : step));
  }
  if (failed) {
    // Nach dem Abbruch laeuft nichts mehr. Faellt die Einrichtung vor dem
    // ersten Schritt ("start"), markiert der Server keinen Schritt: dann
    // zeigt der erste nicht erledigte Schritt den Abbruch.
    steps = steps.map(step => (step.state === 'running' ? {...step, state: 'failed'} : step));
    if (!steps.some(step => step.state === 'failed')) {
      const first = steps.findIndex(step => step.state !== 'done');
      if (first >= 0) steps[first] = {...steps[first], state: 'failed'};
    }
  }
  const rows = steps.map(({key, state, elapsed_s}) => {
    const row = {key, label: STEP_LABELS[key] || key, state, elapsed_s, detail: '', sub: [], tone: state === 'failed' ? 'err' : null,
      progress: null};
    if (key === 'fokus') Object.assign(row, focusParts(setup, state));
    else if (key === 'kamera') row.detail = state === 'done' ? 'Neustart mit festen Reglern'
      : state === 'running' ? 'Neustart mit festen Reglern …' : state === 'failed' ? 'Abgebrochen' : '';
    else if (key === 'belichtung') row.detail = exposureDetail(setup, state);
    else if (key === 'standbilder') Object.assign(row, stillParts(progress, state));
    else if (key === 'vorschlag') Object.assign(row, proposalParts(setup, state));
    else if (state === 'failed') row.detail = 'Abgebrochen';
    return row;
  });
  const confirmedBy = status?.profile?.confirmed_by;
  const review = status?.state === 'setup_ready' ? 'running'
    : CONFIRMED_STATES.includes(status?.state) ? 'done' : 'pending';
  rows.push({key: 'bestaetigen', label: 'Prüfen & Bestätigen', state: review, elapsed_s: null,
    detail: review === 'running' ? 'Vorschlag prüfen, mit Namen bestätigen'
      : review === 'done' ? (confirmedBy ? `Bestätigt von ${confirmedBy}` : 'Bestätigt') : '',
    sub: [], tone: null, progress: null});
  return rows;
}
