/* Projekt-Tour, Kapitel „Regeln“ (docs/uebersicht/projekt-tour.md, Abschnitt
 * #regeln). Szenen melden sich über window.dispreadTour.register an; Helfer und
 * Konventionen stehen in tour.js unter „Schnittstelle Kapitel“.
 *
 * Jede Szene stellt eine Regel aus AGENTS.md („Nicht verhandelbar“, „Kein
 * Erfinden von Protokollen“) gegenüber: links, was ohne die Regel passieren
 * könnte (rot, gestrichelt), rechts der Mechanismus im Code, unten der Test,
 * der ihn festhält. Testnamen und Signaturen sind aus tests/ und src/
 * übernommen und müssen bei Umbenennungen mitgezogen werden. */
(function () {
  "use strict";

  const T = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });

  T.blurbs.regeln = "Was das System bewusst nicht tut";

  // ------------------------------------------------------------- Helfer --

  const BAD_PANEL = "stroke: var(--tour-bad); stroke-width: 2; stroke-dasharray: 7 5";
  const PLAN_PANEL = "stroke: var(--tour-plan); stroke-width: 2; stroke-dasharray: 7 5";
  const GOOD_PANEL = "stroke: var(--tour-valid); stroke-width: 2";

  function heading(layer, title, sub) {
    const g = T.group(layer, "regeln-heading");
    T.label(g, 40, 46, title, "t-title-sm");
    if (sub) T.label(g, 40, 70, sub, "t-small");
    return g;
  }

  // Tafel mit Kopfzeile; kind: "bad" (so nicht), "good" (so gebaut), "plan".
  function board(layer, x, y, w, h, kind, title) {
    const g = T.group(layer, `regeln-board regeln-board--${kind}`);
    const rect = T.panel(g, x, y, w, h, kind === "good" ? "t-panel t-flow-box" : "t-panel");
    if (kind === "bad") rect.setAttribute("style", BAD_PANEL);
    if (kind === "plan") rect.setAttribute("style", PLAN_PANEL);
    if (kind === "valid") rect.setAttribute("style", GOOD_PANEL);
    const cls = kind === "bad" ? "t-bad-text" : kind === "plan" ? "t-plan-text" : kind === "valid" ? "t-valid-text" : "t-strong";
    T.label(g, x + 18, y + 28, title, `t-label ${cls}`);
    return g;
  }

  function testChip(parent, x, y, name) {
    return T.chip(parent, x, y, `Test: ${name}`, "chip--line");
  }

  // Kasten mit Programmtext, eine Zeile je Eintrag.
  function codeBox(parent, x, y, w, lines, cls) {
    const g = T.group(parent, "regeln-code");
    T.panel(g, x, y, w, 18 + lines.length * 22, cls || "t-panel");
    lines.forEach((line, i) => T.label(g, x + 14, y + 28 + i * 22, line, "t-mono t-mono-sm", { style: "white-space: pre" }));
    return g;
  }

  // Roter Stempel, der schräg auf etwas fällt.
  function stamp(parent, x, y, text) {
    const outer = T.group(parent, "", { transform: `translate(${x} ${y}) rotate(-8)` });
    const g = T.group(outer, "regeln-stamp");
    const t = T.label(g, 0, 6, text, "t-label t-bad-text", { "text-anchor": "middle" });
    const w = T.textWidth(t, 8.5) + 28;
    const rect = T.svg("rect", { x: -w / 2, y: -16, width: w, height: 32, rx: 6 });
    rect.setAttribute("style", "fill: var(--tour-bad-bg); stroke: var(--tour-bad); stroke-width: 2.5");
    g.insertBefore(rect, t);
    return g;
  }

  function strikeThrough(parent, x1, y, x2) {
    return T.svg("path", { d: `M${x1} ${y}H${x2}`, class: "t-strike" }, parent);
  }

  // ------------------------------------------------------------- Szenen --

  T.register("regeln-altwert", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Kein Altwert ohne Markierung", "Die Anzeige ist verdeckt. Was geht hinaus?");

    const bad = board(layer, 40, 90, 400, 300, "bad", "Ohne Sperre (so nicht)");
    const rows = [
      ["Bild 1", "0.51230", "gültig", "valid"],
      ["Bild 2", "0.51230", "gültig?", "bad"],
      ["Bild 3", "0.51230", "gültig?", "bad"],
      ["Bild 4", "0.51230", "gültig?", "bad"],
    ].map(([frame, value, status, kind], i) => {
      const g = T.group(bad, "regeln-row");
      const y = 150 + i * 46;
      T.label(g, 66, y, frame, "t-small");
      T.label(g, 190, y, value, kind === "bad" ? "t-mono t-bad-text" : "t-mono t-valid-text", { "text-anchor": "middle" });
      T.badge(g, 330, y - 5, status, kind, 96);
      return g;
    });
    const frozen = T.label(bad, 240, 360, "eingefroren, sieht aber gültig aus", "t-small t-bad-text", { "text-anchor": "middle" });

    const good = board(layer, 500, 90, 420, 300, "good", "Mit Sperre (so gebaut)");
    const attempt = codeBox(good, 520, 130, 380, ["ValueRecord(status=STALE,", "            value=0.51230)"]);
    const hit = stamp(good, 840, 190, "ValueError");
    const ok = codeBox(good, 520, 250, 380, ["ValueRecord(status=STALE,", "            value=None)"]);
    const okMark = T.checkMark(good, 880, 278, "ok");
    const gateNote = T.label(good, 520, 362, "Freigabe: nach stale_after ohne gültigen Wert → veraltet", "t-small");
    tour.docLink(good, "api/vertraege.html", "Verträge (ValueRecord) öffnen", [904, 108]);

    const tests = T.group(layer, "regeln-tests");
    testChip(tests, 40, 420, "test_stale_darf_keinen_zahlenwert_fuehren");
    testChip(tests, 40, 456, "test_nach_verlust_wird_der_wert_veraltet_nicht_weitergefuehrt");
    T.label(tests, 920, 474, "tests/test_records.py · tests/test_gate_und_referenz.py", "t-tiny", { "text-anchor": "end" });

    T.hidden(head, bad, rows, frozen, good, attempt, hit, ok, okMark, gateNote, tests.children);
    T.fadeUp(tl, head, {}, 0);
    T.fadeUp(tl, bad, { duration: 600 }, 150);
    T.fadeUp(tl, rows, { delay: A.stagger(260) }, "-=200");
    T.fadeUp(tl, frozen, {}, "+=100");
    tl.add(rows.slice(1), { translateX: [0, -3, 3, 0], duration: 360, ease: "inOutSine" }, "<<");
    T.fadeUp(tl, good, { duration: 600 }, "+=300");
    T.fadeUp(tl, attempt, {}, "-=200");
    T.popIn(tl, A, [hit], { scale: [2.2, 1], ease: "outBack(1.4)", duration: 600 }, "+=250");
    tl.add(attempt, { opacity: [1, 0.45], duration: 400 }, "<<+=300");
    T.fadeUp(tl, ok, {}, "+=200");
    T.popIn(tl, A, [okMark], { ease: "outElastic(1, .6)", duration: 900 }, "-=200");
    T.fadeUp(tl, gateNote, {}, "-=500");
    T.fadeUp(tl, Array.from(tests.children), { delay: A.stagger(150) }, "+=150");
  });

  T.register("regeln-referenz", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Die Referenz korrigiert nie den Prüfling", "Leser und Freigabe haben schlicht keinen Eingang dafür.");

    const ref = T.group(layer, "regeln-ref");
    T.panel(ref, 40, 130, 210, 80, "t-panel");
    T.label(ref, 145, 162, "Kalibrierreferenz", "t-label t-strong", { "text-anchor": "middle" });
    T.label(ref, 145, 188, "0.46761", "t-mono", { "text-anchor": "middle" });

    const fnRead = T.group(layer, "regeln-fn");
    T.panel(fnRead, 400, 100, 300, 64, "t-panel t-flow-box");
    T.label(fnRead, 416, 126, "ValueReader.read", "t-mono t-mono-sm t-strong");
    T.fact("reader.read_params", ["crop", "layout"]).forEach((name, i) => {
      T.svg("rect", { x: 416 + i * 90, y: 136, width: 80, height: 20, rx: 10, class: "token-box" }, fnRead);
      T.label(fnRead, 456 + i * 90, 151, name, "t-small", { "text-anchor": "middle" });
    });
    tour.docLink(fnRead, "api/ocr.html", "OCR-API öffnen", [686, 116]);

    const fnGate = T.group(layer, "regeln-fn");
    T.panel(fnGate, 400, 180, 300, 64, "t-panel t-flow-box");
    T.label(fnGate, 416, 206, "ReleaseGate.evaluate", "t-mono t-mono-sm t-strong");
    T.fact("gate.evaluate_params", ["read", "capture_ns"]).forEach((name, i) => {
      T.svg("rect", { x: 416 + i * 90, y: 216, width: 80, height: 20, rx: 10, class: "token-box" }, fnGate);
      T.label(fnGate, 456 + i * 90, 231, name, "t-small", { "text-anchor": "middle" });
    });
    tour.docLink(fnGate, "api/validate.html", "Freigabe-API öffnen", [686, 196]);

    const wall = T.svg("path", { d: "M380 92V252", class: "t-bad-line" }, layer);
    const path = T.svg("path", { d: "M250 170C300 170 340 172 372 172", class: "t-path-none" }, layer);
    const token = T.svg("circle", { r: 9, class: "t-pulse", style: "fill: var(--tour-plan); filter: none" }, layer);
    const refused = T.group(layer, "regeln-refused");
    T.checkMark(refused, 380, 172, "bad");
    T.label(refused, 724, 150, "kein Parameter", "t-label t-bad-text");
    T.label(refused, 724, 172, "für den Referenzwert", "t-label t-bad-text");

    // Zweiter Test: gleiche Kette, verfälschte Referenz, gleiche Datensätze.
    const runs = T.group(layer, "regeln-runs");
    const run = (x, title) => {
      const g = T.group(runs, "regeln-run");
      T.panel(g, x, 290, 300, 130, "t-panel");
      T.label(g, x + 16, 316, title, "t-label t-strong");
      ["Datensatz 1", "Datensatz 2", "…", "Datensatz 12"].forEach((row, i) => {
        T.label(g, x + 16, 342 + i * 20, row, "t-small");
        if (row !== "…") T.label(g, x + 284, 342 + i * 20, "gleich", "t-small t-valid-text", { "text-anchor": "end" });
      });
      return g;
    };
    const runA = run(100, "Lauf A: Referenz × 1,0");
    const runB = run(560, "Lauf B: Referenz × 1,2");
    const equal = T.label(runs, 480, 372, "=", "t-title t-valid-text", { "text-anchor": "middle" });

    const tests = T.group(layer, "regeln-tests");
    testChip(tests, 40, 446, "test_leser_bekommt_den_referenzwert_nicht_als_parameter");
    testChip(tests, 40, 482, "test_referenzwert_kann_die_erkennung_nicht_beeinflussen");
    T.label(tests, 920, 500, "tests/test_gate_und_referenz.py", "t-tiny", { "text-anchor": "end" });

    T.hidden(head, ref, fnRead, fnGate, wall, token, refused, runA, runB, equal, tests.children);
    T.fadeUp(tl, head, {}, 0);
    T.fadeUp(tl, ref, {}, 150);
    T.fadeUp(tl, [fnRead, fnGate], { delay: A.stagger(150) }, "-=300");
    tl.add([wall], { opacity: [0, 1], duration: 300 }, "+=100");
    tl.set(token, { opacity: 1 }, "+=100");
    T.travel(tl, A, path, token, { duration: 700, ease: "inQuad" }, "<");
    // Abprallen an der Wand.
    tl.add(token, { translateX: [0, -46, -30], duration: 500, ease: "outQuad" }, "<");
    tl.add(token, { opacity: [1, 0.35], duration: 300 }, "<<+=200");
    T.popIn(tl, A, [refused], { ease: "outBack(2)" }, "<<");
    T.fadeUp(tl, [runA, runB], { delay: A.stagger(200) }, "+=300");
    T.popIn(tl, A, [equal], { ease: "outElastic(1, .6)", duration: 900 }, "+=100");
    T.fadeUp(tl, Array.from(tests.children), { delay: A.stagger(150) }, "-=400");
  });

  T.register("regeln-spruenge", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Echte Sprünge bleiben Sprünge", "Folge aus dem Test: 1, 1, 500, 500, −500, 0");
    const values = [1, 1, 500, 500, -500, 0];
    const Y = (v) => 244 - v * 0.2;

    const chart = (x0, kind, title) => {
      const g = board(layer, x0, 90, 420, 300, kind, title);
      T.svg("path", { d: `M${x0 + 52} ${Y(0)}H${x0 + 404}`, class: "t-axis" }, g);
      T.label(g, x0 + 46, Y(500) + 4, "500", "t-tiny", { "text-anchor": "end" });
      T.label(g, x0 + 46, Y(0) + 4, "0", "t-tiny", { "text-anchor": "end" });
      T.label(g, x0 + 46, Y(-500) + 4, "−500", "t-tiny", { "text-anchor": "end" });
      return g;
    };
    const X = (x0, i) => x0 + 76 + i * 62;

    const bad = chart(40, "bad", "Geglättet (so nicht)");
    // Gleitender Mittelwert über zwei Bilder plus Steigungsbegrenzung: die
    // Spitze schrumpft, der Sprung wird zur Rampe.
    const smooth = values.map((v, i) => (i === 0 ? v : (v + values[i - 1]) / 2));
    const ghost = T.svg("path", {
      d: values.map((v, i) => `${i ? "L" : "M"}${X(40, i)} ${Y(v)}`).join(""),
      class: "t-muted-line", "stroke-dasharray": "3 5",
    }, bad);
    const smoothPath = T.svg("path", {
      d: smooth.map((v, i) => `${i ? "L" : "M"}${X(40, i)} ${Y(v)}`).join(""),
      class: "t-bad-line",
    }, bad);
    const lost = T.label(bad, 250, 372, "Spitze verschwindet, Sprung wird Rampe", "t-small t-bad-text", { "text-anchor": "middle" });

    const good = chart(500, "good", "Unverändert (so gebaut)");
    let d = `M${X(500, 0)} ${Y(values[0])}`;
    for (let i = 1; i < values.length; i++) d += `H${X(500, i)}V${Y(values[i])}`;
    const step = T.svg("path", { d, class: "t-value-line" }, good);
    const dots = values.map((v, i) => T.svg("circle", { cx: X(500, i), cy: Y(v), r: 6, class: "status-dot status-dot--valid" }, good));
    const kept = T.label(good, 710, 372, "jeder Wert kommt so heraus, wie er gelesen wurde", "t-small t-valid-text", { "text-anchor": "middle" });
    tour.docLink(good, "api/validate.html", "Freigabe-API öffnen", [904, 108]);

    const note = T.chip(layer, 40, 410, "Einzige erlaubte Verzögerung: confirm_frames, Dauer steht als confirmation_span_ns im Datensatz", "chip--flow");
    const tests = T.group(layer, "regeln-tests");
    testChip(tests, 40, 450, "test_echte_spruenge_werden_nicht_geglaettet");
    testChip(tests, 40, 486, "test_mehrbildbestaetigung_meldet_ihre_zeitspanne");
    T.label(tests, 920, 504, "tests/test_gate_und_referenz.py", "t-tiny", { "text-anchor": "end" });

    T.hidden(head, bad, ghost, smoothPath, lost, good, step, dots, kept, note, tests.children);
    T.fadeUp(tl, head, {}, 0);
    T.fadeUp(tl, [bad, good], { delay: A.stagger(200) }, 150);
    tl.add(ghost, { opacity: [0, 1], duration: 300 }, "+=100");
    T.drawIn(tl, A, smoothPath, { duration: 1300, ease: "inOutSine" }, "+=100");
    T.drawIn(tl, A, step, { duration: 1300, ease: "linear" }, "<<");
    tl.add(dots, { opacity: [0, 1], scale: [0, 1], delay: A.stagger(200), duration: 400, ease: "outBack(2)" }, "<<");
    T.fadeUp(tl, [lost, kept], { delay: A.stagger(200) }, "+=150");
    T.fadeUp(tl, note, {}, "+=200");
    T.fadeUp(tl, Array.from(tests.children), { delay: A.stagger(150) }, "-=300");
  });

  T.register("regeln-konfidenz", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Konfidenz ist keine Fehlerwahrscheinlichkeit", "Beispielwert aus einem Datensatz:");

    const value = T.group(layer, "regeln-conf");
    T.panel(value, 40, 90, 300, 70, "t-panel t-flow-box");
    T.label(value, 60, 133, "confidence = 0.31", "t-mono t-strong", { style: "font-size: 22px" });

    const bad = board(layer, 40, 190, 300, 200, "bad", "So nicht lesen");
    const wrong = ["„31 % Fehlerrisiko“", "„69 % sicher“"].map((text, i) => {
      const g = T.group(bad, "regeln-wrong");
      T.label(g, 64, 252 + i * 50, text, "t-label");
      strikeThrough(g, 58, 247 + i * 50, 66 + text.length * 8.4);
      return g;
    });
    const why = T.label(bad, 64, 360, "nie gemessen, also keine Quote", "t-small t-bad-text");

    const good = board(layer, 380, 90, 540, 300, "good", "Was sie ist");
    const lines = [
      "eine Qualitätskennzahl der Erkennung",
      "Punktraster-Leser: knappster Abstand",
      "zu einer Schwelle (D_max oder margin_min),",
      "in Einheiten der Vorlagen, höchstens 1",
    ].map((text, i) => T.label(good, 400, 152 + i * 24, text, i === 0 ? "t-label t-strong" : "t-label"));
    const flags = ["dotmatrix", "sevenseg", "tesseract_cli"].map((reader, i) => {
      const g = T.group(good, "regeln-flag");
      T.chip(g, 400, 262 + i * 34, `${reader} · declares_confidence_calibrated = False`, "chip--line");
      return g;
    });
    const until = T.label(good, 650, 376, "True erst mit Kalibriermessung in der Validierung", "t-small t-strong", { "text-anchor": "middle" });
    tour.docLink(good, "api/ocr.html", "OCR-API öffnen", [904, 108]);

    const tests = T.group(layer, "regeln-tests");
    testChip(tests, 40, 420, "test_declares_confidence_calibrated_ist_false");
    T.label(tests, 40, 470, "dazu Prüfungen in test_dotmatrix_reader.py und test_sevenseg.py", "t-tiny");
    const valLink = T.group(layer, "regeln-val");
    T.panel(valLink, 600, 418, 320, 52, "t-panel");
    T.label(valLink, 760, 449, "Validierung (Zahlen) öffnen", "t-label", { "text-anchor": "middle" });
    tour.docLink(valLink, "docs/VALIDATION.html", "Validierung öffnen", [906, 432]);

    T.hidden(head, value, bad, wrong, why, good, lines, flags, until, tests.children, valLink);
    T.fadeUp(tl, head, {}, 0);
    T.popIn(tl, A, [value], { ease: "outBack(1.6)" }, 150);
    T.fadeUp(tl, bad, {}, "+=200");
    wrong.forEach((g, i) => {
      T.fadeUp(tl, g, {}, i === 0 ? "-=200" : "+=150");
      const s = g.querySelector(".t-strike");
      T.drawIn(tl, A, s, { duration: 350 }, "+=150");
    });
    T.fadeUp(tl, why, {}, "+=100");
    T.fadeUp(tl, good, {}, "+=250");
    T.fadeUp(tl, lines, { delay: A.stagger(130) }, "-=300");
    T.popIn(tl, A, flags, { delay: A.stagger(160), scale: [0.8, 1] }, "+=150");
    T.fadeUp(tl, until, {}, "+=100");
    T.fadeUp(tl, [...Array.from(tests.children), valLink], { delay: A.stagger(150) }, "+=100");
  });

  T.register("regeln-protokoll", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Kein erfundenes Protokoll", "Welches Telegramm erwartet GSVmulti? Unbekannt (OQ-07).");

    const rec = T.group(layer, "regeln-rec");
    T.panel(rec, 40, 200, 170, 64, "t-panel t-flow-box");
    T.label(rec, 125, 238, "ValueRecord", "t-mono t-strong", { "text-anchor": "middle" });

    const csv = T.group(layer, "regeln-csv");
    const csvRect = T.panel(csv, 300, 104, 330, 92, "t-panel");
    csvRect.setAttribute("style", PLAN_PANEL);
    T.label(csv, 318, 132, "AsciiCsvFormatter", "t-mono t-strong");
    T.label(csv, 318, 156, "provisional = True", "t-mono t-mono-sm t-plan-text");
    T.label(csv, 318, 180, "nur zum Testen der Ausgabekette", "t-small");
    const csvBadge = T.badge(csv, 580, 132, "vorläufig", "plan", 86);
    void csvBadge;

    const gsvFmt = T.group(layer, "regeln-gsvfmt");
    const gsvRect = T.panel(gsvFmt, 300, 268, 330, 92, "t-panel");
    gsvRect.setAttribute("style", BAD_PANEL);
    T.label(gsvFmt, 318, 296, "GsvAsciiFormatter", "t-mono t-strong");
    T.label(gsvFmt, 318, 320, "raise NotImplementedError", "t-mono t-mono-sm t-bad-text");
    T.label(gsvFmt, 318, 344, "„Format ist nicht bekannt (OQ-07)“", "t-small");
    tour.docLink(gsvFmt, "docs/open-questions.html#oq-07", "OQ-07 öffnen", [616, 284]);

    const toCsv = T.svg("path", { d: "M210 220C250 220 260 150 296 150", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const toGsv = T.svg("path", { d: "M210 244C250 244 260 314 296 314", class: "t-bad-line", "marker-end": "url(#tour-arrow-bad)" }, layer);

    const target = T.group(layer, "regeln-target");
    T.panel(target, 720, 200, 200, 64, "t-panel t-planned-box");
    T.label(target, 820, 228, "GSVmulti", "t-label t-strong", { "text-anchor": "middle" });
    T.label(target, 820, 250, "Format offen", "t-small t-plan-text", { "text-anchor": "middle" });
    tour.docLink(target, "docs/GSVMULTI_PROTOCOL.html", "GSVmulti-Protokoll öffnen", [906, 214]);
    const toTarget = T.svg("path", { d: "M630 314C680 314 680 250 716 242", class: "t-plan-line", "marker-end": "url(#tour-arrow-plan)" }, layer);
    const stop = T.group(layer, "regeln-stop");
    T.checkMark(stop, 676, 284, "bad");

    const guess = T.group(layer, "regeln-guess");
    const guessRect = T.panel(guess, 40, 392, 520, 66, "t-panel");
    guessRect.setAttribute("style", BAD_PANEL);
    T.label(guess, 58, 418, "Geratenes Format?", "t-label t-bad-text");
    T.label(guess, 58, 442, "wäre im Test grün und fiele erst am Laborplatz auf", "t-small");
    const guessStrike = strikeThrough(guess, 56, 413, 196);

    const way = T.chip(layer, 600, 400, "Belastbar: Mitschnitt GSV-Gerät → GSVmulti", "chip--flow");

    T.hidden(head, rec, csv, gsvFmt, toCsv, toGsv, target, toTarget, stop, guess, guessStrike, way);
    T.fadeUp(tl, head, {}, 0);
    T.fadeUp(tl, rec, {}, 150);
    T.drawIn(tl, A, toCsv, { duration: 500 }, "+=100");
    T.fadeUp(tl, csv, {}, "-=200");
    T.drawIn(tl, A, toGsv, { duration: 500 }, "+=200");
    T.fadeUp(tl, gsvFmt, {}, "-=200");
    tl.add(gsvFmt, { translateX: [0, -6, 6, -4, 0], duration: 420, ease: "inOutSine" }, "+=150");
    T.fadeUp(tl, target, {}, "+=100");
    T.drawIn(tl, A, toTarget, { duration: 500 }, "<<");
    T.popIn(tl, A, [stop], { ease: "outBack(2)" }, "+=50");
    T.fadeUp(tl, guess, {}, "+=250");
    T.drawIn(tl, A, guessStrike, { duration: 400 }, "+=150");
    T.fadeUp(tl, way, {}, "+=200");
  });

  T.register("regeln-grenzen", (ctx) => {
    const { tl, A, layer, tour } = ctx;
    const head = heading(layer, "Was noch nicht geprüft ist", "Belegt ist ein Gerät. Alles darüber hinaus ist offen und wird so genannt.");

    const proven = board(layer, 40, 92, 380, 300, "valid", "Belegt");
    // Zählungen aus den Abnahmedateien (abnahme.stufe2c), die Obergrenze aus VALIDATION.md.
    const total = T.fact("abnahme.stufe2c", { gesamt: { richtig: 215, falsch: 0, abgelehnt: 0 } }).gesamt;
    const provenLines = [
      ["Punktraster-Leser", "t-label t-strong"],
      ["am GSV-2AS · Displaytech 161A", "t-label"],
      ["Abnahme 3:", "t-label t-strong"],
      [`${total.richtig} von ${total.richtig + total.falsch + total.abgelehnt} richtig`, "t-label"],
      [`${total.falsch} falsch · ${total.abgelehnt} abgelehnt`, "t-label"],
      ["Obergrenze Fehlerrate 3,5 %", "t-label"],
    ].map(([text, cls], i) => T.label(proven, 62, 150 + i * 32, text, cls));
    const provenMark = T.checkMark(proven, 392, 120, "ok");
    tour.docLink(proven, "docs/VALIDATION.html", "Validierung öffnen", [404, 378]);

    const open = board(layer, 460, 92, 460, 300, "plan", "Offen");
    const items = [
      ["weitere Messverstärker", "GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI, AST", null],
      ["andere Lichtquellen", "bisher eine Beleuchtung", null],
      ["Minuszeichen", "Gerät zeigt nie „−“, der Leser kennt nur „+“", null],
      ["Freigabeschwellen", "an realen Geräten validieren · OQ-14", "docs/open-questions.html#oq-14"],
      ["GSVmulti-Format", "Telegramm unbekannt · OQ-07", "docs/open-questions.html#oq-07"],
    ].map(([title, sub, href], i) => {
      const g = T.group(open, "regeln-open");
      const y = 146 + i * 48;
      const rect = T.svg("rect", { x: 476, y: y - 8, width: 428, height: 44, rx: 8, class: "t-panel" }, g);
      rect.setAttribute("style", "stroke: none; fill: var(--tour-plan-bg)");
      T.label(g, 490, y + 10, title, "t-label t-strong");
      T.label(g, 490, y + 28, sub, "t-small");
      if (href) tour.docLink(g, href, `${title} öffnen`, [890, y + 10]);
      return g;
    });

    const banner = T.chip(layer, 40, 420, "Wer Werte freigibt, nennt diese Grenzen ausdrücklich mit.", "chip--flow");
    const progress = T.group(layer, "regeln-progress");
    T.panel(progress, 600, 412, 320, 52, "t-panel");
    T.label(progress, 760, 443, "Fortschritt Ernten/Training öffnen", "t-label", { "text-anchor": "middle" });
    tour.docLink(progress, "docs/FORTSCHRITT.html", "Fortschritt öffnen", [906, 426]);

    T.hidden(head, proven, provenLines, provenMark, open, items, banner, progress);
    T.fadeUp(tl, head, {}, 0);
    T.fadeUp(tl, proven, {}, 150);
    T.fadeUp(tl, provenLines, { delay: A.stagger(110) }, "-=300");
    T.popIn(tl, A, [provenMark], { ease: "outElastic(1, .6)", duration: 900 }, "+=50");
    T.fadeUp(tl, open, {}, "-=600");
    tl.add(items, { opacity: [0, 1], translateX: [24, 0], delay: A.stagger(170), duration: 600, ease: "outExpo" }, "+=50");
    T.fadeUp(tl, [banner, progress], { delay: A.stagger(150) }, "+=200");
  });
})();
