/* Codebase-Bühne: eine Glaskarte über einer Punktwolke (ein Punkt je 30 Zeilen),
 * sieben Kapitel, Kapitelleiste rechts (schmal: Pillenzeile oben), Zeitschiene unten.
 * Daten: ../data/codebase.json (erzeugt von scripts/codebase-facts.py).
 * Einbettung: ?embed=1, ?theme=dark|light, Nachrichten {type:"codebase:theme"|"codebase:chapter"}
 * nur von location.origin. */
(function () {
  "use strict";
  const root = document.documentElement;
  const EMBED = root.dataset.embed === "1";
  const $ = (id) => document.getElementById(id);
  const WIKI = "../../docs/uebersicht/codebase.html";
  const mqReduce = matchMedia("(prefers-reduced-motion: reduce)");
  let reduce = mqReduce.matches;
  K.reduce = reduce;

  function fail(title, html) {
    $("msgH").textContent = title;
    $("msgP").innerHTML = html;
    $("msg").hidden = false;
    ["card", "host", "bar", "rail", "pv", "nx", "gl", "chips"].forEach((id) => { const e = $(id); if (e) e.style.display = "none"; });
  }
  const wikiLink = `<a href="${WIKI}">Codebase im Überblick</a>`;

  fetch("../data/codebase.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((data) => {
      const need = ["meta", "cats", "snapshots", "perday", "commits", "files"];
      const miss = need.filter((k) => !data || !data[k] || (Array.isArray(data[k]) && !data[k].length));
      if (miss.length) throw new Error("Felder fehlen: " + miss.join(", "));
      try { start(data); } catch (err) {
        console.error(err);
        fail("Die Bühne ließ sich nicht aufbauen", `Die Daten passen nicht zur Bühne (${K.esc(err.message)}). Die Zahlen stehen als Tabellen auf der Wiki-Seite ${wikiLink}.`);
      }
    })
    .catch((err) => {
      fail("Die Daten der Bühne fehlen", `<code>codebase.json</code> ließ sich nicht laden (${K.esc(err.message)}). Die Zahlen stehen als Tabellen auf der Wiki-Seite ${wikiLink}; erzeugt werden sie mit <code>scripts/codebase-facts.py --write</code>.`);
    });

  function start(R) {
    K.init(R);
    const M = R.meta, DAY = K.DAY, TAU = Math.PI * 2, S = K.svg, E = K.el, esc = K.esc;
    const SNAP = R.snapshots, DAYS = R.perday;
    const T0 = SNAP[0].t - DAY, T1 = M.last || SNAP[SNAP.length - 1].t;
    const card = $("card"), host = $("hin"), hostBox = $("host"), nx = $("nx"), pv = $("pv"), bar = $("bar"), rail = $("rail");
    const lensV = $("lensV"), lensH = $("lensH"), ticks = $("ticks"), sayEl = $("say");
    const css = (v) => getComputedStyle(root).getPropertyValue(v).trim();
    const OUT = "cubic-bezier(.16,1,.3,1)";
    const CATS = R.cats.map((c) => c.id), LAB = Object.fromEntries(R.cats.map((c) => [c.id, c.label || c.id]));
    const HAS = Object.fromEntries(CATS.map((c) => [c, !!css("--" + c)]));
    const CV = (c) => `var(--${HAS[c] ? c : "other"})`;
    const LOC = M.loc || {};
    const sumL = (fs) => fs.reduce((a, f) => a + f.l, 0);
    const code = ["core", "workbench", "bridge", "scripts"].reduce((a, k) => a + (LOC[k] || 0), 0);
    const sp = (p) => p.replace("windows/bridge/src/dispread_bridge_app/", "bridge-app/").replace("src/dispread/", "");
    const STAGES = (R.pipeline && R.pipeline.stages) || [], WF = R.workflows || [], H2 = R.health || {};
    const FNS = R.functions || [], NF = Math.min(12, FNS.length);

    /* Farben aus den Tokens, als [r,g,b] 0…1 für WebGL und Kontrastwahl */
    const cx2d = document.createElement("canvas").getContext("2d");
    const rgb = (c) => {
      cx2d.fillStyle = "#000"; cx2d.fillStyle = c || "#888"; const s = cx2d.fillStyle;
      if (s[0] === "#") return [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16) / 255);
      const m = s.match(/[\d.]+/g) || [0, 0, 0]; return [m[0] / 255, m[1] / 255, m[2] / 255];
    };
    const lum = (c) => { const v = c.map((x) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4))); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
    const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    let COL = {};
    const readColors = () => { COL = Object.fromEntries(CATS.map((c) => [c, rgb(css("--" + (HAS[c] ? c : "other")))])); };
    readColors();
    /* Textfarbe auf einer Fläche (Farbe c mit Deckkraft op über dem Glas): die mit dem höheren Kontrast */
    const onFill = (c, op) => {
      const g = rgb(css("--glass-solid")), f = c.map((x, i) => x * op + g[i] * (1 - op));
      const a = css("--on-fill-light") || "#ffffff", b = css("--on-fill-dark") || "#10152a";
      return ratio(f, rgb(a)) >= ratio(f, rgb(b)) ? a : b;
    };

    let W, H, NARROW = false, L = 30, TOP = 60, BOT, RM;
    const heatDay = (R.heat || []).map((row) => row.reduce((a, b) => a + b, 0));
    const busiest = heatDay.length ? heatDay.indexOf(Math.max(...heatDay)) : 0;
    const st = { ci: 0, t: T0, step: [0, 0, busiest, 0, 0, 0, 0], auto: !reduce, autoStarted: false };

    /* ================= Wolke: ein Punkt je 30 Zeilen, je Kapitel neu geformt ================= */
    const FILES = R.files.filter((f) => f.c !== "data" && f.c !== "vendor" && f.l > 0).sort((a, b) => (a.p < b.p ? -1 : 1));
    const PT = []; FILES.forEach((f, i) => { f.i = i; f.n0 = PT.length; f.np = Math.max(1, Math.round(f.l / 30)); for (let k = 0; k < f.np; k++) PT.push({ f, k }); });
    const N = PT.length; let seed = 7;
    const rnd = () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const G = new Float32Array(N * 4); for (let i = 0; i < N * 4; i++) G[i] = i % 4 === 3 ? rnd() : (rnd() + rnd() + rnd() - 1.5) * 1.15;
    const NC = CATS.length, CMID = (NC - 1) / 2;
    const totL = sumL(FILES) || 1; let acc = 0;
    FILES.forEach((f) => {
      f.th = ((acc + f.l / 2) / totL) * TAU; acc += f.l; f.depth = Math.min(6, f.p.split("/").length); f.u1 = rnd(); f.u2 = rnd(); f.ci = CATS.indexOf(f.c);
      f.birth = K.clamp(((f.t0 || T0) - T0) / (T1 - T0), 0, 1); f.hw = f.t ? K.weekHour(f.t) : 0;
      f.stage = STAGES.findIndex((s) => (s.paths || []).some((x) => f.p.startsWith("src/dispread/" + x)));
    });
    const catLoc = CATS.map((c) => LOC[c] || sumL(FILES.filter((f) => f.c === c))), catMax = Math.max(1, ...catLoc);
    const CC = CATS.map((c, i) => { const a = (i / NC) * TAU - Math.PI / 2; return { x: Math.cos(a) * 1.02, y: Math.sin(a) * 0.72, r: 0.13 + 0.33 * Math.sqrt(catLoc[i] / catMax) }; });
    CATS.forEach((c, i) => FILES.filter((f) => f.ci === i).sort((a, b) => b.l - a.l).forEach((f, j, arr) => { const rr = CC[i].r * Math.sqrt((j + 0.5) / arr.length), aa = j * 2.39996; f.cx = CC[i].x + rr * Math.cos(aa); f.cy = CC[i].y + rr * Math.sin(aa); }));
    const codeF = FILES.filter((f) => f.fn > 0 && f.c !== "tests").sort((a, b) => b.cs - a.cs);
    codeF.forEach((f, j) => (f.sx = -1.85 + (3.7 * j) / Math.max(1, codeF.length - 1)));
    const ccMax = Math.max(1, ...codeF.map((f) => f.cc || 0));
    const stMax = Math.max(1, ...STAGES.map((s) => s.loc || 0)), NS = STAGES.length;
    const stageX = (si) => (NS > 1 ? -1.55 + (si * 3.1) / (NS - 1) : 0);
    STAGES.forEach((s, si) => FILES.filter((f) => f.stage === si).sort((a, b) => b.l - a.l).forEach((f, j, arr) => { const rr = (0.07 + 0.2 * Math.sqrt((s.loc || 0) / stMax)) * Math.sqrt((j + 0.5) / arr.length), aa = j * 2.39996; f.px = stageX(si) + rr * Math.cos(aa); f.py = rr * Math.sin(aa); }));
    const FORM = {
      tree: (f, k, g) => { const r = 0.34 + 0.17 * f.depth, s = 0.016 + 0.011 * Math.sqrt(f.np); return [r * Math.cos(f.th) + g[0] * s, (f.ci - CMID) * 0.045 + g[1] * s * 0.7, r * Math.sin(f.th) + g[2] * s]; },
      time: (f, k, g) => [-1.9 + 3.8 * f.birth + g[0] * 0.02, (CMID - f.ci) * 0.2 + g[1] * 0.055, g[2] * 0.22],
      week: (f, k, g) => { const a = (-f.hw / 168) * TAU + g[0] * 0.012, r = 0.92 + 0.5 * (1 - f.birth) + g[1] * 0.03; return [r * Math.cos(a), r * Math.sin(a), g[2] * 0.1]; },
      cats: (f, k, g) => { const s = 0.01 + 0.006 * Math.sqrt(f.np); return [f.cx + g[0] * s, f.cy + g[1] * s, g[2] * 0.07]; },
      sky: (f, k, g) => (f.sx != null ? [f.sx + g[0] * 0.006, -0.72 + 1.5 * Math.sqrt((f.cc || 0) / ccMax) * ((k + 0.5) / f.np), (f.ci - CMID) * 0.07 + g[2] * 0.02] : [-1.9 + 3.8 * f.u1 + g[0] * 0.02, -0.76 + g[1] * 0.008, -0.3 - 1.5 * f.u2 + g[2] * 0.02]),
      pipe: (f, k, g) => (f.stage >= 0 ? [f.px + g[0] * 0.012, f.py + g[1] * 0.012, g[2] * 0.06] : [-1.9 + 3.8 * f.u1 + g[0] * 0.02, -0.62 + g[1] * 0.01, -0.4 - 1.5 * f.u2 + g[2] * 0.02]),
    };

    /* WebGL ist optional: ohne Kontext (oder bei Fehlern) laufen die Kapitel ohne Wolke. */
    const cv = $("gl");
    let gl = null, GLX = null;
    try { gl = cv.getContext("webgl", { antialias: false, alpha: true }); } catch (_) { gl = null; }
    const cam = { yaw: 0.4, pitch: 0.95, dist: 3.5, tx: 0, ty: 0, tz: 0, ox: 0, oy: 0.3 }, camT = Object.assign({}, cam);
    const fx = { mix: 1, hot: 0, hotT: 0, t: 0, nudgeY: 0, nudgeX: 0, hotC: rgb(css("--alert")), hotVar: "--alert" };
    let PV = null;
    if (gl) {
      try { GLX = initGL(); } catch (err) { GLX = null; }
      if (!GLX) gl = null;
    }
    if (!gl) cv.remove();

    function initGL() {
      const VS = `attribute vec3 aA,aB,aC;attribute vec4 aM;uniform mat4 uPV;uniform vec2 uOff;uniform vec3 uHotC;uniform float uMix,uT,uHot,uNow,uPx,uFocus,uDim,uDotA;varying vec4 vC;varying float vE;
void main(){float d=clamp(uMix*1.7-aM.x*.7,0.,1.);d=d*d*(3.-2.*d);vec3 p=mix(aA,aB,d);float s=sin(d*3.1416);p+=vec3((aM.x-.5)*.5,(fract(aM.x*7.3)-.5)*.6,(fract(aM.x*3.1)-.5)*.7)*s;
p+=vec3(sin(uNow*.5+aM.x*40.),cos(uNow*.41+aM.x*31.),sin(uNow*.33+aM.x*17.))*.011;vec4 c=uPV*vec4(p,1.);c.xy+=uOff*c.w;gl_Position=c;
float born=smoothstep(aM.y-.006,aM.y+.004,uT),pop=1.+2.2*exp(-pow((uT-aM.y)*70.,2.));float coc=abs(c.w-uFocus);
float hot=aM.w*uHot;gl_PointSize=max(1.,(aM.z*uPx/c.w)*(1.+coc*1.5)*pop*born*(1.+hot*1.1));vE=clamp(.72-coc*.9,.05,.72);
vC=vec4(mix(aC,uHotC,hot),born*mix(1.,aM.w>.5?1.:uDim,uHot)*uDotA/(1.+coc*coc*5.));}`;
      const FS = `precision mediump float;uniform float uLine;varying vec4 vC;varying float vE;void main(){float m=uLine;if(uLine==0.){float r=length(gl_PointCoord-.5)*2.;m=1.-smoothstep(vE,1.,r);}gl_FragColor=vec4(vC.rgb,vC.a*min(1.,m));}`;
      const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); return gl.getShaderParameter(o, gl.COMPILE_STATUS) ? o : null; };
      const vs = sh(gl.VERTEX_SHADER, VS), fs = sh(gl.FRAGMENT_SHADER, FS); if (!vs || !fs) return null;
      const pr = gl.createProgram(); gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
      gl.useProgram(pr);
      const U = {}; ["uPV", "uOff", "uHotC", "uMix", "uT", "uHot", "uNow", "uPx", "uFocus", "uDim", "uLine", "uDotA"].forEach((n) => (U[n] = gl.getUniformLocation(pr, n)));
      const buf = (name, size, data, dyn) => { const b = gl.createBuffer(), loc = gl.getAttribLocation(pr, name); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, dyn ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0); return b; };
      const FA = {}; Object.keys(FORM).forEach((name) => { const a = new Float32Array(N * 3); PT.forEach((p, i) => { const v = FORM[name](p.f, p.k, G.subarray(i * 4, i * 4 + 4)); a[i * 3] = v[0]; a[i * 3 + 1] = v[1]; a[i * 3 + 2] = v[2]; }); FA[name] = a; });
      const colA = new Float32Array(N * 3), meta = new Float32Array(N * 4);
      PT.forEach((p, i) => { meta[i * 4] = G[i * 4 + 3]; meta[i * 4 + 1] = p.f.birth * 0.985 + G[i * 4 + 3] * 0.004; meta[i * 4 + 2] = 1; });
      const g = { U, FA, colA, meta, posA: FA.tree.slice(), posB: FA.tree };
      g.bA = buf("aA", 3, g.posA, 1); g.bB = buf("aB", 3, g.posB, 1); g.bC = buf("aC", 3, colA, 1); g.bM = buf("aM", 4, meta, 1);
      /* Linien: innerhalb einer Datei, zwischen Nachbarn im Ordner, entlang der Importe */
      const idx = []; FILES.forEach((f) => { for (let k = 0; k < f.np - 1; k++) idx.push(f.n0 + k, f.n0 + k + 1); }); g.nIntra = idx.length;
      const dirs = new Map(); FILES.forEach((f) => { const d = f.p.slice(0, Math.max(0, f.p.lastIndexOf("/"))); if (!dirs.has(d)) dirs.set(d, []); dirs.get(d).push(f); });
      dirs.forEach((fs2) => { for (let k = 0; k < fs2.length - 1; k++) idx.push(fs2[k].n0, fs2[k + 1].n0); }); g.nDir = idx.length - g.nIntra;
      const byP = new Map(FILES.map((f) => [f.p, f]));
      const modF = (id) => { const b = (id.startsWith("dispread_bridge_app") ? "windows/bridge/src/" : "src/") + id.replace(/\./g, "/"); return byP.get(b + ".py") || byP.get(b + "/__init__.py"); };
      (R.modEdges || []).forEach((e) => { const fa = modF(e[0]), fb = modF(e[1]); if (fa && fb && fa !== fb) idx.push(fa.n0, fb.n0); }); g.nImp = idx.length - g.nIntra - g.nDir;
      const big = N > 65535 && gl.getExtension("OES_element_index_uint");
      if (N > 65535 && !big) { g.nIntra = g.nDir = g.nImp = 0; } /* ohne Erweiterung nur Punkte */
      g.itype = big ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT; g.isz = big ? 4 : 2;
      const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, big ? new Uint32Array(idx) : new Uint16Array(N > 65535 ? [] : idx), gl.STATIC_DRAW);
      gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      cv.addEventListener("webglcontextlost", (e) => { e.preventDefault(); gl = null; cv.remove(); chips.forEach((c) => (c.style.opacity = 0)); });
      return g;
    }
    function uploadColors() {
      if (!gl) return;
      PT.forEach((p, i) => GLX.colA.set(COL[p.f.c] || COL[CATS[0]], i * 3));
      gl.bindBuffer(gl.ARRAY_BUFFER, GLX.bC); gl.bufferData(gl.ARRAY_BUFFER, GLX.colA, gl.DYNAMIC_DRAW);
      fx.hotC = rgb(css(fx.hotVar));
    }
    uploadColors();
    function setForm(name) {
      if (!gl) return;
      const { posA, posB, meta } = GLX, cur = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) { let d = K.clamp(fx.mix * 1.7 - meta[i * 4] * 0.7, 0, 1); d = d * d * (3 - 2 * d); for (let j = 0; j < 3; j++) cur[i * 3 + j] = posA[i * 3 + j] + (posB[i * 3 + j] - posA[i * 3 + j]) * d; }
      GLX.posA = cur; GLX.posB = GLX.FA[name];
      gl.bindBuffer(gl.ARRAY_BUFFER, GLX.bA); gl.bufferData(gl.ARRAY_BUFFER, GLX.posA, gl.DYNAMIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, GLX.bB); gl.bufferData(gl.ARRAY_BUFFER, GLX.posB, gl.DYNAMIC_DRAW);
      fx.mix = reduce ? 1 : 0; wake();
    }
    function setHot(set, color) {
      fx.hotT = set ? 1 : 0;
      if (!gl) return;
      const meta = GLX.meta; for (let i = 0; i < N; i++) meta[i * 4 + 3] = set && set.has(PT[i].f.i) ? 1 : 0;
      gl.bindBuffer(gl.ARRAY_BUFFER, GLX.bM); gl.bufferData(gl.ARRAY_BUFFER, meta, gl.DYNAMIC_DRAW);
      if (set) { fx.hotVar = color || "--alert"; fx.hotC = rgb(css(fx.hotVar)); }
      wake();
    }
    function matPV(now) {
      const asp = W / H, t = 1 / Math.tan(0.33), n = 0.1, f = 30, P = [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, (2 * f * n) / (n - f), 0];
      const yaw = cam.yaw + (reduce ? 0 : Math.sin(now * 0.00011) * 0.1) + fx.nudgeX, pitch = cam.pitch + fx.nudgeY, cp = Math.cos(pitch), spi = Math.sin(pitch), cy = Math.cos(yaw), sy = Math.sin(yaw);
      const ex = cam.tx + cam.dist * sy * cp, ey = cam.ty + cam.dist * spi, ez = cam.tz + cam.dist * cy * cp, r = [cy, 0, -sy], u = [-sy * spi, cp, -cy * spi], fw = [-sy * cp, -spi, -cy * cp];
      const V = [r[0], u[0], -fw[0], 0, r[1], u[1], -fw[1], 0, r[2], u[2], -fw[2], 0, -(r[0] * ex + r[1] * ey + r[2] * ez), -(u[0] * ex + u[1] * ey + u[2] * ez), fw[0] * ex + fw[1] * ey + fw[2] * ez, 1], o = new Float32Array(16);
      for (let c = 0; c < 4; c++) for (let rw = 0; rw < 4; rw++) o[c * 4 + rw] = P[rw] * V[c * 4] + P[4 + rw] * V[c * 4 + 1] + P[8 + rw] * V[c * 4 + 2] + P[12 + rw] * V[c * 4 + 3];
      return o;
    }
    const project = (x, y, z) => { const w = PV[3] * x + PV[7] * y + PV[11] * z + PV[15]; return [(((PV[0] * x + PV[4] * y + PV[8] * z + PV[12]) / w + cam.ox + 1) / 2) * W, ((1 - ((PV[1] * x + PV[5] * y + PV[9] * z + PV[13]) / w + cam.oy)) / 2) * H]; };

    /* Bildschleife: läuft nur, solange die Bühne sichtbar ist. Bei reduzierter
     * Bewegung gibt es keine Drift; die Schleife endet, sobald alles am Ziel ist. */
    let rafId = 0, alive = true, visible = true, last = 0, lineK = 1, dotA = 0.9;
    const readCloud = () => { lineK = parseFloat(css("--cloud-line")) || 1; dotA = parseFloat(css("--cloud-dot")) || 0.9; };
    readCloud();
    function wake() { if (gl && alive && visible && !rafId && W) { last = performance.now(); rafId = requestAnimationFrame(frame); } }
    function frame(now) {
      rafId = 0;
      if (!gl || !alive || !visible) return;
      const dt = Math.min(50, Math.max(0, now - last)); last = now;
      const k = reduce ? 1 : 1 - Math.pow(0.0018, dt / 1000);
      let busy = !reduce;
      for (const key in cam) { const d = camT[key] - cam[key]; if (Math.abs(d) > 1e-4) busy = true; cam[key] += d * k; }
      fx.mix = reduce ? 1 : Math.min(1, fx.mix + dt / 1500); if (fx.mix < 1) busy = true;
      const dh = fx.hotT - fx.hot; if (Math.abs(dh) > 1e-3) busy = true; fx.hot += dh * Math.min(1, k * 1.4);
      const tt = K.clamp((st.t - T0) / (T1 - T0), 0, 1) * 1.02, dtt = tt - fx.t; if (Math.abs(dtt) > 1e-4) busy = true; fx.t += dtt * Math.min(1, k * 4);
      if (reduce) { fx.nudgeX = fx.nudgeY = 0; } else { fx.nudgeX *= 0.9; fx.nudgeY *= 0.9; }
      const U = GLX.U, c = CH[st.ci];
      PV = matPV(now);
      gl.uniformMatrix4fv(U.uPV, false, PV); gl.uniform2f(U.uOff, cam.ox, cam.oy); gl.uniform3fv(U.uHotC, fx.hotC); gl.uniform1f(U.uMix, fx.mix);
      gl.uniform1f(U.uT, c.timed ? fx.t : 1.1); gl.uniform1f(U.uHot, fx.hot); gl.uniform1f(U.uDim, c.dim || 0.14); gl.uniform1f(U.uDotA, dotA);
      gl.uniform1f(U.uNow, reduce ? 0 : now / 1000); gl.uniform1f(U.uPx, cv.height * 0.015); gl.uniform1f(U.uFocus, cam.dist);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      const z = GLX.isz;
      if (GLX.nIntra) { gl.uniform1f(U.uLine, 0.12 * lineK); gl.drawElements(gl.LINES, GLX.nIntra, GLX.itype, 0); }
      if (GLX.nDir) { gl.uniform1f(U.uLine, 0.2 * lineK); gl.drawElements(gl.LINES, GLX.nDir, GLX.itype, GLX.nIntra * z); }
      if (GLX.nImp) { gl.uniform1f(U.uLine, 0.26 * lineK); gl.drawElements(gl.LINES, GLX.nImp, GLX.itype, (GLX.nIntra + GLX.nDir) * z); }
      gl.uniform1f(U.uLine, 0); gl.drawArrays(gl.POINTS, 0, N);
      if (c.tick) c.tick();
      if (busy) rafId = requestAnimationFrame(frame);
    }

    /* ================= kleine Hilfen ================= */
    let still = false; /* true: neu zeichnen ohne Einblendung (Größe, Farbschema) */
    const reveal = (el, from) => { if (!reduce && !still) el.animate([{ clipPath: from }, { clipPath: "inset(0 0 0 0)" }], { duration: 950, delay: 240, easing: OUT, fill: "backwards" }); };
    function count(el, to, fmt = K.fmt) {
      const from = el._v == null ? 0 : el._v; el._v = to; el._f = fmt;
      if (el._c) el._c();
      if (reduce || still || from === to) { el.textContent = fmt(to); return; }
      el.textContent = fmt(from);
      el._c = K.tween(700, (e) => (el.textContent = fmt(K.lerp(from, to, e))));
    }
    const CM = R.commits.slice().sort((a, b) => a.t - b.t);
    const slot = (t) => { let i = 0; while (i < DAYS.length - 1 && DAYS[i + 1].t <= t) i++; return i + K.clamp((t - DAYS[i].t) / DAY, 0, 0.999); };
    const slotInv = (s) => { const i = K.clamp(Math.floor(s), 0, DAYS.length - 1); return DAYS[i].t + K.clamp(s - i, 0, 0.999) * DAY; };
    const nearest = (t) => { let b = CM[0], bd = 1e12; for (const c of CM) { const d = Math.abs(c.t - t); if (d < bd) { bd = d; b = c; } } return b; };
    const SN = [{ t: T0, loc: {}, f: 0 }].concat(SNAP);
    const STACK = ["core", "workbench", "bridge", "scripts", "infra", "tests", "docs"].filter((c) => CATS.includes(c)).concat(CATS.filter((c) => !["core", "workbench", "bridge", "scripts", "infra", "tests", "docs"].includes(c)));
    const yMaxLoc = Math.max(1, ...SN.map((s) => Object.values(s.loc || {}).reduce((a, b) => a + b, 0))) * 1.04;
    const weekTicks = () => { const out = []; for (let t = DAYS[0].t; t < T1; t += 7 * DAY) out.push(t); return out; };
    const firstWord = (s) => String(s).split(/\s+/)[0].replace(/[&,]+$/, "");
    const lane = (i) => (R.lanes && R.lanes[i]) || { name: "", row: 0 };

    /* ================= Kapitel ================= */
    const CH = [
      {
        id: "wachstum", label: "Wachstum", timed: 1, form: "tree", nf: [0.36, 1],
        cam: { yaw: 0.4, pitch: 0.95, dist: 3.5, ox: -0.08, oy: 0.34 },
        rect: () => [L, H * 0.5, RM - L, BOT - H * 0.5, 38],
        render(p) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`);
          p.innerHTML = `<div class="row"><div class="lead"><div class="big" data-k="gN" data-in data-say>0</div><div class="h" data-in data-say>Zeilen am <span data-k="gD"></span></div><div class="facts" data-in><span><b data-k="gC">0</b> Commits</span><span><b data-k="gF">0</b> Dateien</span><span>Tag <b data-k="gY">1</b> von ${K.fmt(M.days || 1)}</span></div></div><div class="grow" data-in></div></div>`;
          const g = p.querySelector(".grow"), cw = Math.max(120, g.clientWidth), ch = Math.max(80, g.clientHeight), ph = ch - 24;
          const fxp = cw * (NARROW ? 0.52 : 0.72), ppd = (fxp * 0.97) / ((T1 - T0) / DAY), X = (t) => ((t - T0) / DAY) * ppd, y = K.scale(0, yMaxLoc, ph, 6);
          const svg = S("svg", { width: cw, height: ch, "aria-hidden": "true" }, g), id = "gc" + Math.random().toString(36).slice(2);
          const clip = S("rect", { x: -9999, y: -20, width: 9999, height: ch + 40 }, S("clipPath", { id }, svg));
          const mk = (par, op) => {
            const gg = S("g", { opacity: op }, par); let base = SN.map(() => 0);
            STACK.forEach((c) => { const top = SN.map((s, k) => base[k] + ((s.loc || {})[c] || 0)); S("path", { d: "M" + SN.map((s, k) => X(s.t).toFixed(1) + " " + y(top[k]).toFixed(1)).join("L") + "L" + SN.map((s, k) => X(s.t).toFixed(1) + " " + y(base[k]).toFixed(1)).reverse().join("L") + "Z", style: `fill:${CV(c)}` }, gg); base = top; });
            return gg;
          };
          const mv = S("g", {}, svg); mk(mv, 0.16); mk(S("g", { "clip-path": `url(#${id})` }, mv), 0.8);
          /* Wochenmarken: Beschriftung nur, wenn sie mit 8 px Abstand hinter der vorigen beginnt */
          let lastEnd = -1e9;
          weekTicks().forEach((t) => {
            const x = X(t); S("line", { x1: x, x2: x, y1: ph, y2: ph + 6, style: "stroke:var(--grid)", opacity: 0.5 }, mv);
            if (x + 4 < lastEnd + 8) return;
            const tx = S("text", { x: x + 4, y: ph + 19, text: K.date(t + 10800), class: "m" }, mv);
            let tw = 0; try { tw = tx.getComputedTextLength(); } catch (_) { tw = 0; }
            lastEnd = x + 4 + (tw || K.date(t + 10800).length * 7.5);
          });
          S("line", { x1: fxp, x2: fxp, y1: 0, y2: ph, style: "stroke:var(--ink)", "stroke-width": 1.5 }, svg);
          const labs = STACK.map((c) => { const gg = S("g", {}, svg); S("circle", { cx: fxp + 14, cy: -4, r: 4, style: `fill:${CV(c)}` }, gg); const tx = S("text", { x: fxp + 23, y: 0, "font-weight": 600, style: "fill:var(--ink)" }, gg); return { gg, tx }; });
          this.update = () => {
            const t = st.t, v = K.locAt(t);
            mv.setAttribute("transform", `translate(${(fxp - X(t)).toFixed(1)},0)`); clip.setAttribute("width", 9999 + X(t));
            q("gN").textContent = K.fmt(v.total); q("gD").textContent = K.dateLong(t);
            let lo = 0, hi = CM.length; while (lo < hi) { const m = (lo + hi) >> 1; if (CM[m].t <= t) lo = m + 1; else hi = m; }
            q("gC").textContent = K.fmt(lo);
            let si = 0; while (si < SN.length - 1 && SN[si + 1].t <= t) si++;
            const a = SN[si], b = SN[Math.min(si + 1, SN.length - 1)], uu = b.t === a.t ? 1 : K.clamp((t - a.t) / (b.t - a.t), 0, 1);
            q("gF").textContent = K.fmt(K.lerp(a.f || 0, b.f || 0, uu)); q("gY").textContent = K.clamp(Math.floor((t - DAYS[0].t) / DAY) + 1, 1, M.days || 1);
            let base = 0, ly = 1e9;
            STACK.forEach((c, k) => {
              const top = base + v[c], show = y(base) - y(top) >= 1.5, yy = Math.min(y((base + top) / 2) + 4, ly - 15);
              labs[k].gg.setAttribute("transform", `translate(0,${yy.toFixed(1)})`); labs[k].gg.style.display = show ? "" : "none";
              labs[k].tx.textContent = show ? `${LAB[c]} ${K.kfmt(v[c])}` : ""; if (show) ly = yy; base = top;
            });
          };
          this.ppd = ppd; this.update();
        },
        scrub(dx) { st.t = K.clamp(st.t - (dx / this.ppd) * DAY, T0, T1); this.update(); },
        valueText: () => K.dateLong(st.t),
      },
      {
        id: "branches", label: "Branches", timed: 1, form: "time", nf: [0, 1],
        cam: { yaw: 0, pitch: 0.2, dist: 3.3, ox: 0, oy: 0 },
        rect: () => [L, TOP, RM - L, BOT - TOP, 38],
        render(p) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`);
          p.innerHTML = `<div data-in style="height:92px"><div class="h" data-k="bS" data-say style="margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:clamp(19px,3.2vh,27px)"></div><div class="mono" data-k="bM" style="margin-top:8px"></div></div><div class="grow" data-in style="height:calc(100% - 92px)"></div>`;
          const g = p.querySelector(".grow"), cw = Math.max(120, g.clientWidth), ch = Math.max(80, g.clientHeight), SW = Math.max(120, cw / 7.5), X = (t) => slot(t) * SW;
          const lanes = R.lanes || [], rows = Math.max(1, ...lanes.map((l) => l.row)) + 1, rh = (ch - 34) / rows, Y = (r) => 26 + (r + 0.5) * rh;
          const svg = S("svg", { width: cw, height: ch, "aria-hidden": "true" }, g), mv = S("g", {}, svg), fxp = cw / 2;
          DAYS.forEach((d, k) => { const gap = k && d.t - DAYS[k - 1].t > DAY * 1.5; S("line", { x1: k * SW, x2: k * SW, y1: 16, y2: ch, style: "stroke:var(--grid)", opacity: gap ? 0.45 : 0.14, "stroke-dasharray": gap ? "3 5" : null }, mv); S("text", { x: k * SW + 6, y: 10, text: K.dateLong(d.t + 10800), class: "m" }, mv); });
          const used = [];
          lanes.forEach((l) => {
            const yy = Y(l.row), x0 = X(l.t0), x1 = X(l.t1), main = l.kind === "trunk" || l.kind === "focus"; let d = "";
            if (l.frm != null && lanes[l.frm]) { const xf = X(l.tFork), yf = Y(lanes[l.frm].row); d = `M${xf} ${yf}C${(xf + x0) / 2} ${yf} ${(xf + x0) / 2} ${yy} ${x0} ${yy}`; } else d = `M${x0} ${yy}`;
            d += `L${x1} ${yy}`;
            if (l.into != null && lanes[l.into]) { const xm = X(l.tMerge), ym = Y(lanes[l.into].row); d += `C${(x1 + xm) / 2} ${yy} ${(x1 + xm) / 2} ${ym} ${xm} ${ym}`; }
            S("path", { d, fill: "none", style: `stroke:${l.state === "stale" ? "var(--alert)" : main ? "var(--ink)" : "var(--ink3)"}`, "stroke-width": main ? 4 : 2, "stroke-linecap": "round", "stroke-dasharray": l.state === "stale" ? "2 6" : null }, mv);
            if (l.n >= 3 || l.state === "stale" || l.state === "open") {
              const nm = K.short(l.name, 30), lw = nm.length * 7.2;
              if (!used.some((u) => x0 < u[0] + u[2] + 10 && x0 + lw + 10 > u[0] && u[1] === l.row)) { used.push([x0, l.row, lw]); S("text", { x: x0 + 8, y: yy - 9, text: nm, "font-weight": 600, style: `fill:${l.state === "stale" ? "var(--alert-ink)" : "var(--ink)"}` }, mv); }
            }
          });
          CM.forEach((c) => { const mg = (c.p || []).length > 1; S("circle", { cx: X(c.t), cy: Y(lane(c.l).row), r: mg ? 5 : K.clamp(2.4 + Math.sqrt((c.a || 0) + (c.x || 0)) / 16, 2.6, 8), style: `fill:${mg || c.w !== "h" ? "var(--dot-bg)" : CV(c.c)};stroke:${mg || c.w !== "h" ? "var(--ink)" : "var(--dot-bg)"}`, "stroke-width": mg ? 2 : 1 }, mv); });
          const ring = S("circle", { r: 13, fill: "none", style: "stroke:var(--ink)", "stroke-width": 2.2 }, mv);
          S("line", { x1: fxp, x2: fxp, y1: 16, y2: ch, style: "stroke:var(--ink)", "stroke-width": 1.2, opacity: 0.5 }, svg);
          let cur = null;
          this.update = () => {
            mv.setAttribute("transform", `translate(${(fxp - X(st.t)).toFixed(1)},0)`);
            const c = nearest(st.t); if (c === cur) return; cur = c;
            ring.setAttribute("cx", X(c.t)); ring.setAttribute("cy", Y(lane(c.l).row));
            q("bS").textContent = c.s;
            const who = c.w === "b" ? " · Doku-Bot" : c.w === "c" ? " · Codex" : "";
            q("bM").textContent = `${c.h} · ${K.dateLong(c.t)} ${K.time(c.t)} · ${lane(c.l).name} · ` + ((c.p || []).length > 1 ? "Merge" : `+${K.fmt(c.a || 0)} −${K.fmt(c.x || 0)} in ${K.fmt(c.f || 0)} ${K.plural(c.f, "Datei", "Dateien")}`) + who;
          };
          this.SW = SW; this.update();
        },
        scrub(dx) { st.t = slotInv(K.clamp(slot(st.t) - dx / this.SW, 0, DAYS.length - 0.001)); this.update(); },
        settle() { const c = nearest(st.t), a = st.t; K.tween(320, (e) => { st.t = K.lerp(a, c.t, e); this.update(); railPos(); }); },
        valueText: () => { const c = nearest(st.t); return `${K.dateLong(c.t)} ${K.time(c.t)}: ${c.s}`; },
      },
      {
        id: "rhythmus", label: "Rhythmus", form: "week", nf: [0, 1], steps: K.WD.slice(),
        cam: { yaw: 0, pitch: 0, dist: 3.4, ox: -0.86, oy: 0 },
        geo() { const cx = W * 0.03, Rr = RM - 14 - cx; return { cx, Rr }; },
        rect() { const g = this.geo(); return [g.cx - g.Rr, H / 2 - g.Rr, g.Rr * 2, g.Rr * 2, g.Rr]; },
        stepText: (i) => K.WD[i],
        render(p, i, w) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`); this.q = q;
          const heat = R.heat || [], mx = Math.max(1, ...heat.flat());
          const hubHtml = `<div class="big" data-k="rD" data-in data-say></div><div class="h" data-k="rH" data-in data-say></div><p class="p" data-k="rP" data-in></p><p class="p" data-k="rQ" data-in></p>`;
          let Rr, r0, r1, svg, small;
          if (NARROW) {
            p.innerHTML = `<div style="display:flex;flex-direction:column;height:100%"><div>${hubHtml}</div><div class="grow" data-in style="flex:1"></div></div>`;
            this.stepUpdate(i, null, true);
            const g = p.querySelector(".grow"), D = Math.max(60, Math.min(g.clientWidth, g.clientHeight));
            Rr = D / 2; r0 = Rr * 0.5; r1 = Math.min(Rr * 0.86, Rr - 18); small = true;
            svg = S("svg", { width: D, height: D, "aria-hidden": "true", style: "margin:0 auto" }, g);
          } else {
            p.style.padding = 0; const geo = this.geo(); Rr = geo.Rr; r0 = Rr * 0.64; r1 = Rr * 0.955; small = false;
            svg = S("svg", { width: w, height: w, "aria-hidden": "true" }, p);
            const hub = E("div", "", p);
            hub.style.cssText = `position:absolute;left:${Rr - geo.cx + L + 6}px;top:${Rr - H / 2 + TOP + 34}px;width:${Math.min(430, r0 - 80)}px`;
            hub.innerHTML = hubHtml;
          }
          const wh = S("g", {}, svg);
          wh.style.cssText = `transform-origin:${Rr}px ${Rr}px;transition:transform ${reduce ? 0 : 1.1}s cubic-bezier(.2,1.2,.3,1)`;
          for (let v = 0; v <= mx; v += 5) S("circle", { cx: Rr, cy: Rr, r: r0 + (v / mx) * (r1 - r0), fill: "none", style: "stroke:var(--grid)", opacity: v % 10 ? 0.08 : 0.16 }, wh);
          const sw = ((TAU * r0) / 168) * 0.6;
          heat.forEach((row, d) => {
            S("line", { x1: Rr + r0 - (small ? 24 : 46), x2: Rr + r1 + (small ? 4 : 10), y1: Rr, y2: Rr, style: "stroke:var(--grid)", opacity: 0.3, transform: `rotate(${((d * 24) / 168) * 360} ${Rr} ${Rr})` }, wh);
            const tg = S("g", { transform: `rotate(${((d * 24 + 12) / 168) * 360} ${Rr} ${Rr})` }, wh);
            S("text", { x: Rr + r0 - (small ? 8 : 62), y: Rr + (small ? 4 : 7), text: small ? K.WDS[d] : K.WD[d], "text-anchor": "end", "font-size": small ? 12 : 17, "font-weight": 600, style: "fill:var(--ink)" }, tg);
            row.forEach((v, hh) => {
              const a = ((d * 24 + hh + 0.5) / 168) * 360, gg = S("g", { transform: `rotate(${a} ${Rr} ${Rr})`, class: "d" + d }, wh);
              S("line", { x1: Rr + r0, x2: Rr + r0 + Math.max(0.5, (v / mx) * (r1 - r0)), y1: Rr, y2: Rr, "stroke-width": v ? sw : 3, "stroke-linecap": "round", style: "stroke:var(--docs)" }, gg);
              if (!small && hh % 6 === 0) S("text", { x: Rr + r0 - 6, y: Rr + 4, text: String(hh).padStart(2, "0"), class: "m", "text-anchor": "end", transform: `rotate(${(-0.5 / 168) * 360} ${Rr} ${Rr})` }, gg);
            });
          });
          S("path", { d: `M${Rr + r1 + 16} ${Rr - 7}L${Rr + r1 + 4} ${Rr}L${Rr + r1 + 16} ${Rr + 7}Z`, style: "fill:var(--ink)" }, svg);
          this.wh = wh; this.rot = 0; this.stepUpdate(i);
        },
        stepUpdate(i, prev, textOnly) {
          const q = this.q, heat = R.heat || [], row = heat[i] || [], tot = heatDay[i] || 0, all = heatDay.reduce((a, b) => a + b, 0) || 1;
          if (!textOnly && this.wh) {
            const target = (-(i * 24 + 12) / 168) * 360; let d = target - this.rot; d = ((d + 540) % 360) - 180; this.rot += d;
            this.wh.style.transform = `rotate(${this.rot}deg)`;
            this.wh.querySelectorAll("g[class^=d]").forEach((g) => (g.style.opacity = g.getAttribute("class") === "d" + i ? 1 : 0.32));
          }
          q("rD").textContent = K.WDPL[i];
          q("rH").textContent = tot ? `${K.fmt(tot)} ${K.plural(tot, "Commit", "Commits")}, ${K.pct(tot / all)} der Woche` : "keine Commits";
          if (tot) {
            const pk = row.indexOf(Math.max(...row)), first = row.findIndex((v) => v), lastH = 23 - row.slice().reverse().findIndex((v) => v);
            q("rP").innerHTML = `Stärkste Stunde: <b>${K.hh(pk)}</b> mit ${K.fmt(row[pk])} ${K.plural(row[pk], "Commit", "Commits")}. Die früheste Stunde mit Commits beginnt um ${K.hh(first)}, die späteste um ${K.hh(lastH)}.`;
          } else q("rP").textContent = "An diesem Wochentag gibt es keine Commits.";
          /* stärkste drei aufeinanderfolgende Wochentage, aus dem Raster berechnet */
          let best = 0, bs = -1; for (let a = 0; a + 2 < heatDay.length; a++) { const s3 = heatDay[a] + heatDay[a + 1] + heatDay[a + 2]; if (s3 > bs) { bs = s3; best = a; } }
          const days = M.activeDays != null && M.days ? ` An ${K.fmt(M.activeDays)} von ${K.fmt(M.days)} Tagen wurde überhaupt committet.` : "";
          q("rQ").innerHTML = heatDay.length >= 3 ? `${K.WD[best]} bis ${K.WD[best + 2]} tragen <b>${K.pct(bs / all)}</b> aller ${K.fmt(all)} Commits.${days}` : days.trim();
          return true;
        },
        dragRot(tx) { if (!this.wh) return; this.wh.style.transition = "none"; this.wh.style.transform = `rotate(${this.rot + tx * 0.06}deg)`; },
        dragEnd() { if (!this.wh) return; this.wh.style.transition = `transform ${reduce ? 0 : 1.1}s cubic-bezier(.2,1.2,.3,1)`; this.wh.style.transform = `rotate(${this.rot}deg)`; },
      },
      {
        id: "struktur", label: "Struktur", form: "cats", nf: [0.22, 1], steps: ["Alle"].concat(R.cats.map((c) => firstWord(c.label || c.id))),
        cam: { yaw: 0, pitch: 0, dist: 3.6, ox: 0.5, oy: 0 },
        rect: () => [L, TOP, (RM - L) * 0.45, BOT - TOP, 38],
        stepText: (i) => (i ? LAB[CATS[i - 1]] : "alle Bereiche"),
        camStep(i) { return i ? { tx: CC[i - 1].x, ty: CC[i - 1].y, dist: 1.25 + CC[i - 1].r * 2.6, ox: 0.52 } : { tx: 0, ty: 0, dist: 3.6, ox: 0.5 }; },
        render(p, i, w, h) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`);
          const c = i ? CATS[i - 1] : null, fs = c ? FILES.filter((f) => f.c === c) : FILES, loc = c ? LOC[c] ?? sumL(fs) : M.locTotal ?? sumL(fs);
          const tr = code ? (LOC.tests || 0) / code : 0;
          const TXT = {
            docs: `${K.fmt(LOC.docs || 0)} Zeilen Dokumentation gegenüber ${K.fmt(code)} Zeilen Produktcode.`,
            tests: `${K.dec(tr, 2)} Testzeilen je Zeile Produktcode.`,
            workbench: "Live-Messpfad und Web-Werkbank auf dem Pi.",
            scripts: "Werkzeuge für Ernte, Auswertung und Wartung.",
            core: NS ? `Die Lesekette selbst, in ${K.fmt(NS)} Stufen.` : "Die Lesekette selbst.",
            bridge: "Die Windows-Anwendung, die GSVmulti versorgt.",
            infra: "Konfiguration, CI und Paketierung.",
          };
          const overall = code ? `${K.fmt(LOC.docs || 0)} Zeilen Dokumentation, ${K.fmt(code)} Zeilen Produktcode und ${K.fmt(LOC.tests || 0)} Zeilen Tests: ${K.dec(tr, 2)} Testzeilen je Codezeile.` : "";
          const biggest = fs.slice().sort((a, b) => b.l - a.l)[0];
          const txt = c ? `${TXT[c] || ""} <b>${K.fmt(fs.length)} ${K.plural(fs.length, "Datei", "Dateien")}</b>${biggest ? `, die größte ist <b>${esc(K.base(biggest.p))}</b>` : ""}.` : overall;
          p.innerHTML = `<div class="big" data-in data-k="sN" data-say></div><div class="h" data-in data-say>${c ? `Zeilen in ${esc(LAB[c])}` : `Zeilen in ${K.fmt(fs.length)} Textdateien`}</div><p class="p" data-in data-k="sP">${txt}</p><div data-in data-k="sT" style="position:absolute;left:${NARROW ? 18 : 32}px;right:${NARROW ? 18 : 32}px;bottom:${NARROW ? 20 : 28}px"></div>`;
          count(q("sN"), loc);
          const sP = q("sP"), legend = c && c !== "docs" && c !== "infra";
          const topY = sP.offsetTop + sP.offsetHeight + (legend ? 34 : 18), tw = Math.max(80, w - (NARROW ? 36 : 64)), th = Math.floor(h - (NARROW ? 20 : 28) - topY);
          if (th < 70) return;
          const svg = S("svg", { width: tw, height: th, role: "img", "aria-label": c ? `Dateien in ${LAB[c]} nach Zeilen` : "Bereiche nach Zeilen" }, q("sT"));
          const items = K.treemap(c ? fs.map((f) => ({ v: f.l, f })) : CATS.map((k) => ({ v: LOC[k] || 0, k })), 0, 0, tw, th);
          reveal(svg, "inset(0 100% 0 0)");
          items.forEach((d) => {
            const cat = c || d.k, op = c ? 0.3 + 0.55 * K.clamp(((d.f.cs || 0) / d.f.l) * 4, 0, 1) : 0.78, rx = Math.min(9, d.w / 4, d.h / 4);
            S("rect", { x: d.x + 1.5, y: d.y + 1.5, width: Math.max(0, d.w - 3), height: Math.max(0, d.h - 3), rx, style: `fill:${CV(cat)}`, opacity: op }, svg);
            if (d.w > 26 && d.h > 26) S("rect", { x: d.x + 1.5, y: d.y + 1.5, width: d.w - 3, height: (d.h - 3) * 0.55, rx, fill: "url(#gloss)" }, svg);
            if (d.w > 78 && d.h > 30) S("text", { x: d.x + 10, y: d.y + 20, text: K.short(c ? K.base(d.f.p) : LAB[d.k] + " · " + K.kfmt(d.v), Math.floor(d.w / 7.6)), "font-weight": 600, style: `fill:${onFill(COL[cat] || [0.5, 0.5, 0.5], op)}` }, svg);
          });
          if (legend) S("text", { x: 0, y: -10, text: "Fläche = Zeilen, kräftiger = verzweigter", class: "m" }, svg);
        },
        tick() {
          const s = st.step[3], show = gl && !NARROW;
          chips.forEach((ch, k) => {
            if (!show) { ch.style.opacity = 0; return; }
            const qq = project(CC[k].x, CC[k].y + CC[k].r + 0.06, 0);
            ch.style.transform = `translate(${qq[0].toFixed(1)}px,${qq[1].toFixed(1)}px) translate(-50%,-100%)`;
            ch.style.opacity = (s === 0 || s === k + 1) && qq[0] > RM * 0.47 && qq[0] < RM - 20 && qq[1] > 70 ? 1 : 0;
          });
        },
      },
      {
        id: "komplexitaet", label: "Komplexität", form: "sky", dim: 0.6, nf: [0, 0.8], steps: FNS.slice(0, NF).map((f, i) => String(i + 1)),
        cam: { yaw: 0.12, pitch: 0.1, dist: 3.5, ox: -0.06, oy: -0.42 },
        rect: () => [L, TOP, RM - L, (BOT - TOP) * 0.54, 38],
        stepText: (i) => `Rang ${i + 1}: ${FNS[i].n}`,
        hot(i) { const f = FILES.find((x) => x.p === FNS[i].p); return f ? new Set([f.i]) : null; },
        camStep(i) { const f = FILES.find((x) => x.p === FNS[i].p); return { tx: f && f.sx != null ? f.sx * 0.5 : 0 }; },
        render(p, i) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`); this.q = q;
          let F = FNS.filter((f) => f.cc >= 20); if (!F.length) F = FNS.slice(0, 40); this.F = F;
          p.innerHTML = `<div class="row"><div class="lead" style="flex-basis:290px"><div class="big alert" data-k="cN" data-in data-say></div><div class="h" data-k="cT" data-in data-say style="word-break:break-all"></div><div class="mono" data-k="cP" data-in style="margin-top:8px;word-break:break-all"></div><p class="p" data-k="cL" data-in></p></div><div class="grow" data-in></div></div>`;
          const g = p.querySelector(".grow"), cw = Math.max(80, g.clientWidth), ch = Math.max(60, g.clientHeight);
          const svg = S("svg", { width: cw, height: ch, "aria-hidden": "true" }, g), bw = cw / F.length, top = Math.max(45, Math.max(...F.map((f) => f.cc)) * 1.05), y = K.scale(0, top, ch - 22, 8);
          for (let v = 20; v < top; v += 20) {
            S("line", { x1: 0, x2: cw, y1: y(v), y2: y(v), style: "stroke:var(--grid)", opacity: v === 40 ? 0.5 : 0.14, "stroke-dasharray": v === 40 ? "4 5" : null }, svg);
            S("text", { x: cw, y: y(v) - 5, text: v === 40 ? "40 · schwer zu testen" : String(v), class: "m", "text-anchor": "end" }, svg);
          }
          reveal(svg, "inset(100% 0 0 0)");
          this.bars = F.map((f, k) => S("rect", { x: k * bw + bw * 0.14, y: y(f.cc), width: bw * 0.72, height: ch - 22 - y(f.cc), rx: Math.min(3, bw * 0.3), style: `fill:${CV(f.c)}` }, svg));
          S("text", { x: 0, y: ch - 4, text: NARROW ? `${K.fmt(F.length)} Funktionen ab 20, von ${K.fmt(M.fnTotal || FNS.length)}` : `die ${K.fmt(F.length)} Funktionen ab Komplexität 20, von ${K.fmt(M.fnTotal || FNS.length)} insgesamt`, class: "m" }, svg);
          this.mark = S("path", { d: "M-7 0L7 0L0 9Z", style: "fill:var(--ink)" }, svg); this.mark.style.transition = reduce ? "none" : "transform .7s " + OUT;
          this.y = y; this.bw = bw; this.stepUpdate(i);
        },
        stepUpdate(i) {
          const f = FNS[i], q = this.q; count(q("cN"), f.cc); q("cT").textContent = f.n; q("cP").textContent = `${sp(f.p)}:${f.ln}`;
          q("cL").innerHTML = `Rang <b>${i + 1}</b>. ${K.fmt(f.cc)} unabhängige Pfade durch <b>${K.fmt(f.l)} Zeilen</b>, etwa eine Verzweigung alle ${K.dec(f.l / f.cc, 1)} Zeilen.`;
          const j = this.F.indexOf(f);
          this.bars.forEach((b, k) => b.setAttribute("opacity", k === j ? 1 : 0.38));
          this.mark.style.display = j < 0 ? "none" : "";
          if (j >= 0) this.mark.style.transform = `translate(${(j + 0.5) * this.bw}px,${this.y(f.cc) - 14}px)`;
          return true;
        },
      },
      {
        id: "zustand", label: "Zustand", form: "tree", nf: [0.18, 1], steps: ["ungenutzt", "verwaist", "still", "gemergt", "zu lang", "gesund"],
        cam: { yaw: -0.5, pitch: 1.0, dist: 3.1, ox: 0.63, oy: 0.02 },
        rect: () => [L, TOP, (RM - L) * 0.62, BOT - TOP, 38],
        stepText(i) { return this.steps[i]; },
        hot(i) {
          const by = (ps) => new Set(FILES.filter((f) => ps.includes(f.p)).map((f) => f.i));
          return i === 0 ? by((H2.dead || []).map((d) => d.p)) : i === 1 ? by((H2.orphans || []).map((d) => d.p)) : i === 4 ? by((H2.giants || []).map((d) => d.p)) : i === 5 ? new Set(FILES.filter((f) => f.c === "tests").map((f) => f.i)) : new Set();
        },
        hotCol: (i) => (i === 5 ? "--ok" : "--alert"),
        camStep(i) { return { yaw: -0.5 + i * 0.55 }; },
        render(p, i, w, h) {
          const q = (k) => p.querySelector(`[data-k="${k}"]`);
          const dead = H2.dead || [], orph = H2.orphans || [], brs = H2.branches || [], giants = H2.giants || [];
          const TL = (t) => (((t - T0) / (T1 - T0)) * 100).toFixed(1) + "%";
          const br = (s) => brs.filter((b) => b.state === s).map((b) => {
            const l = (R.lanes || []).find((x) => x.name === b.name) || {}; const a = Math.min(l.tFork || l.t0 || T1, l.t0 || T1);
            return { a: b.name, x0: TL(a), w: Math.max(0.8, (((l.t1 || T1) - a) / (T1 - T0)) * 100).toFixed(1) + "%", dots: 1, n: s === "stale" ? `${K.fmt(b.age)} Tage still · ${K.fmt(b.ahead)} offen` : `${K.fmt(b.age)} Tage` };
          });
          const deadMax = Math.max(1, ...dead.map((d) => d.l)), gMax = Math.max(1, ...giants.map((g) => g.l));
          const gLines = H2.giantLines ?? H2.giantMin ?? (H2.method && H2.method.giantLines);
          const gPaths = new Set(giants.map((g) => g.p)), inG = FNS.slice(0, NF).filter((f) => gPaths.has(f.p)).length;
          const tests = (M.pyTests || 0) + (M.e2eTests || 0), tr = code ? (LOC.tests || 0) / code : 0;
          const D = [
            { n: dead.length, key: "dead", t: K.plural(dead.length, "Definition, die niemand aufruft", "Definitionen, die niemand aufruft"), s: `Eine Suche über das ganze Repository findet für keine davon einen Aufrufer: <b>${K.fmt(dead.reduce((a, d) => a + d.l, 0))} Zeilen</b>, die wegkönnen.`, rows: dead.map((d) => ({ a: d.n, w: (d.l / deadMax) * 100 + "%", n: `${K.fmt(d.l)} Zeilen · ${K.base(d.p)}` })) },
            { n: orph.length, key: "orphans", t: K.plural(orph.length, "zurückgelassenes Skript", "zurückgelassene Skripte"), s: `Weder Code noch CI verweisen noch auf sie. Balken = Tage seit der letzten Änderung, von ${K.fmt(M.days || 0)}.`, rows: orph.map((d) => ({ a: d.p, w: (d.age / (M.days || 1)) * 100 + "%", n: `${K.fmt(d.age)} Tage` })) },
            { n: brs.filter((b) => b.state === "stale").length, key: "branches", t: "still gewordene Branches", s: `Jeder hält noch Commits, die <b>${esc(M.focus || "den Fokus-Branch")}</b> nie erreicht haben. Durchgezogen = aktive Zeit, gepunktet = Stille seitdem.`, rows: br("stale") },
            { n: brs.filter((b) => b.state === "merged").length, key: "branches", t: "gemergte Refs, noch auf dem Remote", s: "Alles darin steckt schon im Hauptzweig. Wer die Refs löscht, verliert nichts.", col: "--infra", ink: "--infra-ink", rows: br("merged") },
            { n: giants.length, key: "giants", t: gLines ? `Quelldateien über ${K.fmt(gLines)} Zeilen` : "besonders lange Quelldateien", s: NF ? `${K.fmt(inG)} der ${K.fmt(NF)} komplexesten Funktionen liegen in diesen Dateien.` : "", col: "--scripts", ink: "--scripts-ink", rows: giants.map((g) => ({ a: sp(g.p), w: (g.l / gMax) * 100 + "%", n: K.fmt(g.l) })) },
            { n: tests, key: "todo", t: "Tests, die den Stand absichern", s: "Nicht alles braucht eine Reparatur.", col: "--ok", ink: "--ok-ink", rows: [
              { a: "Testzeilen je Codezeile", w: Math.min(100, tr * 50) + "%", n: K.dec(tr, 2) + " : 1" },
              { a: "Funktionen mit Komplexität ≤ 10", w: (1 - (M.over10 || 0) / (M.fnTotal || 1)) * 100 + "%", n: K.pct(1 - (M.over10 || 0) / (M.fnTotal || 1)) },
              { a: "pytest-Fälle", w: ((M.pyTests || 0) / (tests || 1)) * 100 + "%", n: K.fmt(M.pyTests || 0) },
              { a: "Browsertests", w: Math.max(3, ((M.e2eTests || 0) / (tests || 1)) * 100) + "%", n: K.fmt(M.e2eTests || 0) },
              { a: "TODO-Marker im Code", w: Math.min(100, ((H2.todo || 0) / (M.files || 1)) * 100) + "%", n: K.fmt(H2.todo || 0) },
            ] },
          ][i];
          if (!D.n && !D.rows.length) D.s = "Die Suche findet derzeit keine.";
          const col = D.col || "--alert", ink = D.ink || (i === 5 ? "--ok-ink" : "--alert-ink");
          const meth = H2.method && typeof H2.method[D.key] === "string" ? `<p class="method" data-in>Methode: ${esc(H2.method[D.key])}</p>` : "";
          p.innerHTML = `<div class="big" data-in data-k="hN" data-say style="color:var(${ink})"></div><div class="h" data-in data-say>${D.t}</div><p class="p" data-in>${D.s}</p>${meth}<div data-in data-k="hR" style="margin-top:22px;--col:var(${col})"></div>`;
          count(q("hN"), D.n);
          const box = q("hR"), avail = h - (NARROW ? 20 : 28) - box.offsetTop - 22;
          const rh = K.clamp(avail / Math.max(1, Math.min(D.rows.length, 11)), 22, 48), fit = Math.max(1, Math.floor(avail / rh));
          const max = D.rows.length > fit ? Math.max(1, fit - 1) : D.rows.length;
          box.style.setProperty("--rh", rh + "px");
          box.innerHTML = D.rows.slice(0, max).map((r, k) => `<div class="hr" style="--k:${k};--w:${r.w};${r.x0 ? "--x0:" + r.x0 : ""}"><span title="${esc(r.a)}">${esc(r.a)}</span><u><b></b>${r.dots ? "<em></em>" : ""}</u><small>${esc(r.n)}</small></div>`).join("") + (D.rows.length > max ? `<div class="hr"><span style="color:var(--ink2)">und ${K.fmt(D.rows.length - max)} weitere</span><i></i><i></i></div>` : "");
        },
      },
      {
        id: "maschine", label: "Maschine", form: "pipe", dim: 0.3, nf: [0.3, 1],
        steps: STAGES.map((s, k) => String(k + 1)).concat(WF.map((w) => K.short(w.name || w.file || "Ablauf", 18))),
        cam: { yaw: 0, pitch: 0.34, dist: 3.5, ox: -0.07, oy: 0.47 },
        rect: () => { const f = H < 780 ? 0.3 : 0.47; return [L, TOP + (BOT - TOP) * f, RM - L, (BOT - TOP) * (1 - f), 38]; },
        stepText: (i) => (i < NS ? `Stufe ${i + 1}: ${STAGES[i].de || STAGES[i].name}` : `Ablauf ${WF[i - NS].name}`),
        hot(i) { return i < NS ? new Set(FILES.filter((f) => f.stage === i).map((f) => f.i)) : new Set(FILES.filter((f) => f.p.startsWith(".github/") || f.p.startsWith("systemd/") || f.p.startsWith("scripts/docs")).map((f) => f.i)); },
        hotCol: () => "--docs",
        camStep(i) { return i < NS ? { tx: stageX(i) * 0.7, dist: 2.3 } : { tx: 0, dist: 3.7 }; },
        render(p, i) {
          const cols = ["--docs", "--tests", "--workbench", "--bridge", "--core", "--scripts"];
          this.pane = p;
          if (i < NS) {
            p.innerHTML = `<div class="chain"><div class="pulse"></div>` + STAGES.map((s, k) => {
              const out = s.out ? `gibt <b>${esc(s.out)}</b> ${k < NS - 1 ? "an die nächste Stufe weiter" : "aus"}<br>` : "";
              const paths = s.paths || [], cc = s.cc != null ? `<br>höchste Funktionskomplexität <b>${K.fmt(s.cc)}</b>` : "";
              return `<div class="node" data-in style="--col:var(${cols[k % cols.length]});--w:${(((s.loc || 0) / stMax) * 100).toFixed(0)}%"><div class="n" data-say>${k + 1}<i></i></div><div class="t" data-say>${esc(s.de || s.name)}</div><div class="d">${out}${K.fmt(s.loc || 0)} Zeilen in ${esc(paths.slice(0, 3).join(", "))}${paths.length > 3 ? " …" : ""}${cc}</div></div>`;
            }).join("") + `</div>`;
            this.pipe = true; this.stepUpdate(i);
          } else {
            const f = WF[i - NS], steps = f.steps || []; this.pipe = false;
            const meta = [f.trigger ? `<b>${esc(f.trigger)}</b>` : "", f.file ? esc(f.file) : "", f.runner ? `läuft auf ${esc(f.runner)}` : ""].filter(Boolean).join(" · ");
            p.innerHTML = `<div class="h" data-in data-say style="margin:0">${esc(f.name)}</div><p class="p" data-in data-k="wM" style="margin-top:4px">${meta}</p><div class="chain wf" style="height:auto;position:absolute;left:${NARROW ? 18 : 32}px;right:${NARROW ? 18 : 32}px;bottom:${NARROW ? 20 : 28}px;top:104px">` + steps.map((s, k) => `<div class="node${k === steps.length - 1 ? " on" : ""}" data-in style="--col:var(--docs);--w:${k === steps.length - 1 ? 100 : 0}%"><div class="n">${k + 1}</div><div class="t">${esc(s)}</div></div>`).join("") + `</div>`;
            const wm = p.querySelector('[data-k="wM"]'); p.querySelector(".wf").style.top = wm.offsetTop + wm.offsetHeight + 14 + "px";
          }
        },
        stepUpdate(i, prev) {
          if (i >= NS || (prev != null && prev >= NS) || !this.pipe) return false;
          [...this.pane.querySelectorAll(".node")].forEach((n, k) => n.classList.toggle("on", k === i));
          this.sayNode = this.pane.querySelectorAll(".node")[i];
          return true;
        },
      },
    ];
    const chips = CATS.map((c) => { const d = E("div", "chip", $("chips")); d.innerHTML = `<i style="background:${CV(c)}"></i>${esc(LAB[c])} · ${K.kfmt(LOC[c] || 0)}`; d.style.opacity = 0; return d; });

    /* ================= Gerüst: Karte, Fenster, Leiste, Schiene ================= */
    let rect = [0, 0, 0, 0, 0], curForm = "tree";
    function swap(buildFn, dx, dy) {
      const old = host.lastElementChild, p = E("div", "pane"); host.appendChild(p);
      if (reduce || still) p.classList.add("still");
      buildFn(p);
      if (reduce || still) { [...host.children].forEach((c) => c !== p && c.remove()); return; }
      if (old) old.animate([{}, { transform: `translate(${-dx * 80}px,${-dy * 80}px)`, opacity: 0 }], { duration: 300, easing: "cubic-bezier(.4,0,.9,.6)", fill: "forwards" }).onfinish = () => old.remove();
      p.animate([{ transform: `translate(${dx * 120}px,${dy * 120}px)`, opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 780, delay: old ? 140 : 0, easing: OUT, fill: "backwards" });
      [...p.querySelectorAll("[data-in]")].forEach((n, k) => n.animate([{ transform: `translate(${dx * 50}px,${dy * 50 + (dx || dy ? 0 : 18)}px)`, opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 820, delay: (old ? 200 : 60) + k * 70, easing: OUT, fill: "backwards" }));
      const sh = card.querySelector(".sheen"); sh.classList.remove("go"); void sh.offsetWidth; sh.classList.add("go");
    }
    let hasRect = false, tintOn = 0;
    function morph(r) {
      const o = card.getBoundingClientRect(); card.style.transition = "none";
      [card, hostBox].forEach((e) => { e.style.left = r[0] + "px"; e.style.top = r[1] + "px"; e.style.width = r[2] + "px"; e.style.height = r[3] + "px"; e.style.borderRadius = r[4] + "px"; });
      card.style.transform = "none";
      if (hasRect && !reduce && !still && o.width) { card.style.transform = `translate(${o.left - r[0]}px,${o.top - r[1]}px) scale(${o.width / r[2]},${o.height / r[3]})`; void card.offsetWidth; card.style.transition = "transform .9s cubic-bezier(.16,1,.3,1)"; card.style.transform = "none"; }
      hasRect = true;
      if (NARROW) { pv.style.transform = `translate(${L}px,${H - 74}px)`; nx.style.transform = `translate(${W - L - 44}px,${H - 74}px)`; }
      else { const cy = K.clamp(r[1] + r[3] / 2, TOP + 50, BOT - 50); nx.style.transform = `translate(${Math.min(r[0] + r[2], RM + 8) - 20}px,${cy - 36}px)`; pv.style.transform = `translate(${Math.max(r[0], L - 8) - 20}px,${cy - 36}px)`; }
    }
    function tint(c) { const a = [$("tA"), $("tB")], n = a[(tintOn ^= 1)]; n.dataset.ch = c.id; n.style.opacity = 1; a[tintOn ^ 1].style.opacity = 0; }
    function rectFor(c) {
      if (!NARROW) return c.rect();
      const f = c.nf || [0, 1], h = BOT - TOP; return [L, TOP + h * f[0], W - 2 * L, h * (f[1] - f[0]), 26];
    }
    function arrow(d) {
      const c = CH[st.ci]; stopAuto();
      if (c.steps) return setStep(st.step[st.ci] + d, Math.sign(d));
      const a = st.t; let b;
      if (c.settle) { const i = CM.indexOf(nearest(st.t)); b = CM[K.clamp(i + d, 0, CM.length - 1)].t; } else b = K.clamp(a + d * 7 * DAY, T0, T1);
      K.tween(420, (e) => { st.t = K.lerp(a, b, e); c.update(); railPos(); });
    }
    function applyCam(c, i) {
      Object.assign(camT, { tx: 0, ty: 0, tz: 0 }, c.cam, c.camStep ? c.camStep(i) : {});
      if (NARROW) {
        /* Wolke in den freien Streifen über oder unter der Karte schieben */
        const f = c.nf || [0, 1], h = BOT - TOP; let yc = null;
        if (f[0] > 0.05) yc = (TOP + TOP + h * f[0]) / 2; else if (f[1] < 0.95) yc = (TOP + h * f[1] + BOT) / 2;
        camT.ox = 0; camT.oy = yc == null ? 0 : 1 - (2 * yc) / H; camT.dist *= 1.25;
      }
      setHot(c.hot ? c.hot(i) : null, c.hotCol ? c.hotCol(i) : "--alert");
      wake();
    }
    /* Ansage für Screenreader: Kapitel bzw. Schritt plus die Überschrift der Karte */
    let sayN = 0;
    function announce(prefix) {
      const p = host.lastElementChild; if (!p) return;
      const c = CH[st.ci], scope = (c.id === "maschine" && c.pipe && c.sayNode) || p;
      const parts = [...scope.querySelectorAll("[data-say]")].map((e) => (e._v != null ? (e._f || K.fmt)(e._v) : e.textContent.trim())).filter(Boolean);
      const text = prefix + (parts.length ? ": " + parts.join(", ") : "");
      const n = ++sayN; sayEl.textContent = ""; setTimeout(() => { if (n === sayN) sayEl.textContent = text; }, 60);
    }
    const buttons = CH.map((c, k) => { const b = E("button", "", bar, c.label); b.type = "button"; b.dataset.k = k; b.addEventListener("click", () => go(k, Math.sign(k - st.ci) || 1)); return b; });
    function placeLens(n) {
      if (NARROW) { const b = buttons[n]; lensV.style.width = b.offsetWidth + "px"; lensV.style.transform = `translateX(${b.offsetLeft}px)`; const sl = b.offsetLeft - (bar.clientWidth - b.offsetWidth) / 2; bar.scrollTo({ left: Math.max(0, sl), behavior: reduce || still ? "auto" : "smooth" }); }
      else { lensV.style.width = ""; lensV.style.transform = `translateY(${n * 44}px)`; }
    }
    function go(n, dir, opts) {
      n = K.clamp(n, 0, CH.length - 1); if (n === st.ci && dir !== 0) return;
      if (dir) stopAuto();
      const c = CH[n]; dir = dir || 0; st.ci = n; still = !!(opts && opts.still);
      rect = rectFor(c); morph(rect);
      if (c.form !== curForm) { curForm = c.form; setForm(c.form); }
      if (opts && opts.first) fx.mix = 1;
      applyCam(c, st.step[n]); tint(c);
      swap((p) => c.render(p, st.step[n], rect[2], rect[3]), 0, dir);
      buttons.forEach((b, k) => b.setAttribute("aria-current", k === n ? "true" : "false"));
      placeLens(n);
      chips.forEach((ch) => (ch.style.opacity = 0)); buildRail();
      try { history.replaceState(null, "", "#" + c.id); } catch (_) { /* file:// oder Sandbox */ }
      if (dir) announce("Kapitel " + c.label);
      still = false;
    }
    function setStep(i, dir) {
      const c = CH[st.ci]; if (!c.steps) return;
      i = K.clamp(i, 0, c.steps.length - 1); const prev = st.step[st.ci]; if (i === prev) return;
      st.step[st.ci] = i; applyCam(c, i); if (!reduce) fx.nudgeX = -dir * 0.05;
      if (!(c.stepUpdate && c.stepUpdate(i, prev))) swap((p) => c.render(p, i, rect[2], rect[3]), dir, 0);
      railPos(); announce(c.stepText ? c.stepText(i) : c.steps[i]);
    }
    let railW = 0;
    function buildRail() {
      const c = CH[st.ci];
      if (NARROW) { railW = W - 2 * L - 104; rail.style.left = L + 52 + "px"; } else { railW = Math.min(720, RM - L - 80); rail.style.left = L + (RM - L - railW) / 2 + "px"; }
      rail.style.width = railW + "px"; ticks.textContent = ""; const iw = railW - 52;
      if (c.steps) c.steps.forEach((s, k) => { E("i", "", ticks).style.left = (c.steps.length > 1 ? (k / (c.steps.length - 1)) * iw : iw / 2) + "px"; });
      else { let lastX = -1e9; weekTicks().forEach((t) => { const x = ((t - T0) / (T1 - T0)) * iw; E("s", "", ticks).style.left = x + "px"; const lab = K.date(t + 10800); if (x + 4 < lastX + 8) return; const e = E("em", "", ticks, lab); e.style.left = x + "px"; const ew = e.offsetWidth || lab.length * 7.5; if (x + 4 + ew > iw + 20) { e.remove(); return; } lastX = x + 4 + ew; }); }
      rail.setAttribute("aria-label", c.steps ? `Schritt im Kapitel ${c.label}` : "Zeitpunkt");
      railPos();
    }
    const nDays = Math.max(1, Math.round((T1 - T0) / DAY));
    function railPos() {
      const c = CH[st.ci], iw = railW - 52, n = c.steps ? c.steps.length : 0, f = c.steps ? (n > 1 ? st.step[st.ci] / (n - 1) : 0.5) : (st.t - T0) / (T1 - T0);
      lensH.textContent = c.steps ? c.steps[st.step[st.ci]] : K.date(st.t);
      const lw = lensH.offsetWidth; lensH.style.transform = `translateX(${K.clamp(26 + f * iw - lw / 2, 5, railW - lw - 7).toFixed(1)}px)`;
      const atEnd = c.steps ? st.step[st.ci] >= n - 1 : st.t >= T1 - 1, atStart = c.steps ? st.step[st.ci] <= 0 : st.t <= T0 + 1;
      nx.classList.toggle("hid", atEnd); pv.classList.toggle("hid", atStart);
      nx.setAttribute("aria-disabled", atEnd ? "true" : "false"); pv.setAttribute("aria-disabled", atStart ? "true" : "false");
      if (c.steps) { rail.setAttribute("aria-valuemin", "1"); rail.setAttribute("aria-valuemax", String(n)); rail.setAttribute("aria-valuenow", String(st.step[st.ci] + 1)); rail.setAttribute("aria-valuetext", `${st.step[st.ci] + 1} von ${n}: ${c.stepText ? c.stepText(st.step[st.ci]) : c.steps[st.step[st.ci]]}`); }
      else { rail.setAttribute("aria-valuemin", "0"); rail.setAttribute("aria-valuemax", String(nDays)); rail.setAttribute("aria-valuenow", String(Math.round((st.t - T0) / DAY))); rail.setAttribute("aria-valuetext", c.valueText ? c.valueText() : K.dateLong(st.t)); }
      wake();
    }
    function layout(first) {
      W = innerWidth; H = innerHeight; NARROW = W < 720; root.classList.toggle("narrow", NARROW);
      if (NARROW) { L = 16; RM = W - 16; TOP = 74; BOT = H - 86; }
      else { L = 30; RM = W - 146 - 48; TOP = EMBED ? Math.max(26, H * 0.045) : Math.max(52, H * 0.075); BOT = H - 98; }
      if (gl) { const d = Math.min(1.5, devicePixelRatio || 1); cv.width = Math.round(W * d); cv.height = Math.round(H * d); gl.viewport(0, 0, cv.width, cv.height); }
      go(st.ci, 0, first ? { first: true } : { still: true });
    }

    /* ================= Zeiger: quer = im Kapitel, hoch/runter = Kapitel (nicht eingebettet) ================= */
    let mode = null, wheelSettle = 0, fling = 0;
    const TEXT = ".p,.h,.big,.mono,.facts,.method,.node .d,.node .t,.hr span,#msg";
    K.gesture(document.body, {
      skip: (e) => !!e.target.closest(".tab,#msg") || (NARROW && !!e.target.closest("#bar")) || (e.pointerType === "mouse" && !!e.target.closest(TEXT)),
      down(e) {
        stopAuto(); cancelAnimationFrame(fling);
        mode = e.target.closest("#bar") ? "bar" : e.target.closest("#rail") ? "rail" : null;
        if (mode === "rail") { lensH.classList.add("live"); railMove(e.x); }
      },
      dragstart(e) {
        if (mode === "bar") { lensV.classList.add("live"); return; }
        if (mode) return;
        const vert = Math.abs(e.ty) > Math.abs(e.tx); mode = vert ? (EMBED ? "none" : "v") : "h"; host.style.transition = "none";
        if (mode === "h") { const s = getSelection && getSelection(); if (s && !s.isCollapsed) s.removeAllRanges(); }
      },
      drag(e) {
        const c = CH[st.ci];
        if (mode === "bar") return barMove(e.y);
        if (mode === "rail") return railMove(e.x);
        if (mode === "v") { host.style.transform = `translateY(${e.ty * 0.28}px)`; host.style.opacity = 1 - Math.min(0.7, Math.abs(e.ty) / 420); if (!reduce) fx.nudgeY = -e.ty * 0.0007; wake(); }
        else if (mode === "h") {
          if (c.scrub) { c.scrub(e.dx); railPos(); }
          else if (c.dragRot) c.dragRot(e.tx);
          else { host.style.transform = `translateX(${e.tx * 0.3}px)`; if (!reduce) fx.nudgeX = -e.tx * 0.00035; wake(); }
        }
      },
      dragend(e) {
        const c = CH[st.ci]; host.style.transition = "transform .6s " + OUT + ",opacity .4s"; host.style.transform = ""; host.style.opacity = "";
        if (mode === "v") { const d = e.ty < -64 || e.vy < -0.45 ? 1 : e.ty > 64 || e.vy > 0.45 ? -1 : 0; if (d) go(st.ci + d, d); }
        else if (mode === "h") {
          if (c.scrub) {
            if (c.settle) c.settle();
            else if (!reduce && Math.abs(e.vx) > 0.2) { let v = e.vx * 16; const m0 = mode; const f = () => { if (Math.abs(v) < 0.4 || mode !== null || st.ci !== CH.indexOf(c)) return; c.scrub(v); railPos(); v *= 0.93; fling = requestAnimationFrame(f); }; mode = null; void m0; fling = requestAnimationFrame(f); }
          } else { if (c.dragEnd) c.dragEnd(); const d = e.tx < -56 || e.vx < -0.4 ? 1 : e.tx > 56 || e.vx > 0.4 ? -1 : 0; if (d) setStep(st.step[st.ci] + d, d); }
        }
        finish();
      },
      tap() { finish(); },
      cancel() {
        host.style.transition = "transform .3s " + OUT + ",opacity .3s"; host.style.transform = ""; host.style.opacity = "";
        const c = CH[st.ci]; if (mode === "h" && c.dragEnd) c.dragEnd();
        if (mode === "bar") { lensV.classList.remove("live"); placeLens(st.ci); }
        if (mode === "rail") { lensH.classList.remove("live"); railPos(); }
        mode = null;
      },
      wheel(e) {
        const c = CH[st.ci]; if (!c.scrub) return false;
        stopAuto(); c.scrub(e.dx); railPos();
        if (c.settle) { clearTimeout(wheelSettle); wheelSettle = setTimeout(() => c.settle(), 180); }
        return true;
      },
    });
    function finish() {
      if (mode === "bar") {
        if (lensV.classList.contains("live")) { lensV.classList.remove("live"); const k = K.clamp(Math.round(barY / 44), 0, CH.length - 1); if (k !== st.ci) go(k, Math.sign(k - st.ci)); else placeLens(k); }
      }
      if (mode === "rail") { lensH.classList.remove("live"); const c = CH[st.ci]; if (c.settle) c.settle(); railPos(); }
      mode = null;
    }
    let barY = 0;
    function barMove(y) { const r = bar.getBoundingClientRect(); barY = K.clamp(y - r.top - 7 - 22, 0, (CH.length - 1) * 44); lensV.style.transform = `translateY(${barY}px)`; }
    function railMove(x) {
      const c = CH[st.ci], r = rail.getBoundingClientRect(), iw = railW - 52, f = K.clamp((x - r.left - 26) / iw, 0, 1);
      if (c.steps) { const k = Math.round(f * (c.steps.length - 1)); if (k !== st.step[st.ci]) setStep(k, Math.sign(k - st.step[st.ci])); lensH.style.transform = `translateX(${K.clamp(26 + f * iw - lensH.offsetWidth / 2, 5, railW - lensH.offsetWidth - 7).toFixed(1)}px)`; }
      else { st.t = T0 + f * (T1 - T0); c.update(); railPos(); }
    }
    function jumpTo(end) {
      const c = CH[st.ci]; stopAuto();
      if (c.steps) return setStep(end ? c.steps.length - 1 : 0, end ? 1 : -1);
      st.t = end ? T1 : T0; if (c.settle) st.t = (end ? CM[CM.length - 1] : CM[0]).t; c.update(); railPos();
    }
    pv.addEventListener("click", () => arrow(-1));
    nx.addEventListener("click", () => arrow(1));
    rail.addEventListener("keydown", (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const k = e.key, big = CH[st.ci].steps ? 1 : 4;
      if (k === "ArrowRight" || k === "ArrowUp") arrow(1);
      else if (k === "ArrowLeft" || k === "ArrowDown") arrow(-1);
      else if (k === "PageUp") arrow(big);
      else if (k === "PageDown") arrow(-big);
      else if (k === "Home") jumpTo(false);
      else if (k === "End") jumpTo(true);
      else return;
      e.preventDefault(); e.stopPropagation();
    });
    addEventListener("keydown", (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
      if (e.key === "ArrowDown") { go(st.ci + 1, 1); e.preventDefault(); }
      else if (e.key === "ArrowUp") { go(st.ci - 1, -1); e.preventDefault(); }
      else if (e.key === "ArrowRight") { arrow(1); e.preventDefault(); }
      else if (e.key === "ArrowLeft") { arrow(-1); e.preventDefault(); }
    });

    /* ================= Farbschema, Einbettung, Lebenszyklus ================= */
    const mqDark = matchMedia("(prefers-color-scheme: dark)");
    function refreshTheme() {
      readColors(); readCloud(); uploadColors();
      go(st.ci, 0, { still: true }); wake();
    }
    function setTheme(t) {
      if (t === "light" || t === "dark") { delete root.dataset.themeAuto; if (root.dataset.theme === t) return; root.dataset.theme = t; }
      else if (t === "system") { root.dataset.themeAuto = "1"; root.dataset.theme = mqDark.matches ? "dark" : "light"; }
      else return;
      refreshTheme();
    }
    const onMq = (mq, fn) => (mq.addEventListener ? mq.addEventListener("change", fn) : mq.addListener(fn));
    onMq(mqDark, () => { if (root.dataset.themeAuto) { root.dataset.theme = mqDark.matches ? "dark" : "light"; refreshTheme(); } });
    onMq(mqReduce, () => { reduce = K.reduce = mqReduce.matches; if (reduce) stopAuto(); go(st.ci, 0, { still: true }); wake(); });
    addEventListener("message", (e) => {
      if (e.origin !== location.origin || (e.source !== window.parent && e.source !== window)) return;
      const d = e.data; if (!d || typeof d !== "object") return;
      if (d.type === "codebase:theme") setTheme(d.theme);
      else if (d.type === "codebase:chapter") { const k = CH.findIndex((c) => c.id === d.id); if (k >= 0 && k !== st.ci) go(k, Math.sign(k - st.ci)); }
    });
    addEventListener("hashchange", () => { const k = CH.findIndex((c) => c.id === location.hash.slice(1)); if (k >= 0 && k !== st.ci) go(k, Math.sign(k - st.ci)); });
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => layout(false), 150); });
    addEventListener("pagehide", () => { alive = false; if (rafId) cancelAnimationFrame(rafId); rafId = 0; stopAuto(); });
    addEventListener("pageshow", (e) => { if (e.persisted) { alive = true; wake(); } });
    document.addEventListener("visibilitychange", () => { visible = !document.hidden; wake(); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((es) => { visible = es[es.length - 1].isIntersecting && !document.hidden; if (visible) { wake(); maybeAutoplay(); } }).observe(root);
    }

    /* Vorlauf: Wachstum spielt einmal von leer bis heute, sobald die Bühne sichtbar ist. */
    function stopAuto() { if (st.auto && !st.autoStarted) st.t = T1; st.auto = false; }
    function maybeAutoplay() {
      if (!st.auto || st.autoStarted || st.ci !== 0 || !W) return;
      st.autoStarted = true; const t0 = performance.now();
      const play = (now) => {
        if (!st.auto) return;
        const u = K.clamp((now - t0 - 500) / 5200, 0, 1), e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
        st.t = K.lerp(T0, T1, e); if (st.ci === 0) CH[0].update(); railPos();
        if (u < 1) requestAnimationFrame(play); else st.auto = false;
      };
      requestAnimationFrame(play);
    }

    const mark = $("mark"), gen = M.generated;
    const genT = typeof gen === "number" ? gen * (gen < 1e12 ? 1 : 0.001) : gen ? Date.parse(gen) / 1000 : null;
    mark.innerHTML = `<b>${esc(String(M.repo || "picam-ai").split("/").pop())}</b>${esc(M.focus || "")}${M.tip ? " · " + esc(M.tip) : ""}${genT && isFinite(genT) ? " · Stand " + esc(K.dateFull(genT)) : ""}`;

    const fontsReady = document.fonts && document.fonts.load
      ? Promise.race([Promise.all(['700 40px "Bricolage Grotesque"', '500 20px "Bricolage Grotesque"', '400 15px "Onest"', '600 15px "Onest"', '400 11px "Martian Mono"'].map((f) => document.fonts.load(f))), new Promise((r) => setTimeout(r, 1500))]).catch(() => {})
      : Promise.resolve();
    fontsReady.then(() => {
      const want = CH.findIndex((c) => c.id === location.hash.slice(1));
      if (want > 0 || reduce || location.hash === "#wachstum") { st.t = T1; st.ci = Math.max(0, want); st.auto = false; }
      layout(true);
      if (!("IntersectionObserver" in window)) maybeAutoplay();
      else if (visible) maybeAutoplay();
    });
  }
})();
