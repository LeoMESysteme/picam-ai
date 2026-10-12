/* Projekt-Tour, Kapitel „Zeit“ (docs/uebersicht/projekt-tour.md, Abschnitt
 * #zeit). Szenen melden sich über window.dispreadTour.register an; Helfer und
 * Konventionen stehen in tour.js unter „Schnittstelle Kapitel“.
 *
 * Quellen der Aussagen: src/dispread/records.py (TimeBaseKind,
 * to_boottime_ns, SUSPEND_TOLERANCE_NS), scripts/sync-record.py
 * (measure_clock_offset_ns, Telegrammstempel in BOOTTIME),
 * src/dispread/timing_calibration.py, scripts/display-offset.py,
 * scripts/gate-label.py (Schutzfenster ±M), docs/TIMING.md und
 * docs/uebersicht/zeitstempel.md. Alle Zahlen auf der Bühne sind Beispiele. */
(function () {
  "use strict";

  const T = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });
  T.blurbs.zeit = "Uhren, Versatz, Zuordnung";

  // --------------------------------------------------------------- Helfer --

  // Zifferblatt mit zwei Zeigern. Jeder Zeiger ist eine Gruppe mit einem
  // unsichtbaren Kreis, damit die Drehung (CSS, fill-box) um die Mitte läuft.
  function clockFace(parent, cx, cy, r, options) {
    const opts = options || {};
    const root = T.group(parent, "clock");
    T.svg("circle", { cx, cy, r, class: opts.planned ? "t-panel t-planned-box" : "t-panel t-flow-box" }, root);
    for (let i = 0; i < 12; i++) {
      const a = (i * Math.PI) / 6;
      const x1 = cx + Math.sin(a) * (r - 7);
      const y1 = cy - Math.cos(a) * (r - 7);
      const x2 = cx + Math.sin(a) * (r - 2);
      const y2 = cy - Math.cos(a) * (r - 2);
      T.svg("path", { d: `M${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}`, style: "stroke: var(--tour-muted); stroke-width: 2" }, root);
    }
    const hand = (length, width) => {
      const g = T.group(root, "clock-hand");
      T.svg("circle", { cx, cy, r: r - 1, fill: "none", stroke: "none" }, g);
      T.svg("path", { d: `M${cx} ${cy}V${cy - length}`, style: `stroke: var(--tour-ink); stroke-width: ${width}; stroke-linecap: round` }, g);
      return g;
    };
    const hour = hand(r * 0.5, 4);
    const minute = hand(r * 0.78, 2.5);
    T.svg("circle", { cx, cy, r: 4, style: "fill: var(--tour-ink)" }, root);
    if (opts.unknown) T.label(root, cx, cy + r * 0.62, "?", "t-label t-plan-text", { "text-anchor": "middle" });
    return { root, hour, minute };
  }

  // Ziel für einen Doku-Link: Gruppe, deren erstes Rechteck den Rahmen bildet.
  function linkPill(parent, x, y, text, kind) {
    const root = T.group(parent, "link-pill");
    const t = T.label(root, x + 12, y + 18, text, kind === "plan" ? "t-small t-plan-text" : "t-small t-strong");
    const w = T.textWidth(t, 7) + 40;
    root.insertBefore(T.svg("rect", { x, y, width: w, height: 28, rx: 14, class: kind === "plan" ? "t-panel t-planned-box" : "t-panel t-flow-box" }), t);
    return { root, w };
  }

  function title(layer, text, sub) {
    const g = T.group(layer, "zeit-title");
    T.label(g, 40, 46, text, "t-label t-strong");
    if (sub) T.label(g, 40, 68, sub, "t-small");
    return g;
  }

  function miniLcd(parent, x, y, w, h, text) {
    const g = T.group(parent, "mini-lcd");
    T.svg("rect", { x, y, width: w, height: h, rx: 3, class: "tp-bezel" }, g);
    T.svg("rect", { x: x + 3, y: y + 3, width: w - 6, height: h - 6, rx: 2, class: "tp-lcd" }, g);
    if (text) T.label(g, x + w / 2, y + h / 2 + 4, text, "t-mono", { "text-anchor": "middle", style: "font-size: 11px; fill: #1f2b10" });
    return g;
  }

  // ------------------------------------------------------- 1 · Drei Uhren --

  T.register("zeit-uhren", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = title(layer, "Drei Quellen, drei Uhren", "Ein Zeitpunkt ist nur zusammen mit seiner Uhr (Zeitbasis) auswertbar.");

    const cols = [];
    // Kamera
    const cam = T.group(layer, "src-cam");
    T.streamCam(cam, 170, 168, 1.2);
    T.label(cam, 170, 236, "StreamCam-Bild", "t-label t-strong", { "text-anchor": "middle" });
    cols.push(cam);
    // Messverstärker
    const dev = T.group(layer, "src-dev");
    T.svg("rect", { x: 385, y: 124, width: 190, height: 82, rx: 10, class: "tp-body" }, dev);
    T.label(dev, 397, 142, "GSV-2AS", "tp-body-text", { style: "font-size: 12px" });
    miniLcd(dev, 397, 152, 166, 38, "+0.46761 mV/V");
    T.label(dev, 480, 236, "serielles Telegramm", "t-label t-strong", { "text-anchor": "middle" });
    cols.push(dev);
    // Referenz
    const ref = T.group(layer, "src-ref");
    T.svg("rect", { x: 695, y: 124, width: 190, height: 82, rx: 10, class: "t-panel" }, ref);
    T.label(ref, 790, 160, "Kalibrierreferenz", "t-label t-strong", { "text-anchor": "middle" });
    T.label(ref, 790, 182, "Vergleichsgerät des Labors", "t-small", { "text-anchor": "middle" });
    T.label(ref, 790, 236, "Referenzwert", "t-label t-strong", { "text-anchor": "middle" });
    cols.push(ref);

    const links = [170, 480, 790].map((x, i) => T.svg("path", {
      d: `M${x} 246V${282}`, class: i === 2 ? "t-plan-line" : "t-flow-line", "marker-end": `url(#${i === 2 ? "tour-arrow-plan" : "tour-arrow"})`,
    }, layer));

    const clocks = [
      clockFace(layer, 170, 334, 44),
      clockFace(layer, 480, 334, 44),
      clockFace(layer, 790, 334, 44, { planned: true, unknown: true }),
    ];
    const names = T.group(layer, "clock-names");
    T.label(names, 170, 404, "CLOCK_MONOTONIC", "t-mono t-strong", { "text-anchor": "middle" });
    T.label(names, 170, 424, "vom Kameratreiber · v4l2_monotonic", "t-small", { "text-anchor": "middle" });
    T.label(names, 480, 404, "CLOCK_BOOTTIME", "t-mono t-strong", { "text-anchor": "middle" });
    T.label(names, 480, 424, "vom Pi beim Empfang gestempelt", "t-small", { "text-anchor": "middle" });
    T.label(names, 790, 404, "eigene Uhr", "t-mono t-strong t-plan-text", { "text-anchor": "middle" });
    T.label(names, 790, 424, "Zeitbezug zum Pi offen", "t-small", { "text-anchor": "middle" });
    const oq = linkPill(layer, 735, 434, "OQ-03 ↗", "plan");
    tour.docLink(oq.root, "docs/open-questions.html#oq-03", "OQ-03 öffnen: Zeitquelle der Referenz");

    const note = T.group(layer, "clock-note");
    T.panel(note, 60, 470, 620, 52, "t-panel");
    T.label(note, 80, 492, "Beide Pi-Uhren zählen ab dem Start. MONOTONIC hält im Ruhezustand", "t-small t-strong");
    T.label(note, 80, 510, "(Suspend) an, BOOTTIME läuft weiter. Ohne Suspend liegen sie wenige ns auseinander.", "t-small t-strong");
    tour.docLink(note, "docs/uebersicht/zeitstempel.html", "Zeitstempel richtig lesen", [664, 486]);

    T.hidden(head, cols, links, clocks.map((c) => c.root), names, oq.root, note);
    T.fadeUp(tl, head, {}, 100);
    T.fadeUp(tl, cols, { delay: A.stagger(160), translateY: [30, 0], ease: "outBack(1.4)", duration: 800 }, "+=100");
    links.forEach((l, i) => T.drawIn(tl, A, l, { duration: 400 }, i === 0 ? "+=50" : "<<+=120"));
    T.popIn(tl, A, clocks.map((c) => c.root), { delay: A.stagger(140), scale: [0.6, 1] }, "+=50");
    T.fadeUp(tl, names, {}, "-=200");
    // Die Zeiger laufen; die Referenzuhr steht anders, ihr Bezug ist unbekannt.
    const spins = [[0, 300], [4, 304], [130, 470]];
    clocks.forEach((c, i) => {
      tl.add(c.minute, { rotate: spins[i], duration: 2200, ease: "inOutSine" }, i === 0 ? "+=100" : "<<");
      tl.add(c.hour, { rotate: [spins[i][0] / 12 + 60, spins[i][1] / 12 + 60], duration: 2200, ease: "inOutSine" }, "<<");
    });
    T.popIn(tl, A, [oq.root], {}, "-=1200");
    T.fadeUp(tl, note, {}, "-=600");
  });

  // ---------------------------------------------------- 2 · Umrechnen ------

  T.register("zeit-versatz", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = title(layer, "Kamerazeit in BOOTTIME umrechnen", "Schematisch: der Versatz ist hier vergrößert gezeichnet.");
    const X0 = 230;
    const X1 = 900;
    const rulers = T.group(layer, "rulers");
    const ruler = (y, name, sub) => {
      T.svg("path", { d: `M${X0} ${y}H${X1}`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, rulers);
      for (let x = X0 + 20; x < X1 - 10; x += 40) T.svg("path", { d: `M${x} ${y - 5}V${y + 5}`, class: "t-axis" }, rulers);
      T.label(rulers, X0 - 16, y - 2, name, "t-mono t-strong", { "text-anchor": "end" });
      T.label(rulers, X0 - 16, y + 16, sub, "t-small", { "text-anchor": "end" });
    };
    ruler(150, "MONOTONIC", "Kamerabilder");
    ruler(290, "BOOTTIME", "Telegramme");
    const frames = T.group(layer, "frames");
    [300, 420, 540, 660, 780].forEach((x) => T.svg("rect", { x: x - 12, y: 120, width: 24, height: 18, rx: 3, class: "tp-frame-mini", style: "stroke: var(--tour-line); stroke-width: 1.5" }, frames));
    const tels = T.group(layer, "telegrams");
    [330, 450, 730, 850].forEach((x) => {
      T.svg("rect", { x: x - 5, y: 262, width: 10, height: 20, rx: 2, style: "fill: var(--tour-flow)" }, tels);
    });
    T.label(tels, 730, 254, "Telegramm", "t-small", { "text-anchor": "middle" });

    const OFF = 70;
    const pick = T.group(layer, "pick");
    T.svg("rect", { x: 528, y: 118, width: 24, height: 22, rx: 3, style: "fill: none; stroke: var(--tour-flow); stroke-width: 3" }, pick);
    T.label(pick, 540, 108, "t_Bild", "t-mono", { "text-anchor": "middle" });
    const drop = T.svg("path", { d: `M540 156C540 210 ${540 + OFF} 222 ${540 + OFF} 276`, class: "t-flow-dash", "marker-end": "url(#tour-arrow)" }, layer);
    const offLabel = T.group(layer, "off-label");
    T.label(offLabel, 600, 210, "+ Versatz", "t-label t-strong", { style: "fill: var(--tour-flow)" });
    const dot = T.svg("circle", { cx: 540 + OFF, cy: 290, r: 7, class: "t-pulse" }, layer);
    const result = T.group(layer, "result");
    T.chip(result, 520, 306, "t_BOOTTIME = t_Bild + Versatz", "chip--flow");

    const sess = T.group(layer, "session");
    T.panel(sess, 60, 360, 330, 150, "t-panel t-flow-box");
    T.label(sess, 80, 388, "session.json", "t-mono t-strong");
    T.label(sess, 80, 412, "Versatz BOOTTIME − MONOTONIC", "t-small t-strong");
    T.label(sess, 80, 434, "zu Beginn und am Ende der Aufnahme", "t-small");
    T.label(sess, 80, 452, "gemessen, je der Median mehrerer", "t-small");
    T.label(sess, 80, 470, "eng geklammerter Einzelmessungen", "t-small");
    T.label(sess, 80, 494, "umgerechnet wird mit dem Startwert", "t-small");
    tour.docLink(sess, "docs/uebersicht/zeitstempel.html", "Zeitstempel richtig lesen", [374, 380]);

    const rules = T.group(layer, "rules");
    T.panel(rules, 420, 360, 480, 150, "t-panel");
    T.label(rules, 440, 388, "records.to_boottime_ns, die einzige Umrechnungsstelle", "t-small t-strong");
    T.checkMark(rules, 452, 418, "bad");
    T.label(rules, 472, 423, "Versatz fehlt → abgelehnt", "t-label");
    T.checkMark(rules, 452, 450, "bad");
    T.label(rules, 472, 455, "Start und Ende > 1 ms auseinander (Suspend?) → abgelehnt", "t-label");
    T.checkMark(rules, 452, 482, "ok");
    T.label(rules, 472, 487, "sonst: umgerechnet, nie geraten", "t-label");
    tour.docLink(rules, "api/vertraege.html", "Verträge (records) öffnen", [884, 380]);
    const ruleRows = Array.from(rules.children).slice(2);

    T.hidden(head, rulers, frames, tels, pick, offLabel, dot, result, sess, rules.querySelector("rect"), rules.children[1], ruleRows);
    T.fadeUp(tl, head, {}, 100);
    tl.add(rulers, { opacity: [0, 1], duration: 500 }, "+=100");
    tl.add(frames.children, { opacity: [0, 1], scale: [0.3, 1], delay: A.stagger(90), duration: 400, ease: "outBack(2)" }, "+=50");
    tl.set(frames, { opacity: 1 }, "<<");
    tl.add(tels.children, { opacity: [0, 1], translateY: [-10, 0], delay: A.stagger(90), duration: 400 }, "<<+=200");
    tl.set(tels, { opacity: 1 }, "<<");
    T.fadeUp(tl, sess, {}, "+=150");
    T.popIn(tl, A, [pick], { ease: "outElastic(1, .6)", duration: 800 }, "+=100");
    T.drawIn(tl, A, drop, { duration: 700 }, "+=100");
    T.fadeUp(tl, offLabel, {}, "<<+=200");
    T.popIn(tl, A, [dot], {}, "+=50");
    T.fadeUp(tl, result, {}, "<<+=100");
    tl.add([rules.querySelector("rect"), rules.children[1]], { opacity: [0, 1], duration: 400 }, "+=200");
    tl.add(ruleRows, { opacity: [0, 1], translateX: [-12, 0], delay: A.stagger(70), duration: 500 }, "<<+=150");
  });

  // ------------------------------------------- 3 · Telegramm und Anzeige --

  T.register("zeit-anzeige", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = title(layer, "Wann zeigt die Anzeige, was das Gerät sendet?", "Gemessen statt angenommen · schematisch, Zeitachse in BOOTTIME");
    const AX = 380;
    const tTel = 300;
    const mid = 520;
    const k = 50 / Math.log(9);
    const p = (x) => 1 / (1 + Math.exp(-(x - mid) / k));
    const Y = (v) => 340 - 130 * v;

    // Schutzfenster ±M um den Telegrammwechsel (gate-label.py).
    const M = 280;
    const guard = T.group(layer, "guard");
    T.svg("rect", { x: 130, y: 96, width: tTel + M - 130, height: AX - 96, rx: 6, style: "fill: var(--tour-plan-bg); opacity: .7" }, guard);
    T.label(guard, 140, 404, "Schutzfenster ±M um den Telegrammwechsel: diese Bilder bekommen beim Ernten kein Label", "t-small t-plan-text");

    const axis = T.svg("path", { d: `M120 ${AX}H890`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, layer);
    const tel = T.group(layer, "telegram");
    T.svg("path", { d: `M${tTel} 104V${AX}`, style: "stroke: var(--tour-flow); stroke-width: 3" }, tel);
    T.chip(tel, tTel - 176, 100, "Telegramm: neuer Wert", "chip--flow");

    const strip = T.group(layer, "strip");
    for (let i = 0; i < 9; i++) {
      const x = 180 + i * 85;
      const v = p(x);
      const text = v < 0.1 ? "alt" : v > 0.9 ? "neu" : "Mix";
      miniLcd(strip, x - 22, 142, 44, 24, text);
    }
    const curve = (() => {
      let d = "";
      for (let x = 140; x <= 870; x += 5) d += `${d ? "L" : "M"}${x} ${Y(p(x)).toFixed(1)}`;
      return T.svg("path", { d, class: "t-value-line" }, layer);
    })();
    const levels = T.group(layer, "levels");
    [[0.1, "0,1"], [0.5, "0,5"], [0.9, "0,9"]].forEach(([v, name]) => {
      const x = mid + k * Math.log(v / (1 - v));
      T.svg("path", { d: `M${x.toFixed(1)} ${Y(v).toFixed(1)}V${AX}`, class: "t-link-line" }, levels);
      T.svg("circle", { cx: x.toFixed(1), cy: Y(v).toFixed(1), r: 5, class: "status-dot status-dot--valid" }, levels);
      T.label(levels, x - 10, Y(v) - 8, `p = ${name}`, "t-small", { "text-anchor": "end" });
    });
    T.label(levels, 880, Y(1) - 12, "Anteil neuer Wert im Bild", "t-small", { "text-anchor": "end" });
    const delta = T.group(layer, "delta");
    T.svg("path", { d: `M${tTel + 4} 362H${mid - 4}`, class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, delta);
    T.label(delta, (tTel + mid) / 2, 354, "Anzeigeversatz δ", "t-small t-strong", { "text-anchor": "middle" });

    const card = T.group(layer, "calib");
    T.panel(card, 60, 428, 480, 90, "t-panel t-flow-box");
    T.label(card, 80, 454, "var/calibration/timing-streamcam.json", "t-mono t-strong", { style: "font-size: 13px" });
    T.label(card, 80, 476, "Anzeigeversatz δ · Schutzabstand M (größter gemessener", "t-small");
    T.label(card, 80, 494, "Wert) · Kamera-USB-ID · Quellen mit Prüfsumme", "t-small");
    tour.docLink(card, "docs/TIMING.html", "Zeitverhalten (TIMING) öffnen", [524, 444]);
    const why = T.group(layer, "why");
    T.panel(why, 560, 428, 340, 90, "t-panel t-planned-box");
    T.label(why, 580, 454, "Warum messen?", "t-small t-strong");
    T.label(why, 580, 476, "Was der Kamera-Zeitstempel genau", "t-small");
    T.label(why, 580, 494, "markiert, ist offen (OQ-43).", "t-small");
    tour.docLink(why, "docs/open-questions.html#oq-43", "OQ-43 öffnen: Bedeutung des Kamera-Zeitstempels", [884, 444]);

    T.hidden(head, guard, axis, tel, strip, strip.children, curve, levels, delta, card, why);
    T.fadeUp(tl, head, {}, 100);
    tl.add(axis, { opacity: [0, 1], duration: 400 }, "+=100");
    T.fadeUp(tl, tel, { translateY: [-16, 0] }, "+=100");
    tl.set(strip, { opacity: 1 }, "+=100");
    tl.add(strip.children, { opacity: [0, 1], translateY: [10, 0], delay: A.stagger(90), duration: 400 }, "<<");
    T.drawIn(tl, A, curve, { duration: 1300, ease: "inOutSine" }, "+=100");
    tl.add(levels, { opacity: [0, 1], duration: 500 }, "+=50");
    T.fadeUp(tl, delta, {}, "+=100");
    tl.add(guard, { opacity: [0, 1], duration: 700, ease: "outQuad" }, "+=300");
    T.fadeUp(tl, [card, why], { delay: A.stagger(150) }, "+=200");
  });

  // ------------------------------------------ 4 · Latenz vs. Unsicherheit --

  T.register("zeit-latenz", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = title(layer, "Latenz ist nicht Unsicherheit", "Links: welche Zeit der Datensatz trägt · rechts: was ins Unsicherheitsbudget geht");

    // Links: Aufnahme, Bestätigung, Rechenzeit, Ergebnis.
    const left = T.group(layer, "left");
    T.svg("path", { d: "M60 250H440", class: "t-axis", "marker-end": "url(#tour-arrow)" }, left);
    const ticks = [[90, "erstes gleiches Bild"], [190, "Aufnahme"], [400, "Ergebnis fertig"]];
    ticks.forEach(([x, name], i) => {
      T.svg("rect", { x: x - 11, y: 232, width: 22, height: 36, rx: 4, class: i === 2 ? "t-panel t-flow-box" : "tick" }, left);
      T.label(left, x, 290, name, "t-small", { "text-anchor": "middle" });
    });
    const stamps = T.group(layer, "stamps");
    T.chip(stamps, 120, 150, "capture_timestamp", "chip--flow");
    T.svg("path", { d: "M190 178V226", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, stamps);
    T.chip(stamps, 310, 110, "result_timestamp", "chip--line");
    T.svg("path", { d: "M400 138V226", class: "t-muted-line", "marker-end": "url(#tour-arrow)" }, stamps);
    const spans = T.group(layer, "spans");
    T.svg("path", { d: "M90 314v8H190v-8", class: "brace-line" }, spans);
    T.label(spans, 140, 342, "confirmation_span_ns", "t-mono", { "text-anchor": "middle", style: "font-size: 12px" });
    T.svg("path", { d: "M190 314v8H400v-8", class: "brace-line brace-line--muted", style: "stroke: var(--tour-line)" }, spans);
    T.label(spans, 296, 342, "Rechenzeit (PipelineTrace)", "t-small", { "text-anchor": "middle" });
    const msg = T.group(layer, "msg");
    T.label(msg, 60, 384, "Der Datensatz trägt die Aufnahmezeit. Schwankt die", "t-small t-strong");
    T.label(msg, 60, 402, "Rechenzeit, verschiebt das die Aufnahmezeit nicht.", "t-small t-strong");
    T.label(msg, 60, 420, "Die Wartezeit der Mehrbildbestätigung steht extra.", "t-small t-strong");
    tour.docLink(msg, "docs/uebersicht/zeitstempel.html", "Zeitstempel richtig lesen");

    // Rechts: zwei Verteilungen aus dem Beispiel in TIMING.md.
    const RX = 520;
    const sx = (ms) => RX + 40 + ms * 1.2;
    const right = T.group(layer, "right");
    T.svg("path", { d: `M${RX + 20} 330H910`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, right);
    [0, 100, 200, 300].forEach((ms) => {
      T.svg("path", { d: `M${sx(ms)} 326V334`, class: "t-axis" }, right);
      T.label(right, sx(ms), 352, `${ms} ms`, "t-small", { "text-anchor": "middle" });
    });
    T.label(right, 910, 372, "Verzögerung", "t-small", { "text-anchor": "end" });
    const bell = (mean, sd, height, cls) => {
      let d = "";
      for (let ms = -20; ms <= 320; ms += 2) {
        const y = 330 - height * Math.exp(-0.5 * ((ms - mean) / sd) ** 2);
        d += `${d ? "L" : "M"}${sx(ms).toFixed(1)} ${y.toFixed(1)}`;
      }
      return T.svg("path", { d, style: `fill: none; stroke-width: 3; stroke: var(${cls})` }, layer);
    };
    const bellA = bell(200, 6, 170, "--tour-valid");
    const bellB = bell(50, 40, 70, "--tour-bad");
    const tags = T.group(layer, "tags");
    T.label(tags, sx(200), 140, "konstant 200 ms", "t-small t-valid-text", { "text-anchor": "middle" });
    T.label(tags, sx(200), 156, "korrigierbar", "t-small", { "text-anchor": "middle" });
    T.label(tags, sx(50), 240, "50 ms ± 40 ms", "t-small t-bad-text", { "text-anchor": "middle" });
    T.label(tags, sx(50), 256, "schlechter: Streuung bleibt", "t-small", { "text-anchor": "middle" });
    T.label(tags, 910, 112, "Beispiel aus TIMING.md", "t-tiny", { "text-anchor": "end" });

    const rule = T.group(layer, "rule");
    T.panel(rule, 520, 400, 390, 76, "t-panel t-flow-box");
    T.label(rule, 540, 428, "Im Bericht immer getrennt:", "t-small t-strong");
    T.label(rule, 540, 450, "Mittelwert (korrigierbar) und Streuung", "t-small");
    T.label(rule, 540, 466, "(nicht korrigierbar). Eine Zahl „Latenz“ reicht nicht.", "t-small");
    tour.docLink(rule, "docs/TIMING.html#grundsatz-latenz-ist-nicht-zeitunsicherheit", "TIMING: Grundsatz öffnen", [894, 416]);

    T.hidden(head, left, stamps, stamps.children, spans, msg, right, bellA, bellB, tags, rule);
    T.fadeUp(tl, head, {}, 100);
    tl.add(left, { opacity: [0, 1], duration: 500 }, "+=100");
    tl.set(stamps, { opacity: 1 }, "+=50");
    tl.add(Array.from(stamps.children).slice(0, 2), { opacity: [0, 1], translateY: [-10, 0], duration: 500 }, "<<");
    tl.add(Array.from(stamps.children).slice(2), { opacity: [0, 1], translateY: [-10, 0], duration: 500 }, "+=200");
    T.fadeUp(tl, spans, {}, "+=150");
    T.fadeUp(tl, msg, {}, "+=150");
    tl.add(right, { opacity: [0, 1], duration: 500 }, "+=200");
    T.drawIn(tl, A, bellA, { duration: 900 }, "+=50");
    T.drawIn(tl, A, bellB, { duration: 900 }, "<<+=300");
    T.fadeUp(tl, tags, {}, "-=300");
    T.fadeUp(tl, rule, {}, "+=150");
  });

  // ---------------------------------------------- 5 · Zuordnung -----------

  T.register("zeit-zuordnung", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = title(layer, "Prüfling und Referenz zeitlich zuordnen", "Nachträglich und außerhalb der Erkennung · gestrichelt: noch nicht belegt");
    const dutY = 160;
    const refY = 290;
    const lines = T.group(layer, "lines");
    T.svg("path", { d: `M200 ${dutY}H900`, class: "t-axis", "marker-end": "url(#tour-arrow)" }, lines);
    T.svg("path", { d: `M200 ${refY}H900`, class: "t-plan-line", "marker-end": "url(#tour-arrow-plan)" }, lines);
    T.label(lines, 184, dutY - 2, "Prüfling", "t-label t-strong", { "text-anchor": "end" });
    T.label(lines, 184, dutY + 16, "Kamera → BOOTTIME", "t-small", { "text-anchor": "end" });
    T.label(lines, 184, refY - 2, "Referenz", "t-label t-strong", { "text-anchor": "end" });
    T.label(lines, 184, refY + 16, "eigene Uhr", "t-small t-plan-text", { "text-anchor": "end" });

    const dutX = [240, 330, 420, 510, 600, 690, 780, 860];
    const refX = [270, 410, 550, 690, 830];
    const dut = T.group(layer, "dut-dots");
    dutX.forEach((x) => T.svg("circle", { cx: x, cy: dutY, r: 7, class: "status-dot status-dot--valid" }, dut));
    const ref = T.group(layer, "ref-dots");
    refX.forEach((x) => T.svg("circle", { cx: x, cy: refY, r: 7, class: "status-dot status-dot--plan" }, ref));
    const pairs = T.group(layer, "pairs");
    refX.forEach((x) => {
      const near = dutX.reduce((a, b) => (Math.abs(b - x) < Math.abs(a - x) ? b : a));
      T.svg("path", { d: `M${near} ${dutY + 8}L${x} ${refY - 8}`, class: "t-plan-line", style: "stroke-width: 2" }, pairs);
      T.label(pairs, (near + x) / 2 + 8, (dutY + refY) / 2 + 4, "?", "t-small t-plan-text");
    });
    const audit = T.group(layer, "audit");
    T.chip(audit, 640, 96, "Quelle Prüfling: JSONL-Audit", "chip--flow");

    const open = T.group(layer, "open");
    T.label(open, 60, 352, "Offen, bevor die Zuordnung belastbar ist:", "t-label t-strong");
    const items = [
      ["OQ-03 · Zeitquelle der Referenz", "docs/open-questions.html#oq-03", "OQ-03 öffnen"],
      ["OQ-02 · zulässige Abweichung", "docs/open-questions.html#oq-02", "OQ-02 öffnen"],
      ["OQ-43 · Bedeutung Kamera-Stempel", "docs/open-questions.html#oq-43", "OQ-43 öffnen"],
      ["M8 · nutzt GSVmulti die Aufnahmezeit?", "docs/TIMING.html#messprogramm", "TIMING: Messprogramm öffnen"],
    ];
    const pills = items.map(([text, path, name], i) => {
      const x = i % 2 === 0 ? 60 : 480;
      const y = 370 + Math.floor(i / 2) * 40;
      const pill = linkPill(open, x, y, `${text} ↗`, "plan");
      tour.docLink(pill.root, path, name);
      return pill.root;
    });
    const m5 = T.group(layer, "m5");
    T.label(m5, 60, 476, "Größter Einzelbeitrag ist vermutlich die Displayaktualisierung des Prüflings (M5).", "t-small t-strong");
    T.label(m5, 60, 494, "Sie ist noch nicht gemessen, und keine Software macht sie kleiner.", "t-small");

    T.hidden(head, lines, dut.children, ref.children, pairs, audit, open.firstChild, pills, m5);
    T.fadeUp(tl, head, {}, 100);
    tl.add(lines, { opacity: [0, 1], duration: 500 }, "+=100");
    tl.add(dut.children, { opacity: [0, 1], scale: [0.2, 1], delay: A.stagger(80), duration: 400, ease: "outBack(2)" }, "+=50");
    T.fadeUp(tl, audit, {}, "<<+=200");
    tl.add(ref.children, { opacity: [0, 1], scale: [0.2, 1], delay: A.stagger(110), duration: 400, ease: "outBack(2)" }, "+=100");
    tl.add(pairs, { opacity: [0, 1], duration: 700 }, "+=200");
    T.fadeUp(tl, open.firstChild, {}, "+=200");
    T.popIn(tl, A, pills, { delay: A.stagger(130), scale: [0.8, 1] }, "+=50");
    T.fadeUp(tl, m5, {}, "+=200");
  });
})();
