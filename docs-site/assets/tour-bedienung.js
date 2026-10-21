/* Projekt-Tour, Kapitel „Bedienung“ (docs/uebersicht/projekt-tour.md, Abschnitt
 * #bedienung). Szenen melden sich über window.dispreadTour.register an; Helfer und
 * Konventionen stehen in tour.js unter „Schnittstelle Kapitel“.
 *
 * Quellen: scripts/camera-commissioning.sh, scripts/harvest-setup.py,
 * src/dispread/setup_checks.py, src/dispread/session_profile.py,
 * src/dispread/live/{camera,service,session}.py (gemeinsamer Kamera-Owner),
 * docs/anleitung/10-kamera-livevorschau.md, TODO.md. Weboberfläche und
 * Terminal sind schematisch. */
(function () {
  "use strict";

  const T = window.dispreadTour || (window.dispreadTour = { scenes: {}, blurbs: {} });
  T.blurbs.bedienung = "Aufstellen, prüfen, einrichten, bestätigen";

  const MONO = "font-family: var(--md-code-font-family, monospace)";

  // Kleines Personensymbol für den Bediener.
  function person(parent, x, y) {
    const g = T.group(parent, "person");
    T.svg("circle", { cx: x, cy: y - 22, r: 13, class: "t-panel", style: "stroke: var(--tour-flow); stroke-width: 2.5" }, g);
    T.svg("path", { d: `M${x - 24} ${y + 26}C${x - 24} ${y - 2} ${x + 24} ${y - 2} ${x + 24} ${y + 26}Z`, class: "t-panel", style: "stroke: var(--tour-flow); stroke-width: 2.5" }, g);
    return g;
  }

  // Karte mit Titel und Zeilen (Mono), gibt die Gruppe zurück.
  function listCard(parent, x, y, w, title, lines, cls) {
    const g = T.group(parent, "list-card");
    T.panel(g, x, y, w, 46 + lines.length * 24, cls || "t-panel");
    T.label(g, x + 16, y + 28, title, "t-label t-strong");
    lines.forEach((line, i) => T.label(g, x + 16, y + 56 + i * 24, line, "t-mono t-mono-sm"));
    return g;
  }

  // --------------------------------------------------- 1. Kamera aufstellen --

  function sceneKamera(ctx) {
    const { tl, A, layer, tour } = ctx;
    const G = 380;
    const side = T.group(layer, "side");
    T.label(side, 40, 52, "Seitenansicht", "t-label t-strong");
    T.svg("path", { d: `M40 ${G}H520`, class: "t-ground" }, side);
    // Messverstärker von der Seite, Anzeige zeigt nach rechts.
    T.svg("rect", { x: 70, y: 250, width: 150, height: 130, rx: 10, class: "tp-body" }, side);
    T.svg("rect", { x: 214, y: 272, width: 12, height: 40, rx: 3, class: "tp-lcd" }, side);
    T.label(side, 145, 322, "GSV-2AS", "tp-body-text tp-small", { "text-anchor": "middle" });

    const cam = T.group(layer, "side-cam");
    T.svg("path", { d: `M392 312V${G - 4}M372 ${G - 2}h40`, class: "t-stand" }, cam);
    T.streamCam(cam, 392, 296, 0.8);

    const height = T.svg("path", { d: "M226 292H368", class: "t-flow-dash" }, layer);
    const heightLabel = T.label(layer, 300, 262, "auf Höhe der Displaymitte", "t-small t-strong", { "text-anchor": "middle" });

    const pi = T.group(layer, "side-pi");
    T.svg("rect", { x: 430, y: 346, width: 84, height: 30, rx: 4, class: "tp-pcb" }, pi);
    const port = T.svg("rect", { x: 440, y: 352, width: 18, height: 12, rx: 2, style: "fill: var(--tour-flow)" }, pi);
    T.label(pi, 472, 404, "Pi 5 · USB3 (blau)", "t-small t-strong", { "text-anchor": "middle" });
    tour.docLink(pi, "docs/HARDWARE_PROFILE.html", "Hardwareprofil öffnen", [522, 344]);
    const cable = T.svg("path", { d: "M412 300C440 300 452 330 449 352", class: "t-cable" }, layer);

    const chips = T.group(layer, "side-chips");
    T.chip(chips, 40, 430, "1920 × 1080 · YUYV · nur über USB3", "chip--flow");
    T.chip(chips, 40, 466, `Fokus per Software: Autofokus aus → fester Wert (${T.fact("camera.focus_absolute", 48)})`, "chip--line");

    // Draufsicht: frontal gelingt der Assistent, schräg noch von Hand.
    const top = T.group(layer, "top");
    T.panel(top, 560, 36, 360, 470, "t-panel");
    T.label(top, 580, 66, "Von oben", "t-label t-strong");
    T.svg("rect", { x: 680, y: 96, width: 120, height: 40, rx: 6, class: "tp-body" }, top);
    T.svg("rect", { x: 700, y: 132, width: 80, height: 6, rx: 2, class: "tp-lcd" }, top);
    T.label(top, 740, 121, "GSV-2AS", "tp-body-text tp-small", { "text-anchor": "middle" });
    tour.docLink(top, "docs/OPTICAL_SETUP.html", "Optischer Aufbau öffnen", [902, 60]);

    const front = T.group(layer, "top-front");
    T.svg("path", { d: "M740 290V146", class: "t-flow-dash" }, front);
    T.svg("rect", { x: 722, y: 290, width: 36, height: 26, rx: 6, class: "tp-cam" }, front);
    T.checkMark(front, 784, 300, "ok");
    T.label(front, 740, 344, "frontal: Assistent findet das Raster", "t-small t-strong", { "text-anchor": "middle" });

    const oblique = T.group(layer, "top-oblique");
    T.svg("path", { d: "M612 410L718 146", class: "t-plan-line" }, oblique);
    T.svg("rect", { x: 592, y: 410, width: 36, height: 26, rx: 6, class: "tp-cam", transform: "rotate(-22 610 423)" }, oblique);
    T.badge(oblique, 770, 430, "schräg: noch von Hand einrichten", "plan", 250);
    T.label(oblique, 770, 466, "assist meldet keine_startlage", "t-small", { "text-anchor": "middle" });
    T.label(oblique, 770, 484, "oder startlage_mehrdeutig", "t-small", { "text-anchor": "middle" });

    T.hidden(side, cam, height, heightLabel, pi, cable, chips.children, top, front, oblique);
    T.fadeUp(tl, side, {}, 100);
    tl.add(cam, { opacity: [0, 1], translateX: [60, 0], duration: 800, ease: "outBack(1.4)" }, "-=300");
    T.drawIn(tl, A, height, { duration: 600 }, "+=100");
    tl.add(heightLabel, { opacity: [0, 1], duration: 400 }, "<");
    T.fadeUp(tl, pi, {}, "+=100");
    T.drawIn(tl, A, cable, { duration: 500 }, "<<");
    tl.add(port, { scale: [1, 1.6, 1], duration: 700, ease: "inOutSine" }, "+=50");
    T.fadeUp(tl, Array.from(chips.children), { delay: A.stagger(200) }, "<<");
    T.fadeUp(tl, top, {}, "+=300");
    T.popIn(tl, A, [front], { scale: [0.8, 1] }, "+=100");
    T.popIn(tl, A, [oblique], { scale: [0.8, 1] }, "+=400");
  }

  // ------------------------------------------------ 2. Inbetriebnahme prüfen --

  function sceneInbetriebnahme(ctx) {
    const { tl, A, layer, tour } = ctx;
    const term = T.group(layer, "terminal");
    T.panel(term, 40, 40, 560, 470, "t-window");
    T.svg("rect", { x: 40, y: 40, width: 560, height: 28, rx: 10, class: "t-window-bar" }, term);
    [0, 1, 2].forEach((i) => T.svg("circle", { cx: 58 + i * 14, cy: 54, r: 4, class: "t-window-dot" }, term));
    T.label(term, 110, 59, "Terminal · schematisch, gekürzt", "t-small");
    tour.docLink(term, "docs/CAMERA_COMMISSIONING.html", "Kamera-Inbetriebnahme öffnen", [584, 59]);

    const command = "$ ./scripts/camera-commissioning.sh";
    const prompt = T.label(term, 64, 104, "", "t-mono");
    const rows = [
      ["1. v4l2-ctl vorhanden", "OK"],
      [`2. StreamCam ${T.fact("camera.usb_id", "046d:0893")} gefunden`, "OK"],
      ["3. USB-Geschwindigkeit 5000 (USB3)", "OK"],
      ["4. Format YUYV 1920x1080 angeboten", "OK"],
      [`5. Autofokus aus, Fokus ${T.fact("camera.focus_absolute", 48)}, zurückgelesen`, "OK"],
      ["6. Testbild 1920x1080 aufgenommen", "OK"],
    ];
    const rowEls = rows.map(([text, status], i) => {
      const y = 150 + i * 46;
      const g = T.group(term, "row");
      T.label(g, 64, y + 5, text, "t-label", { style: MONO + "; font-size: 14px" });
      T.badge(g, 548, y, status, "valid", 60);
      return g;
    });
    const verdict = T.group(term, "verdict");
    T.svg("path", { d: "M64 440H576", class: "t-row-line" }, verdict);
    T.label(verdict, 64, 476, "Urteil: Kamera einsatzbereit", "t-label t-strong");
    T.badge(verdict, 520, 471, "Exit 0", "valid", 100);

    const notes = T.group(layer, "notes");
    const note = (y, kind, head, line1, line2) => {
      const g = T.group(notes, "note");
      T.panel(g, 630, y, 290, 120, "t-panel");
      T.badge(g, 630 + 20 + 55, y + 30, head, kind, 110);
      T.label(g, 650, y + 72, line1, "t-label");
      T.label(g, 650, y + 96, line2, "t-label");
      return g;
    };
    const n1 = note(40, "plan", "an USB2", "nur WARNUNG im Skript,", "aber keine volle Auflösung");
    const n2 = note(190, "bad", "FEHLER", "irgendein FEHLER →", "nicht einsatzbereit (Exit 1)");
    const n3 = note(340, "valid", "danach", "Regler stehen wieder", "wie vorher, Testbild in var/");

    T.hidden(term, rowEls, verdict, n1, n2, n3);
    T.fadeUp(tl, term, {}, 100);
    const typed = { n: 0 };
    tl.add(typed, {
      n: [0, command.length],
      duration: 1100,
      ease: "linear",
      onUpdate: () => { prompt.textContent = command.slice(0, Math.round(typed.n)); },
    }, "+=100");
    rowEls.forEach((row, i) => {
      tl.add(row, { opacity: [0, 1], translateX: [-12, 0], duration: 360, ease: "outExpo" }, i === 0 ? "+=250" : "+=220");
      tl.add(row.querySelector(".badge"), { scale: [0.3, 1], duration: 420, ease: "outBack(2.2)" }, "<<+=120");
    });
    T.popIn(tl, A, [verdict], { scale: [0.9, 1] }, "+=300");
    T.fadeUp(tl, [n1, n2, n3], { delay: A.stagger(220) }, "+=200");
  }

  // ---------------------------------------------- 3. Einrichtungsassistent --

  function sceneAssistent(ctx) {
    const { tl, A, layer, tour } = ctx;
    const cards = [];
    const card = (x, title, sub) => {
      const g = T.group(layer, "step-card");
      T.panel(g, x, 70, 196, 150, "t-panel t-flow-box");
      T.label(g, x + 98, 96, title, "t-label t-strong", { "text-anchor": "middle" });
      T.label(g, x + 98, 206, sub, "t-small", { "text-anchor": "middle" });
      cards.push(g);
      return g;
    };
    // 1 Fokus-Sweep: Schärfekurve mit Spitze.
    const c1 = card(30, "Fokus-Sweep", "schärfsten Wert suchen");
    T.svg("path", { d: "M52 186C80 184 96 176 112 150C122 128 132 118 140 118C150 118 160 132 170 152C184 178 196 184 206 186", class: "t-flow-line", style: "stroke-width: 2.5" }, c1);
    T.svg("circle", { cx: 140, cy: 118, r: 5, style: "fill: var(--tour-valid)" }, c1);
    // 2 Zwei Standbilder.
    const stability = T.num(T.fact("setup.stability_s", 30));
    const c2 = card(262, "2 Standbilder", `mindestens ${stability} s Abstand`);
    T.svg("rect", { x: 290, y: 116, width: 56, height: 38, rx: 4, class: "tp-frame-mini" }, c2);
    T.svg("rect", { x: 372, y: 116, width: 56, height: 38, rx: 4, class: "tp-frame-mini" }, c2);
    T.svg("rect", { x: 300, y: 130, width: 36, height: 10, rx: 2, class: "tp-lcd" }, c2);
    T.svg("rect", { x: 382, y: 130, width: 36, height: 10, rx: 2, class: "tp-lcd" }, c2);
    T.label(c2, 360, 178, `≥ ${stability} s`, "t-small t-strong", { "text-anchor": "middle" });
    T.svg("path", { d: "M348 135H368", class: "t-flow-dash", "marker-end": "url(#tour-arrow)" }, c2);
    // 3 Punktraster.
    const c3 = card(494, "Punktraster", "über die Anzeige legen");
    T.drawLCD(c3, T.DISPLAY, 507, 128, 1.72);
    T.svg("rect", { x: 504, y: 125, width: T.LCD_W * 1.72 + 6, height: T.LCD_H * 1.72 + 6, class: "quad quad--thin" }, c3);
    // 4 Prüfungen.
    const c4 = card(726, "Prüfungen", "OK · WARNUNG · FEHLER");
    T.checkMark(c4, 790, 140, "ok");
    T.checkMark(c4, 824, 140, "ok");
    T.checkMark(c4, 858, 140, "ok");
    const arrows = T.group(layer, "step-arrows");
    [226, 458, 690].forEach((x) => T.svg("path", { d: `M${x} 145H${x + 32}`, class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, arrows));

    // Serieller Sollwert vom GSV-2AS.
    const serial = T.group(layer, "serial");
    T.panel(serial, 470, 8, 244, 40, "t-panel");
    T.label(serial, 592, 33, "GSV-2AS seriell: +0.46761", "t-label", { "text-anchor": "middle", style: MONO + "; font-size: 13px" });
    const serialArrow = T.svg("path", { d: "M592 48V66", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const serialNote = T.label(layer, 726, 33, "← was die Anzeige zeigen sollte", "t-small");

    // Prüfliste (Beispiel) und Ergebnis.
    const checks = T.group(layer, "checks");
    T.panel(checks, 30, 250, 610, 260, "t-panel");
    T.label(checks, 50, 280, "Prüfungen (Beispiel)", "t-label t-strong");
    const names = [
      ["Kontrast", "OK"], ["Kanten", "OK"], ["Rahmen", "OK"], ["Glanz", "OK"],
      ["Auflösung", "OK"], ["Raster", "OK"], ["Stabilität", "OK"], ["Rasterversatz", "WARNUNG"],
    ];
    const checkEls = names.map(([name, status], i) => {
      const x = 50 + (i % 2) * 300;
      const y = 316 + Math.floor(i / 2) * 46;
      const g = T.group(checks, "check");
      T.label(g, x, y + 5, name, "t-label");
      T.badge(g, x + 220, y, status, status === "OK" ? "valid" : "plan", status === "OK" ? 60 : 100);
      return g;
    });
    const out = T.group(layer, "out");
    T.panel(out, 676, 286, 250, 170, "t-panel t-flow-box");
    T.label(out, 801, 320, "Vorschlag", "t-label t-strong", { "text-anchor": "middle" });
    T.label(out, 801, 350, "proposal.json", "t-mono", { "text-anchor": "middle" });
    T.label(out, 801, 380, "+ Kontrollbilder", "t-label", { "text-anchor": "middle" });
    T.label(out, 801, 420, "noch kein Profil", "t-small t-plan-text", { "text-anchor": "middle" });
    tour.docLink(out, "docs/anleitung/11-datensatz-sammeln.html", "Datensatz sammeln öffnen", [910, 302]);
    const outArrow = T.svg("path", { d: "M640 370H672", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, layer);
    const liveCheck = T.label(layer, 480, 532, "Live zusätzlich: Gegenlesen am Standbild · schwankende Zellen maskiert · Lesesperre bis OK", "t-small t-strong", { "text-anchor": "middle" });

    T.hidden(cards, arrows.children, serial, serialArrow, serialNote, checks, checkEls, out, outArrow, liveCheck);
    cards.forEach((g, i) => {
      T.fadeUp(tl, g, {}, i === 0 ? 100 : "+=150");
      if (i > 0) tl.add(arrows.children[i - 1], { opacity: [0, 1], duration: 300 }, "<<");
      if (i === 2) {
        T.fadeUp(tl, [serial], {}, "+=50");
        tl.add([serialArrow, serialNote], { opacity: [0, 1], duration: 400 }, "<");
      }
    });
    tl.add(checks, { opacity: [0, 1], duration: 400 }, "+=200");
    tl.add(checkEls, { opacity: [0, 1], translateY: [10, 0], delay: A.stagger(110), duration: 420, ease: "outBack(1.6)" }, "<<+=100");
    tl.add(outArrow, { opacity: [0, 1], duration: 300 }, "+=150");
    T.popIn(tl, A, [out], { scale: [0.85, 1] }, "<<");
    T.fadeUp(tl, liveCheck, {}, "+=100");
  }

  // -------------------------------------------------- 4. Der Mensch bestätigt --

  function sceneBestaetigen(ctx) {
    const { tl, A, layer, tour } = ctx;
    const proposal = listCard(layer, 30, 70, 230, "proposal.json", ["Viereck", "Raster", "Kamera", "Prüfungen"], "t-panel t-flow-box");

    const look = T.group(layer, "look");
    T.panel(look, 296, 60, 310, 200, "t-panel");
    T.label(look, 451, 88, "Kontrollbilder ansehen", "t-label t-strong", { "text-anchor": "middle" });
    T.svg("rect", { x: 330, y: 106, width: 190, height: 112, rx: 6, class: "tp-frame" }, look);
    T.drawLCD(look, T.DISPLAY, 340, 146, 1.72);
    const grid = T.group(look, "grid");
    for (let i = 0; i < 9; i++) {
      const x = 340 + (2 + i * 6 - 0.4) * 1.72;
      T.svg("rect", { x, y: 146 + 2.1 * 1.72, width: 5 * 1.72, height: 8 * 1.72, style: "fill: none; stroke: var(--tour-flow); stroke-width: 1" }, grid);
    }
    const who = person(look, 560, 172);
    T.label(look, 560, 230, "Bediener", "t-small t-strong", { "text-anchor": "middle" });

    const confirm = T.group(layer, "confirm");
    T.svg("path", { d: "M612 160H678", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, confirm);
    T.label(confirm, 645, 146, "confirm", "t-mono t-mono-sm", { "text-anchor": "middle" });

    const profile = listCard(layer, 684, 50, 250, "profile.json · bestätigt",
      ["quad, grid", "camera", "setup_checks", "confirmed_by", "confirmed_at_utc"], "t-panel t-flow-box");
    T.checkMark(profile, 912, 74, "ok");
    tour.docLink(profile, "docs/anleitung/04-geraeteprofile.html", "Geräteprofile öffnen", [912, 200]);

    const rules = T.group(layer, "rules");
    const rule = (x, kind, head, a, b) => {
      const g = T.group(rules, "rule");
      T.panel(g, x, 330, 285, 150, "t-panel");
      T.badge(g, x + 20 + 70, 362, head, kind, 140);
      T.label(g, x + 20, 410, a, "t-label");
      T.label(g, x + 20, 436, b, "t-label");
      return g;
    };
    const r1 = rule(30, "bad", "FEHLER", "CLI: --override-reason", "Live: nicht bestätigbar");
    const r2 = rule(337, "plan", "NICHT_GEPRUEFT", "ohne Prüfungen steht das", "ehrlich so im Profil");
    const r3 = rule(644, "plan", "schräg", "Raster von Hand:", "profile-regrid.py still");
    T.label(layer, 480, 310, "Bestätigung mit Namen · Live zusätzlich: Einheit und Format geprüft", "t-label t-strong", { "text-anchor": "middle" });
    const rulesHead = layer.lastChild;
    const tolerance = T.label(layer, 480, 516, "Angepasste Toleranz: serielle Gegenprobe + eigenes Häkchen · weiterhin nicht validiert", "t-small t-plan-text", { "text-anchor": "middle" });

    T.hidden(proposal, look, grid.children, who, confirm, profile, r1, r2, r3, rulesHead, tolerance);
    T.fadeUp(tl, proposal, {}, 100);
    T.fadeUp(tl, look, {}, "+=150");
    tl.add(grid.children, { opacity: [0, 1], delay: A.stagger(60), duration: 300 }, "+=50");
    T.popIn(tl, A, [who], { scale: [0.5, 1] }, "+=100");
    tl.add(who, { translateY: [0, -6, 0], duration: 500, ease: "inOutSine" }, "+=100");
    tl.add(confirm, { opacity: [0, 1], translateX: [-10, 0], duration: 400 }, "+=100");
    T.popIn(tl, A, [profile], { scale: [0.85, 1], ease: "outElastic(1, .7)", duration: 900 }, "<<+=200");
    tl.add(rulesHead, { opacity: [0, 1], duration: 300 }, "+=200");
    T.fadeUp(tl, [r1, r2, r3], { delay: A.stagger(200) }, "<<");
    T.fadeUp(tl, tolerance, {}, "+=100");
  }

  // ---------------------------------------------------- 5. Werkbank und Betrieb --

  function sceneWerkbank(ctx) {
    const { tl, A, layer, tour } = ctx;
    const browser = T.group(layer, "browser");
    T.panel(browser, 30, 40, 500, 340, "t-window");
    T.svg("rect", { x: 30, y: 40, width: 500, height: 28, rx: 10, class: "t-window-bar" }, browser);
    [0, 1, 2].forEach((i) => T.svg("circle", { cx: 48 + i * 14, cy: 54, r: 4, class: "t-window-dot" }, browser));
    T.label(browser, 100, 59, "Werkbank · HTTPS, Anmeldung · schematisch", "t-small");
    tour.docLink(browser, "docs/anleitung/10-kamera-livevorschau.html", "Kamera-Workbench öffnen", [514, 59]);
    // Schematische Live-Seite: Kamera und Freigabe sind angeschlossen.
    const camArea = T.group(browser, "cam-area");
    T.panel(camArea, 48, 84, 290, 170, "t-panel t-flow-box");
    T.label(camArea, 193, 150, "Kamerabild", "t-label t-strong", { "text-anchor": "middle" });
    T.label(camArea, 193, 176, "StreamCam · gemeinsamer CameraOwner", "t-small", { "text-anchor": "middle" });
    T.label(camArea, 193, 198, "/live · Einrichtung → Lauf", "t-small", { "text-anchor": "middle", style: MONO });
    // Log rechts, Shell-Tabs unten.
    const log = T.group(browser, "log");
    T.panel(log, 352, 84, 160, 170, "t-panel");
    T.label(log, 432, 108, "Log", "t-small t-strong", { "text-anchor": "middle" });
    for (let i = 0; i < 5; i++) T.svg("path", { d: `M366 ${130 + i * 22}H${490 - (i % 3) * 22}`, class: "t-row-line", style: "stroke-width: 6; stroke-linecap: round" }, log);
    const shell = T.group(browser, "shell");
    T.panel(shell, 48, 268, 464, 96, "t-panel");
    T.svg("rect", { x: 48, y: 268, width: 72, height: 24, rx: 6, style: "fill: var(--tour-flow-soft); stroke: var(--tour-flow)" }, shell);
    T.label(shell, 84, 285, "setup", "t-small t-strong", { "text-anchor": "middle" });
    T.label(shell, 132, 285, "+", "t-small t-strong");
    T.label(shell, 64, 322, "Einrichten → bestätigen → starten → stoppen", "t-small", { style: MONO });
    const role = T.group(layer, "role");
    T.chip(role, 30, 400, "Live: einrichten · bestätigen · lesen · Audit", "chip--flow");
    T.label(role, 30, 454, "TESTLAUF: markiert, keine Messnutzung", "t-small t-plan-text");
    T.label(role, 30, 476, "Kann dennoch VALID anzeigen / protokollieren · OQ-44", "t-small");
    tour.docLink(role, "docs/open-questions.html#oq-44", "OQ-44: Testlauf-Freigabe öffnen", [500, 474]);
    T.label(role, 30, 510, "Toleranz erhöht: weiterhin nicht validiert", "t-small t-plan-text");

    // Rechts: Lesen im Betrieb.
    const run = T.group(layer, "run");
    T.label(run, 735, 52, "Lesen im Betrieb", "t-label t-strong", { "text-anchor": "middle" });
    const box = (x, y, w, title, sub, cls) => {
      const g = T.group(run, "run-box");
      T.panel(g, x, y, w, 58, cls);
      T.label(g, x + w / 2, y + 26, title, "t-label t-strong", { "text-anchor": "middle" });
      T.label(g, x + w / 2, y + 46, sub, "t-small", { "text-anchor": "middle" });
      return g;
    };
    const bCam = box(620, 70, 230, "StreamCam", "v4l2:// · Bildquelle fertig", "t-panel");
    const bRead = box(620, 186, 230, "Lesen · Freigabe", "Dot-Matrix · am Aufbau gelaufen", "t-panel t-flow-box");
    const bLog = box(560, 300, 160, "JSONL-Audit", "je Lauf", "t-panel t-flow-box");
    const bGsv = box(750, 300, 170, "GSVmulti", "Format offen · OQ-07", "t-planned-box");
    tour.docLink(bGsv, "docs/open-questions.html#oq-07", "OQ-07 öffnen", [904, 314]);
    const links = T.group(layer, "run-links");
    T.svg("path", { d: "M735 128V182", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, links);
    T.label(links, 745, 160, "laufendes Lesen", "t-small");
    T.svg("path", { d: "M690 244L650 296", class: "t-flow-line", "marker-end": "url(#tour-arrow)" }, links);
    T.svg("path", { d: "M780 244L825 296", class: "t-plan-line", "marker-end": "url(#tour-arrow-plan)" }, links);
    const next = T.group(layer, "next");
    T.badge(next, 740, 410, "Offen: große Wertwechsel · Live-Abnahme", "plan", 360);
    T.label(next, 740, 460, "reference.jsonl optional · Gegenprobe nachträglich", "t-small", { "text-anchor": "middle" });
    T.label(next, 740, 486, "GSV-2AS-Strom ≠ Kalibrierreferenz", "t-small", { "text-anchor": "middle" });
    T.label(next, 740, 512, "Planende stoppt den Lauf nicht automatisch", "t-small", { "text-anchor": "middle" });
    tour.docLink(next, "TODO.html", "Arbeitsliste öffnen", [928, 404]);

    T.hidden(browser, camArea, log, shell, role, run.children, links.children, next);
    T.fadeUp(tl, browser, {}, 100);
    T.fadeUp(tl, [camArea, log, shell], { delay: A.stagger(180) }, "-=300");
    tl.add(camArea.querySelector("rect"), { strokeWidth: [2, 4, 2], duration: 700, ease: "inOutSine" }, "+=100");
    T.fadeUp(tl, role, {}, "<<");
    tl.add(run.children[0], { opacity: [0, 1], duration: 300 }, "+=200");
    T.fadeUp(tl, [bCam], {}, "<<");
    tl.add(links.children[0], { opacity: [0, 1], duration: 400 }, "+=100");
    tl.add(links.children[1], { opacity: [0, 1], duration: 400 }, "<<");
    T.fadeUp(tl, [bRead], {}, "<<+=100");
    tl.add([links.children[2], links.children[3]], { opacity: [0, 1], duration: 400 }, "+=100");
    T.fadeUp(tl, [bLog, bGsv], { delay: A.stagger(150) }, "<<");
    T.popIn(tl, A, [next], { scale: [0.85, 1], ease: "outElastic(1, .7)", duration: 900 }, "+=200");
  }

  T.register("bedienung-kamera", sceneKamera);
  T.register("bedienung-inbetriebnahme", sceneInbetriebnahme);
  T.register("bedienung-assistent", sceneAssistent);
  T.register("bedienung-bestaetigen", sceneBestaetigen);
  T.register("bedienung-werkbank", sceneWerkbank);
})();
