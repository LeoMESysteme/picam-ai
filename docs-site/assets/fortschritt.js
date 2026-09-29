/* Diagramme der Seite "Fortschritt Ernten und Training" (docs/FORTSCHRITT.md).
 *
 * Vanilla-JS mit SVG, ohne Fremdbibliotheken: Die Doku liegt hinter einer
 * Anmeldung und soll ohne fremde Skripte laufen. Farben kommen aus CSS-Klassen
 * (fortschritt.css), damit der Wechsel zwischen hellem und dunklem Theme ohne
 * Neuzeichnen greift. Daten: assets/data/fortschritt.json, Schema fortschritt_v1,
 * erzeugt von scripts/docs-progress-data.py. Jedes Zahlenfeld darf null sein. */
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  // Die Skriptadresse liegt unter assets/. Sie ist absolut und bleibt bei der
  // Sofortnavigation (navigation.instant) gültig, anders als ein Pfad relativ
  // zur gerade angezeigten Seite.
  const SCRIPT_SRC = document.currentScript ? document.currentScript.src : "";

  // Geplante Abnahmen, für die es noch keine Ergebnisdatei gibt. Sie erscheinen
  // als "ausstehend", solange kein Eintrag in `abnahmen` zum Muster passt.
  // Fest eingetragen: Abnahme 2 mit der Normierung bg_closing_v1 ist geplant
  // (Stufe 2 am 2026-09-29 erneut eingefroren, siehe docs/status.md). Den
  // Eintrag entfernen, wenn weitere Abnahmen nicht mehr von Hand stehen sollen.
  const PENDING_ABNAHMEN = [
    { pattern: /abnahme[\s_-]*2(?!\d)/i, label: "Abnahme 2 (bg_closing_v1)" },
  ];
  const REJECT_LIMIT = 0.2;
  const ROLE_ORDER = ["training", "abnahme", "verworfen", "other"];
  const ROLE_LABELS = { training: "Training", abnahme: "Abnahme", verworfen: "verworfen", other: "ohne Rolle" };

  let observers = [];
  let tooltip = null;
  let pinned = null;
  const tips = new WeakMap();

  /* ---------- Hilfen ---------- */

  function isNum(value) { return typeof value === "number" && Number.isFinite(value); }
  function num(value) { return isNum(value) ? value : 0; }
  function arr(value) { return Array.isArray(value) ? value : []; }
  function obj(value) { return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
  function str(value, fallback) { return typeof value === "string" && value ? value : fallback; }

  function fmtInt(value) {
    return isNum(value) ? Math.round(value).toLocaleString("de-DE") : "k. A.";
  }
  function fmtPct(value, digits) {
    if (!isNum(value)) return "k. A.";
    const d = digits === undefined ? 1 : digits;
    return `${(value * 100).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d })} %`;
  }
  function fmtNum(value) {
    return isNum(value) ? value.toLocaleString("de-DE", { maximumFractionDigits: 3 }) : "k. A.";
  }
  function fmtDate(value) {
    if (typeof value !== "string" || !value) return "k. A.";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return `${date.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" })} UTC`;
  }
  function shortDate(value) {
    const date = typeof value === "string" ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return "ohne Datum";
    return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", timeZone: "UTC" });
  }
  function roleOf(value) {
    const role = typeof value === "string" ? value.toLocaleLowerCase("de") : "";
    return ROLE_LABELS[role] && role !== "other" ? role : "other";
  }

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function svg(tag, attrs, parent, text) {
    const element = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value !== undefined && value !== null) element.setAttribute(key, String(value));
    }
    if (text !== undefined) element.textContent = text;
    if (parent) parent.append(element);
    return element;
  }

  // Kürzt einen Text grob auf eine Breite in Pixeln (Schätzung 0,6 × Schriftgröße je Zeichen).
  function fit(text, width, size) {
    const max = Math.max(1, Math.floor(width / (size * 0.6)));
    return text.length <= max ? text : `${text.slice(0, Math.max(1, max - 1))}…`;
  }

  function niceMax(value) {
    if (!(value > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(value));
    for (const step of [1, 2, 2.5, 5, 10]) {
      if (step * power >= value) return step * power;
    }
    return 10 * power;
  }

  function dataUrl() {
    if (SCRIPT_SRC) return new URL("data/fortschritt.json", SCRIPT_SRC).href;
    const config = document.getElementById("__config");
    let base = ".";
    try { base = JSON.parse(config.textContent).base || "."; } catch (error) { /* Standard behalten */ }
    return new URL(`${base}/assets/data/fortschritt.json`, location.href).href;
  }

  /* ---------- Tooltip ---------- */

  function setTip(element, lines, label) {
    tips.set(element, lines);
    element.setAttribute("data-tip", "");
    element.setAttribute("tabindex", "0");
    element.setAttribute("aria-label", label || lines.join(", "));
  }

  function ensureTooltip() {
    if (!tooltip || !tooltip.isConnected) {
      tooltip = make("div", "fs-tooltip");
      tooltip.setAttribute("role", "tooltip");
      tooltip.hidden = true;
      document.body.append(tooltip);
    }
    return tooltip;
  }

  function showTip(element, x, y) {
    const lines = tips.get(element);
    if (!lines) return;
    const tip = ensureTooltip();
    tip.replaceChildren(...lines.map((line, index) => make(index === 0 ? "strong" : "span", "", line)));
    tip.hidden = false;
    const rect = tip.getBoundingClientRect();
    const pad = 8;
    let left = x + 14;
    let top = y + 14;
    if (left + rect.width > window.innerWidth - pad) left = Math.max(pad, x - rect.width - 14);
    if (top + rect.height > window.innerHeight - pad) top = Math.max(pad, y - rect.height - 14);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
    document.querySelectorAll(".fs-active").forEach((other) => other.classList.remove("fs-active"));
    element.classList.add("fs-active");
  }

  function hideTip() {
    pinned = null;
    if (tooltip) tooltip.hidden = true;
    document.querySelectorAll(".fs-active").forEach((other) => other.classList.remove("fs-active"));
  }

  function bindTips(container) {
    const target = (event) => (event.target instanceof Element ? event.target.closest("[data-tip]") : null);
    container.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" || pinned) return;
      const element = target(event);
      if (element) showTip(element, event.clientX, event.clientY);
      else hideTip();
    });
    container.addEventListener("pointerleave", (event) => {
      if (event.pointerType !== "touch" && !pinned) hideTip();
    });
    container.addEventListener("click", (event) => {
      const element = target(event);
      if (!element) return;
      if (pinned === element) { hideTip(); return; }
      showTip(element, event.clientX, event.clientY);
      pinned = element;
      event.stopPropagation();
    });
    container.addEventListener("focusin", (event) => {
      const element = target(event);
      if (!element) return;
      const rect = element.getBoundingClientRect();
      showTip(element, rect.left + rect.width / 2, rect.bottom);
    });
    container.addEventListener("focusout", () => { if (!pinned) hideTip(); });
  }

  document.addEventListener("click", (event) => {
    if (pinned && !(event.target instanceof Element && event.target.closest("[data-tip]"))) hideTip();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") hideTip(); });
  // Beim Scrollen am Element mitführen statt ausblenden: Das Scroll-Ereignis kann
  // nach dem Überfahren eintreffen und würde den Tooltip sonst sofort schließen.
  window.addEventListener("scroll", () => {
    if (!tooltip || tooltip.hidden) return;
    const active = document.querySelector(".fs-active");
    if (!active) { hideTip(); return; }
    const rect = active.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) { hideTip(); return; }
    const keep = pinned;
    showTip(active, rect.left + rect.width / 2, rect.top + rect.height / 2);
    pinned = keep;
  }, { passive: true });

  /* ---------- Legende und Rahmen ---------- */

  // items: {key, label, swatch, toggle}. Nicht schaltbare Einträge sind reine Farberklärung.
  function legend(items, hidden, onChange) {
    const box = make("div", "fs-legend");
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", "Legende");
    for (const item of items) {
      const swatch = make("span", `fs-swatch ${item.swatch}`);
      swatch.setAttribute("aria-hidden", "true");
      if (item.toggle === false) {
        const key = make("span", "fs-legend-key");
        key.append(swatch, document.createTextNode(item.label));
        box.append(key);
        continue;
      }
      const button = make("button", "fs-legend-item");
      button.type = "button";
      button.dataset.key = item.key;
      button.setAttribute("aria-pressed", hidden.has(item.key) ? "false" : "true");
      button.append(swatch, document.createTextNode(item.label));
      button.addEventListener("click", () => {
        if (hidden.has(item.key)) hidden.delete(item.key);
        else hidden.add(item.key);
        button.setAttribute("aria-pressed", hidden.has(item.key) ? "false" : "true");
        onChange();
      });
      box.append(button);
    }
    return box;
  }

  // Baut den Rahmen eines Diagramms und zeichnet bei jeder Breitenänderung neu.
  function mount(container, spec) {
    const hidden = new Set();
    const headline = make("div", "fs-headline");
    const plot = make("div", spec.scroll ? "fs-plot fs-plot--scroll" : "fs-plot");
    const note = make("p", "fs-note");
    let lastWidth = 0;
    function draw() {
      lastWidth = container.clientWidth;
      hideTip();
      plot.replaceChildren();
      headline.textContent = spec.headline ? spec.headline(hidden) : "";
      headline.hidden = !headline.textContent;
      if (spec.empty) {
        plot.append(make("p", "fs-empty", spec.empty));
        return;
      }
      spec.draw(plot, Math.max(280, plot.clientWidth || lastWidth), hidden);
    }
    container.replaceChildren(headline);
    if (!spec.empty && spec.legend) container.append(legend(spec.legend, hidden, draw));
    container.append(plot);
    if (spec.note) { note.textContent = spec.note; container.append(note); }
    bindTips(plot);
    draw();
    if (typeof ResizeObserver !== "undefined") {
      let frame = 0;
      const observer = new ResizeObserver(() => {
        if (Math.abs(container.clientWidth - lastWidth) < 2) return;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(draw);
      });
      observer.observe(container);
      observers.push(observer);
    }
  }

  /* ---------- a) Datensatz je Gruppe ---------- */

  function datasetGroups(data) {
    const groups = arr(obj(data.dataset).groups).filter((group) => group && typeof group.group === "string");
    return groups.slice().sort((a, b) =>
      ROLE_ORDER.indexOf(roleOf(a.role)) - ROLE_ORDER.indexOf(roleOf(b.role)) ||
      num(b.samples) - num(a.samples) || a.group.localeCompare(b.group, "de"));
  }

  function chartDataset(container, data) {
    const groups = datasetGroups(data);
    const declared = obj(data.dataset).total_samples;
    const total = isNum(declared) ? declared : groups.reduce((sum, group) => sum + num(group.samples), 0);
    const roles = ROLE_ORDER.filter((role) => groups.some((group) => roleOf(group.role) === role));
    mount(container, {
      empty: groups.length ? "" : "Keine Gruppen in den Daten.",
      headline: (hidden) => {
        const visible = groups.filter((group) => !hidden.has(roleOf(group.role)))
          .reduce((sum, group) => sum + num(group.samples), 0);
        const base = `Summe: ${fmtInt(total)} Proben in ${groups.length} Gruppen`;
        return hidden.size ? `${base} (eingeblendet: ${fmtInt(visible)})` : base;
      },
      legend: roles.map((role) => ({ key: role, label: ROLE_LABELS[role], swatch: `fs-fill--${role}` })),
      draw(plot, width, hidden) {
        const rows = groups.filter((group) => !hidden.has(roleOf(group.role)));
        if (!rows.length) { plot.append(make("p", "fs-empty", "Alle Rollen ausgeblendet.")); return; }
        const size = 13;
        const rowHeight = 28;
        const labelWidth = Math.min(width * 0.35, Math.max(...rows.map((group) => group.group.length)) * size * 0.62 + 12);
        const valueWidth = 60;
        const barMax = Math.max(40, width - labelWidth - valueWidth);
        const max = Math.max(1, ...rows.map((group) => num(group.samples)));
        const height = rows.length * rowHeight + 8;
        const root = svg("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "fs-svg", role: "img",
          "aria-label": "Proben je Gruppe" }, plot);
        rows.forEach((group, index) => {
          const role = roleOf(group.role);
          const y = index * rowHeight + 4;
          svg("text", { x: labelWidth - 8, y: y + rowHeight / 2, class: "fs-label", "text-anchor": "end",
            "dominant-baseline": "middle" }, root, fit(group.group, labelWidth - 10, size));
          const barWidth = Math.max(isNum(group.samples) && group.samples > 0 ? 2 : 0, (num(group.samples) / max) * barMax);
          svg("rect", { x: labelWidth, y: y + 4, width: Math.max(barWidth, 1), height: rowHeight - 8, rx: 2,
            class: `fs-bar fs-fill--${role}${isNum(group.samples) ? "" : " fs-missing"}`, "data-role": role,
            "data-group": group.group }, root);
          const hit = svg("rect", { x: 0, y, width, height: rowHeight, class: "fs-hit" }, root);
          svg("text", { x: labelWidth + barWidth + 6, y: y + rowHeight / 2, class: "fs-value",
            "dominant-baseline": "middle" }, root, fmtInt(group.samples));
          const lines = [group.group, `Rolle: ${ROLE_LABELS[role]}${role === "other" && group.role ? ` (${group.role})` : ""}`,
            `Proben: ${fmtInt(group.samples)}`,
            `Anteil an der Summe: ${isNum(group.samples) && total > 0 ? fmtPct(group.samples / total) : "k. A."}`,
            `In der Profilzuordnung: ${group.in_profile_map === true ? "ja" : group.in_profile_map === false ? "nein" : "k. A."}`];
          setTip(hit, lines, `${group.group}: ${fmtInt(group.samples)} Proben, ${ROLE_LABELS[role]}`);
        });
      },
    });
  }

  /* ---------- b) Ernten im Zeitverlauf ---------- */

  const HARVEST_SERIES = [
    { key: "labeled", label: "beschriftet", swatch: "fs-fill--labeled" },
    { key: "unlabeled", label: "nicht beschriftet", swatch: "fs-fill--unlabeled" },
    { key: "dropped", label: "verworfen (Bildverlust)", swatch: "fs-fill--dropped" },
    { key: "drop", label: "Verlustquote", swatch: "fs-swatch--line" },
  ];

  function harvestTime(run) {
    const time = typeof run.started_at_utc === "string" ? Date.parse(run.started_at_utc) : NaN;
    return Number.isNaN(time) ? Infinity : time;
  }

  function chartHarvests(container, data) {
    const runs = arr(data.harvests).filter((run) => run && typeof run === "object")
      .slice().sort((a, b) => harvestTime(a) - harvestTime(b) || str(a.run, "").localeCompare(str(b.run, ""), "de"));
    const anyRam = runs.some((run) => run.staging_ram === true);
    const items = HARVEST_SERIES.slice();
    if (anyRam) items.push({ key: "ram", label: "RAM-Zwischenablage", swatch: "fs-swatch--ram", toggle: false });
    mount(container, {
      scroll: true,
      empty: runs.length ? "" : "Keine Ernten in den Daten.",
      headline: () => {
        const frames = runs.reduce((sum, run) => sum + num(run.frames_recorded), 0);
        const labeled = runs.reduce((sum, run) => sum + num(run.labeled), 0);
        return `${runs.length} Ernten, ${fmtInt(frames)} Bilder aufgenommen, ${fmtInt(labeled)} beschriftet`;
      },
      legend: items,
      note: anyRam ? "Mit „RAM“ markierte Ernten liefen über die RAM-Zwischenablage (--staging-root). RAM-Zwischenablage seit 2026-09-29." : "",
      draw(plot, width, hidden) {
        const ml = 52, mr = hidden.has("drop") ? 12 : 46, mt = 26, mb = 44;
        const slotMin = 64;
        const svgWidth = Math.max(width, ml + mr + runs.length * slotMin);
        const height = 300;
        const innerW = svgWidth - ml - mr;
        const innerH = height - mt - mb;
        const slot = innerW / runs.length;
        const barW = Math.min(slot * 0.62, 56);
        const parts = (run) => {
          const recorded = num(run.frames_recorded);
          const labeled = Math.min(num(run.labeled), recorded);
          return {
            labeled: hidden.has("labeled") ? 0 : labeled,
            unlabeled: hidden.has("unlabeled") ? 0 : Math.max(0, recorded - labeled),
            dropped: hidden.has("dropped") ? 0 : num(run.frames_dropped),
          };
        };
        const max = niceMax(Math.max(1, ...runs.map((run) => {
          const p = parts(run);
          return p.labeled + p.unlabeled + p.dropped;
        })));
        const y = (value) => mt + innerH - (value / max) * innerH;
        const root = svg("svg", { width: svgWidth, height, viewBox: `0 0 ${svgWidth} ${height}`, class: "fs-svg",
          role: "img", "aria-label": "Ernten im Zeitverlauf" }, plot);
        for (let i = 0; i <= 4; i += 1) {
          const value = (max / 4) * i;
          svg("line", { x1: ml, x2: svgWidth - mr, y1: y(value), y2: y(value), class: "fs-grid" }, root);
          svg("text", { x: ml - 6, y: y(value), class: "fs-axis", "text-anchor": "end", "dominant-baseline": "middle" },
            root, fmtInt(value));
        }
        svg("text", { x: 4, y: 12, class: "fs-axis" }, root, "Bilder");
        if (!hidden.has("drop")) {
          for (let i = 0; i <= 4; i += 1) {
            svg("text", { x: svgWidth - mr + 6, y: y((max / 4) * i), class: "fs-axis fs-axis--drop",
              "dominant-baseline": "middle" }, root, `${i * 25} %`);
          }
          svg("text", { x: svgWidth - 4, y: 12, class: "fs-axis fs-axis--drop", "text-anchor": "end" }, root, "Verlust");
        }
        const points = [];
        runs.forEach((run, index) => {
          const cx = ml + slot * index + slot / 2;
          const p = parts(run);
          let base = 0;
          for (const key of ["labeled", "unlabeled", "dropped"]) {
            if (p[key] <= 0) continue;
            svg("rect", { x: cx - barW / 2, y: y(base + p[key]), width: barW, height: y(base) - y(base + p[key]),
              class: `fs-bar fs-fill--${key}`, "data-series": key, "data-run": str(run.run, "") }, root);
            base += p[key];
          }
          if (run.staging_ram === true) {
            const top = y(base) - 18;
            svg("rect", { x: cx - 17, y: top, width: 34, height: 15, rx: 7, class: "fs-ram", "data-ram": "" }, root);
            svg("text", { x: cx, y: top + 8, class: "fs-ram-text", "text-anchor": "middle", "dominant-baseline": "middle" },
              root, "RAM");
          }
          const name = str(run.run, "ohne Namen");
          svg("text", { x: cx, y: height - mb + 16, class: "fs-label", "text-anchor": "middle" }, root, fit(name, slot - 4, 13));
          svg("text", { x: cx, y: height - mb + 32, class: "fs-axis", "text-anchor": "middle" }, root, shortDate(run.started_at_utc));
          if (isNum(run.drop_fraction)) points.push([cx, mt + innerH - Math.min(1, Math.max(0, run.drop_fraction)) * innerH, run]);
          const recorded = num(run.frames_recorded);
          const unlabeled = isNum(run.frames_recorded) && isNum(run.labeled) ? Math.max(0, recorded - run.labeled) : null;
          const lines = [name,
            `Aufstellung ${str(run.setup, "k. A.")} · Gruppe ${str(run.group, "k. A.")} · Rolle ${ROLE_LABELS[roleOf(run.role)]}`,
            `Start: ${fmtDate(run.started_at_utc)}`,
            `Aufgenommen: ${fmtInt(run.frames_recorded)} Bilder`,
            `beschriftet: ${fmtInt(run.labeled)} · nicht beschriftet: ${fmtInt(unlabeled)}`,
            `verworfen: ${fmtInt(run.frames_dropped)} · Verlustquote ${fmtPct(run.drop_fraction)}`,
            `verschiedene Werte: ${fmtInt(run.distinct_values)}`,
            `importiert: ${fmtInt(run.imported)} · Import abgelehnt: ${fmtInt(run.import_rejected)}`,
            `RAM-Zwischenablage: ${run.staging_ram === true ? "ja" : run.staging_ram === false ? "nein" : "k. A."}`];
          const hit = svg("rect", { x: ml + slot * index, y: mt - 20, width: slot, height: innerH + 20 + mb, class: "fs-hit",
            "data-run": name }, root);
          setTip(hit, lines, `${name}: ${fmtInt(run.frames_recorded)} Bilder, ${fmtInt(run.labeled)} beschriftet`);
        });
        if (!hidden.has("drop") && points.length) {
          if (points.length > 1) {
            svg("polyline", { points: points.map(([px, py]) => `${px},${py}`).join(" "), class: "fs-line" }, root);
          }
          for (const [px, py] of points) svg("circle", { cx: px, cy: py, r: 4.5, class: "fs-dot", "data-series": "drop" }, root);
        }
        // Trefferflächen nach oben holen, damit Linie und Punkte den Tooltip nicht verdecken.
        root.querySelectorAll(".fs-hit").forEach((hit) => root.append(hit));
      },
    });
  }

  /* ---------- c) Leser-Entwicklung (loo) ---------- */

  function chartLoo(container, data) {
    const runs = arr(data.loo_runs).filter((run) => run && typeof run === "object").slice()
      .sort((a, b) => (isNum(a.order) ? a.order : Infinity) - (isNum(b.order) ? b.order : Infinity) ||
        str(a.label, "").localeCompare(str(b.label, ""), "de"));
    const known = datasetGroups(data);
    const roleByGroup = new Map(known.map((group) => [group.group, roleOf(group.role)]));
    const names = [];
    for (const group of known) names.push(group.group);
    const extra = new Set();
    for (const run of runs) for (const name of Object.keys(obj(run.groups))) if (!roleByGroup.has(name)) extra.add(name);
    names.push(...Array.from(extra).sort((a, b) => a.localeCompare(b, "de")));
    const present = names.filter((name) => runs.some((run) => obj(run.groups)[name]));
    const role = (name) => roleByGroup.get(name) || "other";
    const roles = ROLE_ORDER.filter((key) => present.some((name) => role(name) === key));
    const wrongCells = runs.reduce((sum, run) =>
      sum + Object.values(obj(run.groups)).filter((cell) => num(obj(cell).falsch) > 0).length, 0);
    mount(container, {
      scroll: true,
      empty: runs.length && present.length ? "" : "Keine loo-Läufe in den Daten.",
      headline: () => (wrongCells
        ? `${runs.length} loo-Läufe · ${wrongCells} ${wrongCells === 1 ? "Zelle" : "Zellen"} mit falschen Lesungen (Ziel 0)`
        : `${runs.length} loo-Läufe · keine falschen Lesungen`),
      legend: roles.map((key) => ({ key, label: `${ROLE_LABELS[key]}-Gruppen`, swatch: `fs-fill--${key}` }))
        .concat([
          { key: "k-ok", label: "richtig", swatch: "fs-fill--correct", toggle: false },
          { key: "k-rej", label: "abgelehnt", swatch: "fs-fill--rejected", toggle: false },
          { key: "k-wrong", label: "falsch > 0", swatch: "fs-fill--wrong", toggle: false },
        ]),
      draw(plot, width, hidden) {
        const rows = present.filter((name) => !hidden.has(role(name)));
        if (!rows.length) { plot.append(make("p", "fs-empty", "Alle Gruppen ausgeblendet.")); return; }
        const labelW = Math.min(140, Math.max(...rows.map((name) => name.length)) * 8 + 16);
        const colW = Math.max(84, Math.min(140, (width - labelW) / runs.length));
        const headH = 44, rowH = 34;
        const svgWidth = Math.max(width, labelW + runs.length * colW);
        const height = headH + rows.length * rowH + 4;
        const root = svg("svg", { width: svgWidth, height, viewBox: `0 0 ${svgWidth} ${height}`, class: "fs-svg",
          role: "img", "aria-label": "Leser-Entwicklung je Gruppe und loo-Lauf" }, plot);
        runs.forEach((run, col) => {
          const cx = labelW + col * colW + colW / 2;
          const head = svg("g", { class: "fs-colhead" }, root);
          svg("text", { x: cx, y: 16, class: "fs-label fs-label--strong", "text-anchor": "middle" }, head,
            fit(str(run.label, `Lauf ${col + 1}`), colW - 6, 13));
          svg("text", { x: cx, y: 33, class: "fs-axis", "text-anchor": "middle" }, head,
            fit(str(run.normalization, "k. A."), colW - 6, 12));
          const hit = svg("rect", { x: labelW + col * colW, y: 0, width: colW, height: headH, class: "fs-hit" }, head);
          setTip(hit, [str(run.label, `Lauf ${col + 1}`), `Normierung: ${str(run.normalization, "k. A.")}`,
            `Reihenfolge: ${fmtInt(run.order)}`, `Code: ${str(run.code_commit, "k. A.")}`, `Datei: ${str(run.file, "k. A.")}`]);
        });
        rows.forEach((name, rowIndex) => {
          const y = headH + rowIndex * rowH;
          svg("text", { x: labelW - 8, y: y + rowH / 2, class: "fs-label", "text-anchor": "end", "dominant-baseline": "middle" },
            root, fit(name, labelW - 10, 13));
          runs.forEach((run, col) => {
            const x = labelW + col * colW + 2;
            const w = colW - 4, h = rowH - 4;
            const cell = obj(run.groups)[name];
            const label = `${name} in ${str(run.label, `Lauf ${col + 1}`)}`;
            if (!cell || typeof cell !== "object") {
              const rect = svg("rect", { x, y: y + 2, width: w, height: h, rx: 3, class: "fs-cell fs-cell--none" }, root);
              svg("text", { x: x + w / 2, y: y + rowH / 2, class: "fs-axis", "text-anchor": "middle", "dominant-baseline": "middle" },
                root, "–");
              setTip(rect, [label, "nicht in diesem Lauf"]);
              return;
            }
            const r = cell.richtig, a = cell.abgelehnt, f = cell.falsch;
            const total = num(r) + num(a) + num(f);
            const share = total > 0 && isNum(r) ? r / total : null;
            const wrong = num(f) > 0;
            const group = svg("g", { class: `fs-cell-group${wrong ? " fs-cell-group--falsch" : ""}`, "data-group": name,
              "data-run": str(run.label, "") }, root);
            const rect = svg("rect", { x, y: y + 2, width: w, height: h, rx: 3,
              class: wrong ? "fs-cell fs-cell--falsch" : "fs-cell fs-fill--rejected" }, group);
            if (!wrong && share !== null && share > 0) {
              svg("rect", { x, y: y + 2, width: w, height: h, rx: 3, class: "fs-fill--correct", "fill-opacity": 0.25 + 0.75 * share,
                "pointer-events": "none" }, group);
            }
            svg("text", { x: x + w / 2, y: y + rowH / 2, class: wrong ? "fs-cell-text fs-cell-text--falsch" : "fs-cell-text",
              "text-anchor": "middle", "dominant-baseline": "middle", "pointer-events": "none" }, group,
              wrong ? `✕ ${fmtInt(f)} falsch` : share === null ? "k. A." : fmtPct(share, 0));
            setTip(rect, [label,
              `richtig ${fmtInt(r)} · abgelehnt ${fmtInt(a)} · falsch ${fmtInt(f)}`,
              `Anteil richtig: ${fmtPct(share)}`,
              `Plateaus r/a/f: ${fmtInt(cell.plateaus_richtig)} / ${fmtInt(cell.plateaus_abgelehnt)} / ${fmtInt(cell.plateaus_falsch)}`,
              `d_max: ${fmtNum(cell.d_max)}`,
              `trainierbar: ${cell.training_eligible === true ? "ja" : cell.training_eligible === false ? "nein" : "k. A."}`],
            `${label}: richtig ${fmtInt(r)}, abgelehnt ${fmtInt(a)}, falsch ${fmtInt(f)}`);
          });
        });
      },
    });
  }

  /* ---------- d) Abnahmen ---------- */

  function chartAbnahmen(container, data) {
    const list = arr(data.abnahmen).filter((item) => item && typeof item === "object").map((item) => {
      const groups = obj(item.groups);
      const cells = Object.values(groups).map(obj);
      const sum = (key) => (cells.some((cell) => isNum(cell[key])) ? cells.reduce((s, cell) => s + num(cell[key]), 0) : null);
      const richtig = sum("richtig"), abgelehnt = sum("abgelehnt"), falsch = sum("falsch");
      const total = num(richtig) + num(abgelehnt) + num(falsch);
      const share = isNum(item.abgelehnt_anteil) ? item.abgelehnt_anteil : (total > 0 && isNum(abgelehnt) ? abgelehnt / total : null);
      return { label: str(item.label, str(item.file, "Abnahme")), item, groups, richtig, abgelehnt, falsch, share,
        verdict: item.bestanden === true ? "pass" : item.bestanden === false ? "fail" : "unknown" };
    });
    for (const pending of PENDING_ABNAHMEN) {
      const found = arr(data.abnahmen).some((item) => pending.pattern.test(`${str(obj(item).label, "")} ${str(obj(item).file, "")}`));
      if (!found) list.push({ label: pending.label, pending: true, verdict: "pending", share: null, falsch: null, groups: {} });
    }
    const VERDICT = { pass: "bestanden", fail: "nicht bestanden", pending: "ausstehend", unknown: "k. A." };
    mount(container, {
      empty: list.length ? "" : "Keine Abnahmen in den Daten.",
      headline: () => {
        const done = list.filter((entry) => !entry.pending);
        const passed = done.filter((entry) => entry.verdict === "pass").length;
        const open = list.length - done.length;
        return `${done.length} ${done.length === 1 ? "Abnahme" : "Abnahmen"}, davon ${passed} bestanden${open ? ` · ${open} ausstehend` : ""}`;
      },
      legend: [
        { key: "share", label: "Anteil abgelehnt", swatch: "fs-fill--rejected-bar" },
        { key: "limit", label: "Grenze 20 %", swatch: "fs-swatch--limit" },
        { key: "wrong", label: "falsch (Ziel 0)", swatch: "fs-fill--wrong" },
      ],
      draw(plot, width, hidden) {
        const rowH = 76, ml = 8, mr = 12;
        const trackW = width - ml - mr;
        const height = list.length * rowH + 6;
        const root = svg("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "fs-svg", role: "img",
          "aria-label": "Abnahmen: Anteil abgelehnt gegen Grenze 20 %" }, plot);
        list.forEach((entry, index) => {
          const y = index * rowH + 4;
          const group = svg("g", { class: `fs-abnahme fs-abnahme--${entry.verdict}`, "data-abnahme": entry.label }, root);
          const badgeText = VERDICT[entry.verdict];
          const badgeW = badgeText.length * 7.2 + 18;
          svg("text", { x: ml, y: y + 12, class: "fs-label fs-label--strong", "dominant-baseline": "middle" }, group,
            fit(entry.label, trackW - badgeW - 10, 13));
          svg("rect", { x: width - mr - badgeW, y: y + 2, width: badgeW, height: 20, rx: 10,
            class: `fs-badge fs-badge--${entry.verdict}` }, group);
          svg("text", { x: width - mr - badgeW / 2, y: y + 12, class: `fs-badge-text fs-badge-text--${entry.verdict}`,
            "text-anchor": "middle", "dominant-baseline": "middle" }, group, badgeText);
          const trackY = y + 30;
          svg("rect", { x: ml, y: trackY, width: trackW, height: 16, rx: 3,
            class: entry.pending ? "fs-track fs-track--pending" : "fs-track" }, group);
          if (!hidden.has("share") && isNum(entry.share)) {
            const over = entry.share > REJECT_LIMIT;
            svg("rect", { x: ml, y: trackY, width: Math.max(1, Math.min(1, entry.share) * trackW), height: 16, rx: 3,
              class: `fs-bar fs-fill--rejected-bar${over ? " fs-over" : ""}`, "data-series": "share" }, group);
          }
          if (!hidden.has("limit")) {
            const lx = ml + REJECT_LIMIT * trackW;
            svg("line", { x1: lx, x2: lx, y1: trackY - 4, y2: trackY + 20, class: "fs-limit", "data-series": "limit" }, group);
          }
          const parts = [];
          if (!hidden.has("share")) parts.push(entry.pending ? "noch keine Ergebnisdatei" : `abgelehnt ${fmtPct(entry.share)} (Grenze 20 %)`);
          if (!hidden.has("wrong") && !entry.pending) parts.push(`falsch ${fmtInt(entry.falsch)} (Ziel 0)`);
          const text = svg("text", { x: ml, y: trackY + 32, class: "fs-axis", "dominant-baseline": "middle" }, group);
          parts.forEach((part, partIndex) => {
            const wrong = part.startsWith("falsch") && num(entry.falsch) > 0;
            svg("tspan", { class: wrong ? "fs-wrong-text" : undefined, "data-series": part.startsWith("falsch") ? "wrong" : undefined },
              text, `${partIndex ? " · " : ""}${part}`);
          });
          const lines = [entry.label, `Urteil: ${badgeText}`];
          if (entry.pending) {
            lines.push("Geplant, noch keine Ergebnisdatei.");
          } else {
            lines.push(`Anteil abgelehnt: ${fmtPct(entry.share)} (Grenze 20 %)`,
              `richtig ${fmtInt(entry.richtig)} · abgelehnt ${fmtInt(entry.abgelehnt)} · falsch ${fmtInt(entry.falsch)}`);
            for (const [name, cell] of Object.entries(entry.groups)) {
              const c = obj(cell);
              lines.push(`${name}: ${fmtInt(c.richtig)} / ${fmtInt(c.abgelehnt)} / ${fmtInt(c.falsch)} (r/a/f)`);
            }
            if (entry.item.templates_sha256) lines.push(`Vorlagen sha256 ${String(entry.item.templates_sha256).slice(0, 8)}…`);
            if (entry.item.file) lines.push(`Datei: ${entry.item.file}`);
          }
          const hit = svg("rect", { x: 0, y, width, height: rowH - 4, class: "fs-hit" }, group);
          setTip(hit, lines, `${entry.label}: ${badgeText}`);
        });
      },
    });
  }

  /* ---------- Laden und Einhängen ---------- */

  function showStatus(status, text, kind) {
    if (!status) return;
    status.replaceChildren(make("p", "", text));
    status.dataset.state = kind;
    status.setAttribute("role", kind === "error" ? "alert" : "status");
  }

  const CHARTS = { dataset: chartDataset, harvests: chartHarvests, loo: chartLoo, abnahmen: chartAbnahmen };

  async function init() {
    observers.forEach((observer) => observer.disconnect());
    observers = [];
    hideTip();
    const containers = Array.from(document.querySelectorAll("[data-fs-chart]"));
    if (!containers.length) return;
    const status = document.querySelector("[data-fs-status]");
    showStatus(status, "Fortschrittsdaten werden geladen …", "loading");
    const url = dataUrl();
    let data;
    try {
      const response = await fetch(url, { cache: "no-cache" });
      if (!response.ok) throw Object.assign(new Error(`HTTP ${response.status}`), { missing: response.status === 404 });
      data = await response.json();
    } catch (error) {
      if (!containers[0].isConnected) return;
      const reason = error && error.missing
        ? "Die Fortschrittsdaten fehlen noch: assets/data/fortschritt.json wurde nicht gefunden."
        : `Die Fortschrittsdaten konnten nicht geladen werden (${error && error.message ? error.message : "unbekannter Fehler"}).`;
      showStatus(status, `${reason} Sie entstehen mit scripts/docs-progress-data.py vor dem Bau der Doku.`, "error");
      containers.forEach((container) => container.replaceChildren(make("p", "fs-empty", "Keine Daten.")));
      return;
    }
    if (!containers[0].isConnected) return;
    data = obj(data);
    const schemaNote = data.schema === "fortschritt_v1" ? "" : ` Unerwartetes Schema „${str(data.schema, "keins")}“, Anzeige ohne Gewähr.`;
    showStatus(status, `Stand der Daten: ${fmtDate(data.generated_at)}.${schemaNote}`, schemaNote ? "warning" : "ok");
    for (const container of containers) {
      const chart = CHARTS[container.dataset.fsChart];
      if (!chart) continue;
      try {
        chart(container, data);
        container.dataset.fsReady = "true";
      } catch (error) {
        container.replaceChildren(make("p", "fs-empty", `Diagramm nicht darstellbar: ${error.message}`));
      }
    }
  }

  if (typeof document$ !== "undefined") document$.subscribe(init);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
