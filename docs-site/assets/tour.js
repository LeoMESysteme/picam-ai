/* Projekt-Tour (docs/uebersicht/projekt-tour.md): Kapitel und Schritte als
 * animierte SVG-Bühne.
 *
 * Die Texte stehen im Markdown. Jeder `.tour-step` ist ein Schritt, seine
 * h3-ID ist zugleich Szenenname und Direktlink (#erkennung-zelle). Ohne
 * JavaScript bleibt die Seite als Text lesbar; dieses Skript ergänzt nur die
 * Bühne. Fehlt zu einer ID die Szene, zeigt die Bühne einen Platzhalter, und
 * der Docs-Test schlägt fehl.
 *
 * anime.js 4.5.0 liegt als lokale Kopie unter assets/vendor/ (die Doku liegt
 * hinter einer Anmeldung und lädt keine fremden Skripte) und wird nur auf
 * dieser Seite nachgeladen. Farben kommen aus CSS-Klassen (tour.css), damit
 * der Wechsel zwischen hellem und dunklem Theme ohne Neuzeichnen greift.
 *
 * Inhaltliche Regel: Die Bühne zeigt nur, was der Code tut. Geplantes ist
 * bernsteinfarben und gestrichelt, Zahlen sind als Beispiel gekennzeichnet. */
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  // Absolut und damit auch nach einer Sofortnavigation gültig (vgl. fortschritt.js).
  const SCRIPT_SRC = document.currentScript ? document.currentScript.src : "";
  // Wurzel der Doku-Seite (tour.js liegt unter assets/), für Links von der Bühne.
  const SITE_ROOT = new URL("../", SCRIPT_SRC || document.baseURI).href;
  const ANIME_FILE = "vendor/anime-4.5.0.umd.min.js";
  const W = 960;
  const H = 540;

  let animePromise = null;
  let factsPromise = null;
  let active = null;
  // Werte aus dem Code, erzeugt von scripts/tour-facts.py. Die Szenen lesen
  // sie über fact(id, fallback); der Fallback ist der Stand beim Schreiben der
  // Szene und greift nur, wenn die Datei nicht geladen werden kann.
  let facts = {};

  function fact(id, fallback) {
    const entry = facts[id];
    return entry && entry.value !== undefined ? entry.value : fallback;
  }

  function loadFacts() {
    if (!factsPromise) {
      const url = new URL("data/tour-facts.json", SCRIPT_SRC || document.baseURI).href;
      factsPromise = fetch(url, { cache: "no-cache" })
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
        .then((data) => {
          facts = (data && data.facts) || {};
          applyFacts();
        })
        .catch((error) => {
          factsPromise = null;
          console.warn(`Projekt-Tour: Faktendatei nicht geladen (${error.message}), Szenen zeigen den Stand ihres Entwurfs.`);
        });
    }
    return factsPromise;
  }

  // Deutsche Zahl mit Komma, ohne überflüssige Nachkommastellen.
  function num(value, digits) {
    return Number(value).toLocaleString("de-DE", { maximumFractionDigits: digits === undefined ? 3 : digits });
  }

  function loadAnime() {
    if (window.anime && window.anime.createTimeline) return Promise.resolve(window.anime);
    if (!animePromise) {
      animePromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = new URL(ANIME_FILE, SCRIPT_SRC || document.baseURI).href;
        script.onload = () => (window.anime ? resolve(window.anime) : reject(new Error("anime.js fehlt")));
        script.onerror = () => reject(new Error("anime.js nicht ladbar"));
        document.head.appendChild(script);
      }).catch((error) => {
        animePromise = null;
        throw error;
      });
    }
    return animePromise;
  }

  // ---------------------------------------------------------------- Helfer --

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function svg(tag, attrs, parent) {
    const element = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value !== undefined && value !== null) element.setAttribute(key, String(value));
    }
    if (parent) parent.appendChild(element);
    return element;
  }

  function group(parent, cls, attrs) {
    return svg("g", Object.assign({ class: cls }, attrs), parent);
  }

  function label(parent, x, y, text, cls, attrs) {
    const element = svg("text", Object.assign({ x, y, class: cls || "t-label" }, attrs), parent);
    element.textContent = text;
    return element;
  }

  function flat(items) {
    const out = [];
    for (const item of items) {
      if (!item) continue;
      if (item instanceof Element) out.push(item);
      else out.push(...flat(Array.from(item)));
    }
    return out;
  }

  function hidden(...elements) {
    for (const element of flat(elements)) element.style.opacity = "0";
    return elements.length === 1 ? elements[0] : elements;
  }

  // Breite eines Textes auf der Bühne; vor dem ersten Rendern geschätzt.
  function textWidth(element, fallbackPerChar) {
    try {
      const width = element.getComputedTextLength();
      if (width > 0) return width;
    } catch (error) {
      // nicht gerendert
    }
    return element.textContent.length * fallbackPerChar;
  }

  function points(list) {
    return list.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  }

  function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
  }

  // Deterministisches Rauschen, damit jede Wiederholung gleich aussieht.
  function seeded(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state * 1664525 + 1013904223) >>> 0;
      return state / 4294967296;
    };
  }

  // ------------------------------------------------------------ Geometrie --
  // Affine Abbildung aus Verschiebung, Drehung, Scherung und Skalierung. Sie
  // ersetzt die Perspektive der Kamera schematisch; Viereck und Anzeige werden
  // aus derselben Matrix berechnet und passen deshalb in jedem Zwischenbild.

  function matrix(p) {
    const r = (p.rot * Math.PI) / 180;
    const kx = Math.tan((p.skx * Math.PI) / 180);
    const ky = Math.tan((p.sky * Math.PI) / 180);
    const a0 = (1 + kx * ky) * p.s;
    const c0 = kx * p.s;
    const b0 = ky * p.s;
    const d0 = p.s;
    const cos = Math.cos(r);
    const sin = Math.sin(r);
    return {
      a: cos * a0 - sin * b0, b: sin * a0 + cos * b0,
      c: cos * c0 - sin * d0, d: sin * c0 + cos * d0,
      e: p.tx, f: p.ty,
    };
  }

  function apply(m, x, y) {
    return [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
  }

  function matrixAttr(m) {
    return `matrix(${[m.a, m.b, m.c, m.d, m.e, m.f].map((v) => v.toFixed(4)).join(" ")})`;
  }

  function lerpParams(p0, p1, t) {
    const out = {};
    for (const key of Object.keys(p0)) out[key] = p0[key] + (p1[key] - p0[key]) * t;
    return out;
  }

  // ------------------------------------------------------ Punktraster-LCD --
  // HD44780, ROM A00, 5 × 8 Punkte (7 Zeilen Zeichen, 8. Zeile Cursor). Die
  // Ziffern, ".", "+" und " " sind aus src/dispread/ocr/dotmatrix_font.py
  // übernommen; "m", "V" und "/" ergänzen die Einheit für die Darstellung.
  const ROM = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110", "00000"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110", "00000"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111", "00000"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110", "00000"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010", "00000"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110", "00000"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110", "00000"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000", "00000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110", "00000"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000", "00000"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "m": ["00000", "00000", "11010", "10101", "10101", "10001", "10001", "00000"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100", "00000"],
    "/": ["00000", "00001", "00010", "00100", "01000", "10000", "00000", "00000"],
  };
  // Die Klassen, die der Dot-Matrix-Leser kennt (dotmatrix_font.CLASSES).
  const READER_CLASSES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "+", " "];

  // Zeichensatz und Klassen kommen aus dem Code (ocr.rom_a00, ocr.classes);
  // die Einheitszeichen m, V und / bleiben Ergänzungen der Darstellung.
  function applyFacts() {
    const rom = fact("ocr.rom_a00", null);
    if (rom) Object.assign(ROM, rom);
    const classes = fact("ocr.classes", null);
    if (Array.isArray(classes)) READER_CLASSES.splice(0, READER_CLASSES.length, ...classes);
  }
  const DISPLAY = "+0.46761 mV/V   ";
  const LCD_PAD_X = 2;
  const LCD_PAD_Y = 2.5;
  const LCD_W = 16 * 6 - 1 + 2 * LCD_PAD_X;
  const LCD_H = 8 + 2 * LCD_PAD_Y;
  const DOT = 0.8;

  function glyphVector(ch) {
    return ROM[ch].join("").split("").map(Number);
  }

  function dotsPath(x0, y0, u, filter) {
    let d = "";
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 5; c++) {
        if (!filter(c, r)) continue;
        const x = x0 + c * u;
        const y = y0 + r * u;
        d += `M${x.toFixed(2)} ${y.toFixed(2)}h${(DOT * u).toFixed(2)}v${(DOT * u).toFixed(2)}h${(-DOT * u).toFixed(2)}z`;
      }
    }
    return d;
  }

  // Zeichnet eine 16-stellige Anzeige mit Glas an (x, y); u = Punktabstand.
  function drawLCD(parent, text, x, y, u) {
    const root = group(parent, "lcd");
    svg("rect", { x, y, width: LCD_W * u, height: LCD_H * u, rx: u * 0.8, class: "tp-lcd" }, root);
    const cells = [];
    for (let i = 0; i < 16; i++) {
      const ch = ROM[text[i]] ? text[i] : " ";
      const cx = x + (LCD_PAD_X + i * 6) * u;
      const cy = y + LCD_PAD_Y * u;
      const cell = group(root, "lcd-cell");
      svg("path", { d: dotsPath(cx, cy, u, () => true), class: "tp-dot-off" }, cell);
      svg("path", { d: dotsPath(cx, cy, u, (c, r) => ROM[ch][r][c] === "1"), class: "tp-dot-on" }, cell);
      cells.push(cell);
    }
    return { root, cells };
  }

  // Zellrechteck (Glas-Koordinaten in Punktabständen).
  function cellBox(i) {
    return { x: LCD_PAD_X + i * 6 - 0.4, y: LCD_PAD_Y - 0.4, w: 5.0, h: 8.0 };
  }

  // ------------------------------------------------------ Bausteine Szene --

  function chip(parent, x, y, text, cls) {
    const root = group(parent, `chip ${cls || ""}`);
    const t = label(root, x + 10, y + 17, text, "chip-text");
    const width = Math.max(40, textWidth(t, 7) + 20);
    const rect = svg("rect", { x, y, width, height: 26, rx: 13, class: "chip-bg" });
    root.insertBefore(rect, t);
    return root;
  }

  function badge(parent, x, y, text, kind, width) {
    const root = group(parent, `badge badge--${kind}`);
    const t = label(root, x, y + 5, text, "badge-text", { "text-anchor": "middle" });
    const w = width || Math.max(70, textWidth(t, 7.5) + 24);
    root.insertBefore(svg("rect", { x: x - w / 2, y: y - 14, width: w, height: 28, rx: 14 }), t);
    return root;
  }

  function panel(parent, x, y, w, h, cls) {
    return svg("rect", { x, y, width: w, height: h, rx: 10, class: cls || "t-panel" }, parent);
  }

  function arrow(parent, d, cls) {
    return svg("path", { d, class: cls || "t-flow-line", "marker-end": "url(#tour-arrow)" }, parent);
  }

  function checkMark(parent, x, y, kind) {
    const root = group(parent, `mark mark--${kind}`);
    svg("circle", { cx: x, cy: y, r: 11 }, root);
    if (kind === "ok") svg("path", { d: `M${x - 5} ${y}l3.5 3.8l6.5-7.6`, class: "mark-stroke" }, root);
    else svg("path", { d: `M${x - 4.5} ${y - 4.5}l9 9M${x + 4.5} ${y - 4.5}l-9 9`, class: "mark-stroke" }, root);
    return root;
  }

  function streamCam(parent, x, y, scale) {
    const root = group(parent, "cam", { transform: `translate(${x} ${y}) scale(${scale || 1})` });
    svg("rect", { x: -26, y: -34, width: 52, height: 64, rx: 12, class: "tp-cam" }, root);
    svg("circle", { cx: 0, cy: -4, r: 17, class: "tp-cam-ring" }, root);
    svg("circle", { cx: 0, cy: -4, r: 10, class: "tp-lens" }, root);
    svg("circle", { cx: -3.5, cy: -7.5, r: 3, class: "tp-lens-glint" }, root);
    return root;
  }

  // Der Messverstärker in Gerätekoordinaten um den Ursprung (560 × 250).
  const LCD_U = 4.4;
  const LCD_X = -230;
  const LCD_Y = -80;

  function drawDevice(parent) {
    const root = group(parent, "device");
    const body = group(root, "device-body");
    svg("rect", { x: -280, y: -125, width: 560, height: 250, rx: 16, class: "tp-body" }, body);
    svg("rect", { x: -280, y: 105, width: 560, height: 20, rx: 8, class: "tp-body-shade" }, body);
    label(body, -258, -98, "GSV-2AS", "tp-body-text");
    ["MENU", "▲", "▼", "ENTER"].forEach((name, i) => {
      svg("rect", { x: -230 + i * 72, y: 30, width: 58, height: 30, rx: 6, class: "tp-key" }, body);
      label(body, -201 + i * 72, 50, name, "tp-key-text", { "text-anchor": "middle" });
    });
    ["POWER", "SENSOR", "ERROR"].forEach((name, i) => {
      svg("circle", { cx: 150, cy: 22 + i * 26, r: 6, class: i === 0 ? "tp-led-on" : "tp-led" }, body);
      label(body, 164, 26 + i * 26, name, "tp-key-text");
    });
    const lcd = group(root, "device-lcd");
    svg("rect", { x: LCD_X - 12, y: LCD_Y - 12, width: LCD_W * LCD_U + 24, height: LCD_H * LCD_U + 24, rx: 8, class: "tp-bezel" }, lcd);
    const display = drawLCD(lcd, DISPLAY, LCD_X, LCD_Y, LCD_U);
    return { root, body, lcd, display };
  }

  // Ecken einer Zelle oder des Glases in Gerätekoordinaten.
  function glassCorners() {
    const w = LCD_W * LCD_U;
    const h = LCD_H * LCD_U;
    return [[LCD_X, LCD_Y], [LCD_X + w, LCD_Y], [LCD_X + w, LCD_Y + h], [LCD_X, LCD_Y + h]];
  }

  function cellCorners(i) {
    const b = cellBox(i);
    const x = LCD_X + b.x * LCD_U;
    const y = LCD_Y + b.y * LCD_U;
    const w = b.w * LCD_U;
    const h = b.h * LCD_U;
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  }

  // Drei Ansichten des Geräts: im Kamerabild (schräg), entzerrt (groß) und
  // entzerrt als Kopfzeile für die Lese-Schritte.
  const VIEW_CAMERA = { tx: 480, ty: 290, s: 0.92, rot: -3, skx: -10, sky: 4 };
  const GLASS_CX = LCD_X + (LCD_W * LCD_U) / 2;
  const GLASS_CY = LCD_Y + (LCD_H * LCD_U) / 2;
  const RECT_S = 832 / (LCD_W * LCD_U);
  const VIEW_RECT = { tx: 480 - GLASS_CX * RECT_S, ty: 270 - GLASS_CY * RECT_S, s: RECT_S, rot: 0, skx: 0, sky: 0 };
  const HEAD_S = RECT_S * 0.62;
  const VIEW_HEAD = { tx: 480 - GLASS_CX * HEAD_S, ty: 88 - GLASS_CY * HEAD_S, s: HEAD_S, rot: 0, skx: 0, sky: 0 };

  const FRAME = { x: 120, y: 60, w: 720, h: 405 };

  // Kamerabild mit Gerät, Bildnummer und Zeitstempel. `state` steuert, welche
  // Teile schon sichtbar sind; die Szenen blenden den Rest selbst ein.
  function cameraScene(layer, options) {
    const opts = Object.assign({ quad: false, view: VIEW_CAMERA }, options);
    const cam = group(layer, "cam-wrap");
    streamCam(cam, 62, 262, 1.05);
    const frame = group(layer, "frame");
    svg("rect", { x: FRAME.x, y: FRAME.y, width: FRAME.w, height: FRAME.h, rx: 10, class: "tp-frame" }, frame);
    svg("rect", { x: FRAME.x, y: FRAME.y + 300, width: FRAME.w, height: 105, rx: 10, class: "tp-table" }, frame);
    const deviceLayer = group(layer, "device-layer");
    const device = drawDevice(deviceLayer);
    const quad = svg("polygon", { class: "quad", points: "" }, layer);
    const handles = group(layer, "handles");
    const handleDots = [0, 1, 2, 3].map(() => svg("circle", { r: 7, class: "quad-handle" }, handles));
    const flash = svg("rect", { x: FRAME.x, y: FRAME.y, width: FRAME.w, height: FRAME.h, rx: 10, class: "tp-flash" }, layer);
    flash.style.opacity = "0";
    const chips = group(layer, "frame-chips");
    const seqChip = chip(chips, FRAME.x + 16, FRAME.y + 16, "Bild 1842 · Beispiel", "chip--dark");
    const timeChip = chip(chips, FRAME.x + 16, FRAME.y + FRAME.h - 42, "t = 812 345 678 901 ns · CLOCK_MONOTONIC", "chip--dark");

    const state = { device: Object.assign({}, opts.view), quad: Object.assign({}, opts.view) };
    function render() {
      const m = matrix(state.device);
      device.root.setAttribute("transform", matrixAttr(m));
      const mq = matrix(state.quad);
      const corners = glassCorners().map(([x, y]) => apply(mq, x, y));
      quad.setAttribute("points", points(corners));
      corners.forEach(([x, y], i) => {
        handleDots[i].setAttribute("cx", x.toFixed(1));
        handleDots[i].setAttribute("cy", y.toFixed(1));
      });
    }
    render();
    if (!opts.quad) hidden(quad, handles);
    return { cam, frame, device, quad, handles, handleDots, flash, chips, seqChip, timeChip, state, render };
  }

  // Nur die entzerrte Anzeige (ohne Kamerabild) in einer der festen Ansichten.
  function rectifiedScene(layer, view) {
    const deviceLayer = group(layer, "device-layer");
    const device = drawDevice(deviceLayer);
    device.body.style.opacity = "0";
    const state = Object.assign({}, view);
    function render() {
      device.root.setAttribute("transform", matrixAttr(matrix(state)));
    }
    render();
    return { device, state, render, matrix: () => matrix(state) };
  }

  function cellPolygon(m, i) {
    return points(cellCorners(i).map(([x, y]) => apply(m, x, y)));
  }

  function cellCenter(m, i) {
    const c = cellCorners(i);
    return apply(m, (c[0][0] + c[2][0]) / 2, (c[0][1] + c[2][1]) / 2);
  }

  // Ein Weg mit einem Punkt, der ihn entlangläuft (eigene Bahnberechnung statt
  // createMotionPath, damit die skalierte SVG-Bühne keine Rolle spielt).
  function travel(tl, A, path, dot, params, position) {
    const length = path.getTotalLength();
    const proxy = { t: 0 };
    const place = () => {
      const p = path.getPointAtLength(proxy.t * length);
      dot.setAttribute("cx", p.x.toFixed(1));
      dot.setAttribute("cy", p.y.toFixed(1));
    };
    place();
    tl.add(proxy, Object.assign({ t: [0, 1], ease: "inOutSine", duration: 1200, onUpdate: place }, params), position);
  }

  function drawIn(tl, A, element, params, position) {
    hidden(element);
    const drawable = A.svg.createDrawable(element);
    tl.set(element, { opacity: 1 }, position);
    tl.add(drawable, Object.assign({ draw: ["0 0", "0 1"], duration: 900, ease: "inOutQuad" }, params), "<<");
  }

  function popIn(tl, A, targets, params, position) {
    hidden(Array.from(targets.length !== undefined ? targets : [targets]));
    tl.add(targets, Object.assign({
      opacity: [0, 1],
      scale: [0.4, 1],
      ease: "outBack(1.8)",
      duration: 520,
    }, params), position);
  }

  function fadeUp(tl, targets, params, position) {
    hidden(Array.from(targets.length !== undefined ? targets : [targets]));
    tl.add(targets, Object.assign({
      opacity: [0, 1],
      translateY: [18, 0],
      ease: "outExpo",
      duration: 700,
    }, params), position);
  }

  // ------------------------------------------------------- Szenen Überblick --

  const BENCH_Y = 404;

  function benchScene(layer, tour) {
    const refs = {};
    refs.title = group(layer, "bench-title");
    label(refs.title, 40, 62, "picam-ai · dispread", "t-title");
    label(refs.title, 40, 90, "Messanzeigen optisch lesen – Werte nachvollziehbar erfassen", "t-subtitle");

    refs.ground = svg("path", { d: `M24 ${BENCH_Y}H936`, class: "t-ground" }, layer);

    // Prüfling mit kleiner Anzeige.
    refs.device = group(layer, "bench-device");
    const dev = group(refs.device, "", { transform: "translate(40 268)" });
    svg("rect", { x: 0, y: 0, width: 262, height: 136, rx: 12, class: "tp-body" }, dev);
    label(dev, 16, 24, "GSV-2AS", "tp-body-text tp-small");
    svg("rect", { x: 14, y: 36, width: LCD_W * 2.2 + 12, height: LCD_H * 2.2 + 12, rx: 6, class: "tp-bezel" }, dev);
    drawLCD(dev, DISPLAY, 20, 42, 2.2);
    for (let i = 0; i < 4; i++) svg("rect", { x: 18 + i * 44, y: 96, width: 34, height: 18, rx: 4, class: "tp-key" }, dev);
    svg("circle", { cx: 232, cy: 104, r: 5, class: "tp-led-on" }, dev);

    // Kamera auf Stativ, Blick nach links auf die Anzeige.
    refs.cone = svg("polygon", { points: "352,286 254,308 254,342 352,300", class: "t-cone" }, layer);
    refs.camera = group(layer, "bench-camera");
    svg("path", { d: `M372 316V${BENCH_Y - 6}M352 ${BENCH_Y - 4}h40`, class: "t-stand" }, refs.camera);
    streamCam(refs.camera, 372, 296, 0.82);

    // Kabel zum Pi.
    refs.cable = svg("path", { d: `M392 300C430 300 430 382 486 382`, class: "t-cable" }, layer);

    // Raspberry Pi 5.
    refs.pi = group(layer, "bench-pi");
    svg("rect", { x: 486, y: 362, width: 132, height: 38, rx: 5, class: "tp-pcb" }, refs.pi);
    svg("rect", { x: 528, y: 368, width: 34, height: 26, rx: 3, class: "tp-chip-ic" }, refs.pi);
    svg("rect", { x: 572, y: 370, width: 18, height: 12, rx: 2, class: "tp-port" }, refs.pi);
    svg("rect", { x: 596, y: 370, width: 18, height: 12, rx: 2, class: "tp-port" }, refs.pi);
    label(refs.pi, 552, 352, "Raspberry Pi 5", "t-small", { "text-anchor": "middle" });

    // Werkbank im Browser.
    refs.browser = group(layer, "bench-browser");
    panel(refs.browser, 650, 118, 270, 168, "t-window");
    svg("rect", { x: 650, y: 118, width: 270, height: 24, rx: 10, class: "t-window-bar" }, refs.browser);
    [0, 1, 2].forEach((i) => svg("circle", { cx: 664 + i * 12, cy: 130, r: 3.5, class: "t-window-dot" }, refs.browser));
    label(refs.browser, 702, 135, "Werkbank", "t-small");
    svg("rect", { x: 664, y: 152, width: 242, height: 66, rx: 6, class: "tp-frame" }, refs.browser);
    drawLCD(refs.browser, DISPLAY, 672, 170, 2.35);
    svg("rect", { x: 670, y: 167, width: LCD_W * 2.35 + 4, height: LCD_H * 2.35 + 6, class: "quad quad--thin" }, refs.browser);
    svg("rect", { x: 744, y: 232, width: 162, height: 36, rx: 8, class: "t-button-ok" }, refs.browser);
    label(refs.browser, 825, 255, "Anzeige bestätigen", "t-button-text", { "text-anchor": "middle" });
    refs.browserLink = svg("path", { d: "M600 362C640 330 650 310 700 286", class: "t-link-line" }, layer);

    // GSVmulti, geplant.
    refs.gsv = group(layer, "bench-gsv");
    panel(refs.gsv, 760, 318, 160, 84, "t-window t-planned-box");
    label(refs.gsv, 840, 352, "GSVmulti", "t-label t-strong", { "text-anchor": "middle" });
    label(refs.gsv, 840, 376, "offen · OQ-07", "t-small t-plan-text", { "text-anchor": "middle" });
    refs.gsvLink = svg("path", { d: "M618 384H756", class: "t-plan-line" }, layer);
    tour.docLink(refs.gsv, "docs/GSVMULTI_PROTOCOL.html", "GSVmulti-Protokoll öffnen", [906, 334]);
    tour.docLink(refs.pi, "docs/HARDWARE_PROFILE.html", "Hardwareprofil öffnen", [630, 370]);

    // Anklickbare Kapitel-Etiketten.
    refs.hot = group(layer, "hotspots");
    const spots = [
      { chapter: "training", x: 171, y: 248, text: "Training" },
      { chapter: "erkennung", x: 372, y: 228, text: "Erkennung" },
      { chapter: "zeit", x: 552, y: 452, text: "Zeit" },
      { chapter: "bedienung", x: 785, y: 100, text: "Bedienung" },
      { chapter: "regeln", x: 840, y: 434, text: "Regeln" },
    ];
    refs.spots = spots.map((spot) => tour.hotspot(refs.hot, spot));
    return refs;
  }

  function sceneUeberblickAufbau(ctx) {
    const { tl, A, layer, tour } = ctx;
    const b = benchScene(layer, tour);
    fadeUp(tl, Array.from(b.title.children), { delay: A.stagger(120) }, 0);
    hidden(b.ground);
    tl.add(b.ground, { opacity: [0, 1], scaleX: [0, 1], duration: 900, ease: "inOutQuart" }, 150);
    fadeUp(tl, [b.device, b.camera, b.pi, b.browser, b.gsv], { translateY: [40, 0], delay: A.stagger(140), ease: "outBack(1.4)", duration: 800 }, 400);
    hidden(b.cone);
    tl.add(b.cone, { opacity: [0, 1], duration: 800, ease: "outQuad" }, "-=200");
    drawIn(tl, A, b.cable, { duration: 600 }, "<<");
    drawIn(tl, A, b.browserLink, { duration: 600 }, "<<+=150");
    drawIn(tl, A, b.gsvLink, { duration: 600 }, "<<+=150");
    popIn(tl, A, b.spots, { delay: A.stagger(110) }, "+=100");
  }

  function sceneUeberblickWeg(ctx) {
    const { tl, A, layer, tour } = ctx;
    const b = benchScene(layer, tour);
    hidden(b.spots);

    const flows = group(layer, "flows");
    const main = svg("path", { d: "M170 330C210 316 260 312 352 300C380 300 398 300 410 320C430 360 450 382 486 382", class: "t-path-ghost" }, flows);
    const toLog = svg("path", { d: "M552 400C552 430 520 440 486 452", class: "t-flow-line" }, flows);
    const toGsv = svg("path", { d: "M618 384H756", class: "t-path-ghost" }, flows);

    const log = group(layer, "log");
    panel(log, 400, 452, 150, 46, "t-panel t-flow-box");
    label(log, 475, 481, "JSONL · Audit", "t-label t-strong", { "text-anchor": "middle" });
    tour.docLink(log, "api/sink.html", "Ausgabe-API öffnen", [540, 466]);

    const ref = group(layer, "ref");
    panel(ref, 40, 440, 190, 64, "t-panel");
    label(ref, 135, 466, "Kalibrierreferenz", "t-label t-strong", { "text-anchor": "middle" });
    label(ref, 135, 488, "eigener Strom, eigene Zeit", "t-small", { "text-anchor": "middle" });

    const match = group(layer, "match");
    panel(match, 690, 452, 230, 46, "t-panel");
    label(match, 805, 481, "Zeitliche Zuordnung", "t-label t-strong", { "text-anchor": "middle" });
    tour.docLink(match, "docs/uebersicht/zeitstempel.html", "Zeitstempel richtig lesen", [908, 466]);
    const logToMatch = svg("path", { d: "M550 475H686", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const refToMatch = svg("path", { d: "M230 500C330 528 600 528 690 490", class: "t-muted-line", "marker-end": "url(#tour-arrow)" }, layer);

    const forbid = group(layer, "forbid");
    svg("path", { d: "M200 440C260 420 420 420 486 400", class: "t-bad-line" }, forbid);
    checkMark(forbid, 341, 420, "bad");
    label(forbid, 330, 450, "nie in die Erkennung", "t-small t-bad-text", { "text-anchor": "middle" });

    const motto = group(layer, "motto");
    panel(motto, 600, 30, 320, 64, "t-panel");
    label(motto, 760, 56, "Kein Sprachmodell im Messpfad", "t-label t-strong", { "text-anchor": "middle" });
    label(motto, 760, 80, "Bildverarbeitung + Regeln · im Zweifel ablehnen", "t-small", { "text-anchor": "middle" });
    tour.docLink(motto, "Konzept.html#7-erkennungssicherheit-und-fehlerbehandlung", "Konzept §7 öffnen", [906, 46]);

    const dot = svg("circle", { r: 8, class: "t-pulse" }, layer);
    const dot2 = svg("circle", { r: 7, class: "t-pulse" }, layer);
    const dot3 = svg("circle", { r: 7, class: "t-pulse t-pulse--plan" }, layer);
    hidden(dot, dot2, dot3);
    const stop = group(layer, "stop");
    svg("circle", { cx: 690, cy: 384, r: 13, class: "t-plan-fill" }, stop);
    label(stop, 690, 389, "?", "t-label t-strong", { "text-anchor": "middle" });
    tour.docLink(stop, "docs/open-questions.html#oq-07", "OQ-07 öffnen: GSVmulti-Telegrammformat");

    hidden(log, ref, match, motto, stop, forbid, logToMatch, refToMatch, toLog);
    tl.set(dot, { opacity: 1 }, 100);
    travel(tl, A, main, dot, { duration: 1700 }, "<<");
    tl.add(dot, { opacity: [1, 0], duration: 200 }, "<");
    tl.set([dot2, dot3], { opacity: 1 }, "<<");
    drawIn(tl, A, toLog, { duration: 500 }, "<<");
    travel(tl, A, toLog, dot2, { duration: 700 }, "<<");
    travel(tl, A, toGsv, dot3, { duration: 900, ease: "outQuad" }, "<<");
    tl.add(dot3, { opacity: [1, 0], duration: 250 }, "<");
    popIn(tl, A, [stop], {}, "<<");
    fadeUp(tl, [log], {}, "-=600");
    tl.add(dot2, { opacity: [1, 0], duration: 250 }, "<<+=200");
    fadeUp(tl, [ref], {}, "+=150");
    fadeUp(tl, [forbid], {}, "+=100");
    fadeUp(tl, [match], {}, "+=150");
    tl.add([logToMatch, refToMatch], { opacity: [0, 1], duration: 600, delay: A.stagger(150) }, "<<");
    fadeUp(tl, [motto], {}, "+=200");
  }

  function sceneUeberblickKapitel(ctx) {
    const { tl, A, layer, tour } = ctx;
    label(layer, 40, 62, "Kapitel", "t-title");
    label(layer, 40, 90, "Ein Kapitel anklicken oder mit Weiter fortfahren.", "t-subtitle");
    const cards = tour.chapters.map((chapter, i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const x = 40 + col * 300;
      const y = 124 + row * 196;
      const card = group(layer, "card-wrap");
      const inner = tour.chapterCard(card, chapter, x, y, 280, 176);
      return inner;
    });
    popIn(tl, A, cards, { delay: A.stagger(90, { from: "first" }), scale: [0.85, 1], duration: 640 }, 100);
  }

  // ------------------------------------------------------- Szenen Erkennung --

  function sceneErkennungBild(ctx) {
    const { tl, A, layer } = ctx;
    const s = cameraScene(layer);
    const offset = svg("g", { class: "boottime" }, layer);
    arrow(offset, "M400 492H452");
    chip(offset, 120, 479, "Zeitbasis: CLOCK_MONOTONIC", "chip--line");
    chip(offset, 460, 479, "Vergleich in BOOTTIME · Versatz aus session.json", "chip--flow");
    hidden(s.cam, s.frame, s.device.root, s.seqChip, s.timeChip, offset);

    fadeUp(tl, s.cam, { translateY: [0, 0], translateX: [-30, 0], duration: 600 }, 0);
    tl.add(s.cam, { scale: [1, 0.9, 1], duration: 300, ease: "inOutSine" }, "+=50");
    tl.add(s.frame, { opacity: [0, 1], scale: [0.08, 1], translateX: [-330, 0], duration: 900, ease: "outExpo" }, "<<+=120");
    tl.add(s.flash, { opacity: [0.85, 0], duration: 700, ease: "outQuad" }, "<<+=450");
    tl.add(s.device.root, { opacity: [0, 1], duration: 400 }, "<<");
    const counter = { n: 1834 };
    const seqText = s.seqChip.querySelector("text");
    fadeUp(tl, s.seqChip, { duration: 500 }, "+=100");
    tl.add(counter, {
      n: [1834, 1842],
      duration: 1600,
      ease: "linear",
      onUpdate: () => { seqText.textContent = `Bild ${Math.round(counter.n)} · Beispiel`; },
    }, "<<");
    fadeUp(tl, s.timeChip, { duration: 500 }, "<<+=300");
    fadeUp(tl, offset, {}, "+=300");
  }

  function sceneErkennungRoi(ctx) {
    const { tl, A, layer } = ctx;
    const s = cameraScene(layer);
    const card = group(layer, "roi-card");
    panel(card, 590, 76, 234, 86, "tp-card");
    label(card, 606, 100, "vom Bediener bestätigt", "tp-card-title");
    label(card, 606, 122, "Raster · Format gsv2as_v1", "tp-card-text");
    label(card, 606, 142, "Einheit mV/V (aus dem Profil)", "tp-card-text");
    ctx.tour.docLink(card, "docs/anleitung/04-geraeteprofile.html", "Geräteprofile öffnen", [810, 98]);
    hidden(card);
    drawIn(tl, A, s.quad, { duration: 1100, ease: "inOutCubic" }, 200);
    popIn(tl, A, s.handleDots, { delay: A.stagger(110), ease: "outElastic(1, .55)", duration: 900 }, "-=300");
    tl.set(s.handles, { opacity: 1 }, "<<");
    tl.add(s.quad, { strokeWidth: [3, 6, 3], duration: 600, ease: "inOutSine" }, "-=500");
    fadeUp(tl, card, { translateY: [0, 0], translateX: [24, 0] }, "-=200");
  }

  function sceneErkennungNachfuehrung(ctx) {
    const { tl, A, layer } = ctx;
    const s = cameraScene(layer, { quad: true });
    const ref = group(layer, "ref-thumb");
    svg("rect", { x: 640, y: 74, width: 190, height: 104, rx: 8, class: "tp-card" }, ref);
    svg("rect", { x: 652, y: 84, width: 166, height: 64, rx: 4, class: "tp-frame-mini" }, ref);
    svg("rect", { x: 690, y: 104, width: 90, height: 24, rx: 3, class: "tp-body" }, ref);
    svg("rect", { x: 696, y: 109, width: 78, height: 14, rx: 2, class: "tp-lcd" }, ref);
    svg("rect", { x: 694, y: 107, width: 82, height: 18, class: "quad quad--thin" }, ref);
    label(ref, 735, 166, "Referenzbild der Bestätigung", "tp-card-text", { "text-anchor": "middle" });
    ctx.tour.docLink(ref, "docs/anleitung/07-lokalisierung.html", "Lokalisierung und Nachführung öffnen", [818, 168]);
    const link = svg("path", { d: "M540 226C590 214 610 170 636 140", class: "t-flow-dash", "marker-end": "url(#tour-arrow)" }, layer);
    const note = chip(layer, 120, 479, "ECC gegen die Referenz, nie gegen das Vorbild", "chip--flow");
    const bound = chip(layer, 500, 479, "Zu großer Ruck → keine Korrektur, unlesbar", "chip--bad");
    hidden(ref, link, note, bound);

    fadeUp(tl, ref, {}, 100);
    drawIn(tl, A, link, { duration: 600 }, "-=300");
    fadeUp(tl, note, {}, "<<");
    const shake = (values, quadDelay, duration) => {
      const keys = (field) => values.map((v) => ({ to: VIEW_CAMERA[field] + (v[field] || 0), duration }));
      const params = (target) => ({
        tx: keys("tx"), ty: keys("ty"), rot: keys("rot"),
        ease: "inOutSine",
        onUpdate: s.render,
      });
      tl.add(s.state.device, params(), "+=150");
      tl.add(s.state.quad, params(), `<<+=${quadDelay}`);
    };
    const wobble = [{ tx: 9, rot: 1.1 }, { tx: -7, ty: 4, rot: -0.8 }, { tx: 5, ty: -3, rot: 0.6 }, {}];
    shake(wobble, 140, 360);
    // Großer Ruck: der Tracker korrigiert nicht, das Viereck bleibt stehen.
    tl.add(s.state.device, { tx: VIEW_CAMERA.tx + 70, rot: VIEW_CAMERA.rot + 5, duration: 500, ease: "outBack(1.6)", onUpdate: s.render }, "+=250");
    tl.add(s.quad, { stroke: ["var(--tour-flow)", "var(--tour-bad)"], duration: 200 }, "<");
    tl.add(s.handleDots, { fill: ["var(--tour-flow)", "var(--tour-bad)"], duration: 200 }, "<<");
    fadeUp(tl, bound, {}, "<<");
    tl.add(s.state.device, { tx: VIEW_CAMERA.tx, rot: VIEW_CAMERA.rot, duration: 700, ease: "inOutQuad", onUpdate: s.render }, "+=1200");
    tl.add(s.quad, { stroke: "var(--tour-flow)", duration: 300 }, "<");
    tl.add(s.handleDots, { fill: "var(--tour-flow)", duration: 300 }, "<<");
  }

  function sceneErkennungEntzerren(ctx) {
    const { tl, A, layer } = ctx;
    const s = cameraScene(layer, { quad: true });
    const caption = group(layer, "rect-caption");
    chip(caption, 250, 360, "Vierpunkt-Transformation · direkt aus dem Rohbild", "chip--flow");
    hidden(caption);
    const proxy = { t: 0 };
    const morph = () => {
      Object.assign(s.state.device, lerpParams(VIEW_CAMERA, VIEW_RECT, proxy.t));
      Object.assign(s.state.quad, s.state.device);
      s.render();
    };
    tl.add([s.frame, s.chips, s.cam], { opacity: [1, 0], duration: 700, ease: "outQuad" }, 200);
    tl.add(s.device.body, { opacity: [1, 0], duration: 600, ease: "outQuad" }, "<<+=200");
    tl.add(s.handles, { opacity: [1, 0], duration: 300 }, "<<");
    tl.add(proxy, { t: [0, 1], duration: 1500, ease: "inOutCubic", onUpdate: morph }, "<<");
    tl.add(s.quad, { strokeWidth: [3, 2], duration: 400 }, "<");
    fadeUp(tl, caption, {}, "<<+=100");
  }

  function sceneErkennungRaster(ctx) {
    const { tl, A, layer } = ctx;
    const r = rectifiedScene(layer, VIEW_RECT);
    const m = r.matrix();
    const boxes = group(layer, "cell-boxes");
    const kinds = [];
    for (let i = 0; i < 16; i++) {
      const kind = i === 0 ? "sign" : i <= 7 ? "num" : i === 8 ? "blank" : "unit";
      kinds.push(kind);
      svg("polygon", { points: cellPolygon(m, i), class: `cell-box cell-box--${kind}` }, boxes);
    }
    const head = group(layer, "raster-head");
    label(head, 480, 160, "Displaytech 161A · 16 Zeichen × 1 Zeile · je 5 × 8 Punkte", "t-label t-strong", { "text-anchor": "middle" });
    const yBrace = apply(m, 0, LCD_Y + LCD_H * LCD_U + 12)[1] + 16;
    const span = (from, to) => [apply(m, cellCorners(from)[0][0], 0)[0], apply(m, cellCorners(to)[1][0], 0)[0]];
    const braces = group(layer, "braces");
    const brace = (from, to, text, cls, line2) => {
      const [x0, x1] = span(from, to);
      const b = group(braces, `brace ${cls}`);
      svg("path", { d: `M${x0} ${yBrace}v8H${x1}v-8`, class: "brace-line" }, b);
      label(b, (x0 + x1) / 2, yBrace + 30, text, "t-small t-strong", { "text-anchor": "middle" });
      if (line2) label(b, (x0 + x1) / 2, yBrace + 48, line2, "t-small", { "text-anchor": "middle" });
      return b;
    };
    const parts = [
      brace(0, 0, "Vorzeichen", "brace--flow"),
      brace(1, 7, "Zahl mit Punkt · Zellen 1–7", "brace--flow"),
      brace(8, 8, "leer", "brace--flow"),
      brace(9, 15, "Einheit: aus dem Profil", "brace--muted", "wird nicht gelesen"),
    ];
    const cellBoxes = Array.from(boxes.children);
    hidden(cellBoxes, head, parts);
    fadeUp(tl, head, {}, 100);
    tl.add(cellBoxes, { opacity: [0, 1], scaleY: [0.2, 1], delay: A.stagger(55), duration: 500, ease: "outBack(1.7)" }, "-=300");
    // Gelesene Zellen kurz aufleuchten lassen.
    tl.add(r.device.display.cells.slice(0, 9), { opacity: [1, 0.35, 1], delay: A.stagger(70), duration: 420, ease: "inOutSine" }, "+=100");
    fadeUp(tl, parts, { delay: A.stagger(160) }, "-=200");
  }

  function sampledCell(ch) {
    const rnd = seeded(7);
    const rom = glyphVector(ch);
    // Etwas Unschärfe: Nachbarpunkte färben leicht ab, dazu Rauschen.
    return rom.map((v, i) => {
      const r = Math.floor(i / 5);
      const c = i % 5;
      let spill = 0;
      for (const [dr, dc] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const rr = r + dr;
        const cc = c + dc;
        if (rr >= 0 && rr < 8 && cc >= 0 && cc < 5) spill += rom[rr * 5 + cc];
      }
      return clamp(v * 0.86 + spill * 0.025 + (rnd() - 0.5) * 0.12 + 0.04, 0, 1);
    });
  }

  function sceneErkennungZelle(ctx) {
    const { tl, A, layer } = ctx;
    const r = rectifiedScene(layer, VIEW_HEAD);
    const m = r.matrix();
    const CELL = 3;
    const ch = DISPLAY[CELL];
    const focus = svg("polygon", { points: cellPolygon(m, CELL), class: "cell-box cell-box--focus" }, layer);

    // Vergrößerte Zelle mit 40 abgetasteten Punkten.
    const big = group(layer, "big-cell");
    const P = 32;
    const bx = 70;
    const by = 196;
    svg("rect", { x: bx - 14, y: by - 14, width: 5 * P + 20, height: 8 * P + 20, rx: 10, class: "tp-lcd" }, big);
    const sample = sampledCell(ch);
    const dots = [];
    for (let i = 0; i < 40; i++) {
      const c = i % 5;
      const row = Math.floor(i / 5);
      const dotEl = svg("rect", { x: bx + c * P, y: by + row * P, width: P - 6, height: P - 6, rx: 4, class: "big-dot" }, big);
      dotEl.style.setProperty("--ink", sample[i].toFixed(3));
      dots.push(dotEl);
    }
    const [fx, fy] = cellCenter(m, CELL);
    const zoom = svg("path", { d: `M${fx} ${fy + 20}C${fx} 160 ${bx + 80} 150 ${bx + 80} ${by - 18}`, class: "t-flow-dash", "marker-end": "url(#tour-arrow)" }, layer);
    const bigCaption = label(layer, bx + 66, by + 8 * P + 34, "40 Punkte abgetastet", "t-small", { "text-anchor": "middle" });

    // Abstände zu jeder Klasse, schematisch gegen das ROM-Muster.
    const dist = READER_CLASSES.map((cls) => {
      const rom = glyphVector(cls);
      let sum = 0;
      for (let i = 0; i < 40; i++) sum += (sample[i] - rom[i]) ** 2;
      return { cls, d: Math.sqrt(sum) };
    }).sort((a, b) => a.d - b.d);
    const best = dist[0];
    const second = dist[1];
    const maxD = dist[dist.length - 1].d;
    const X0 = 400;
    const BW = 420;
    const scale = (d) => (d / maxD) * BW;
    const dMax = best.d + (second.d - best.d) * 0.45;
    const rows = group(layer, "dist-rows");
    label(layer, X0 - 40, 176, "Abstand zur Vorlage (kürzer = ähnlicher)", "t-label t-strong");
    const rowEls = [];
    const bars = [];
    dist.forEach((entry, i) => {
      const y = 200 + i * 22;
      const row = group(rows, "dist-row");
      const name = entry.cls === " " ? "␣" : entry.cls;
      label(row, X0 - 28, y + 14, name, "t-mono", { "text-anchor": "middle" });
      const bar = svg("rect", { x: X0, y: y + 3, width: scale(entry.d), height: 14, rx: 4, class: i === 0 ? "dist-bar dist-bar--best" : "dist-bar" }, row);
      bars.push(bar);
      rowEls.push(row);
    });
    const yTop = 196;
    const yBottom = 200 + dist.length * 22;
    const dMaxLine = group(layer, "dmax");
    svg("path", { d: `M${X0 + scale(dMax)} ${yTop}V${yBottom}`, class: "t-plan-line" }, dMaxLine);
    label(dMaxLine, X0 + scale(dMax) + 6, yTop + 2, "D_max", "t-small t-plan-text");
    const gap = group(layer, "gap");
    const gy = 200 + 9;
    svg("path", { d: `M${X0 + scale(best.d) + 4} ${gy}H${X0 + scale(second.d)}V${gy + 16}`, class: "brace-line brace-line--valid" }, gap);
    label(gap, X0 + scale(second.d) + 8, gy + 4, "Vorsprung ≥ margin_min", "t-small t-valid-text");
    const result = group(layer, "result");
    badge(result, 610, 506, `Zelle ${CELL} = ${ch}`, "valid", 150);
    label(result, 700, 511, "", "t-small");
    const note = label(layer, 900, 530, "schematisch: Abstand gegen das ROM-Muster", "t-tiny", { "text-anchor": "end" });

    hidden(focus, zoom, bigCaption, rows, dMaxLine, gap, result, note, Array.from(big.children));
    for (const bar of bars) bar.style.transform = "scaleX(0)";
    tl.add(focus, { opacity: [0, 1], duration: 400 }, 100);
    tl.add(focus, { strokeWidth: [2, 5, 2], duration: 600, ease: "inOutSine" }, "<");
    drawIn(tl, A, zoom, { duration: 700 }, "-=200");
    tl.add(big.children[0], { opacity: [0, 1], scale: [0.2, 1], duration: 700, ease: "outExpo" }, "-=300");
    tl.add(dots, { opacity: [0, 1], scale: [0, 1], delay: A.stagger(28, { grid: [5, 8], from: "first" }), duration: 360, ease: "outBack(2)" }, "-=400");
    tl.add(bigCaption, { opacity: [0, 1], duration: 400 }, "<");
    tl.add(rows, { opacity: [0, 1], duration: 300 }, "-=200");
    tl.add(bars, { scaleX: [0, 1], delay: A.stagger(70), duration: 700, ease: "outExpo" }, "<<");
    fadeUp(tl, dMaxLine, { translateY: [0, 0] }, "+=100");
    fadeUp(tl, gap, {}, "+=150");
    tl.add(rowEls[0], { scale: [1, 1.04, 1], duration: 500, ease: "inOutSine" }, "+=100");
    popIn(tl, A, [result], { ease: "outElastic(1, .6)", duration: 1000 }, "<<");
    tl.add(note, { opacity: [0, 1], duration: 400 }, "<<");
  }

  function sceneErkennungFormat(ctx) {
    const { tl, A, layer } = ctx;
    const r = rectifiedScene(layer, VIEW_HEAD);
    const m = r.matrix();
    const text = DISPLAY.slice(0, 9);
    const pre = group(layer, "pre-checks");
    chip(pre, 120, 150, `Belichtung: ≤ ${num(fact("ocr.max_saturated", 0.02) * 100)} % gesättigt`, "chip--valid");
    chip(pre, 360, 150, "Kontrast ausreichend", "chip--valid");
    const tokens = [];
    const TX = 480 - (9 * 62) / 2;
    for (let i = 0; i < 9; i++) {
      const tok = group(layer, "token");
      svg("rect", { x: TX + i * 62, y: 204, width: 54, height: 60, rx: 8, class: "token-box" }, tok);
      label(tok, TX + i * 62 + 27, 246, text[i] === " " ? "␣" : text[i], "token-text", { "text-anchor": "middle" });
      const [cx, cy] = cellCenter(m, i);
      tok.dataset.dx = String(cx - (TX + i * 62 + 27));
      tok.dataset.dy = String(cy - 234);
      tokens.push(tok);
    }
    const rules = [
      "Vorzeichen +",
      "genau ein Punkt",
      "sechs Ziffern",
      "Zelle 8 leer",
      "Leerzellen wirklich leer",
    ];
    const ruleEls = rules.map((rule, i) => {
      const x = 150 + (i % 3) * 230;
      const y = 300 + Math.floor(i / 3) * 40;
      const el = group(layer, "rule");
      checkMark(el, x, y, "ok");
      label(el, x + 20, y + 5, rule, "t-label");
      return el;
    });
    const value = group(layer, "value");
    badge(value, 480, 410, "gelesen: +0.46761 mV/V", "valid", 280);
    ctx.tour.docLink(value, "api/ocr.html", "OCR-API öffnen", [636, 415]);
    const counter = group(layer, "counter");
    label(counter, 120, 468, "Gegenbeispiel", "t-small t-strong");
    const bad = "+0.4?761";
    for (let i = 0; i < bad.length; i++) {
      const isBad = bad[i] === "?";
      svg("rect", { x: 120 + i * 30, y: 480, width: 26, height: 34, rx: 5, class: isBad ? "token-box token-box--bad" : "token-box token-box--muted" }, counter);
      label(counter, 133 + i * 30, 503, bad[i], isBad ? "token-small t-bad-text" : "token-small", { "text-anchor": "middle" });
    }
    badge(counter, 560, 497, "ganzer Wert abgelehnt · zelle_unbekannt", "bad", 330);

    hidden(pre.children, tokens, ruleEls, value, counter);
    fadeUp(tl, Array.from(pre.children), { delay: A.stagger(150) }, 100);
    tl.add(tokens, {
      opacity: [0, 1],
      translateX: [(el) => Number(el.dataset.dx), 0],
      translateY: [(el) => Number(el.dataset.dy), 0],
      scale: [0.6, 1],
      delay: A.stagger(80),
      duration: 800,
      ease: "outExpo",
    }, "+=100");
    popIn(tl, A, ruleEls, { delay: A.stagger(180), scale: [0.8, 1] }, "+=100");
    popIn(tl, A, [value], { ease: "outElastic(1, .6)", duration: 1000 }, "+=100");
    fadeUp(tl, counter, {}, "+=500");
  }

  function sceneErkennungFreigabe(ctx) {
    const { tl, A, layer, tour } = ctx;
    label(layer, 40, 50, "Fünf Bilder nacheinander · Beispiel mit confirm_frames = 2", "t-label t-strong");
    const confirmDefault = fact("gate.confirm_frames", 1);
    label(layer, 40, 72, confirmDefault === 1
      ? "Grundeinstellung ist 1: dann ist schon das erste Bild gültig."
      : `Grundeinstellung ist ${confirmDefault}.`, "t-small");
    const frames = [
      { v: "0.46761", s: "Übergang", k: "plan", y: 200, why: "erst 1 von 2" },
      { v: "0.46761", s: "gültig", k: "valid", y: 200, why: "2 gleiche" },
      { v: "0.46761", s: "gültig", k: "valid", y: 200, why: "" },
      { v: "0.51230", s: "Übergang", k: "plan", y: 130, why: "neuer Wert" },
      { v: "0.51230", s: "gültig", k: "valid", y: 130, why: "bestätigt" },
    ];
    const X = (i) => 190 + i * 150;
    const axis = svg("path", { d: `M140 270H${X(4) + 90}`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, layer);
    label(layer, X(4) + 80, 250, "Bilder", "t-small", { "text-anchor": "end" });
    label(layer, 120, 326, "gelesen", "t-small", { "text-anchor": "end" });
    label(layer, 120, 372, "Status", "t-small", { "text-anchor": "end" });
    const per = frames.map((f, i) => {
      const g = group(layer, "frame-step");
      svg("rect", { x: X(i) - 13, y: 252, width: 26, height: 36, rx: 4, class: "tick" }, g);
      label(g, X(i), 330, f.v, "t-mono", { "text-anchor": "middle" });
      badge(g, X(i), 368, f.s, f.k, 96);
      if (f.why) label(g, X(i), 400, f.why, "t-small", { "text-anchor": "middle" });
      return g;
    });
    // Gelesene Werte als Treppe: der Sprung bleibt ein senkrechter Sprung.
    const plot = svg("path", { d: `M${X(0)} 200H${X(3)}V130H${X(4)}`, class: "t-value-line" }, layer);
    const dots = group(layer, "status-dots");
    frames.forEach((f, i) => svg("circle", { cx: X(i), cy: f.y, r: 7, class: `status-dot status-dot--${f.k}` }, dots));
    const jump = group(layer, "jump");
    label(jump, X(3) + 12, 116, "Sprung bleibt Sprung · nichts geglättet", "t-small t-strong");
    const ref = group(layer, "ref-block");
    panel(ref, 600, 452, 300, 64, "t-panel");
    label(ref, 750, 478, "Kalibrierreferenz", "t-label t-strong", { "text-anchor": "middle" });
    label(ref, 750, 500, "wird der Freigabe nicht übergeben", "t-small", { "text-anchor": "middle" });
    const gate = group(layer, "gate-block");
    panel(gate, 120, 452, 260, 64, "t-panel t-flow-box");
    label(gate, 250, 490, "Lesen · Freigabe", "t-label t-strong", { "text-anchor": "middle" });
    tour.docLink(gate, "api/validate.html", "Freigabe-API öffnen", [366, 468]);
    const noLink = group(layer, "no-link");
    svg("path", { d: "M596 484H386", class: "t-bad-line", "marker-end": "url(#tour-arrow-bad)" }, noLink);
    checkMark(noLink, 491, 484, "bad");

    hidden(axis, per, plot, dots, dots.children, jump, ref, gate, noLink);
    tl.add(axis, { opacity: [0, 1], duration: 400 }, 100);
    const plotDraw = A.svg.createDrawable(plot);
    const reach = [0.01, 0.224, 0.448, 0.776, 1];
    per.forEach((g, i) => {
      tl.add(g, { opacity: [0, 1], translateY: [14, 0], duration: 420, ease: "outBack(1.6)" }, i === 0 ? "+=100" : "+=420");
      tl.add(dots.children[i], { opacity: [0, 1], scale: [0.2, 1], duration: 380, ease: "outBack(2)" }, "<<");
      if (i === 0) tl.set([dots, plot], { opacity: 1 }, "<<");
      tl.add(plotDraw, { draw: i === 0 ? ["0 0", `0 ${reach[0]}`] : `0 ${reach[i]}`, duration: 320 }, "<<");
      if (i === 3) fadeUp(tl, jump, {}, "<<");
    });
    fadeUp(tl, [gate, ref], { delay: A.stagger(150) }, "+=300");
    tl.add(noLink, { opacity: [0, 1], duration: 300 }, "+=100");
    tl.add(noLink.querySelector(".mark"), { scale: [0.3, 1.25, 1], duration: 600, ease: "outBack(2)" }, "<<");
  }

  // Eine schematische Hand, die die Anzeige verdeckt.
  function drawHand(parent, x, y) {
    const outer = group(parent, "", { transform: `translate(${x} ${y})` });
    const hand = group(outer, "hand");
    [0, 1, 2, 3].forEach((i) => svg("rect", { x: 6 + i * 26, y: i === 0 || i === 3 ? 14 : 0, width: 22, height: 70, rx: 11, class: "tp-hand" }, hand));
    svg("rect", { x: 0, y: 44, width: 112, height: 86, rx: 30, class: "tp-hand" }, hand);
    svg("rect", { x: -30, y: 60, width: 60, height: 22, rx: 11, class: "tp-hand", transform: "rotate(-28 0 71)" }, hand);
    return hand;
  }

  function sceneErkennungVeraltet(ctx) {
    const { tl, A, layer, tour } = ctx;
    label(layer, 40, 44, "Was passiert, wenn die Anzeige verdeckt ist?", "t-label t-strong");
    const staleMs = fact("gate.stale_after_ns", 500e6) / 1e6;
    const staleText = `${num(staleMs / 1000, 2)} s`;
    const frameMs = 1000 / 30;
    const at = (n) => `${Math.round(n * frameMs)} ms`;
    const lastBefore = Math.floor(staleMs / frameMs);
    label(layer, 40, 64, `Beispiel: 30 Bilder pro Sekunde · stale_after = ${staleText} (vorläufig)`, "t-small");

    // Kleine Anzeige mit Hand davor.
    const lcd = group(layer, "mini-lcd");
    svg("rect", { x: 560, y: 22, width: LCD_W * 3 + 16, height: LCD_H * 3 + 16, rx: 6, class: "tp-bezel" }, lcd);
    drawLCD(lcd, "+0.51230 mV/V   ", 568, 30, 3);
    const hand = drawHand(layer, 660, 6);
    const handLabel = label(layer, 716, 154, "Hand vor der Anzeige", "t-small t-strong", { "text-anchor": "middle" });

    const cols = [
      { x: 170, t: "0 ms", read: "0.51230", s: "gültig", k: "valid", out: "0.51230", covered: false },
      { x: 290, t: at(1), read: "?", s: "unlesbar", k: "bad", out: "keine Zahl", covered: true },
      { x: 410, t: at(2), read: "?", s: "unlesbar", k: "bad", out: "keine Zahl", covered: true },
      { gap: true, x: 510 },
      { x: 610, t: at(lastBefore), read: "?", s: "unlesbar", k: "bad", out: "keine Zahl", covered: true },
      { x: 730, t: at(lastBefore + 1), read: "?", s: "veraltet", k: "stale", out: "keine Zahl", covered: true },
      { x: 850, t: at(lastBefore + 2), read: "?", s: "veraltet", k: "stale", out: "keine Zahl", covered: true },
    ];
    const rowsY = { frame: 186, time: 226, read: 262, status: 300, out: 340 };
    const heads = group(layer, "row-heads");
    [["Bild", rowsY.frame + 5], ["Zeit", rowsY.time], ["gelesen", rowsY.read], ["Status", rowsY.status], ["ausgegeben", rowsY.out]]
      .forEach(([text, y]) => label(heads, 104, y, text, "t-small", { "text-anchor": "end" }));
    const colEls = cols.map((c) => {
      const g = group(layer, "col");
      if (c.gap) {
        label(g, c.x, rowsY.read, "⋯", "t-title", { "text-anchor": "middle" });
        label(g, c.x, rowsY.status + 4, "weitere", "t-small", { "text-anchor": "middle" });
        label(g, c.x, rowsY.status + 20, "unlesbare Bilder", "t-small", { "text-anchor": "middle" });
        return g;
      }
      svg("rect", { x: c.x - 24, y: rowsY.frame - 14, width: 48, height: 30, rx: 4, class: "tp-frame-mini" }, g);
      svg("rect", { x: c.x - 16, y: rowsY.frame - 5, width: 32, height: 10, rx: 2, class: "tp-lcd" }, g);
      if (c.covered) svg("rect", { x: c.x - 6, y: rowsY.frame - 12, width: 26, height: 26, rx: 9, class: "tp-hand" }, g);
      label(g, c.x, rowsY.time, c.t, "t-small", { "text-anchor": "middle" });
      label(g, c.x, rowsY.read, c.read, c.read === "?" ? "t-mono t-bad-text" : "t-mono", { "text-anchor": "middle" });
      badge(g, c.x, rowsY.status, c.s, c.k === "stale" ? "bad" : c.k, 96);
      label(g, c.x, rowsY.out + 4, c.out, c.out === "keine Zahl" ? "t-small" : "t-mono t-valid-text", { "text-anchor": "middle" });
      return g;
    });
    // Der alte Wert wird nicht weitergereicht.
    const ghost = group(layer, "ghost");
    label(ghost, 290, rowsY.out + 4, "0.51230", "t-mono t-bad-text", { "text-anchor": "middle" });
    const strike = svg("path", { d: `M252 ${rowsY.out}H328`, class: "t-strike" }, ghost);
    const noRepeat = label(layer, 350, rowsY.out + 30, "Der alte Wert 0.51230 wird nicht wiederholt.", "t-small t-bad-text", { "text-anchor": "middle" });

    const brace = group(layer, "stale-brace");
    svg("path", { d: `M170 392v8H670v-8`, class: "brace-line brace-line--bad" }, brace);
    label(brace, 420, 420, `${staleText} ohne gültigen Wert (stale_after)`, "t-small t-strong", { "text-anchor": "middle" });
    // Senkrechte Grenze bei 0,5 s: rechts davon gilt "veraltet".
    const turn = group(layer, "stale-limit");
    svg("path", { d: "M670 172V400", class: "t-bad-line" }, turn);
    label(turn, 678, 398, `Grenze ${staleText}`, "t-small t-bad-text");

    const defs = group(layer, "definitions");
    panel(defs, 60, 444, 410, 72, "t-panel");
    badge(defs, 128, 480, "unlesbar", "bad", 100);
    label(defs, 192, 474, "dieses eine Bild ließ sich", "t-label");
    label(defs, 192, 494, "nicht sicher lesen", "t-label");
    panel(defs, 490, 444, 410, 72, "t-panel");
    badge(defs, 558, 480, "veraltet", "bad", 100);
    label(defs, 622, 474, "schon länger gibt es keinen", "t-label");
    label(defs, 622, 494, "aktuellen Wert mehr", "t-label");
    tour.docLink(defs, "api/validate.html", "Freigabe-API öffnen", [886, 460]);

    hidden(lcd, hand, handLabel, colEls, ghost, noRepeat, brace, turn, defs);
    fadeUp(tl, lcd, {}, 100);
    fadeUp(tl, colEls[0], {}, "+=200");
    tl.add(hand, { opacity: [0, 1], translateX: [180, 0], translateY: [40, 0], rotate: [12, 0], duration: 900, ease: "outBack(1.3)" }, "+=300");
    fadeUp(tl, handLabel, {}, "-=300");
    fadeUp(tl, colEls[1], {}, "+=200");
    tl.add(ghost, { opacity: [0, 1], duration: 300 }, "+=200");
    tl.set(strike, { opacity: 1 }, "<");
    tl.add(A.svg.createDrawable(strike), { draw: ["0 0", "0 1"], duration: 400 }, "<<");
    tl.add(ghost, { opacity: [1, 0], translateY: [0, -14], duration: 500 }, "+=500");
    fadeUp(tl, noRepeat, {}, "<<");
    fadeUp(tl, colEls.slice(2, 5), { delay: A.stagger(300) }, "+=200");
    tl.set(brace, { opacity: 1 }, "+=100");
    drawIn(tl, A, brace.querySelector("path"), { duration: 700 }, "<");
    tl.add(brace.querySelector("text"), { opacity: [0, 1], duration: 300 }, "<");
    tl.add(turn, { opacity: [0, 1], duration: 400 }, "+=100");
    popIn(tl, A, colEls.slice(5), { delay: A.stagger(250), scale: [0.7, 1] }, "+=50");
    fadeUp(tl, defs, {}, "+=300");
  }

  function sceneErkennungAusgabe(ctx) {
    const { tl, A, layer } = ctx;
    const card = group(layer, "record");
    panel(card, 50, 40, 420, 464, "t-panel t-record");
    label(card, 72, 74, "ValueRecord", "t-title-sm");
    // Feldnamen und Reihenfolge aus dem Code (record.fields); neue Felder
    // erscheinen ohne Beispielwert, bis die Szene einen bekommt.
    const examples = {
      frame_sequence: ["1842", ""],
      capture_timestamp: ["Zeit + Zeitbasis", ""],
      value: ["0.46761", ""],
      unit: ["mV/V", ""],
      status: ["VALID", "valid"],
      confidence: ["Kennzahl, keine Fehlerwahrsch.", "muted"],
      profile_id: ["bestätigtes Profil", ""],
      trigger_sequence: ["— (optional)", "muted"],
      result_timestamp: ["Abschluss der Kette", ""],
    };
    const fieldNames = fact("record.fields", Object.keys(examples));
    const fields = fieldNames.map((name) => [name, ...(examples[name] || ["—", "muted"])]);
    label(card, 452, 74, `Konzept §8 · ${fields.length} Felder`, "t-small", { "text-anchor": "end" });
    const rowGap = Math.min(42, 378 / Math.max(fields.length, 1));
    const rows = fields.map(([name, value, kind], i) => {
      const y = 112 + i * rowGap;
      const row = group(card, "record-row");
      svg("path", { d: `M72 ${y + 16}H448`, class: "t-row-line" }, row);
      label(row, 72, y + 4, name, "t-mono t-mono-sm");
      label(row, 448, y + 4, value, `t-label ${kind ? `t-${kind}-text` : ""}`, { "text-anchor": "end" });
      return row;
    });
    label(card, 72, 494, "Beispielwerte", "t-tiny");
    ctx.tour.docLink(card, "api/vertraege.html", "Verträge (ValueRecord) öffnen", [452, 494]);

    const log = group(layer, "out-log");
    panel(log, 610, 70, 290, 70, "t-panel t-flow-box");
    label(log, 755, 100, "JSONL · Audit", "t-label t-strong", { "text-anchor": "middle" });
    label(log, 755, 122, "jeder Datensatz, auch Ablehnungen", "t-small", { "text-anchor": "middle" });
    ctx.tour.docLink(log, "api/sink.html", "Ausgabe-API öffnen", [888, 88]);
    const toLog = svg("path", { d: "M470 190C540 190 540 105 606 105", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);

    const serial = group(layer, "out-serial");
    panel(serial, 610, 230, 140, 64, "t-panel t-flow-box");
    label(serial, 680, 258, "serial_out", "t-mono", { "text-anchor": "middle" });
    label(serial, 680, 278, "/dev/ttyAMA0", "t-small", { "text-anchor": "middle" });
    ctx.tour.docLink(serial, "docs/GSVMULTI_PROTOCOL.html", "GSVmulti-Protokoll öffnen", [740, 246]);
    const toSerial = svg("path", { d: "M470 262H606", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);

    const gsv = group(layer, "out-gsv");
    panel(gsv, 800, 230, 120, 64, "t-panel t-planned-box");
    label(gsv, 860, 258, "GSVmulti", "t-label t-strong", { "text-anchor": "middle" });
    label(gsv, 860, 278, "Ziel", "t-small", { "text-anchor": "middle" });
    const toGsv = svg("path", { d: "M750 262H796", class: "t-plan-line", "marker-end": "url(#tour-arrow-plan)" }, layer);
    const open = group(layer, "oq07");
    badge(open, 850, 326, "Format offen · OQ-07", "plan", 176);
    ctx.tour.docLink(open, "docs/open-questions.html#oq-07", "OQ-07 öffnen");

    const receipt = group(layer, "receipt");
    panel(receipt, 610, 390, 290, 70, "t-panel");
    label(receipt, 755, 420, "TxReceipt", "t-mono", { "text-anchor": "middle" });
    label(receipt, 755, 442, "was über die Leitung ging · getrennt", "t-small", { "text-anchor": "middle" });
    const toReceipt = svg("path", { d: "M680 294V386", class: "t-muted-line", "marker-end": "url(#tour-arrow)" }, layer);

    const d1 = svg("circle", { r: 7, class: "t-pulse" }, layer);
    const d2 = svg("circle", { r: 7, class: "t-pulse" }, layer);
    const d3 = svg("circle", { r: 7, class: "t-pulse t-pulse--plan" }, layer);
    const pathGsv = svg("path", { d: "M750 262H796", class: "t-path-none" }, layer);

    hidden(card.querySelector("rect"), Array.from(card.children).filter((el) => el.tagName === "text"), rows, log, serial, gsv, open, receipt, toReceipt, d1, d2, d3);
    tl.add(card.querySelector("rect"), { opacity: [0, 1], scale: [0.94, 1], duration: 600, ease: "outExpo" }, 100);
    tl.add(Array.from(card.children).filter((el) => el.tagName === "text"), { opacity: [0, 1], duration: 400 }, "<<+=200");
    tl.add(rows, { opacity: [0, 1], translateX: [-24, 0], delay: A.stagger(90), duration: 600, ease: "outExpo" }, "<<+=150");
    tl.add(rows[5], { scale: [1, 1.03, 1], duration: 600, ease: "inOutSine" }, "+=100");
    drawIn(tl, A, toLog, { duration: 600 }, "+=100");
    fadeUp(tl, log, {}, "-=250");
    tl.set(d1, { opacity: 1 }, "<<");
    travel(tl, A, toLog, d1, { duration: 700 }, "<<");
    tl.add(d1, { opacity: 0, duration: 200 }, "<");
    drawIn(tl, A, toSerial, { duration: 500 }, "+=100");
    fadeUp(tl, serial, {}, "-=250");
    tl.set(d2, { opacity: 1 }, "<<");
    travel(tl, A, toSerial, d2, { duration: 600 }, "<<");
    tl.add(d2, { opacity: 0, duration: 200 }, "<");
    fadeUp(tl, gsv, {}, "+=50");
    drawIn(tl, A, toGsv, { duration: 400 }, "<<");
    tl.set(d3, { opacity: 1 }, "<");
    travel(tl, A, pathGsv, d3, { t: [0, 0.6], duration: 500, ease: "outQuad" }, "<<");
    tl.add(d3, { opacity: 0, duration: 250 }, "<");
    popIn(tl, A, [open], { ease: "outElastic(1, .6)", duration: 900 }, "<<");
    tl.add(toReceipt, { opacity: [0, 1], duration: 400 }, "+=100");
    fadeUp(tl, receipt, {}, "<<");
  }

  // -------------------------------------------------- geplante Kapitel ----

  function scenePlanned(ctx, step, chapter) {
    const { tl, A, layer, tour } = ctx;
    const card = group(layer, "planned");
    panel(card, 180, 110, 600, 300, "t-panel t-planned-box");
    label(card, 480, 200, chapter.label, "t-title", { "text-anchor": "middle" });
    badge(card, 480, 246, "Kapitel in Vorbereitung", "plan", 230);
    label(card, 480, 300, "Was es zeigen wird, steht unter der Bühne.", "t-label", { "text-anchor": "middle" });
    const back = tour.hotspot(card, { chapter: "erkennung", x: 400, y: 356, text: "Erkennung" });
    const over = tour.hotspot(card, { chapter: "ueberblick", x: 560, y: 356, text: "Überblick" });
    hidden(card);
    tl.add(card, { opacity: [0, 1], scale: [0.92, 1], duration: 700, ease: "outExpo" }, 100);
    void step;
    void back;
    void over;
  }

  function scenePlaceholder(ctx, step) {
    label(ctx.layer, 480, 270, `Szene „${step.id}“ fehlt`, "t-label", { "text-anchor": "middle" });
  }

  const SCENES = {
    "ueberblick-aufbau": sceneUeberblickAufbau,
    "ueberblick-weg": sceneUeberblickWeg,
    "ueberblick-kapitel": sceneUeberblickKapitel,
    "erkennung-bild": sceneErkennungBild,
    "erkennung-roi": sceneErkennungRoi,
    "erkennung-nachfuehrung": sceneErkennungNachfuehrung,
    "erkennung-entzerren": sceneErkennungEntzerren,
    "erkennung-raster": sceneErkennungRaster,
    "erkennung-zelle": sceneErkennungZelle,
    "erkennung-format": sceneErkennungFormat,
    "erkennung-freigabe": sceneErkennungFreigabe,
    "erkennung-veraltet": sceneErkennungVeraltet,
    "erkennung-ausgabe": sceneErkennungAusgabe,
  };

  const CHAPTER_BLURB = {
    ueberblick: "Aufbau und Weg eines Werts",
    erkennung: "Vom Kamerabild zum Datensatz",
    zeit: "Drei Uhren, ein Versatz",
    training: "Vom Gerät zum Label zur Vorlage",
    bedienung: "Einrichten und lesen",
    regeln: "Was das System nicht tut",
  };

  // ------------------------------------------------- Schnittstelle Kapitel --
  // Kapitel in eigenen Dateien (tour-zeit.js, tour-training.js, ...) melden
  // ihre Szenen über window.dispreadTour.register(id, fn) an und benutzen die
  // Helfer unten. Eine Szene bekommt ctx = { tl, A, layer, tour } und baut
  // ihren Endzustand vollständig selbst auf (Direktlinks springen mitten in
  // ein Kapitel). Die Kapiteldateien laden nach tour.js; die Szenen werden
  // erst beim Anzeigen aufgerufen.
  const API = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });
  API.scenes = API.scenes || {};
  API.blurbs = API.blurbs || {};
  API.register = (id, fn) => { API.scenes[id] = fn; };
  Object.assign(API, {
    W, H, NS, svg, group, label, make, hidden, flat, textWidth, points, clamp, seeded,
    matrix, apply, matrixAttr, lerpParams,
    ROM, READER_CLASSES, DISPLAY, LCD_W, LCD_H, LCD_U, LCD_X, LCD_Y, glyphVector, drawLCD, cellBox,
    chip, badge, panel, arrow, checkMark, streamCam, drawDevice, drawHand,
    glassCorners, cellCorners, cellPolygon, cellCenter,
    VIEW_CAMERA, VIEW_RECT, VIEW_HEAD, FRAME, cameraScene, rectifiedScene, benchScene,
    travel, drawIn, popIn, fadeUp, fact, num,
  });

  // ----------------------------------------------------------------- Tour --

  function readChapters(root) {
    return Array.from(root.querySelectorAll(":scope > .tour-chapter")).map((section) => {
      const heading = section.querySelector("h2");
      const steps = Array.from(section.querySelectorAll(".tour-step")).map((stepEl) => {
        const h3 = stepEl.querySelector("h3");
        const title = h3 ? Array.from(h3.childNodes).filter((n) => !(n.classList && n.classList.contains("headerlink"))).map((n) => n.textContent).join("").trim() : "";
        return { id: h3 ? h3.id : "", title, el: stepEl };
      });
      return {
        id: section.dataset.chapter,
        headingId: heading ? heading.id : section.dataset.chapter,
        label: section.dataset.label || (heading ? heading.textContent.trim() : section.dataset.chapter),
        planned: section.dataset.state === "geplant",
        steps,
      };
    }).filter((chapter) => chapter.steps.length);
  }

  class Tour {
    constructor(root, A) {
      this.root = root;
      this.A = A;
      this.chapters = readChapters(root);
      this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      this.playing = !this.reduced;
      this.visible = false;
      this.ci = 0;
      this.si = 0;
      this.tl = null;
      this.token = 0;
      this.done = false;
      this.started = false;
      this.dwell = null;
      this.build();
      this.onHash = () => this.fromHash(true);
      window.addEventListener("hashchange", this.onHash);
      window.addEventListener("popstate", this.onHash);
      // Die Sofortnavigation verarbeitet Ankerklicks (z. B. im Inhaltsverzeichnis)
      // selbst per pushState, ohne hashchange. Klicks auf Anker der Tour
      // werden deshalb vorher abgefangen.
      this.onClick = (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target instanceof Element ? event.target.closest("a[href*='#']") : null;
        if (!link || link.closest(".tour-ui")) return;
        const url = new URL(link.href, window.location.href);
        if (url.pathname !== window.location.pathname) return;
        const target = this.find(decodeURIComponent(url.hash.slice(1)));
        if (!target) return;
        event.preventDefault();
        event.stopPropagation();
        history.pushState(history.state, "", url.hash);
        this.go(target[0], target[1], true);
        this.ui.scrollIntoView({ block: "start", behavior: this.reduced ? "auto" : "smooth" });
      };
      document.addEventListener("click", this.onClick, true);
      this.observer = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
        for (const entry of entries) this.setVisible(entry.isIntersecting);
      }, { threshold: 0.35 }) : null;
      if (this.observer) this.observer.observe(this.stage);
      else this.visible = true;
      // Beim ersten Aufbau ohne Anker bleibt die Adresse unverändert.
      this.keepHash = true;
      // Der Browser hat beim Laden schon zum Anker im Textfallback gescrollt,
      // der jetzt ausgeblendet ist; deshalb zur Tour zurückscrollen.
      if (this.fromHash(false)) this.ui.scrollIntoView({ block: "start" });
      else this.go(0, 0, false);
      this.keepHash = false;
      root.dataset.tourReady = "true";
    }

    build() {
      const ui = make("div", "tour-ui");
      ui.setAttribute("role", "region");
      ui.setAttribute("aria-label", "Projekt-Tour");

      const nav = make("div", "tour-chapters");
      nav.setAttribute("role", "group");
      nav.setAttribute("aria-label", "Kapitel");
      this.chapterButtons = this.chapters.map((chapter, ci) => {
        const button = make("button", `tour-chapter-button${chapter.planned ? " tour-chapter-button--planned" : ""}`, chapter.label);
        button.type = "button";
        if (chapter.planned) button.setAttribute("aria-label", `${chapter.label} (geplant)`);
        button.addEventListener("click", () => this.go(ci, 0, true));
        nav.appendChild(button);
        return button;
      });

      this.stage = make("div", "tour-stage");
      this.svg = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Projekt-Tour", class: "tour-svg" });
      const defs = svg("defs", {}, this.svg);
      for (const [id, cls] of [["tour-arrow", "t-arrow-head"], ["tour-arrow-plan", "t-arrow-head t-arrow-head--plan"], ["tour-arrow-bad", "t-arrow-head t-arrow-head--bad"]]) {
        const marker = svg("marker", { id, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
        svg("path", { d: "M0 0L10 5L0 10z", class: cls }, marker);
      }
      this.stage.appendChild(this.svg);
      this.progress = make("div", "tour-progress");
      this.progressBar = make("span");
      this.progress.appendChild(this.progressBar);
      this.stage.appendChild(this.progress);

      const bar = make("div", "tour-bar");
      const controls = make("div", "tour-controls");
      this.prevButton = this.controlButton("‹", "Zurück", () => this.step(-1));
      this.playButton = this.controlButton("", "", () => this.togglePlay());
      this.nextButton = this.controlButton("›", "Weiter", () => this.step(1));
      this.replayButton = this.controlButton("↺", "Schritt wiederholen", () => this.go(this.ci, this.si, false));
      controls.append(this.prevButton, this.playButton, this.nextButton, this.replayButton);
      if (document.fullscreenEnabled) {
        this.fullButton = this.controlButton("⛶", "Vollbild", () => this.toggleFullscreen());
        controls.append(this.fullButton);
      }
      this.dots = make("div", "tour-dots");
      this.dots.setAttribute("role", "group");
      this.dots.setAttribute("aria-label", "Schritte");
      this.count = make("output", "tour-count");
      bar.append(controls, this.dots, this.count);

      this.caption = make("div", "tour-caption");
      this.caption.setAttribute("aria-live", "polite");

      ui.append(nav, this.stage, bar, this.caption);
      // Die Tour füllt die Seite; Pfeiltasten blättern deshalb überall, außer
      // in Eingabefeldern (z. B. der Suche).
      this.onKey = (event) => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        const target = event.target;
        if (target instanceof HTMLElement && (target.isContentEditable || target.closest("input, textarea, select"))) return;
        if (event.key === "ArrowRight") { this.step(1); event.preventDefault(); }
        if (event.key === "ArrowLeft") { this.step(-1); event.preventDefault(); }
      };
      document.addEventListener("keydown", this.onKey);
      this.root.prepend(ui);
      this.root.classList.add("tour--ready");
      this.ui = ui;
      this.updatePlayButton();
    }

    controlButton(text, title, handler) {
      const button = make("button", "tour-control", text);
      button.type = "button";
      if (title) {
        button.title = title;
        button.setAttribute("aria-label", title);
      }
      button.addEventListener("click", handler);
      return button;
    }

    toggleFullscreen() {
      if (document.fullscreenElement) document.exitFullscreen();
      else this.ui.requestFullscreen().catch(() => {});
    }

    // Macht einen Bühnenteil zum Link auf eine Doku-Seite (Pfad ab der
    // Wurzel der Seite). `mark` setzt ein "↗" an diese Stelle.
    docLink(element, path, title, mark) {
      element.classList.add("doc-link");
      element.setAttribute("role", "link");
      element.setAttribute("tabindex", "0");
      element.setAttribute("aria-label", title);
      element.dataset.href = path;
      svg("title", {}, element).textContent = title;
      if (mark) label(element, mark[0], mark[1], "↗", "doc-mark", { "text-anchor": "middle" });
      const open = (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.navigate(path);
      };
      element.addEventListener("click", open);
      element.addEventListener("keydown", (event) => {
        if (event.key === "Enter") open(event);
      });
      return element;
    }

    // Über einen echten Link, damit die Sofortnavigation von Zensical greift.
    navigate(path) {
      const link = make("a");
      link.href = new URL(path, SITE_ROOT).href;
      link.hidden = true;
      this.ui.appendChild(link);
      link.click();
      link.remove();
    }

    // Anklickbares Etikett auf der Bühne, öffnet ein Kapitel.
    hotspot(parent, spot) {
      const ci = this.chapters.findIndex((chapter) => chapter.id === spot.chapter);
      if (ci < 0) return group(parent, "hotspot-missing");
      const chapter = this.chapters[ci];
      const outer = group(parent, "", { transform: `translate(${spot.x} ${spot.y})` });
      const root = group(outer, `hotspot${chapter.planned ? " hotspot--planned" : ""}`, {
        tabindex: 0, role: "button", "aria-label": `Kapitel ${chapter.label}${chapter.planned ? " (geplant)" : ""}`,
      });
      const text = `${spot.text}${chapter.planned ? " · geplant" : ""} ›`;
      const t = label(root, 0, 5, text, "hotspot-text", { "text-anchor": "middle" });
      const w = textWidth(t, 7.4) + 26;
      root.insertBefore(svg("rect", { x: -w / 2, y: -14, width: w, height: 28, rx: 14 }), t);
      const open = (event) => {
        event.preventDefault();
        this.go(ci, 0, true);
      };
      root.addEventListener("click", open);
      root.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") open(event);
      });
      return root;
    }

    chapterCard(parent, chapter, x, y, w, h) {
      const ci = this.chapters.indexOf(chapter);
      const current = ci === this.ci;
      const root = group(parent, `chapter-card${chapter.planned ? " chapter-card--planned" : ""}${current ? " chapter-card--current" : ""}`, {
        tabindex: 0, role: "button", "aria-label": `Kapitel ${chapter.label}${chapter.planned ? " (geplant)" : ""}`,
      });
      svg("rect", { x, y, width: w, height: h, rx: 14, class: "chapter-card-bg" }, root);
      label(root, x + 20, y + 40, chapter.label, "t-title-sm");
      label(root, x + 20, y + 68, API.blurbs[chapter.id] || CHAPTER_BLURB[chapter.id] || "", "t-small");
      const state = chapter.planned ? "geplant" : `${chapter.steps.length} Schritte`;
      badge(root, x + 20 + 55, y + h - 32, state, chapter.planned ? "plan" : "valid", 110);
      if (current) label(root, x + w - 20, y + h - 27, "du bist hier", "t-small", { "text-anchor": "end" });
      else label(root, x + w - 20, y + h - 27, "öffnen ›", "t-small t-strong", { "text-anchor": "end" });
      const open = (event) => {
        event.preventDefault();
        this.go(ci, 0, true);
      };
      root.addEventListener("click", open);
      root.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") open(event);
      });
      return root;
    }

    find(id) {
      if (!id) return null;
      for (let ci = 0; ci < this.chapters.length; ci++) {
        const chapter = this.chapters[ci];
        const si = chapter.headingId === id ? 0 : chapter.steps.findIndex((step) => step.id === id);
        if (si >= 0) return [ci, si];
      }
      return null;
    }

    fromHash(scroll) {
      const target = this.find(decodeURIComponent(window.location.hash.slice(1)));
      if (!target) return false;
      if (target[0] === this.ci && target[1] === this.si && this.tl) return true;
      this.go(target[0], target[1], true);
      if (scroll) this.ui.scrollIntoView({ block: "start", behavior: this.reduced ? "auto" : "smooth" });
      return true;
    }

    setVisible(visible) {
      this.visible = visible;
      if (!this.tl) return;
      if (visible) {
        if (!this.started) this.startTimeline();
        else if (!this.done) this.tl.resume();
        else this.scheduleAdvance();
      } else {
        if (!this.done) this.tl.pause();
        this.clearAdvance();
      }
    }

    stopStep() {
      this.clearAdvance();
      if (this.tl) {
        this.tl.pause();
        this.tl.cancel();
        this.tl = null;
      }
    }

    go(ci, si, userAction) {
      this.stopStep();
      this.ci = ci;
      this.si = si;
      const chapter = this.chapters[ci];
      const step = chapter.steps[si];
      const token = ++this.token;
      this.done = false;
      this.started = false;
      if (userAction && !this.reduced && !this.playing) this.updatePlayButton();

      // Bühne neu aufbauen.
      if (this.layer) this.layer.remove();
      this.layer = group(this.svg, `scene scene--${step.id}`);
      this.svg.setAttribute("aria-label", `${chapter.label}: ${step.title}`);
      const tl = this.A.createTimeline({
        autoplay: false,
        defaults: { ease: "outExpo", duration: 700 },
        onComplete: () => {
          if (token !== this.token) return;
          this.done = true;
          this.scheduleAdvance();
        },
      });
      this.tl = tl;
      const own = API.scenes[step.id] || SCENES[step.id];
      const scene = own || (chapter.planned ? scenePlanned : scenePlaceholder);
      this.stage.dataset.scene = own || chapter.planned ? step.id : "fehlt";
      scene({ tl, A: this.A, layer: this.layer, tour: this }, step, chapter);
      tl.add({ duration: 1 });

      this.renderCaption(chapter, step);
      this.renderNav();
      const hash = `#${si === 0 && step.id.endsWith("-geplant") ? chapter.headingId : step.id}`;
      if (!this.keepHash && window.location.hash !== hash) history.replaceState(history.state, "", hash);

      if (this.reduced) {
        tl.seek(tl.duration);
        this.started = true;
        this.done = true;
      } else if (this.visible) {
        this.startTimeline();
      }
    }

    startTimeline() {
      if (!this.tl) return;
      this.started = true;
      this.tl.play();
    }

    dwellTime() {
      const chars = this.caption.textContent.length;
      return clamp(2000 + chars * 32, 5000, 13000);
    }

    scheduleAdvance() {
      this.clearAdvance();
      if (!this.playing || !this.visible || !this.done) return;
      const next = this.nextIndex();
      if (!next) {
        this.playing = false;
        this.updatePlayButton();
        return;
      }
      const ms = this.dwellTime();
      this.progressBar.style.transition = "none";
      this.progressBar.style.transform = "scaleX(0)";
      void this.progressBar.offsetWidth;
      this.progressBar.style.transition = `transform ${ms}ms linear`;
      this.progressBar.style.transform = "scaleX(1)";
      this.dwell = window.setTimeout(() => this.go(next[0], next[1], false), ms);
    }

    clearAdvance() {
      if (this.dwell) window.clearTimeout(this.dwell);
      this.dwell = null;
      if (this.progressBar) {
        this.progressBar.style.transition = "none";
        this.progressBar.style.transform = "scaleX(0)";
      }
    }

    // Automatisch weiter nur innerhalb fertiger Kapitel und in das nächste
    // fertige Kapitel; vor einem geplanten Kapitel hält die Tour an.
    nextIndex() {
      const chapter = this.chapters[this.ci];
      if (this.si + 1 < chapter.steps.length) return [this.ci, this.si + 1];
      const following = this.chapters[this.ci + 1];
      if (following && !following.planned && !chapter.planned) return [this.ci + 1, 0];
      return null;
    }

    step(direction) {
      const chapter = this.chapters[this.ci];
      let ci = this.ci;
      let si = this.si + direction;
      if (si >= chapter.steps.length) {
        ci = Math.min(this.chapters.length - 1, ci + 1);
        si = ci === this.ci ? chapter.steps.length - 1 : 0;
      } else if (si < 0) {
        ci = Math.max(0, ci - 1);
        si = ci === this.ci ? 0 : this.chapters[ci].steps.length - 1;
      }
      if (ci !== this.ci || si !== this.si) this.go(ci, si, true);
    }

    togglePlay() {
      this.playing = !this.playing;
      this.updatePlayButton();
      if (this.playing) {
        if (this.done) {
          if (this.nextIndex()) this.scheduleAdvance();
          else {
            // Am Kapitelende neu starten statt stehen zu bleiben.
            this.go(this.ci, 0, true);
          }
        }
      } else {
        this.clearAdvance();
      }
    }

    updatePlayButton() {
      const label = this.playing ? "Automatisch weiter: an" : "Automatisch weiter: aus";
      this.playButton.textContent = this.playing ? "❚❚" : "▶";
      this.playButton.title = label;
      this.playButton.setAttribute("aria-label", label);
      this.playButton.setAttribute("aria-pressed", String(this.playing));
    }

    renderCaption(chapter, step) {
      const content = make("div", "tour-caption-body");
      const head = make("p", "tour-caption-title");
      head.append(make("span", "tour-caption-chapter", chapter.label), document.createTextNode(step.title));
      content.appendChild(head);
      for (const node of Array.from(step.el.children)) {
        if (node.tagName === "H3") continue;
        const clone = node.cloneNode(true);
        clone.removeAttribute && clone.removeAttribute("id");
        clone.querySelectorAll && clone.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
        content.appendChild(clone);
      }
      this.caption.replaceChildren(content);
    }

    renderNav() {
      this.chapterButtons.forEach((button, ci) => {
        if (ci === this.ci) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
      });
      const chapter = this.chapters[this.ci];
      this.dots.replaceChildren(...chapter.steps.map((step, si) => {
        const dot = make("button", "tour-dot");
        dot.type = "button";
        dot.title = step.title;
        dot.setAttribute("aria-label", `Schritt ${si + 1}: ${step.title}`);
        if (si === this.si) dot.setAttribute("aria-current", "step");
        if (si < this.si) dot.classList.add("tour-dot--seen");
        dot.addEventListener("click", () => this.go(this.ci, si, true));
        return dot;
      }));
      this.count.textContent = `${this.si + 1} / ${chapter.steps.length}`;
      const first = this.ci === 0 && this.si === 0;
      const last = this.ci === this.chapters.length - 1 && this.si === chapter.steps.length - 1;
      this.prevButton.disabled = first;
      this.nextButton.disabled = last;
    }

    destroy() {
      this.stopStep();
      window.removeEventListener("hashchange", this.onHash);
      window.removeEventListener("popstate", this.onHash);
      document.removeEventListener("click", this.onClick, true);
      document.removeEventListener("keydown", this.onKey);
      if (this.observer) this.observer.disconnect();
    }
  }

  function init() {
    if (active) {
      active.destroy();
      active = null;
    }
    const root = document.querySelector("[data-tour]");
    // Die Seitenklasse schaltet das Vollseiten-Layout (tour.css); bei der
    // Sofortnavigation bleibt body erhalten und muss zurückgesetzt werden.
    document.body.classList.toggle("tour-page", Boolean(root));
    if (!root || root.dataset.tourReady) return;
    Promise.all([loadAnime(), loadFacts()]).then(([A]) => {
      if (!root.isConnected || root.dataset.tourReady) return;
      active = new Tour(root, A);
    }).catch((error) => {
      const note = make("p", "tour-error", `Die Animation ist nicht verfügbar (${error.message}). Alle Schritte stehen unten als Text.`);
      root.prepend(note);
    });
  }

  if (typeof document$ !== "undefined") document$.subscribe(init);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
