/* Projekt-Tour, Kapitel „Training“ (docs/uebersicht/projekt-tour.md, Abschnitt
 * #training). Szenen melden sich über window.dispreadTour.register an; Helfer und
 * Konventionen stehen in tour.js unter „Schnittstelle Kapitel“.
 *
 * Belege: scripts/harvest.py (Faktorplan, Haltezeit 4 s, Mindestsprung 1,3,
 * 15 Bilder/s fürs Labeln), scripts/gate-label.py (Schutzintervall M,
 * Ablehnungsgründe), scripts/import-harvest.py (Zellen ausschneiden,
 * Bildgüte, Zellenkonsistenz), src/dispread/ocr/dotmatrix_templates.py
 * (Mittelwert-Vorlage, ROM-Gegenprobe mit höchstens 1 Punkt Abweichung,
 * thresholds_v1), scripts/dotmatrix-train.py (Exit 3), VALIDATION.md
 * 2026-09-30 (Stufe 2c, Abnahme 3). Werte auf der Bühne ohne Beleg sind als
 * Beispiel beschriftet. */
(function () {
  "use strict";

  const T = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });
  T.blurbs.training = "Vom Gerät zum Label zur Vorlage";

  // ------------------------------------------------------------- Helfer --

  // Eine Zelle aus 40 Punktwerten (0..1) auf LCD-Grund; pitch = Punktabstand.
  function drawCell(parent, vec, x, y, pitch, cls) {
    const g = T.group(parent, `train-cell ${cls || ""}`);
    const pad = Math.max(4, pitch * 0.45);
    T.svg("rect", { x: x - pad, y: y - pad, width: 5 * pitch + 2 * pad - pitch * 0.18, height: 8 * pitch + 2 * pad - pitch * 0.18, rx: pitch * 0.4, class: "tp-lcd" }, g);
    const dots = [];
    for (let i = 0; i < 40; i++) {
      const c = i % 5;
      const r = Math.floor(i / 5);
      const d = T.svg("rect", { x: x + c * pitch, y: y + r * pitch, width: pitch * 0.82, height: pitch * 0.82, rx: pitch * 0.18, class: "big-dot" }, g);
      d.style.setProperty("--ink", Math.max(0.07, vec[i]).toFixed(3));
      dots.push(d);
    }
    return { g, dots };
  }

  function rom(ch) {
    return T.glyphVector(ch);
  }

  // Abwandlungen des ROM-Musters, wie die Kamera sie sieht (schematisch).
  function blurred(vec, amount) {
    return vec.map((v, i) => {
      const r = Math.floor(i / 5);
      const c = i % 5;
      let sum = 0;
      let n = 0;
      for (const [dr, dc] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const rr = r + dr;
        const cc = c + dc;
        if (rr >= 0 && rr < 8 && cc >= 0 && cc < 5) { sum += vec[rr * 5 + cc]; n += 1; }
      }
      return T.clamp(v * (1 - amount) + (sum / n) * amount, 0, 1);
    });
  }

  function noisy(vec, seed, amount) {
    const rnd = T.seeded(seed);
    return vec.map((v) => T.clamp(v * 0.9 + 0.05 + (rnd() - 0.5) * amount, 0, 1));
  }

  function shaded(vec) {
    // Ungleiches Licht: zur rechten Seite hin weniger Kontrast.
    return vec.map((v, i) => T.clamp(0.08 + v * (0.95 - (i % 5) * 0.11), 0, 1));
  }

  function slanted(vec) {
    // Schräger Blick: obere Zeilen leicht nach rechts verschoben (Teilpunkte).
    return vec.map((_, i) => {
      const r = Math.floor(i / 5);
      const c = i % 5;
      const shift = (7 - r) * 0.12;
      const src = c - shift;
      const c0 = Math.floor(src);
      const f = src - c0;
      const a = c0 >= 0 && c0 < 5 ? vec[r * 5 + c0] : 0;
      const b = c0 + 1 >= 0 && c0 + 1 < 5 ? vec[r * 5 + c0 + 1] : 0;
      return T.clamp(a * (1 - f) + b * f, 0, 1);
    });
  }

  function mean(vectors) {
    return vectors[0].map((_, i) => vectors.reduce((s, v) => s + v[i], 0) / vectors.length);
  }

  function variants(ch) {
    const base = rom(ch);
    return [
      { name: "scharf", vec: noisy(base, 11, 0.12) },
      { name: "unscharf", vec: noisy(blurred(base, 0.45), 12, 0.1) },
      { name: "schräg", vec: noisy(slanted(base), 13, 0.1) },
      { name: "Schatten", vec: noisy(shaded(base), 14, 0.08) },
    ];
  }

  // Kleines Gerät mit Anzeige; zwei Anzeigen übereinander zum Überblenden.
  function miniDevice(parent, x, y, textA, textB) {
    const g = T.group(parent, "mini-device");
    T.svg("rect", { x, y, width: 300, height: 128, rx: 12, class: "tp-body" }, g);
    T.label(g, x + 16, y + 24, "GSV-2AS", "tp-body-text tp-small");
    T.svg("rect", { x: x + 12, y: y + 36, width: T.LCD_W * 2.6 + 12, height: T.LCD_H * 2.6 + 12, rx: 6, class: "tp-bezel" }, g);
    const a = T.drawLCD(g, textA, x + 18, y + 42, 2.6);
    const b = textB ? T.drawLCD(g, textB, x + 18, y + 42, 2.6) : null;
    for (let i = 0; i < 4; i++) T.svg("rect", { x: x + 18 + i * 46, y: y + 92, width: 36, height: 20, rx: 4, class: "tp-key" }, g);
    T.svg("circle", { cx: x + 272, cy: y + 102, r: 5, class: "tp-led-on" }, g);
    return { g, a: a.root, b: b ? b.root : null };
  }

  function lock(parent, x, y) {
    const g = T.group(parent, "lock");
    T.svg("path", { d: `M${x - 7} ${y}v-6a7 7 0 0 1 14 0v6`, style: "fill:none;stroke:var(--tour-flow);stroke-width:2.5" }, g);
    T.svg("rect", { x: x - 10, y, width: 20, height: 15, rx: 3, style: "fill:var(--tour-flow)" }, g);
    return g;
  }

  // ------------------------------------------------------------ Szenen --

  T.register("training-vorlagen", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    T.label(layer, 40, 44, "Woran erkennt der Leser eine 4?", "t-label t-strong");
    T.label(layer, 40, 64, "Datenblatt, Kamera und gelernte Vorlage im Vergleich (schematisch)", "t-small");

    const left = T.group(layer, "rom-side");
    T.label(left, 125, 112, "Datenblatt", "t-label t-strong", { "text-anchor": "middle" });
    T.label(left, 125, 130, "ideales ROM-Muster", "t-small", { "text-anchor": "middle" });
    const romCell = drawCell(left, rom("4"), 76, 150, 20);

    const mid = T.group(layer, "camera-side");
    T.label(mid, 470, 112, "Echte Kamerabilder", "t-label t-strong", { "text-anchor": "middle" });
    T.label(mid, 470, 130, "dieselbe 4, je nach Aufstellung", "t-small", { "text-anchor": "middle" });
    const vars = variants("4");
    const varEls = vars.map((v, i) => {
      const x = 310 + i * 86;
      const g = T.group(mid, "variant");
      drawCell(g, v.vec, x, 160, 12);
      T.label(g, x + 29, 278, v.name, "t-small", { "text-anchor": "middle" });
      return g;
    });

    const right = T.group(layer, "template-side");
    T.label(right, 815, 112, "Gelernte Vorlage", "t-label t-strong", { "text-anchor": "middle" });
    T.label(right, 815, 130, "Mittel aus vielen Bildern", "t-small", { "text-anchor": "middle" });
    const tpl = drawCell(right, mean(vars.map((v) => v.vec)), 766, 150, 20);

    const a1 = T.arrow(layer, "M210 230H286");
    const a2 = T.arrow(layer, "M660 230H736");

    const classes = T.group(layer, "classes");
    T.label(classes, 480, 384, "13 Zeichen, die der Leser kennt · je eine Vorlage", "t-label t-strong", { "text-anchor": "middle" });
    const chips = T.READER_CLASSES.map((ch, i) => {
      const x = 480 + (i - 6) * 56;
      const g = T.group(classes, "class-chip");
      T.svg("rect", { x: x - 22, y: 404, width: 44, height: 50, rx: 8, class: "token-box" }, g);
      T.label(g, x, 438, ch === " " ? "␣" : ch, "token-small", { "text-anchor": "middle" });
      return g;
    });
    tour.docLink(classes, "api/ocr.html", "OCR-API öffnen", [880, 382]);
    const note = T.label(layer, 480, 500, "Ohne echte Beispiele mit richtigem Label gibt es keine Vorlage.", "t-small t-strong", { "text-anchor": "middle" });

    T.hidden(left, mid.children, right, a1, a2, classes, chips, note);
    T.fadeUp(tl, left, {}, 100);
    tl.add(romCell.dots, { opacity: [0, 1], delay: A.stagger(14), duration: 260 }, "<<");
    T.drawIn(tl, A, a1, { duration: 500 }, "+=100");
    T.fadeUp(tl, Array.from(mid.children).filter((el) => el.tagName === "text"), {}, "<<");
    T.popIn(tl, A, varEls, { delay: A.stagger(160), scale: [0.7, 1] }, "-=200");
    T.drawIn(tl, A, a2, { duration: 500 }, "+=100");
    T.fadeUp(tl, right, {}, "<<");
    tl.add(tpl.dots, { opacity: [0, 1], scale: [0.3, 1], delay: A.stagger(18, { grid: [5, 8], from: "center" }), duration: 380, ease: "outBack(1.8)" }, "<<+=200");
    tl.set(classes, { opacity: 1 }, "+=200");
    T.popIn(tl, A, chips, { delay: A.stagger(60), scale: [0.5, 1] }, "<");
    T.fadeUp(tl, note, {}, "+=150");
  });

  T.register("training-lehrer", (ctx) => {
    const { tl, A, layer } = ctx;
    T.label(layer, 40, 44, "Das Gerät sagt selbst, was es anzeigt", "t-label t-strong");
    T.label(layer, 40, 64, "Beispielwerte · Anzeige = Normierungsfaktor × Messwert", "t-small");

    const pi = T.group(layer, "pi-box");
    T.panel(pi, 40, 170, 200, 120, "t-panel t-flow-box");
    T.svg("rect", { x: 70, y: 196, width: 140, height: 38, rx: 5, class: "tp-pcb" }, pi);
    T.svg("rect", { x: 112, y: 202, width: 34, height: 26, rx: 3, class: "tp-chip-ic" }, pi);
    T.label(pi, 140, 258, "Raspberry Pi 5", "t-label t-strong", { "text-anchor": "middle" });
    T.label(pi, 140, 278, "Ernte-Skript", "t-small", { "text-anchor": "middle" });

    const dev = miniDevice(layer, 610, 168, "+0.46761 mV/V   ", "+2.33805 mV/V   ");
    dev.b.style.opacity = "0";
    const devLabel = T.label(layer, 760, 320, "Prüfling: GSV-2AS", "t-small", { "text-anchor": "middle" });

    const cmdPath = T.svg("path", { d: "M244 200H604", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const ackPath = T.svg("path", { d: "M604 262H244", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const rs = T.label(layer, 424, 236, "RS232", "t-small t-strong", { "text-anchor": "middle" });
    const cmd = T.chip(layer, 340, 168, "set norm 5 · Beispiel", "chip--flow");
    const ack = T.chip(layer, 300, 272, "ASCII: +2.33805 mV/V", "chip--line");
    const pulse = T.svg("circle", { r: 7, class: "t-pulse" }, layer);
    const pulse2 = T.svg("circle", { r: 7, class: "t-pulse" }, layer);

    const cam = T.group(layer, "cam-wrap");
    T.streamCam(cam, 760, 92, 0.8);
    const cone = T.svg("polygon", { points: "760,120 690,212 840,212", class: "t-cone" }, layer);

    const pair = T.group(layer, "labeled");
    T.panel(pair, 330, 360, 300, 84, "t-panel t-valid-box");
    pair.firstChild.style.stroke = "var(--tour-valid)";
    T.svg("rect", { x: 346, y: 374, width: 92, height: 56, rx: 4, class: "tp-frame" }, pair);
    T.svg("rect", { x: 356, y: 396, width: 72, height: 12, rx: 2, class: "tp-lcd" }, pair);
    T.label(pair, 450, 396, "Bild", "t-small");
    T.label(pair, 450, 420, "+ Label +2.33805", "t-mono t-valid-text");
    const pairArrow = T.arrow(layer, "M760 340C760 400 700 402 634 402");

    const warn = T.group(layer, "only-training");
    T.panel(warn, 40, 470, 880, 46, "t-panel t-planned-box");
    T.label(warn, 480, 499, "Nur zum Sammeln von Trainingsdaten. Im Messbetrieb liest das System ausschließlich das Bild.", "t-label", { "text-anchor": "middle" });

    T.hidden(pi, dev.g, devLabel, cmdPath, ackPath, rs, cmd, ack, pulse, pulse2, cam, cone, pair, pairArrow, warn);
    T.fadeUp(tl, [pi, dev.g], { delay: A.stagger(150) }, 100);
    tl.add(devLabel, { opacity: [0, 1], duration: 300 }, "<");
    T.drawIn(tl, A, cmdPath, { duration: 500 }, "+=100");
    tl.add(rs, { opacity: [0, 1], duration: 300 }, "<<");
    T.fadeUp(tl, cmd, {}, "<<");
    tl.set(pulse, { opacity: 1 }, "+=100");
    T.travel(tl, A, cmdPath, pulse, { duration: 800 }, "<");
    tl.add(pulse, { opacity: 0, duration: 150 }, "<");
    // Die Anzeige springt auf den neuen Wert.
    tl.add(dev.a, { opacity: [1, 0], duration: 250 }, "<<");
    tl.add(dev.b, { opacity: [0, 1], duration: 250 }, "<<");
    tl.add(dev.g, { scale: [1, 1.04, 1], duration: 400, ease: "inOutSine" }, "<<");
    T.drawIn(tl, A, ackPath, { duration: 500 }, "+=200");
    tl.set(pulse2, { opacity: 1 }, "<");
    T.travel(tl, A, ackPath, pulse2, { duration: 800 }, "<<");
    T.fadeUp(tl, ack, {}, "<<+=300");
    tl.add(pulse2, { opacity: 0, duration: 150 }, "+=100");
    T.fadeUp(tl, cam, {}, "+=100");
    tl.add(cone, { opacity: [0, 0.9], duration: 400 }, "<<");
    T.drawIn(tl, A, pairArrow, { duration: 500 }, "+=100");
    T.popIn(tl, A, [pair], { scale: [0.85, 1] }, "-=200");
    T.fadeUp(tl, warn, {}, "+=300");
  });

  T.register("training-ernte", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    T.label(layer, 40, 44, "Welche Bilder bekommen ein Label?", "t-label t-strong");
    T.label(layer, 40, 64, "Schematisch: 3 Anzeigewerte, je etwa 4 s gehalten · M = Sicherheitsabstand", "t-small");

    const X0 = 110;
    const X1 = 900;
    const cuts = [110, 373, 637, 900];
    const values = ["+0.46761", "+2.33805", "+0.84170"];
    const levels = [176, 126, 156];
    const M = 46;

    // Telegrammwerte als Treppe.
    const steps = T.group(layer, "telegram-steps");
    T.label(layer, 100, 154, "Telegramm", "t-small", { "text-anchor": "end" });
    const stepEls = values.map((v, i) => {
      const g = T.group(steps, "step");
      T.svg("path", { d: `M${cuts[i]} ${levels[i]}H${cuts[i + 1]}`, class: "t-value-line" }, g);
      T.label(g, (cuts[i] + cuts[i + 1]) / 2, levels[i] - 12, v, "t-mono", { "text-anchor": "middle" });
      return g;
    });
    const risers = T.svg("path", { d: `M${cuts[1]} ${levels[0]}V${levels[1]}M${cuts[2]} ${levels[1]}V${levels[2]}`, class: "t-value-line", style: "stroke-dasharray:4 4" }, layer);

    // Unsichere Bereiche: Start, ±M um jeden Wechsel, Ende des letzten Werts.
    const zones = T.group(layer, "guard-zones");
    const zoneRects = [
      [cuts[0], M], [cuts[1] - M, 2 * M], [cuts[2] - M, 2 * M], [cuts[3] - M, M],
    ].map(([x, w]) => T.svg("rect", { x, y: 196, width: w, height: 112, rx: 4, style: "fill:var(--tour-bad-bg);stroke:var(--tour-bad);stroke-dasharray:4 3" }, zones));
    const mLabel = T.group(layer, "m-label");
    T.svg("path", { d: `M${cuts[1] - M} 320H${cuts[1]}`, class: "brace-line brace-line--bad" }, mLabel);
    T.label(mLabel, cuts[1] - M / 2, 338, "M", "t-label t-bad-text", { "text-anchor": "middle" });
    T.svg("path", { d: `M${cuts[1]} 320H${cuts[1] + M}`, class: "brace-line brace-line--bad" }, mLabel);
    T.label(mLabel, cuts[1] + M / 2, 338, "M", "t-label t-bad-text", { "text-anchor": "middle" });

    // Kamerabilder als Striche auf der Zeitachse.
    T.label(layer, 100, 258, "Bilder", "t-small", { "text-anchor": "end" });
    const axis = T.svg("path", { d: `M${X0} 284H${X1 + 20}`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, layer);
    const ticks = [];
    const inGuard = (x) => x < cuts[0] + M || x >= cuts[3] - M || Math.abs(x - cuts[1]) < M || Math.abs(x - cuts[2]) < M;
    for (let x = X0 + 8; x < X1; x += 17) {
      const bad = inGuard(x);
      const t = T.svg("rect", { x: x - 5, y: 236, width: 10, height: 40, rx: 2, style: bad ? "fill:var(--tour-bad-bg);stroke:var(--tour-bad)" : "fill:var(--tour-valid-bg);stroke:var(--tour-valid)" }, layer);
      t.dataset.bad = bad ? "1" : "0";
      ticks.push(t);
    }

    const legend = T.group(layer, "legend");
    T.badge(legend, 210, 380, "beschriftet", "valid", 120);
    T.label(legend, 280, 385, "sicher mitten in einem Wert", "t-small");
    T.badge(legend, 560, 380, "verworfen", "bad", 120);
    T.label(legend, 630, 385, "zu nah an einem Wechsel", "t-small");

    const facts = T.group(layer, "facts");
    T.panel(facts, 40, 420, 880, 96, "t-panel");
    T.label(facts, 60, 448, "harvest.py: fester Faktorplan, jeder Sprung mindestens ×1,3 · sync-record.py: Bilder und Telegramme gemeinsam", "t-small t-strong");
    T.label(facts, 60, 472, "gate-label.py: verwirft ±M um jeden Wechsel, Telegrammlücken und das offene Ende des letzten Werts", "t-small t-strong");
    T.label(facts, 60, 496, "M wird je Kamera gemessen (Timing-Kalibrierung); ohne passende Kalibrierung keine Ernte", "t-small t-strong");
    tour.docLink(facts, "docs/TIMING.html", "Zeitverhalten öffnen", [904, 438]);

    T.hidden(stepEls, risers, zoneRects, mLabel, axis, ticks, legend, facts);
    tl.add(axis, { opacity: [0, 1], duration: 300 }, 100);
    stepEls.forEach((g, i) => {
      T.fadeUp(tl, g, { duration: 500 }, i === 0 ? "+=100" : "+=200");
      if (i === 1) tl.add(risers, { opacity: [0, 1], duration: 300 }, "<<");
    });
    tl.add(ticks, { opacity: [0, 1], scaleY: [0.2, 1], delay: A.stagger(25), duration: 300, ease: "outBack(1.6)" }, "+=100");
    tl.add(zoneRects, { opacity: [0, 0.85], scaleX: [0.3, 1], delay: A.stagger(150), duration: 500, ease: "outExpo" }, "+=200");
    T.fadeUp(tl, mLabel, {}, "<<+=200");
    const badTicks = ticks.filter((t) => t.dataset.bad === "1");
    tl.add(badTicks, { translateY: [0, -6, 0], duration: 400, delay: A.stagger(30), ease: "inOutSine" }, "+=100");
    T.fadeUp(tl, legend, {}, "+=100");
    T.fadeUp(tl, facts, {}, "+=200");
  });

  T.register("training-lernen", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    T.label(layer, 40, 44, "Aus vielen Kästchen wird eine Vorlage", "t-label t-strong");
    T.label(layer, 40, 64, "Beispiel für das Zeichen 4 · schematisch", "t-small");

    // Ausschneiden.
    const cut = T.group(layer, "cut");
    T.svg("rect", { x: 34, y: 92, width: T.LCD_W * 2.6 + 12, height: T.LCD_H * 2.6 + 12, rx: 6, class: "tp-bezel" }, cut);
    T.drawLCD(cut, "+0.46761 mV/V   ", 40, 98, 2.6);
    const cellX = 40 + (2 + 3 * 6) * 2.6 - 1;
    T.svg("rect", { x: cellX, y: 98 + 2.5 * 2.6 - 1, width: 5 * 2.6 + 2, height: 8 * 2.6 + 2, class: "cell-box cell-box--focus" }, cut);
    T.label(cut, 40, 162, "Kästchen ausschneiden", "t-small t-strong");

    const checks = T.group(layer, "import-checks");
    T.chip(checks, 40, 176, "Bildgüte ✓", "chip--valid");
    T.chip(checks, 140, 176, "passt zu den anderen ✓", "chip--valid");

    const stack = T.group(layer, "stack");
    const vars = variants("4").concat([{ vec: noisy(blurred(rom("4"), 0.25), 21, 0.1) }, { vec: noisy(rom("4"), 22, 0.16) }]);
    const stackEls = vars.map((v, i) => {
      const g = T.group(stack, "stack-cell");
      drawCell(g, v.vec, 60 + (i % 3) * 66, 236 + Math.floor(i / 3) * 112, 10);
      return g;
    });
    T.label(stack, 128, 466, "viele beschriftete 4er", "t-small", { "text-anchor": "middle" });

    const toMean = T.arrow(layer, "M262 330H318");
    const tplGroup = T.group(layer, "template");
    T.label(tplGroup, 386, 214, "Vorlage", "t-label t-strong", { "text-anchor": "middle" });
    const tplVec = mean(vars.map((v) => v.vec));
    const tpl = drawCell(tplGroup, tplVec, 344, 236, 17);

    // ROM-Gegenprobe.
    const toRom = T.arrow(layer, "M458 330H514");
    const check = T.group(layer, "rom-check");
    T.label(check, 640, 214, "ROM-Gegenprobe", "t-label t-strong", { "text-anchor": "middle" });
    const bin = tplVec.map((v) => (v >= 0.5 ? 1 : 0));
    const romVec = rom("4");
    let deviation = 0;
    const P = 17;
    const cx0 = 540;
    const cy0 = 236;
    T.svg("rect", { x: cx0 - 8, y: cy0 - 8, width: 5 * P + 13, height: 8 * P + 13, rx: 7, class: "t-panel" }, check);
    for (let i = 0; i < 40; i++) {
      const c = i % 5;
      const r = Math.floor(i / 5);
      const same = bin[i] === romVec[i];
      if (!same) deviation += 1;
      const on = romVec[i] === 1;
      T.svg("rect", {
        x: cx0 + c * P, y: cy0 + r * P, width: P * 0.8, height: P * 0.8, rx: 3,
        style: same ? (on ? "fill:var(--tour-ink)" : "fill:var(--tour-faint)") : "fill:var(--tour-bad)",
      }, check);
    }
    T.label(check, 664, 262, "Vorlage in an/aus geteilt", "t-small");
    T.label(check, 664, 280, "(Grenze 0,5), dann Punkt", "t-small");
    T.label(check, 664, 298, "für Punkt mit dem", "t-small");
    T.label(check, 664, 316, "HD44780-Muster verglichen", "t-small");
    T.label(check, 664, 334, "(rot = Abweichung)", "t-small");
    const okBadge = T.group(check, "ok");
    T.badge(okBadge, 760, 360, `${deviation} Punkte Abweichung ✓`, "valid", 200);
    T.label(okBadge, 760, 392, "erlaubt: höchstens 1", "t-small", { "text-anchor": "middle" });

    const fail = T.group(layer, "rom-fail");
    const wrong = rom("1");
    let wrongDev = 0;
    for (let i = 0; i < 40; i++) if (wrong[i] !== romVec[i]) wrongDev += 1;
    T.panel(fail, 520, 418, 400, 60, "t-panel");
    fail.firstChild.style.stroke = "var(--tour-bad)";
    T.label(fail, 536, 442, `Falsches Label (eine 1 als „4“): ${wrongDev} Punkte daneben`, "t-small t-bad-text");
    T.label(fail, 536, 462, "→ Training schreibt nichts (Exit 3), Schwellen bleiben unberührt", "t-small t-strong");

    const thr = T.group(layer, "thresholds");
    T.panel(thr, 40, 486, 880, 44, "t-panel t-flow-box");
    T.label(thr, 56, 513, "Schwellen (thresholds_v1): D_max = 1,25 × 99,5-Perzentil richtiger Abstände · margin_min aus Vorsprüngen", "t-small t-strong");
    tour.docLink(thr, "docs/VALIDATION.html", "Validierung öffnen", [906, 500]);
    const frozen = T.group(layer, "frozen");
    lock(frozen, 840, 110);
    T.label(frozen, 840, 150, "fertige Vorlagen:", "t-small", { "text-anchor": "middle" });
    T.label(frozen, 840, 166, "eingefroren, mit Prüfsumme", "t-small t-strong", { "text-anchor": "middle" });

    T.hidden(cut, checks.children, stackEls, stack.querySelector("text"), toMean, tplGroup, toRom, check, okBadge, fail, thr, frozen);
    T.fadeUp(tl, cut, {}, 100);
    T.fadeUp(tl, Array.from(checks.children), { delay: A.stagger(150) }, "+=100");
    T.popIn(tl, A, stackEls, { delay: A.stagger(90), scale: [0.6, 1] }, "+=100");
    tl.add(stack.querySelector("text"), { opacity: [0, 1], duration: 300 }, "<");
    T.drawIn(tl, A, toMean, { duration: 400 }, "+=100");
    T.fadeUp(tl, tplGroup, {}, "<<");
    tl.add(tpl.dots, { opacity: [0, 1], delay: A.stagger(15), duration: 260 }, "<<");
    T.drawIn(tl, A, toRom, { duration: 400 }, "+=100");
    T.fadeUp(tl, check, {}, "<<");
    T.popIn(tl, A, [okBadge], { ease: "outElastic(1, .6)", duration: 900 }, "+=100");
    T.fadeUp(tl, fail, {}, "+=300");
    T.fadeUp(tl, thr, {}, "+=200");
    T.popIn(tl, A, [frozen], {}, "+=100");
  });

  T.register("training-abnahme", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    T.label(layer, 40, 44, "Prüfen an Aufstellungen, die das Training nie gesehen hat", "t-label t-strong");
    T.label(layer, 40, 64, "Abnahme 3, 2026-09-30 · Zahlen aus VALIDATION.md", "t-small");

    const train = T.group(layer, "train-groups");
    T.panel(train, 40, 92, 300, 222, "t-panel");
    T.label(train, 60, 120, "Training (Stufe 2c)", "t-label t-strong");
    const groups = ["ab1", "ab2", "ab3", "ab4", "auf2", "ernte1", "sc3", "sc4", "sc5", "sc6"];
    const groupEls = groups.map((name, i) => {
      const g = T.group(train, "group-chip");
      const x = 60 + (i % 4) * 68;
      const y = 140 + Math.floor(i / 4) * 40;
      T.svg("rect", { x, y, width: 58, height: 28, rx: 14, class: "chip-bg" }, g);
      T.label(g, x + 29, y + 19, name, "t-mono t-mono-sm", { "text-anchor": "middle" });
      return g;
    });
    T.label(train, 60, 290, "Entwicklung: loo, je Gruppe einmal zurückgehalten", "t-small");
    tour.docLink(train, "docs/FORTSCHRITT.html", "Fortschritt Ernten/Training öffnen", [324, 110]);

    const toFrozen = T.arrow(layer, "M344 202H396");
    const frozen = T.group(layer, "frozen");
    T.panel(frozen, 400, 152, 170, 100, "t-panel t-flow-box");
    lock(frozen, 485, 178);
    T.label(frozen, 485, 216, "Vorlagen eingefroren", "t-small t-strong", { "text-anchor": "middle" });
    T.label(frozen, 485, 236, "sha256 6f20dec4…", "t-mono t-mono-sm", { "text-anchor": "middle" });
    const toTest = T.arrow(layer, "M574 202H626");

    const test = T.group(layer, "test-groups");
    T.panel(test, 630, 92, 290, 222, "t-panel t-flow-box");
    T.label(test, 650, 120, "Abnahme: zwei neue Aufstellungen", "t-label t-strong");
    T.label(test, 650, 152, "ab5", "t-mono t-strong");
    T.label(test, 700, 152, "fast frontal, gedreht", "t-small");
    T.label(test, 650, 180, "ab6", "t-mono t-strong");
    T.label(test, 700, 180, "schräg von links", "t-small");
    T.label(test, 650, 214, "Kriterium, vorher festgelegt:", "t-small");
    T.label(test, 650, 234, "0 falsch, höchstens 20 % abgelehnt", "t-small t-strong");
    T.label(test, 650, 262, "Neue Aufstellungen desselben Geräts,", "t-small");
    T.label(test, 650, 280, "kein zweites Gerät.", "t-small");

    const result = T.group(layer, "result-table");
    T.panel(result, 40, 334, 530, 150, "t-panel t-record");
    const rows = [
      ["Gruppe", "richtig / abgelehnt / falsch", "Plateaus"],
      ["ab5", "142 / 0 / 0", "48"],
      ["ab6", "73 / 0 / 0", "37"],
      ["gesamt", "215 / 0 / 0", "85"],
    ];
    const rowEls = rows.map((row, i) => {
      const g = T.group(result, "result-row");
      const y = 364 + i * 30;
      const cls = i === 0 ? "t-small" : i === 3 ? "t-label t-strong" : "t-label";
      T.label(g, 60, y, row[0], i === 0 ? "t-small" : "t-mono");
      T.label(g, 330, y, row[1], cls, { "text-anchor": "middle" });
      T.label(g, 540, y, row[2], cls, { "text-anchor": "end" });
      if (i < 3) T.svg("path", { d: `M60 ${y + 10}H550`, class: "t-row-line" }, g);
      return g;
    });
    tour.docLink(result, "docs/VALIDATION.html", "Validierung öffnen", [552, 352]);

    const verdict = T.group(layer, "verdict");
    T.badge(verdict, 745, 368, "bestanden", "valid", 160);
    T.label(verdict, 745, 404, "Obergrenze der Fehlerrate", "t-small", { "text-anchor": "middle" });
    T.label(verdict, 745, 428, "3,5 % (95 %, 85 Plateaus)", "t-label t-strong", { "text-anchor": "middle" });

    const limits = T.group(layer, "limits");
    T.panel(limits, 40, 494, 880, 36, "t-panel t-planned-box");
    T.label(limits, 480, 517, "Grenzen: ein Gerät · nur Raumlicht · nur mV/V · keine negativen Werte", "t-small t-plan-text", { "text-anchor": "middle" });
    tour.docLink(limits, "docs/uebersicht/daten-und-abnahme.html", "Daten und Abnahme öffnen");

    T.hidden(train, groupEls, toFrozen, frozen, toTest, test, result, rowEls, verdict, limits);
    T.fadeUp(tl, train, {}, 100);
    T.popIn(tl, A, groupEls, { delay: A.stagger(60), scale: [0.6, 1] }, "-=300");
    T.drawIn(tl, A, toFrozen, { duration: 400 }, "+=100");
    T.popIn(tl, A, [frozen], {}, "-=100");
    T.drawIn(tl, A, toTest, { duration: 400 }, "+=100");
    T.fadeUp(tl, test, {}, "-=100");
    T.fadeUp(tl, result, {}, "+=300");
    T.fadeUp(tl, rowEls, { delay: A.stagger(180) }, "<<+=200");
    T.popIn(tl, A, [verdict], { ease: "outElastic(1, .6)", duration: 1000 }, "+=150");
    T.fadeUp(tl, limits, {}, "+=300");
  });
})();
