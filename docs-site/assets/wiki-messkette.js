/* Messkette der Startseite (nur lebendige Darstellung, wiki-messkette.css).
 *
 * Eine Bühne zeigt den Messweg aus assets/data/kette.json: jede Stufe ein
 * Glasknoten mit Zustandspunkt, darüber ein Anzeigewert, der von Stufe zu
 * Stufe wandert und sich dabei verwandelt (Bildausschnitt → gefundene
 * Anzeige → nachgeführtes Viereck → entzerrtes Raster → gelesene Ziffern →
 * Datensatz VALID → Audit, DUT-Ausgabe gesperrt). Die Bewegung erklärt die
 * Reihenfolge der Kette; sie läuft nur, solange die Bühne im Blick ist.
 *
 * - Platzhalter im Markdown: <div class="wiki-messkette" data-messkette>.
 *   Ohne JavaScript und in „ruhig“ bleibt er leer und unsichtbar.
 * - Überfahren oder Fokus einer Stufe hält an und zeigt ihren Zweck; ein
 *   Klick öffnet die Doku der Stufe (kette.json „doku“).
 * - Reduzierte Bewegung: kein Wandern; jede Stufe trägt ihr Standbild.
 * - Wert und Zeichensatz wie in der Projekt-Tour (tour.js, „+0.46761 mV/V“);
 *   Punktmuster aus tour-facts.json (ocr.rom_a00), m, V und / ergänzen nur
 *   die Darstellung der Einheit. */
(function () {
  "use strict";

  const { onPage, siteUrl, loadJson, make } = window.wiki;
  const NS = "http://www.w3.org/2000/svg";
  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const OUT = "cubic-bezier(.16, 1, .3, 1)";
  const lively = () => root.getAttribute("data-wiki-look") === "lebendig";
  const STATES = { fertig: "resolved", gebaut: "progress", teilweise: "partial", "außer Betrieb": "discarded" };

  // Zeitplan eines Durchlaufs: Ankunft an der ersten Stufe, dann je Stufe
  // Fahrt und Verweilen; danach ruhige Pause im Endzustand.
  const T_FIRST = 700;
  const T_MOVE = 620;
  const T_DWELL = 380;
  const T_REST = 4200;
  const T_BACK = 900;
  const T_RESUME = 1100;

  // HD44780 ROM A00, 5 × 8 Punkte; überschrieben aus tour-facts.json.
  const ROM = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110", "00000"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110", "00000"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010", "00000"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110", "00000"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000", "00000"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "m": ["00000", "00000", "11010", "10101", "10101", "10001", "10001", "00000"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100", "00000"],
    "/": ["00000", "00001", "00010", "00100", "01000", "10000", "00000", "00000"],
  };
  const DISPLAY = "+0.46761 mV/V   ";
  const READ = "+0.46761";
  const VALUE = "0.46761";
  const UNIT = "mV/V";
  const LCD_W = 16 * 6 - 1 + 4; // 16 Zellen à 5 Punkte + Abstand, Rand 2
  const LCD_H = 8 + 5;

  // Was der Wert an jeder Stufe ist (Beschriftung unter dem Träger).
  const FORM_LABEL = {
    frames: "Bild mit Zeitstempel",
    detect: "Anzeige gefunden",
    track: "Viereck nachgeführt",
    rectify: "entzerrtes Raster",
    ocr: `gelesen: ${READ}`,
    validate: "Datensatz · VALID",
    sink: "Audit · DUT gesperrt",
  };

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
    if (parent) parent.append(node);
    return node;
  }

  function text(parent, x, y, content, cls, extra) {
    const node = el("text", { x, y, class: cls, ...(extra || {}) }, parent);
    node.textContent = content;
    return node;
  }

  function dots(x0, y0, u, ch, on) {
    const glyph = ROM[ch] || ROM[" "];
    const size = (0.8 * u).toFixed(2);
    let d = "";
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 5; c++) {
        if (on && glyph[r][c] !== "1") continue;
        d += `M${(x0 + c * u).toFixed(2)} ${(y0 + r * u).toFixed(2)}h${size}v${size}h-${size}z`;
      }
    }
    return d;
  }

  // 16-stellige Punktraster-Anzeige; u = Punktabstand.
  function lcd(parent, x, y, u, grid) {
    el("rect", { x: x - 2.5, y: y - 2.5, width: LCD_W * u + 5, height: LCD_H * u + 5, rx: 2.5, class: "tp-bezel" }, parent);
    el("rect", { x, y, width: LCD_W * u, height: LCD_H * u, rx: u * 0.8, class: "tp-lcd" }, parent);
    let off = "";
    let on = "";
    for (let i = 0; i < 16; i++) {
      const cx = x + (2 + i * 6) * u;
      const cy = y + 2.5 * u;
      off += dots(cx, cy, u, " ", false);
      on += dots(cx, cy, u, DISPLAY[i], true);
      if (grid) el("rect", { x: cx - 0.4 * u, y: cy - 0.4 * u, width: 5 * u, height: 8 * u, class: "wmk-zelle" }, parent);
    }
    el("path", { d: off, class: "tp-dot-off" }, parent);
    el("path", { d: on, class: "tp-dot-on" }, parent);
  }

  // Kamerabild: Gerät leicht gedreht und gekippt im dunklen Bildrahmen.
  const SCENE = { x: 21, y: 15, rotate: -5, skew: -9 };
  const LCD_AT = { x: 7, y: 9, u: 1.02 };

  function lcdQuad(scene) {
    const matrix = new DOMMatrix().translate(scene.x, scene.y).rotate(scene.rotate).skewX(scene.skew);
    const w = LCD_W * LCD_AT.u;
    const h = LCD_H * LCD_AT.u;
    return [[0, 0], [w, 0], [w, h], [0, h]].map(([px, py]) => {
      const p = matrix.transformPoint(new DOMPoint(LCD_AT.x + px, LCD_AT.y + py));
      return [p.x, p.y];
    });
  }

  function cameraImage(parent, scene) {
    el("rect", { x: 0, y: 0, width: 160, height: 84, rx: 8, class: "tp-frame" }, parent);
    const g = el("g", { transform: `translate(${scene.x} ${scene.y}) rotate(${scene.rotate}) skewX(${scene.skew})` }, parent);
    el("rect", { x: 0, y: 0, width: 118, height: 50, rx: 5, class: "tp-body" }, g);
    lcd(g, LCD_AT.x, LCD_AT.y, LCD_AT.u, false);
    for (let i = 0; i < 4; i++) el("rect", { x: 8 + i * 17, y: 34, width: 12, height: 8, rx: 2, class: "tp-key" }, g);
    el("circle", { cx: 106, cy: 38, r: 2.4, class: "tp-led-on" }, g);
  }

  function quad(parent, points, cls) {
    el("polygon", { points: points.map((p) => p.map((v) => v.toFixed(2)).join(",")).join(" "), class: cls }, parent);
    if (!cls.includes("geist")) for (const [cx, cy] of points) el("circle", { cx, cy, r: 1.9, class: "wmk-ecke" }, parent);
  }

  function lock(parent, x, y) {
    const g = el("g", { class: "wmk-schloss", transform: `translate(${x} ${y})` }, parent);
    el("rect", { x: 0, y: 4.5, width: 9, height: 7, rx: 1.6 }, g);
    el("path", { d: "M2 4.5V3a2.5 2.5 0 0 1 5 0v1.5", fill: "none" }, g);
    return g;
  }

  // Eine Form je Stufe, alle im selben Rahmen 160 × 84.
  const FORMS = {
    frames(svg) {
      cameraImage(svg, SCENE);
    },
    detect(svg) {
      cameraImage(svg, SCENE);
      quad(svg, lcdQuad(SCENE), "wmk-quad");
    },
    track(svg) {
      // Das Gerät hat sich ein wenig bewegt; das bestätigte Viereck folgt ihm
      // (begrenzte Nachregistrierung), der alte Sitz bleibt als Umriss.
      const moved = { ...SCENE, x: SCENE.x + 3.5, y: SCENE.y - 2, rotate: SCENE.rotate + 1.2 };
      cameraImage(svg, moved);
      quad(svg, lcdQuad(SCENE), "wmk-quad wmk-quad--geist");
      quad(svg, lcdQuad(moved), "wmk-quad");
    },
    rectify(svg) {
      el("rect", { x: 0, y: 0, width: 160, height: 84, rx: 8, class: "wmk-grund" }, svg);
      lcd(svg, (160 - LCD_W * 1.42) / 2, 30, 1.42, true);
    },
    ocr(svg) {
      el("rect", { x: 0, y: 0, width: 160, height: 84, rx: 8, class: "wmk-grund" }, svg);
      const g = el("g", { class: "wmk-blass" }, svg);
      lcd(g, (160 - LCD_W * 1.2) / 2, 10, 1.2, false);
      const cell = 15;
      const x0 = 10;
      [...READ].forEach((ch, i) => {
        el("rect", { x: x0 + i * cell, y: 42, width: cell - 2.5, height: 21, rx: 3.5, class: "wmk-ziffer-feld" }, svg);
        text(svg, x0 + i * cell + (cell - 2.5) / 2, 57, ch, "wmk-ziffer", { "text-anchor": "middle" });
      });
      text(svg, x0 + READ.length * cell + 2, 57, UNIT, "wmk-einheit");
    },
    validate(svg) {
      el("rect", { x: 6, y: 4, width: 148, height: 76, rx: 9, class: "wmk-karte" }, svg);
      text(svg, 16, 20, "ValueRecord", "wmk-karte-titel");
      const rows = [["value", VALUE], ["unit", UNIT]];
      rows.forEach(([name, value], i) => {
        const y = 38 + i * 15;
        text(svg, 16, y, name, "wmk-feld");
        text(svg, 144, y, value, "wmk-wert", { "text-anchor": "end" });
      });
      text(svg, 16, 68, "status", "wmk-feld");
      el("rect", { x: 104, y: 58, width: 40, height: 14, rx: 7, class: "wmk-valid" }, svg);
      text(svg, 124, 68.5, "VALID", "wmk-valid-text", { "text-anchor": "middle" });
    },
    sink(svg) {
      el("rect", { x: 6, y: 6, width: 148, height: 30, rx: 8, class: "wmk-karte" }, svg);
      el("path", { d: "M15 21.5l3.4 3.4 6.6-7", class: "wmk-haken" }, svg);
      text(svg, 32, 19, "JSONL · Audit", "wmk-karte-titel");
      text(svg, 32, 30, `${VALUE} ${UNIT} · VALID`, "wmk-feld wmk-feld--eng");
      el("path", { d: "M80 37v9", class: "wmk-sperrlinie" }, svg);
      el("rect", { x: 6, y: 48, width: 148, height: 30, rx: 8, class: "wmk-karte wmk-karte--gesperrt" }, svg);
      lock(svg, 14, 54);
      text(svg, 32, 61, "GSVmulti", "wmk-karte-titel");
      text(svg, 32, 72, "DUT-Ausgabe gesperrt", "wmk-gesperrt");
    },
  };

  function form(id) {
    const svg = el("svg", { viewBox: "0 0 160 84", class: "wmk-form", "aria-hidden": "true", focusable: "false" });
    svg.dataset.form = id;
    FORMS[id](svg);
    return svg;
  }

  function lockedOutput(stage) {
    return /gesperrt/i.test(`${stage.zweck} ${stage.einstellung}`);
  }

  function mount(host, stages) {
    const still = reduce.matches;
    const figure = make("figure", "wmk");
    figure.dataset.modus = still ? "standbild" : "bewegt";
    const stageBox = make("div", "wmk-buehne");
    const lane = make("div", "wmk-bahn");
    lane.setAttribute("aria-hidden", "true");
    const carrier = make("div", "wmk-traeger");
    const formBox = make("div", "wmk-formen");
    const carrierLabel = make("span", "wmk-traeger-text");
    const forms = stages.map((stage) => {
      const svg = form(stage.id);
      formBox.append(svg);
      return svg;
    });
    carrier.append(formBox, carrierLabel);
    lane.append(carrier);

    const list = make("ol", "wmk-stufen");
    const rail = make("span", "wmk-schiene");
    rail.setAttribute("aria-hidden", "true");
    const fill = make("i", "wmk-fuellung");
    rail.append(fill);
    const caption = make("figcaption", "wmk-text");
    const idleText = still
      ? "Der Messweg: was aus dem Anzeigewert an jeder Stufe wird. Stufe überfahren oder fokussieren zeigt ihren Zweck; ein Klick öffnet die Doku."
      : "Ein Anzeigewert auf dem Messweg. Stufe überfahren oder fokussieren hält an und zeigt ihren Zweck; ein Klick öffnet die Doku.";
    const nodes = stages.map((stage, index) => {
      const item = make("li", "wmk-stufe");
      item.dataset.zustand = STATES[stage.zustand];
      const link = make("a", "wmk-knoten");
      link.href = siteUrl(stage.doku);
      link.dataset.stufe = stage.id;
      const dot = make("span", `wmk-punkt wmk-punkt--${STATES[stage.zustand]}`);
      dot.setAttribute("aria-hidden", "true");
      const sign = make("span", "wmk-schild");
      sign.append(make("span", "wmk-titel", stage.titel), make("span", "wmk-zustand", stage.zustand));
      if (stage.id === "sink" && lockedOutput(stage)) {
        // Ehrlicher Zustand der Ausgabe: gebaut bis zur Brücke, DUT gesperrt.
        sign.append(make("span", "wmk-sperre", "DUT gesperrt"));
        link.dataset.gesperrt = "";
      }
      link.append(dot, sign);
      const why = make("span", "wmk-zweck", stage.zweck);
      why.id = `wmk-zweck-${stage.id}`;
      link.setAttribute("aria-describedby", why.id);
      item.append(link, why);
      if (still) {
        const picture = form(stage.id);
        picture.classList.add("wmk-standbild");
        const label = make("span", "wmk-standbild-text", FORM_LABEL[stage.id]);
        label.setAttribute("aria-hidden", "true");
        const frame = make("span", "wmk-standbild-rahmen");
        frame.append(picture, label);
        item.append(frame);
      }
      list.append(item);
      link.addEventListener("pointerenter", () => hold(index));
      link.addEventListener("focus", () => hold(index));
      return { item, link, dot };
    });
    if (still) stageBox.append(list, rail);
    else stageBox.append(lane, list, rail);
    const footer = make("div", "wmk-fuss");
    footer.append(caption);
    // Glaspille „Nochmal“ (Linien-Icon wie die Tour-Knöpfe), erst im Ruhezustand.
    const again = make("button", "wmk-nochmal");
    again.type = "button";
    again.hidden = true;
    const againIcon = document.createElementNS(NS, "svg");
    for (const [key, value] of Object.entries({ viewBox: "0 0 24 24", width: "1em", height: "1em", fill: "none",
      stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) {
      againIcon.setAttribute(key, value);
    }
    el("path", { d: "M4 4v5h5M4.6 9A8 8 0 1 1 4 13" }, againIcon);
    again.append(againIcon, make("span", "", "Nochmal"));
    again.setAttribute("aria-label", "Messweg nochmal abspielen");
    if (!still) footer.append(again);
    figure.append(stageBox, footer);
    host.replaceChildren(figure);
    host.classList.add("wmk-an");
    caption.textContent = idleText;

    let disposed = false;
    let generation = 0;
    let current = 0;
    let shown = -1;
    let visible = false;
    let holding = -1;
    let passesLeft = 2;
    let resumeTimer = 0;
    let running = [];
    const timers = new Set();

    function wait(ms, gen) {
      return new Promise((resolve) => {
        const id = setTimeout(() => { timers.delete(id); resolve(gen === generation && !disposed); }, ms);
        timers.add(id);
      });
    }

    function vertical() {
      return getComputedStyle(stageBox).getPropertyValue("--wmk-richtung").trim() === "senkrecht";
    }

    // Mittelpunkt der Zustandspunkte relativ zur Bühne.
    function centers() {
      const box = stageBox.getBoundingClientRect();
      return nodes.map(({ dot }) => {
        const r = dot.getBoundingClientRect();
        return { x: r.left + r.width / 2 - box.left, y: r.top + r.height / 2 - box.top };
      });
    }

    function carrierPos(index) {
      const laneBox = lane.getBoundingClientRect();
      const node = nodes[index].link.getBoundingClientRect();
      if (vertical()) {
        const y = node.top + node.height / 2 - laneBox.top - carrier.offsetHeight / 2;
        return `translate(0px, ${Math.max(0, Math.min(laneBox.height - carrier.offsetHeight, y)).toFixed(1)}px)`;
      }
      const x = node.left + node.width / 2 - laneBox.left - carrier.offsetWidth / 2;
      return `translate(${Math.max(0, Math.min(laneBox.width - carrier.offsetWidth, x)).toFixed(1)}px, 0px)`;
    }

    function railScale(index) {
      return String(index / Math.max(1, stages.length - 1));
    }

    function layout() {
      const points = centers();
      const first = points[0];
      const last = points[points.length - 1];
      const down = vertical();
      rail.dataset.richtung = down ? "senkrecht" : "waagerecht";
      if (down) {
        Object.assign(rail.style, { left: `${first.x - 1}px`, top: `${first.y}px`, width: "2px", height: `${Math.max(0, last.y - first.y)}px` });
      } else {
        Object.assign(rail.style, { left: `${first.x}px`, top: `${first.y - 1}px`, width: `${Math.max(0, last.x - first.x)}px`, height: "2px" });
      }
      if (still) {
        fill.style.transform = down ? "scaleY(1)" : "scaleX(1)";
        return;
      }
      carrier.style.transform = carrierPos(current);
      fill.style.transform = down ? `scaleY(${railScale(current)})` : `scaleX(${railScale(current)})`;
    }

    function cancelRunning() {
      running.forEach((animation) => animation.cancel());
      running = [];
      settleNow();
    }

    function mark(index) {
      nodes.forEach(({ item }, k) => {
        item.classList.toggle("wmk-hier", k === index);
        item.classList.toggle("wmk-durch", k < index);
      });
    }

    // Genau eine Form ist „an“. Während einer Wischblende liegt die neue
    // („neu“, darüber) auf der alten, die bis zum Ende voll sichtbar bleibt.
    let settle = null;

    function showForm(index) {
      forms.forEach((svg, k) => {
        svg.classList.toggle("wmk-form--an", k === index);
        svg.classList.remove("wmk-form--neu");
      });
      carrierLabel.textContent = FORM_LABEL[stages[index].id];
      shown = index;
    }

    function settleNow() {
      const done = settle;
      settle = null;
      done?.();
    }

    // Fahrt zur Stufe index: Die neue Form deckt die alte per Wischblende in
    // Fahrtrichtung zu (beide Ebenen sind dabei da, Formen haben einen
    // deckenden Grund); erst danach wird die alte abgelegt. Die Schiene
    // füllt (oder leert) sich bis zur neuen Stufe.
    function travel(index, duration) {
      settleNow();
      const fromTransform = carrier.style.transform || carrierPos(current);
      const toTransform = carrierPos(index);
      const down = vertical();
      const forward = index >= current;
      const axis = down ? "scaleY" : "scaleX";
      const fromFill = fill.style.transform || `${axis}(${railScale(current)})`;
      const toFill = `${axis}(${railScale(index)})`;
      const next = forms[index];
      const wipeFrom = down
        ? (forward ? "inset(0 0 100% 0)" : "inset(100% 0 0 0)")
        : (forward ? "inset(0 100% 0 0)" : "inset(0 0 0 100%)");
      cancelRunning();
      carrier.style.transform = toTransform;
      fill.style.transform = toFill;
      running.push(carrier.animate([{ transform: fromTransform }, { transform: toTransform }], { duration, easing: OUT }));
      running.push(fill.animate([{ transform: fromFill }, { transform: toFill }], { duration, easing: OUT }));
      if (shown !== index && shown >= 0) {
        next.classList.add("wmk-form--neu");
        const wipe = next.animate([{ clipPath: wipeFrom }, { clipPath: "inset(0 0 0 0)" }],
          { duration: duration * 0.72, delay: duration * 0.18, easing: OUT, fill: "backwards" });
        running.push(wipe);
        // Form, Unterschrift und Markierung des Knotens wechseln gemeinsam,
        // wenn die neue Form die alte ganz zugedeckt hat.
        settle = () => { showForm(index); mark(index); };
        wipe.finished.then(() => { if (settle && next.classList.contains("wmk-form--neu")) settleNow(); }, () => {});
      } else {
        showForm(index);
        mark(index);
      }
      current = index;
    }

    function start() {
      cancelRunning();
      settle = null;
      current = 0;
      carrier.style.transform = carrierPos(0);
      fill.style.transform = `${vertical() ? "scaleY" : "scaleX"}(0)`;
      showForm(0);
      mark(0);
    }

    async function loop(from) {
      const gen = ++generation;
      let index = from;
      if (index < 0) {
        start();
        if (!(await wait(T_FIRST, gen))) return;
        index = 0;
      } else if (index >= stages.length - 1) {
        // Von vorn: die Linse gleitet zurück zur ersten Stufe, die Schiene
        // leert sich; der Inhalt wechselt per Wischblende gegen die Fahrt.
        travel(0, T_BACK);
        if (!(await wait(T_BACK + T_FIRST, gen))) return;
        index = 0;
      }
      for (let k = index + 1; k < stages.length; k++) {
        travel(k, T_MOVE);
        if (!(await wait(T_MOVE + T_DWELL, gen))) return;
      }
      figure.dataset.durchlauf = String(Number(figure.dataset.durchlauf || 0) + 1);
      passesLeft -= 1;
      if (passesLeft <= 0) { rest(); return; }
      if (!(await wait(T_REST, gen))) return;
      loop(stages.length - 1);
    }

    function pause() {
      generation++;
      timers.forEach(clearTimeout);
      timers.clear();
      running.forEach((animation) => animation.finish());
      running = [];
      settleNow();
      if (shown >= 0) mark(current);
      figure.dataset.lauf = passesLeft <= 0 ? "ruht" : "angehalten";
    }

    // Ruhe im Lesemodus: nach zwei Durchläufen bleibt die Kette im
    // Endzustand stehen. „Nochmal“ oder Überfahren einer Stufe startet einen
    // weiteren Durchlauf.
    function rest() {
      generation++;
      figure.dataset.lauf = "ruht";
      again.hidden = false;
    }

    function restart(fromStart) {
      passesLeft = Math.max(passesLeft, 1);
      again.hidden = true;
      if (fromStart) {
        clearTimeout(resumeTimer);
        figure.dataset.lauf = "läuft";
        loop(stages.length - 1);
      }
    }

    function play() {
      if (still || disposed || !visible || holding >= 0 || document.hidden || passesLeft <= 0) return;
      figure.dataset.lauf = "läuft";
      loop(shown < 0 ? -1 : current);
    }

    function hold(index) {
      clearTimeout(resumeTimer);
      holding = index;
      nodes.forEach(({ item }, k) => item.classList.toggle("wmk-fokus", k === index));
      caption.replaceChildren(make("strong", "", stages[index].titel), " · ", stages[index].zweck);
      if (still) return;
      pause();
      if (index !== current || shown !== index) travel(index, 300);
    }

    function release() {
      if (list.contains(document.activeElement) && document.activeElement.matches(":focus-visible")) return;
      holding = -1;
      nodes.forEach(({ item }) => item.classList.remove("wmk-fokus"));
      caption.textContent = idleText;
      if (still) return;
      if (passesLeft <= 0) restart(false);
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(play, T_RESUME);
    }

    again.addEventListener("click", () => restart(true));
    list.addEventListener("pointerleave", release);
    list.addEventListener("focusout", (event) => {
      if (!list.contains(event.relatedTarget)) {
        holding = -1;
        release();
      }
    });

    let observer = null;
    if (!still && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver((entries) => {
        const now = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= .35);
        if (now === visible) return;
        visible = now;
        if (visible) play();
        else pause();
      }, { threshold: [0, .35, .6] });
      observer.observe(figure);
    }
    function visibilityChanged() {
      if (document.hidden) pause();
      else play();
    }
    if (!still) document.addEventListener("visibilitychange", visibilityChanged);

    let frame = 0;
    const resize = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (disposed) return;
        const wasRunning = figure.dataset.lauf === "läuft";
        if (wasRunning) pause();
        layout();
        if (wasRunning) play();
      });
    }) : null;
    resize?.observe(stageBox);

    // Schriften kommen später als das erste Zeichnen und ändern die Breiten.
    const fontsDone = () => { if (!disposed) layout(); };
    document.fonts?.addEventListener?.("loadingdone", fontsDone);

    if (still) {
      mark(stages.length);
      layout();
    } else {
      showForm(0);
      mark(0);
      layout();
      if (typeof IntersectionObserver === "undefined") { visible = true; play(); }
    }

    return () => {
      disposed = true;
      generation++;
      timers.forEach(clearTimeout);
      timers.clear();
      clearTimeout(resumeTimer);
      cancelAnimationFrame(frame);
      cancelRunning();
      observer?.disconnect();
      resize?.disconnect();
      document.removeEventListener("visibilitychange", visibilityChanged);
      document.fonts?.removeEventListener?.("loadingdone", fontsDone);
      host.classList.remove("wmk-an");
      host.replaceChildren();
    };
  }

  function valid(data) {
    return data?.schema === "kette_v1" && Array.isArray(data.stufen) && data.stufen.length > 0
      && data.stufen.every((stage) => stage && Object.hasOwn(FORMS, stage.id) && Object.hasOwn(STATES, stage.zustand)
        && ["titel", "zweck", "doku"].every((field) => typeof stage[field] === "string" && stage[field].trim()));
  }

  onPage((article) => {
    const host = article.querySelector(".wiki-messkette[data-messkette]");
    if (!host) return;
    let stopped = false;
    let unmount = null;
    let stages = null;

    function sync() {
      if (stopped || !stages) return;
      unmount?.();
      unmount = null;
      if (lively()) unmount = mount(host, stages);
    }

    Promise.all([
      loadJson("assets/data/kette.json"),
      loadJson("assets/data/tour-facts.json").catch(() => null),
    ]).then(([data, facts]) => {
      if (stopped || !valid(data)) return;
      const rom = facts?.facts?.["ocr.rom_a00"]?.value;
      if (rom && typeof rom === "object") {
        for (const [ch, rows] of Object.entries(rom)) {
          if (Array.isArray(rows) && rows.length === 8) ROM[ch] = rows;
        }
      }
      stages = data.stufen;
      sync();
    }).catch(() => { /* Ohne Daten bleibt der Platzhalter leer. */ });

    window.addEventListener("wiki:look", sync);
    reduce.addEventListener("change", sync);
    return () => {
      stopped = true;
      window.removeEventListener("wiki:look", sync);
      reduce.removeEventListener("change", sync);
      unmount?.();
    };
  });
})();
