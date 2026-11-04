// Zustandseffekte des Viewers (Spec "Zustandseffekte", Mock-Kapitel 8a–8e).
// Eigene Canvas-Ebene ueber dem Bild; sie zeigt, WO das Problem ist.
// Es laeuft immer nur der Effekt mit dem hoechsten Vorrang
// (effectState in model.js: offline > stalled > error > correcting > transition).
//
// createEffects(canvas, {reducedMotion}) ist die reine Zeichenebene (in node
// mit Attrappe testbar):
//   set(effectState, geometry)  Zustand und Geometrie dieses Bilds
//   frame(dtMs)                 Teilchen fortschreiben und zeichnen
//   stats()                     {particles, lastDrawMs, kind, corners, fps, ...}
// geometry = {quad, regions (Mitten, Bildkoordinaten), imageToScreen, scale,
// width, height, dpr, live}. Teilchen leben in Bildkoordinaten und werden je
// Bild ueber imageToScreen abgebildet: Zoom und Verschieben ziehen mit.
//
// mountEffects(stage, viewer) baut die DOM-Seite: Effekt-Canvas, Innenleuchten
// (CSS, GPU), Stillstandsfeld, Kamera-Neustart-Hinweis und das Band
// "Verbindung zur Werkbank verloren".
//
// Die Teilchenlogik (Rauschfeld, Emitter, Sprite) stammt aus dem Mock
// (mock.src.html, "particles"), die Werte ebenso.
import {effectState, stepRows} from '../model.js';

const RED = 'rgba(255,98,80,1)';
const TEAL = '#30c6b7';
const TEAL_HI = '#5fe3d4';
const WARN = '#e5a535';
export const MAX_PARTICLES = 560;
// Vorrang wie effectState (model.js), hoechster zuerst.
export const PRIORITY = ['offline', 'stalled', 'error', 'correcting', 'transition'];
// Unter 20 fps Client-Bildrate halbiert sich die Teilchenzahl (Spec).
const LOW_FPS = 20;
const CORRECTION_S = 1.6;
const PULSE_S = 0.5;
const PULSE_EVERY_S = 1.2;
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const lerp = (a, b, k) => a + (b - a) * k;
const easeOut = (k) => 1 - Math.pow(1 - clamp(k, 0, 1), 3);
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const validQuad = (q) => Array.isArray(q) && q.length === 4 && q.every((p) => Array.isArray(p) && finite(p[0]) && finite(p[1]));

// Rauschfeld der Drift (Mock "flow"): Winkel je Ort und Zeit.
function flow(x, y, t) {
  return Math.sin(x * 0.011 + t * 0.37) * 1.9 + Math.cos(y * 0.014 - t * 0.29) * 1.7 + Math.sin((x + y) * 0.006 + t * 0.21) * 1.3;
}

function mulberry(a) {
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// Punkt auf dem Umfang des Vierecks, s in [0, 1).
function perimeter(q, s) {
  s = ((s % 1) + 1) % 1;
  const lengths = q.map((a, i) => Math.hypot(q[(i + 1) % 4][0] - a[0], q[(i + 1) % 4][1] - a[1]));
  let d = s * lengths.reduce((x, y) => x + y, 0);
  for (let i = 0; i < 4; i++) {
    if (d <= lengths[i]) {
      const a = q[i], b = q[(i + 1) % 4], k = lengths[i] ? d / lengths[i] : 0;
      return [lerp(a[0], b[0], k), lerp(a[1], b[1], k)];
    }
    d -= lengths[i];
  }
  return q[0];
}

// Weicher roter Punkt in genau der gezeichneten Groesse: ungeskaliertes
// drawImage auf ganzen Pixeln ist der billigste Weg (4-ms-Budget).
function defaultSprite(size) {
  const doc = globalThis.document;
  if (!doc?.createElement) return null;
  const c = doc.createElement('canvas');
  c.width = c.height = size;
  const x = c.getContext('2d');
  const r = size / 2;
  const g = x.createRadialGradient(r, r, 0, r, r, r);
  g.addColorStop(0, RED);
  g.addColorStop(0.35, 'rgba(255,98,80,0.45)');
  g.addColorStop(1, 'rgba(255,98,80,0)');
  x.fillStyle = g;
  x.fillRect(0, 0, size, size);
  return c;
}

export function createEffects(canvas, {reducedMotion = false, random = Math.random, sprite = defaultSprite} = {}) {
  const ctx = canvas.getContext('2d');
  const parts = [];
  const sprites = new Map();
  const spriteOf = (size) => {
    if (!sprites.has(size)) sprites.set(size, sprite?.(size) || null);
    return sprites.get(size);
  };
  let state = {kind: null, corners: [], regions: []};
  let geo = null;
  let t = 0;
  let fps = 60;
  let lastDrawMs = 0;
  let streaks = 0;
  let correction = null; // {from, to, t0}
  let lastQuad = null;
  let pulseT0 = null;
  let dirty = false;

  const nowMs = () => globalThis.performance?.now?.() ?? Date.now();
  const budget = () => (fps < LOW_FPS ? 0.5 : 1);
  const maxParticles = () => Math.round(MAX_PARTICLES * budget());

  // Gezeichnete Art: der gesetzte Zustand, ausser eine noch auslaufende Korrektur
  // hat Vorrang (sie schlaegt Wechselt und das Ende des Ausloesebilds).
  const latched = () => Boolean(correction && t - correction.t0 < CORRECTION_S);
  function kind() {
    if (latched() && (!state.kind || PRIORITY.indexOf(state.kind) > PRIORITY.indexOf('correcting'))) return 'correcting';
    return state.kind;
  }

  function set(next, geometry) {
    const k = next?.kind ?? null;
    geo = geometry || null;
    const quad = validQuad(geo?.quad) ? geo.quad : null;
    if (k === 'correcting') {
      if (!correction || t - correction.t0 >= CORRECTION_S) correction = {from: lastQuad || quad, to: quad, t0: t};
      else if (quad) correction.to = quad;
    } else if (k && PRIORITY.indexOf(k) < PRIORITY.indexOf('correcting')) {
      // Ein Zustand mit hoeherem Vorrang verdraengt eine auslaufende Korrektur.
      correction = null;
    }
    if (k !== 'correcting' && quad) lastQuad = quad;
    if (k === 'transition' && state.kind !== 'transition') pulseT0 = t;
    if (k !== 'transition') pulseT0 = null;
    // Nur ein Effekt: wechselt der Zustand auf einen anderen, ist die Wolke weg.
    // Faellt er weg (Erholung), laeuft die Wolke aus.
    if (k && k !== 'error' && parts.length) parts.length = 0;
    state = {kind: k, corners: next?.corners || [], regions: next?.regions || []};
  }

  // Emitter des Fehlerorts (Mock "emitters"): betroffene Ecken und Bereiche
  // stark, die uebrigen Ecken schwach, dazu die passenden Viewer-Ecken.
  function emitters() {
    if (kind() !== 'error' || !geo?.live) return [];
    const quad = validQuad(geo.quad) ? geo.quad : null;
    const out = [];
    const hot = new Set(state.corners);
    if (quad) {
      quad.forEach(([x, y], i) => {
        if (hot.has(i)) out.push({img: true, x, y, rad: 34, rate: 90});
        else out.push({img: true, x, y, rad: 18, rate: 8});
      });
    }
    for (const i of state.regions) {
      const c = geo.regions?.[i];
      if (Array.isArray(c) && finite(c[0]) && finite(c[1])) out.push({img: true, x: c[0], y: c[1], rad: 30, rate: 40});
    }
    const W = geo.width || 0, H = geo.height || 0;
    const viewCorners = [[0, 0], [W, 0], [W, H], [0, H]];
    for (const i of hot) out.push({img: false, x: viewCorners[i][0], y: viewCorners[i][1], rad: 90, rate: 16});
    return out;
  }

  function step(dt) {
    const k = budget();
    const cap = maxParticles();
    for (const e of emitters()) {
      let n = Math.floor(e.rate * k * dt + random());
      while (n-- > 0 && parts.length < cap) {
        const a = random() * 6.283, d = Math.sqrt(random()) * e.rad;
        parts.push({img: e.img, x: e.x + Math.cos(a) * d, y: e.y + Math.sin(a) * d, ax: e.x, ay: e.y,
          vx: 0, vy: 0, age: 0, life: 1.6 + random() * 2.4, sz: 0.6 + random() * random() * 1.8, haze: random() < 0.14});
      }
    }
    // Faellt die Rate, schrumpft die Wolke sofort auf das halbe Budget.
    if (parts.length > cap) parts.splice(0, parts.length - cap);
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      p.age += dt;
      if (p.age > p.life) { parts.splice(i, 1); continue; }
      const a = flow(p.x, p.y, t);
      const F = p.img ? 30 : 40;
      p.vx += Math.cos(a) * F * dt + (p.ax - p.x) * 0.55 * dt;
      p.vy += Math.sin(a) * F * dt + (p.ay - p.y) * 0.55 * dt;
      p.vx *= 0.965; p.vy *= 0.965;
      p.x += p.vx * dt; p.y += p.vy * dt;
    }
  }

  function drawParticles(toS, zs) {
    for (const p of parts) {
      const life = Math.sin(Math.PI * p.age / p.life);
      const [x, y] = p.img ? toS([p.x, p.y]) : [p.x, p.y];
      // Durchmesser wie im Mock (Dunst 2·14·zs bzw. 68 px, Punkt 3,2·sz), ganzzahlig.
      const d = Math.max(2, Math.round(p.haze ? (p.img ? 28 * zs : 68) : p.sz * (p.img ? 1.5 * zs : 2.2) * 3.2));
      ctx.globalAlpha = (p.haze ? 0.07 : p.img ? 0.62 : 0.32) * life;
      const spr = spriteOf(d);
      if (spr) ctx.drawImage(spr, Math.round(x - d / 2), Math.round(y - d / 2));
      else { ctx.fillStyle = RED; ctx.fillRect(x - d / 4, y - d / 4, d / 2, d / 2); }
    }
    ctx.globalAlpha = 1;
  }

  // Reduzierte Bewegung: statische Punktwolke und markierte Ecken.
  function drawStatic(toS, scale) {
    const rnd = mulberry(7);
    ctx.fillStyle = '#ff6250';
    for (const e of emitters()) {
      if (!e.img) continue;
      const [x, y] = toS([e.x, e.y]);
      const rad = e.rad * scale;
      for (let i = 0; i < 40; i++) {
        const a = rnd() * 6.283, d = Math.sqrt(rnd()) * rad;
        ctx.globalAlpha = 0.18 + 0.3 * rnd();
        ctx.fillRect(x + Math.cos(a) * d, y + Math.sin(a) * d, 2, 2);
      }
    }
    ctx.globalAlpha = 1;
    const quad = validQuad(geo.quad) ? geo.quad : null;
    if (!quad) return;
    ctx.strokeStyle = '#ee5b4d';
    ctx.lineWidth = 1.5;
    for (const i of state.corners) {
      const [x, y] = toS(quad[i]);
      ctx.beginPath();
      ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function poly(toS, q) {
    ctx.beginPath();
    q.forEach((p, i) => { const [x, y] = toS(p); if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); });
    ctx.closePath();
  }

  // Korrektur (Mock "drawCorrection"): Geisterbild des alten Vierecks blendet
  // aus, Teal-Striche fliessen entlang der Kanten vom alten zum neuen Viereck.
  function drawCorrection(toS) {
    streaks = 0;
    const c = correction;
    const to = validQuad(c?.to) ? c.to : null;
    if (!to) return;
    const from = validQuad(c.from) ? c.from : to;
    const p = clamp((t - c.t0) / CORRECTION_S, 0, 1);
    const ghost = 1 - easeOut(p);
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.strokeStyle = TEAL;
    ctx.globalAlpha = 0.75 * ghost;
    poly(toS, from);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = TEAL;
    poly(toS, to);
    ctx.stroke();
    if (reducedMotion) return;
    const n = Math.round(120 * budget());
    ctx.lineCap = 'round';
    ctx.lineWidth = 1.6;
    ctx.strokeStyle = TEAL_HI;
    for (let i = 0; i < n; i++) {
      const s0 = i / n;
      const age = (p * 2.4 + ((i * 0.6180339) % 1)) % 1;
      const at = (a) => {
        const k = easeOut(clamp(p * 1.3 + a * 0.3, 0, 1));
        const s = s0 + a * 0.08;
        const A = perimeter(from, s), B = perimeter(to, s);
        return toS([lerp(A[0], B[0], k), lerp(A[1], B[1], k)]);
      };
      const [x, y] = at(age), [x0, y0] = at(Math.max(0, age - 0.09));
      ctx.globalAlpha = 0.85 * Math.sin(Math.PI * age) * (1 - p * 0.5);
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x, y);
      ctx.stroke();
      streaks++;
    }
    ctx.globalAlpha = 1;
  }

  // Wechsel: kurzer Puls am Viereck-Rand, kein Leuchten am Rahmen.
  function drawPulse(toS) {
    const quad = validQuad(geo.quad) ? geo.quad : null;
    if (!quad || reducedMotion || pulseT0 === null) return;
    const phase = ((t - pulseT0) % PULSE_EVERY_S) / PULSE_S;
    if (phase > 1) return;
    const a = Math.sin(Math.PI * phase);
    ctx.strokeStyle = WARN;
    ctx.globalAlpha = 0.35 * a;
    ctx.lineWidth = 7;
    poly(toS, quad);
    ctx.stroke();
    ctx.globalAlpha = 0.9 * a;
    ctx.lineWidth = 1.5 + 1.5 * a;
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function draw() {
    const start = nowMs();
    const dpr = geo?.dpr || 1;
    const W = geo?.width ?? canvas.clientWidth ?? 0, H = geo?.height ?? canvas.clientHeight ?? 0;
    const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
    if (canvas.width !== bw) canvas.width = bw;
    if (canvas.height !== bh) canvas.height = bh;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    streaks = 0;
    const k = kind();
    const toS = geo?.imageToScreen;
    if (toS && geo.live) {
      const scale = geo.scale || 1;
      if (k === 'error' && reducedMotion) drawStatic(toS, scale);
      else if (parts.length) drawParticles(toS, clamp(scale, 0.7, 3));
      if (k === 'correcting') drawCorrection(toS);
      if (k === 'transition') drawPulse(toS);
    }
    dirty = Boolean(k || parts.length);
    lastDrawMs = nowMs() - start;
  }

  return {
    set,
    frame(dtMs) {
      const dt = Math.min(0.1, Math.max(0, dtMs) / 1000);
      if (dtMs > 0) fps = fps * 0.85 + (1000 / dtMs) * 0.15;
      t += dt;
      if (!reducedMotion) step(dt);
      if (kind() || parts.length || dirty) draw();
    },
    // Laeuft noch etwas (Zustand, auslaufende Wolke oder Korrektur)?
    busy: () => Boolean(kind() || parts.length || dirty),
    stats: () => ({particles: parts.length, lastDrawMs, kind: kind(), corners: [...state.corners],
      regions: [...state.regions], fps, maxParticles: maxParticles(), streaks,
      // Versatz altes -> neues Viereck der laufenden Korrektur (Bildpixel, Ecke oben links).
      correctionPx: kind() === 'correcting' && validQuad(correction?.from) && validQuad(correction?.to)
        ? Math.hypot(correction.from[0][0] - correction.to[0][0], correction.from[0][1] - correction.to[0][1]) : null}),
  };
}

// ---------------------------------------------------------------------------
// DOM-Seite
// ---------------------------------------------------------------------------
const dec = (x, digits) => x.toFixed(digits).replace('.', ',');
const STALE_BLUR_MAX = 5;

// Stillstand (Mock camState): zunehmend unscharf, entsaettigt, etwas dunkler.
export function staleFilter(ageS, {reducedMotion = false, dpr = 1} = {}) {
  const a = reducedMotion ? 10 : Math.max(0, ageS);
  const blur = Math.min(a * 1.1, STALE_BLUR_MAX) * dpr;
  const sat = Math.max(0.12, 1 - a / 3.2);
  const bright = 1 - Math.min(a * 0.06, 0.25);
  return `blur(${blur.toFixed(2)}px) saturate(${sat.toFixed(2)}) brightness(${bright.toFixed(3)})`;
}

export function mountEffects(stage, viewer, {reducedMotion} = {}) {
  const doc = stage.ownerDocument;
  const win = doc.defaultView || globalThis;
  const reduce = reducedMotion ?? Boolean(win.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  const canvas = doc.createElement('canvas');
  canvas.className = 'vfx';
  canvas.setAttribute('aria-hidden', 'true');
  const glow = doc.createElement('div');
  glow.className = 'vglow';
  glow.setAttribute('aria-hidden', 'true');
  const stale = doc.createElement('div');
  stale.className = 'stalep';
  stale.setAttribute('role', 'status');
  stale.hidden = true;
  const restart = doc.createElement('div');
  restart.className = 'vmsg';
  restart.textContent = 'Kamera wird mit festen Reglern neu gestartet';
  restart.hidden = true;
  const base = stage.querySelector('.vcanvas');
  base.after(canvas, glow, stale, restart);
  const band = doc.createElement('div');
  band.className = 'netband';
  band.setAttribute('role', 'alert');
  band.hidden = true;
  band.innerHTML = '<svg class="i" aria-hidden="true" viewBox="0 0 16 16"><path d="M2 6.5a9 9 0 0 1 12 0M4.2 9a5.6 5.6 0 0 1 7.6 0M6.5 11.5a2.2 2.2 0 0 1 3 0"/><path d="M2.5 2.5l11 11"/></svg>' +
    '<b>Verbindung zur Werkbank verloren – Werte veraltet</b><span data-part="why"></span><span class="num" data-part="age"></span>';
  doc.body.append(band);

  const fx = createEffects(canvas, {reducedMotion: reduce});
  canvas.effects = fx;
  let status = null;
  let conn = null;
  let current = {kind: null, corners: [], regions: []};
  let raf = null;
  let last = null;
  let lastText = 0;
  let filter = 'none';
  let darkTimer = null;

  const geometry = () => {
    const vs = viewer.viewState();
    const track = viewer.hud()?.track;
    // Ansicht einmal je Bild auslesen: die Abbildung ist Massstab plus Versatz.
    // (viewState().imageToScreen liest je Aufruf die Canvas-Groesse, zu teuer je Teilchen.)
    const [ox, oy] = vs.imageToScreen([0, 0]);
    const s = vs.scale;
    return {quad: track?.quad || null, regions: (track?.regions || []).map((r) => r?.c), live: vs.source === 'live',
      imageToScreen: ([x, y]) => [ox + x * s, oy + y * s], scale: s, width: vs.width, height: vs.height, dpr: vs.dpr};
  };

  // Kamera-Neustart der Einrichtung: der kurze Bildausfall ist erwartet.
  const cameraRestart = () => status?.state === 'setup_running' &&
    stepRows(status).some((row) => row.key === 'kamera' && row.state === 'running');

  // Alter des eingefrorenen Bilds: der frueheste Hinweis auf das letzte neue Bild,
  // aus dem letzten Bild dieses Clients und dem Alter des letzten Datensatzes
  // (nach dem Neuladen kam hier vielleicht nur noch das alte Bild an).
  let stallSince = null;
  function noteStall() {
    const t = win.performance.now();
    const recAge = status?.state === 'running' ? status.run?.latest_age_s : null;
    const candidates = [t - viewer.frameAgeS() * 1000];
    if (finite(recAge)) candidates.push(t - recAge * 1000);
    stallSince = Math.min(stallSince ?? Infinity, ...candidates);
  }
  const staleAge = () => (stallSince === null ? viewer.frameAgeS() : (win.performance.now() - stallSince) / 1000);

  function setFilter(next) {
    if (next === filter) return;
    filter = next;
    viewer.setImageFilter(next);
  }

  function texts(force = false) {
    const t = win.performance.now();
    if (!force && t - lastText < 100) return;
    lastText = t;
    if (current.kind === 'stalled' && !stale.hidden) {
      const age = staleAge();
      const html = '<div class="h"><span class="sq stale"></span>Streamstillstand: kein neues Kamerabild</div>' +
        `<div class="big">Kein neues Kamerabild seit <span class="num">${dec(age, 1)}</span> s</div>` +
        (status?.state === 'running'
          ? '<p>Werte werden als <b>Veraltet</b> geführt, nicht freigegeben. USB-Kabel und Kamera prüfen.</p>' : '');
      if (stale._html !== html) { stale._html = html; stale.innerHTML = html; }
      // Unschaerfe in Stufen von 0,25 s: das Bild wird nur dann neu gezeichnet.
      setFilter(staleFilter(Math.floor(age * 4) / 4, {reducedMotion: reduce, dpr: viewer.viewState().dpr}));
    }
    if (current.kind === 'offline') {
      const age = finite(conn?.lastOkMs) ? (t - conn.lastOkMs) / 1000 : null;
      const text = age === null ? '' : `seit ${dec(age, 1)} s`;
      const el = band.querySelector('[data-part="age"]');
      if (el.textContent !== text) el.textContent = text;
    }
  }

  function apply() {
    const restarting = cameraRestart();
    let next = status ? effectState(status, {offline: Boolean(conn?.offline), frameAgeS: viewer.frameAgeS(), hud: viewer.hud()})
      : {kind: conn?.offline ? 'offline' : null, corners: [], regions: []};
    if (restarting && next.kind === 'stalled') next = {kind: null, corners: [], regions: []};
    const changed = next.kind !== current.kind;
    current = next;
    if (next.kind === 'stalled') noteStall(); else stallSince = null;
    stage.classList.toggle('fx-err', next.kind === 'error');
    stage.classList.toggle('fx-stalled', next.kind === 'stalled');
    // Kamera neu gestartet: Bild 0,6 s dunkel, Hinweis solange der Schritt laeuft.
    if (restarting && restart.hidden) {
      stage.classList.add('fx-dark');
      win.clearTimeout(darkTimer);
      darkTimer = win.setTimeout(() => stage.classList.remove('fx-dark'), 600);
    }
    restart.hidden = !restarting;
    stale.hidden = next.kind !== 'stalled';
    if (next.kind !== 'stalled') setFilter('none');
    band.hidden = next.kind !== 'offline';
    const why = band.querySelector('[data-part="why"]');
    const whyText = conn?.httpStatus === 401 ? 'Anmeldung abgelaufen' : 'Anzeige eingefroren, neuer Versuch läuft';
    if (why.textContent !== whyText) why.textContent = whyText;
    if (changed) texts(true);
    fx.set(current, geometry());
    start();
  }

  function loop(ts) {
    raf = null;
    const dt = last === null ? 16.7 : ts - last;
    last = ts;
    fx.set(current, geometry());
    fx.frame(dt);
    texts();
    if (fx.busy() || current.kind) raf = win.requestAnimationFrame(loop);
    else last = null;
  }

  function start() {
    if (raf !== null || doc.hidden) return;
    if (!fx.busy() && !current.kind) return;
    raf = win.requestAnimationFrame(loop);
  }

  doc.addEventListener('visibilitychange', () => {
    if (doc.hidden && raf !== null) { win.cancelAnimationFrame(raf); raf = null; last = null; } else start();
  });

  return {
    canvas,
    effects: fx,
    update(nextStatus, nextConn) {
      if (nextStatus !== undefined) status = nextStatus;
      if (nextConn !== undefined) conn = nextConn;
      apply();
    },
    // Neues Bild: HUD (Korrektur, Bereiche) und Bildalter neu bewerten.
    refresh: apply,
    kind: () => current.kind,
  };
}
