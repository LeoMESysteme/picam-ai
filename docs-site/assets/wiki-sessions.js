/* Prepared statistics only; raw records are loaded solely by the selected explorer. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  // Reihenfolge = Stapelreihenfolge von unten; Farben sind die Diagrammtöne des Wikis.
  const STATUS = [["valid", "VALID", "good"], ["transition", "TRANSITION", "warning"], ["unreadable", "UNREADABLE", "critical"], ["stale", "STALE", "muted"]];
  const num = (v, digits = 2) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("de-DE", { maximumFractionDigits: digits }) : "—";
  const withUnit = (v, unit, digits) => Number.isFinite(v) ? num(v, digits) + (unit ? "\u00a0" + unit : "") : "—";
  // date() steht vor seinen Helfern: tests/session_transport.test.mjs prüft genau diesen Abschnitt.
  const date = value => { const d = parse(value); return d ? longDate.format(d) + " UTC" : "Zeit unbekannt"; };
  const parse = value => typeof value === "string" && value.trim() && Number.isFinite(Date.parse(value)) ? new Date(value) : null;
  const fmt = (options) => new Intl.DateTimeFormat("de-DE", { timeZone: "UTC", ...options });
  const longDate = fmt({ day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const dayOnly = fmt({ day: "2-digit", month: "2-digit" });
  const clockOnly = fmt({ hour: "2-digit", minute: "2-digit" });
  const startTime = run => parse(run.started_at_utc)?.getTime() ?? null;
  function chronological(a, b, newest = false) {
    const left = startTime(a), right = startTime(b);
    if (left === null || right === null) return left === null ? (right === null ? a.id.localeCompare(b.id) : 1) : -1;
    return newest ? right - left : left - right;
  }
  function bytes(size) {
    if (!Number.isFinite(size)) return "Größe unbekannt";
    return size >= 1048576 ? num(size / 1048576, 1) + " MiB" : num(size / 1024, 1) + " KiB";
  }
  function el(tag, text, cls) {
    const node = document.createElement(tag); if (text != null) node.textContent = text; if (cls) node.className = cls; return node;
  }
  function button(text, callback, cls) { const b = el("button", text, cls); b.type = "button"; b.addEventListener("click", callback); return b; }
  function chip(text, kind) { return el("span", text, "session-chip session-chip--" + kind); }
  function svg(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; return n;
  }
  const share = (run, key) => run.stats?.frames ? (run.stats.counts?.[key] || 0) / run.stats.frames * 100 : null;
  const tracking = run => run.stats?.frames && Number.isFinite(run.stats.tracking_lost) ? run.stats.tracking_lost / run.stats.frames * 1000 : null;
  const confidence = run => Number.isFinite(run.stats?.confidence?.median) ? run.stats.confidence.median * 100 : null;
  // Kurzname eines Laufs für Bediener: Startzeit statt Verzeichniskennung.
  const runName = run => { const d = parse(run.started_at_utc); return d ? longDate.format(d) : run.id; };
  // Runde Achsenschritte (1, 2, 2,5, 5 × 10^k).
  function niceStep(value) {
    if (!(value > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(value));
    return power * ([1, 2, 2.5, 5, 10].find(step => step * power >= value) || 10);
  }
  function spread(values) {
    const finite = values.filter(Number.isFinite).sort((a, b) => a - b);
    return finite.length ? { min: finite[0], max: finite[finite.length - 1] } : null;
  }
  function versionText(versions) {
    const parts = Object.entries(versions || {}).map(([name, value]) => name + " " + (Array.isArray(value) ? value.join(", ") : String(value)));
    return parts.join(" · ") || "unbekannt";
  }
  const READERS = { dotmatrix: "Punktmatrix-Leser", sevenseg: "Siebensegment-Leser", tesseract_cli: "Tesseract-Leser" };
  function configText(config = {}) {
    const camera = config.camera || {};
    const tolerance = config.tolerance == null ? "Toleranz unbekannt" : typeof config.tolerance === "number" ? "Toleranz ×" + num(config.tolerance) : "Toleranz " + config.tolerance;
    return [READERS[config.reader_family] || config.reader_family || "Leser unbekannt", tolerance, (config.confirm_frames ?? "?") + " Bestätigungen",
      "Kamera " + (Array.isArray(camera.size) ? camera.size.join("×") : "Größe unbekannt") + " bei " + (camera.fps ?? "?") + " Hz"].join(" · ");
  }

  /* Auffälligkeiten: Tukey-Zäune (1,5 × Interquartilsabstand) innerhalb der Gruppe. */
  const NOTABLE = [
    ["valid", "VALID", run => share(run, "valid"), "low", "%", 0],
    ["p95", "Verarbeitung p95", run => run.stats?.processing_ms?.p95, "high", "ms", 1],
    ["rate", "Leserate", run => run.stats?.rate_hz, "low", "Hz", 1],
    ["confidence", "Konfidenzmedian", confidence, "low", "%", 0],
    ["tracking", "Trackingverluste je 1.000 Frames", tracking, "high", "", 0],
  ];
  function quantile(sorted, q) {
    const pos = (sorted.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }
  function notableRuns(runs) {
    const found = new Map();
    for (const [key, label, read, side, unit, digits] of NOTABLE) {
      const values = runs.map(read).filter(Number.isFinite).sort((a, b) => a - b);
      if (values.length < 4) continue; // Zu wenige Läufe für eine Aussage über die Gruppe.
      const q1 = quantile(values, .25), q3 = quantile(values, .75), fence = 1.5 * (q3 - q1);
      for (const run of runs) {
        const v = read(run);
        if (!Number.isFinite(v) || (side === "low" ? v >= q1 - fence : v <= q3 + fence)) continue;
        const list = found.get(run.id) || []; found.set(run.id, list);
        list.push({ key, label, value: v, unit, digits, q1, q3 });
      }
    }
    return found;
  }
  /* Ende Auffälligkeiten */
  const notableText = n => `${n.label} ${withUnit(n.value, n.unit, n.digits)}; mittlere Hälfte der Gruppe ${num(n.q1, n.digits)} bis ${withUnit(n.q3, n.unit, n.digits)}`;

  window.wiki.onPage(function sessionsPage(article) {
    const host = article.querySelector("#session-dashboard"), trendsHost = article.querySelector("#session-trends");
    const listHost = article.querySelector("#session-list"), viewerHost = article.querySelector("#session-viewer");
    if (!host || !trendsHost || !listHost || !viewerHost) return;
    const viewerHeading = article.querySelector("#untersuchen");
    const abort = new AbortController(); const signal = abort.signal;
    let frame = null, catalog = null, selectedGroup = null, slotA = null, slotB = null, weight = "run_equal";
    let query = "", sort = "new", scope = "group", activeRun = null, metric = "status", openDetails = new Set(), depthOpen = false;
    let themeObserver = null, resizeObserver = null, chartWidth = 0, versionIndex = new Map(), versionCount = 1, notable = new Map();
    const highlighters = new Set();
    document.documentElement.classList.add("session-page");
    const loading = el("p", "Archivübersicht wird geladen …", "session-load-status"); loading.setAttribute("role", "status");
    host.replaceChildren(loading);
    // Eine einzige, knappe Ansage für Tastaturwechsel; die sichtbare Zeile unter dem Diagramm bleibt stumm.
    const announcer = el("p", null, "session-announce"); announcer.setAttribute("aria-live", "polite"); article.append(announcer);
    function theme() { return document.body.dataset.mdColorScheme === "slate" ? "dark" : "light"; }
    function sendTheme() { if (frame?.contentWindow) frame.contentWindow.postMessage({ type: "records-explorer:theme", theme: theme() }, location.origin); }
    const runById = id => catalog.runs.find(r => r.id === id);
    const rowFor = id => [...listHost.querySelectorAll("tr[data-session]")].find(tr => tr.dataset.session === id);

    function revealViewer(focus = true) {
      (viewerHeading || viewerHost).scrollIntoView({ block: "start", behavior: "instant" });
      if (focus && viewerHeading) { viewerHeading.tabIndex = -1; viewerHeading.focus({ preventScroll: true }); }
    }
    function launch(a, b, reveal = true) {
      slotA = a; slotB = a ? b : null;
      const url = new URL(location.href);
      for (const [key, value] of [["a", slotA], ["b", slotB]]) value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
      history.replaceState(history.state, "", url);
      renderViewer(); drawList();
      if (reveal && slotA) revealViewer();
    }
    // Lauf in der Tabelle zeigen, ohne Rohdaten zu laden.
    function reveal(id, focus = false) {
      if (!runById(id)) return;
      if (scope === "group" && runById(id).group !== selectedGroup) { scope = "all"; drawList(); }
      if (query && !rowFor(id)) { query = ""; drawList(); }
      highlight(id);
      const row = rowFor(id); if (!row) return;
      row.scrollIntoView({ block: "nearest", behavior: "instant" });
      if (focus) (row.querySelector(".session-open") || row.querySelector(".session-more"))?.focus({ preventScroll: true });
    }
    function renderViewer() {
      viewerHost.replaceChildren(); frame = null;
      if (!slotA) {
        viewerHost.append(el("p", "Noch kein Lauf gewählt. „Ansehen“ in der Tabelle öffnet ihn hier Frame für Frame.", "session-viewer-empty"));
        return;
      }
      const head = el("div", null, "session-viewer-head");
      const picked = el("div", null, "session-viewer-picked");
      for (const [slot, id] of [["A", slotA], ["B", slotB]]) {
        if (!id) continue;
        const run = runById(id), line = el("p");
        line.append(chip(slot, slot.toLowerCase()), " ", el("strong", run ? runName(run) + " UTC" : id), " ", el("span", id, "session-id"));
        picked.append(line);
      }
      const actions = el("div", null, "session-viewer-actions");
      const url = new URL(window.wiki.siteUrl("assets/records-explorer/index.html"));
      url.searchParams.set("a", slotA); if (slotB) url.searchParams.set("b", slotB);
      const full = el("a", "In voller Fenstergröße öffnen"); full.href = url.href; full.target = "_blank"; full.rel = "noopener";
      // Der gedrückte Knopf verschwindet beim Neuzeichnen; der Fokus geht an die Abschnittsüberschrift.
      const keepFocus = () => { if (viewerHeading) { viewerHeading.tabIndex = -1; viewerHeading.focus({ preventScroll: true }); } };
      if (slotB) actions.append(button("B entfernen", () => { launch(slotA, null, false); keepFocus(); }));
      actions.append(button("Ansicht schließen", () => { launch(null, null, false); keepFocus(); }),
        button("Zurück zur Tabelle", () => reveal(slotA, true)), full);
      head.append(picked, actions); viewerHost.append(head);
      url.searchParams.set("theme", theme()); url.searchParams.set("embed", "1");
      frame = el("iframe"); frame.title = slotB ? "Records Explorer, Vergleich zweier Aufnahmen" : "Records Explorer";
      frame.src = url.href; frame.loading = "lazy"; frame.addEventListener("load", sendTheme, { signal });
      const box = el("div", null, "session-viewer"); box.append(frame); viewerHost.append(box);
    }
    function highlight(id, announce = false) {
      activeRun = id; for (const fn of highlighters) fn(id);
      for (const tr of listHost.querySelectorAll("tr[data-session]")) tr.classList.toggle("session-row--active", tr.dataset.session === id);
      const run = id && runById(id);
      if (announce && run) announcer.textContent = `${runName(run)} UTC: VALID ${withUnit(share(run, "valid"), "%", 1)}, Verarbeitung ${withUnit(run.stats?.processing_ms?.median, "ms", 1)}, Leserate ${withUnit(run.stats?.rate_hz, "Hz", 1)}.`;
    }

    /* Ein Diagramm = eine Spalte je Lauf in Startreihenfolge. kind: status | range | dot. */
    function chart({ title, headline, runs, kind, series, unit, baselines, describe, floor = false, flags = [] }) {
      // Nur Gründe aus der gezeigten Kennzahl markieren; die übrigen nennt die Auslesezeile.
      const flagged = id => (notable.get(id) || []).some(n => flags.includes(n.key));
      // wiki-chart liefert die Diagrammtöne des Wikis (hell und dunkel).
      const figure = el("figure", null, "session-trend wiki-chart"); figure.append(el("figcaption", title));
      if (headline) figure.append(el("p", headline, "session-headline"));
      const legend = el("p", null, "session-legend");
      for (const [, label, tone, shape] of series) {
        const item = el("span", null, "session-key"); const swatch = el("span", null, `session-swatch session-swatch--${shape || kind} session-tone--${tone}`);
        swatch.setAttribute("aria-hidden", "true"); item.append(swatch, document.createTextNode(label)); legend.append(item);
      }
      for (const [label, value, tone, dash] of baselines) {
        if (!Number.isFinite(value)) continue;
        const item = el("span", null, "session-key session-key--baseline"); const swatch = el("span", null, `session-swatch session-swatch--baseline${dash ? "-" + dash : ""} session-tone--${tone}`);
        swatch.setAttribute("aria-hidden", "true"); item.append(swatch, document.createTextNode(`${label}: ${withUnit(value, unit, 1)}`)); legend.append(item);
      }
      if (runs.some(r => flagged(r.id))) {
        const item = el("span", null, "session-key"); const swatch = el("span", null, "session-swatch session-swatch--dot session-swatch--notable");
        swatch.setAttribute("aria-hidden", "true"); item.append(swatch, document.createTextNode("Auffällig in dieser Kennzahl")); legend.append(item);
      }
      figure.append(legend);
      const rows = runs.filter(r => startTime(r) !== null);
      const values = rows.flatMap(r => series.map(([read]) => read(r))).filter(Number.isFinite);
      if (!rows.length || !values.length) { figure.append(el("p", "Für diese Kennzahl fehlen auswertbare Daten.", "session-empty")); return figure; }
      const W = Math.max(300, Math.min(1000, trendsHost.clientWidth)), H = 230, L = 50, R = 10, T = 24, B = 46;
      const slot = (W - L - R) / rows.length, X = i => L + slot * (i + .5);
      const marks = [...values, ...baselines.map(b => b[1]).filter(Number.isFinite)];
      // Teilstriche auf runden Schritten; die Leserate bekommt eine Achse um die Daten statt ab null.
      let bottom = 0, top, step;
      if (unit === "%") { top = 100; step = 25; }
      else if (floor) {
        const lo = Math.min(...marks), hi = Math.max(...marks);
        step = niceStep(Math.max(hi - lo, Math.abs(hi) * .05, 1e-9) / 3);
        bottom = Math.floor(lo / step) * step; if (bottom === lo) bottom -= step; bottom = Math.max(0, bottom);
        top = Math.ceil(hi / step) * step; if (top === hi) top += step;
      } else { step = niceStep(Math.max(...marks) / 4); top = Math.ceil(Math.max(...marks) / step) * step; }
      const Y = v => H - B - (v - bottom) / (top - bottom) * (H - B - T);
      const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, tabindex: "0", role: "group",
        "aria-label": `${title}. ${rows.length} Läufe. Pfeiltasten wählen einen Lauf, Enter springt zu ihm in der Tabelle.` });
      const ticks = Math.round((top - bottom) / step);
      for (let i = 0; i <= ticks; i++) {
        const v = bottom + step * i;
        plot.append(svg("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), class: i ? "session-grid" : "session-axis" }),
          svg("text", { x: L - 7, y: Y(v) + 4, "text-anchor": "end", class: "session-tick" }, num(v, 1) + (i === ticks ? " " + unit : "")));
      }
      // Tagesgruppen unter der Achse; Trennlinie zwischen Tagen.
      let dayStart = 0;
      rows.forEach((run, i) => {
        const day = dayOnly.format(new Date(startTime(run)));
        const next = rows[i + 1] ? dayOnly.format(new Date(startTime(rows[i + 1]))) : null;
        if (slot >= 40) plot.append(svg("text", { x: X(i), y: H - B + 16, "text-anchor": "middle", class: "session-tick" }, clockOnly.format(new Date(startTime(run)))));
        if (next !== day) {
          const mid = (X(dayStart) + X(i)) / 2;
          plot.append(svg("text", { x: mid, y: H - 6, "text-anchor": "middle", class: "session-day" }, day));
          if (next) plot.append(svg("line", { x1: L + slot * (i + 1), x2: L + slot * (i + 1), y1: T - 6, y2: H - 4, class: "session-daybreak" }));
          dayStart = i + 1;
        }
      });
      // Softwarestand: Marke am ersten Lauf jedes Stands, erst ab zwei Ständen.
      if (versionCount > 1) rows.forEach((run, i) => {
        const number = versionIndex.get(run.id), before = i ? versionIndex.get(rows[i - 1].id) : null;
        if (number === before) return;
        const mark = svg("g", { class: "session-version" });
        mark.append(svg("line", { x1: L + slot * i, x2: L + slot * i, y1: T - 4, y2: H - B }), svg("text", { x: L + slot * i + 3, y: T - 9 }, "V" + number));
        plot.append(mark);
      });
      const bandWidth = Math.min(slot, 56);
      const band = svg("rect", { y: T - 4, height: H - B - T + 4, width: bandWidth, rx: 3, class: "session-band", visibility: "hidden" }); plot.append(band);
      const bar = Math.max(4, Math.min(26, slot * .55));
      rows.forEach((run, i) => {
        const g = svg("g", { class: "session-run" });
        if (kind === "status") {
          let base = 0;
          for (const [read, , tone] of series) {
            const v = read(run); if (!Number.isFinite(v) || v <= 0) continue;
            g.append(svg("rect", { x: X(i) - bar / 2, width: bar, y: Y(base + v), height: Math.max(.5, Y(base) - Y(base + v)), class: `session-fill session-tone--${tone}` }));
            base += v;
          }
        } else if (kind === "range") {
          const [lo, hi] = series.map(([read]) => read(run));
          if (Number.isFinite(lo) && Number.isFinite(hi)) g.append(svg("line", { x1: X(i), x2: X(i), y1: Y(lo), y2: Y(hi), class: `session-range session-tone--${series[1][2]}` }));
          if (Number.isFinite(hi)) g.append(svg("line", { x1: X(i) - bar / 3, x2: X(i) + bar / 3, y1: Y(hi), y2: Y(hi), class: `session-tick-mark session-tone--${series[1][2]}` }));
          if (Number.isFinite(lo)) g.append(svg("circle", { cx: X(i), cy: Y(lo), r: 4, class: `session-dot session-tone--${series[0][2]}` }));
        } else {
          const v = series[0][0](run);
          if (Number.isFinite(v)) g.append(svg("circle", { cx: X(i), cy: Y(v), r: 4, class: `session-dot session-tone--${series[0][2]}` }));
        }
        if (flagged(run.id)) g.append(svg("circle", { cx: X(i), cy: T - 12, r: 3.5, class: "session-notable-mark" }));
        plot.append(g);
      });
      if (kind === "dot") {
        // Linie nur innerhalb eines Tages: über Lücken ohne Läufe wird kein Verlauf behauptet.
        let path = "", previousDay = null;
        rows.forEach((run, i) => {
          const v = series[0][0](run), day = dayOnly.format(new Date(startTime(run)));
          if (!Number.isFinite(v)) { previousDay = null; return; }
          path += `${previousDay === day ? "L" : "M"}${X(i)},${Y(v)} `; previousDay = day;
        });
        plot.insertBefore(svg("path", { d: path, class: `session-line session-tone--${series[0][2]}` }), band.nextSibling);
      }
      for (const [, value, tone, dash] of baselines) if (Number.isFinite(value)) plot.append(svg("line", { x1: L, x2: W - R, y1: Y(value), y2: Y(value), class: `session-baseline${dash ? " session-baseline--" + dash : ""} session-tone--${tone}` }));
      // Trefferflächen je Spalte: markieren und zur Tabellenzeile führen, ohne Rohdaten zu laden.
      rows.forEach((run, i) => {
        const hit = svg("rect", { x: L + slot * i, y: T - 4, width: slot, height: H - B - T + 4, class: "session-hit" });
        hit.addEventListener("pointerenter", () => highlight(run.id));
        hit.addEventListener("click", () => reveal(run.id));
        plot.append(hit);
      });
      const readout = el("p", "Lauf überfahren oder Diagramm fokussieren und mit den Pfeiltasten wählen. Ein Klick oder Enter zeigt ihn in der Tabelle.", "session-point-readout");
      const show = id => {
        const i = rows.findIndex(r => r.id === id);
        if (i < 0) { band.setAttribute("visibility", "hidden"); return; }
        band.setAttribute("x", X(i) - bandWidth / 2); band.setAttribute("visibility", "visible");
        const run = rows[i];
        readout.replaceChildren(el("strong", runName(run) + " UTC"), document.createTextNode(` · ${describe(run)}`));
        const why = notable.get(run.id);
        if (why) readout.append(el("span", "Auffällig: " + why.map(notableText).join(" · "), "session-readout-why"));
      };
      highlighters.add(show); if (activeRun) show(activeRun);
      plot.addEventListener("focus", () => { if (!rows.some(r => r.id === activeRun)) highlight(rows[rows.length - 1].id, true); else show(activeRun); });
      plot.addEventListener("keydown", e => {
        const i = Math.max(0, rows.findIndex(r => r.id === activeRun));
        const next = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: rows.length - 1 }[e.key];
        if (next !== undefined) { e.preventDefault(); highlight(rows[Math.max(0, Math.min(rows.length - 1, next))].id, true); }
        else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); reveal(rows[i].id, true); }
      });
      figure.append(plot, readout); return figure;
    }

    function ruleLink(text) { const a = el("a", text, "session-rule-link"); a.href = "#kennzahlen-einordnen"; return a; }
    function metricTile(dl, label, value, unit, note) {
      const div = el("div"); const dd = el("dd", withUnit(value, unit, 1));
      if (note) dd.append(el("span", note, "session-metric-note"));
      div.append(el("dt", label), dd); dl.append(div);
    }
    function drawOverview(group, runs) {
      const body = el("div", null, "session-overview");
      if (!group) { body.append(el("p", "Keine auswertbare Gruppe vorhanden. Alle archivierten Dateien stehen in der Tabelle unter „Läufe im Vergleich“.", "session-empty")); return body; }
      const values = group[weight] || {}, equal = weight === "run_equal";
      const days = runs.map(startTime).filter(t => t !== null);
      const fullDay = fmt({ day: "2-digit", month: "2-digit", year: "numeric" });
      const first = days.length ? Math.min(...days) : null, last = days.length ? Math.max(...days) : null;
      const span = first === null ? "ohne dokumentierten Start" : fullDay.format(new Date(first)) === fullDay.format(new Date(last))
        ? `am ${fullDay.format(new Date(first))}` : `vom ${dayOnly.format(new Date(first))} bis ${fullDay.format(new Date(last))}`;
      const lead = el("p", null, "session-lead");
      lead.append(el("strong", `${group.session_count} ${group.test_run ? (group.session_count === 1 ? "Testlauf" : "Testläufe") : (group.session_count === 1 ? "Lauf" : "Läufe")} ${span}`),
        document.createTextNode(` · ${num(group.frames, 0)} Frames`));
      if (group.test_run) lead.append(" ", chip("Testläufe – nicht für Messungen verwenden", "test"));
      body.append(lead);

      // Urteil aus den Daten: letzter Lauf und benannte Auffälligkeiten.
      const verdict = el("div", null, "session-verdict");
      const latest = [...runs].filter(r => r.stats?.frames > 0).sort((a, b) => chronological(a, b, true))[0];
      if (latest) {
        const line = el("p", null, "session-latest"), flags = notable.get(latest.id);
        line.append(el("span", "Letzter Lauf ", "session-verdict-label"), button(runName(latest) + " UTC", () => reveal(latest.id, true), "session-runlink"),
          document.createTextNode(`: VALID ${withUnit(share(latest, "valid"), "%", 0)}, Verarbeitung ${withUnit(latest.stats?.processing_ms?.median, "ms", 0)}, Leserate ${withUnit(latest.stats?.rate_hz, "Hz", 1)}. `),
          document.createTextNode(flags ? "Fällt gegenüber der Gruppe auf, siehe unten." : runs.length >= 4 ? "Im üblichen Bereich der Gruppe – das ist keine Messfreigabe. " : ""));
        if (!flags && runs.length >= 4) line.append(ruleLink("Was das heißt"));
        verdict.append(line);
      }
      const flagged = runs.filter(r => notable.has(r.id)).sort((a, b) => chronological(a, b, true));
      if (runs.length < 4) verdict.append(el("p", "Für einen Vergleich innerhalb der Gruppe braucht es mindestens vier Läufe.", "session-verdict-quiet"));
      else if (!flagged.length) verdict.append(el("p", "Kein Lauf fällt gegenüber der Gruppe auf.", "session-verdict-quiet"));
      else {
        const head = el("p", null, "session-verdict-head");
        head.append(el("span", `Zum Nachsehen: ${flagged.length} ${flagged.length === 1 ? "Lauf fällt" : "Läufe fallen"} gegenüber der Gruppe auf.`, "session-verdict-label"), " ",
          button("Nur diese in der Tabelle zeigen", () => { scope = "notable"; drawList(); listHost.querySelector(".session-matrix")?.scrollIntoView({ block: "start", behavior: "instant" }); listHost.querySelector(".session-scope")?.focus({ preventScroll: true }); }, "session-runlink session-runlink--quiet"),
          " · ", ruleLink("Wie „auffällig“ bestimmt wird"));
        verdict.append(head);
        const list = el("ul", null, "session-notable");
        for (const run of flagged) {
          const item = el("li"); item.append(button(runName(run) + " UTC", () => reveal(run.id, true), "session-runlink"),
            el("span", notable.get(run.id).map(notableText).join(" · "), "session-notable-why"));
          list.append(item);
        }
        verdict.append(list);
      }
      body.append(verdict);

      const dl = el("dl", null, "session-metrics");
      metricTile(dl, equal ? "VALID-Anteil, Mittel der Läufe" : "VALID-Anteil aller Frames", (values.shares?.valid ?? (group.frames ? 0 : NaN)) * 100, "%");
      metricTile(dl, equal ? "Verarbeitung, Median der Läufe" : "Verarbeitung, Median aller Frames", values.processing_median_ms, "ms",
        Number.isFinite(values.processing_p95_ms) ? `p95 ${withUnit(values.processing_p95_ms, "ms", 1)}` : null);
      const fps = group.config?.camera?.fps;
      metricTile(dl, equal ? "Leserate, Mittel der Läufe" : "Leserate, Frames je Aufnahmedauer", values.rate_hz, "Hz", Number.isFinite(fps) ? `Kamera ${num(fps)} Hz` : null);
      body.append(dl);
      return body;
    }
    function drawDepth(group, runs) {
      // Tiefenebene: Gewichtung, seltene Kennzahlen, Softwarestand.
      const depth = el("details", null, "session-depth wiki-layer wiki-layer--hintergrund"); depth.open = depthOpen;
      depth.addEventListener("toggle", () => { depthOpen = depth.open; });
      depth.append(el("summary", "Gewichtung, weitere Kennzahlen und Softwarestand"));
      const inner = el("div", null, "session-depth-body");
      const weightLabel = el("label", "Gewichtung"), weightSelect = el("select");
      for (const [value, text] of [["run_equal", "Jeder Lauf zählt gleich"], ["frame_weighted", "Alle Frames gemeinsam"]]) { const option = el("option", text); option.value = value; weightSelect.append(option); }
      weightSelect.value = weight;
      const weightHint = el("span", weight === "run_equal" ? "Mittel bzw. Median über die Läufe; kurze Läufe zählen wie lange." : "Addierte Frames und echte Quantile; lange Läufe wiegen mehr.", "session-hint");
      weightHint.id = "session-weight-hint"; weightSelect.setAttribute("aria-describedby", weightHint.id);
      weightSelect.addEventListener("change", () => { weight = weightSelect.value; draw(); host.querySelector(".session-depth select")?.focus(); });
      weightLabel.append(weightSelect);
      const field = el("div", null, "session-field"); field.append(weightLabel, weightHint); inner.append(field);
      const values = group[weight] || {}, equal = weight === "run_equal";
      const dl = el("dl", null, "session-metrics session-metrics--quiet");
      metricTile(dl, equal ? "Konfidenzmedian VALID, Median der Läufe" : "Konfidenzmedian aller VALID", (values.confidence_median ?? NaN) * 100, "%");
      metricTile(dl, "Trackingverluste je 1.000 Frames", values.tracking_per_1000, "");
      inner.append(dl);
      const versions = [...new Set(runs.map(r => JSON.stringify(r.versions || {})))];
      inner.append(el("p", versions.length === 1 ? "Alle Läufe dieser Gruppe haben denselben dokumentierten Softwarestand:" : `${versions.length} dokumentierte Softwarestände; die Marke V… im Verlauf steht am ersten Lauf jedes Stands:`, "session-hint"));
      const list = el("ul", null, "session-versions"); versions.forEach((key, i) => list.append(el("li", `V${i + 1}: ${versionText(JSON.parse(key))}`))); inner.append(list);
      depth.append(inner); return depth;
    }

    const METRICS = [["status", "Statusanteile"], ["processing", "Verarbeitung"], ["rate", "Leserate"]];
    // Spanne als Satz; bei nur einem Wert kein „zwischen 0 und 0“.
    const between = (range, unit, digits) => range.min === range.max ? `bei allen Läufen ${withUnit(range.min, unit, digits)}` : `zwischen ${num(range.min, digits)} und ${withUnit(range.max, unit, digits)}`;
    function flaggedNote(runs, keys) {
      const count = runs.filter(r => (notable.get(r.id) || []).some(n => keys.includes(n.key))).length;
      return count ? ` ${count === 1 ? "Ein Lauf fällt" : count + " Läufe fallen"} hier auf (Punkt über der Spalte).` : "";
    }
    function drawTrend(group, runs) {
      const values = group[weight] || {};
      if (metric === "status") {
        const valid = spread(runs.map(r => share(r, "valid")));
        return chart({
          title: "Statusanteile je Lauf", kind: "status", runs, unit: "%", flags: ["valid"],
          headline: valid ? `VALID ${between(valid, "%", 0)}.${flaggedNote(runs, ["valid"])}` : null,
          series: STATUS.map(([key, label, tone]) => [r => share(r, key), label, tone]),
          baselines: [["VALID gesamt", (values.shares?.valid ?? NaN) * 100, "ink"]],
          describe: run => run.stats?.frames ? STATUS.map(([key, label]) => `${label} ${withUnit(share(run, key), "%", 1)}`).join(" · ") : "keine auswertbaren Frames",
        });
      }
      if (metric === "processing") {
        const proc = spread(runs.map(r => r.stats?.processing_ms?.median)), p95 = spread(runs.map(r => r.stats?.processing_ms?.p95));
        return chart({
          title: "Verarbeitungsdauer je Lauf", kind: "range", runs, unit: "ms", flags: ["p95"],
          headline: proc && p95 ? `Median ${between(proc, "ms", 1)}, p95 bis ${withUnit(p95.max, "ms", 1)}.${flaggedNote(runs, ["p95"])}` : null,
          series: [[r => r.stats?.processing_ms?.median, "Median", "series", "dot"], [r => r.stats?.processing_ms?.p95, "p95", "series", "tick"]],
          baselines: [["Median gesamt", values.processing_median_ms, "series"], ["p95 gesamt", values.processing_p95_ms, "series", "dotted"]],
          describe: run => `Verarbeitung Median ${withUnit(run.stats?.processing_ms?.median, "ms")}, p95 ${withUnit(run.stats?.processing_ms?.p95, "ms")}`,
        });
      }
      const rate = spread(runs.map(r => r.stats?.rate_hz)), fps = group.config?.camera?.fps;
      return chart({
        title: "Leserate je Lauf", kind: "dot", runs, unit: "Hz", floor: true, flags: ["rate"],
        headline: rate ? `Aufgezeichnet ${between(rate, "Hz", 1)}${Number.isFinite(fps) ? `; die Kamera liefert ${withUnit(fps, "Hz")}` : ""}.${flaggedNote(runs, ["rate"])}` : null,
        series: [[r => r.stats?.rate_hz, "Leserate (aufgezeichnete Datensätze pro Sekunde)", "series"]],
        baselines: [["Leserate gesamt", values.rate_hz, "series"], ...(Number.isFinite(fps) ? [["Kamera", fps, "ink", "camera"]] : [])],
        describe: run => Number.isFinite(run.stats?.rate_hz) ? `Leserate ${withUnit(run.stats.rate_hz, "Hz")}` : "Leserate unbekannt (keine belastbare Aufnahmezeitbasis)",
      });
    }
    function drawTrends(group, runs) {
      trendsHost.replaceChildren();
      if (!group) { trendsHost.append(el("p", "Keine Gruppe mit auswertbaren Läufen.", "session-empty")); return; }
      const tabs = el("div", null, "session-switch"); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Verlauf zeigen");
      const panel = el("div", null, "session-switch-panel"); panel.id = "session-trend-panel"; panel.setAttribute("role", "tabpanel");
      METRICS.forEach(([key, label]) => {
        const tab = button(label, () => { metric = key; drawTrends(group, runs); trendsHost.querySelector(`[data-metric="${key}"]`)?.focus(); });
        tab.dataset.metric = key; tab.id = "session-tab-" + key;
        tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", String(key === metric)); tab.setAttribute("aria-controls", panel.id);
        tab.tabIndex = key === metric ? 0 : -1;
        tab.addEventListener("keydown", e => {
          const i = METRICS.findIndex(([k]) => k === key), next = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: METRICS.length - 1 }[e.key];
          if (next === undefined) return; e.preventDefault();
          metric = METRICS[(next + METRICS.length) % METRICS.length][0]; drawTrends(group, runs); trendsHost.querySelector(`[data-metric="${metric}"]`)?.focus();
        });
        tabs.append(tab);
      });
      panel.setAttribute("aria-labelledby", "session-tab-" + metric);
      highlighters.clear();
      panel.append(drawTrend(group, runs));
      trendsHost.append(tabs, panel, el("p", "Spalten stehen in Startreihenfolge; Abstände sind keine Zeitabstände. Ein Trend ist noch kein Nachweis einer Verbesserung der Messrichtigkeit.", "session-trend-note"));
    }

    function draw() {
      highlighters.clear();
      const group = catalog.groups.find(g => g.id === selectedGroup);
      const runs = group ? catalog.runs.filter(r => r.group === group.id).sort(chronological) : [];
      notable = notableRuns(runs);
      versionIndex = new Map(); const versions = [];
      for (const run of runs) {
        const key = JSON.stringify(run.versions || {}); let index = versions.indexOf(key);
        if (index < 0) { versions.push(key); index = versions.length - 1; }
        versionIndex.set(run.id, index + 1);
      }
      versionCount = versions.length;
      host.querySelector(".session-overview")?.remove(); host.querySelector(".session-depth")?.remove();
      host.append(drawOverview(group, runs));
      if (group) host.append(drawDepth(group, runs));
      drawTrends(group, runs);
      drawList();
    }

    function detailRow(run, columns) {
      const tr = el("tr", null, "session-detail-row"); tr.dataset.detailFor = run.id;
      const td = el("td"); td.colSpan = columns; tr.append(td);
      const facts = el("dl", null, "session-facts");
      const value = run.stats?.value?.median;
      for (const [label, text] of [
        ["Kennung", run.id], ["Gerät", run.device_id ?? "unbekannt"], ["Einstellungen", configText(run.config)],
        ["Frames · Dauer", `${num(run.stats?.frames, 0)} · ${Number.isFinite(run.stats?.duration_s) ? num(run.stats.duration_s / 60, 1) + " min" : "Dauer unbekannt"}`],
        ["Konfidenzmedian VALID", withUnit(confidence(run), "%", 1)], ["Trackingverluste je 1.000 Frames", withUnit(tracking(run), "", 1)],
        ["Messwertmedian VALID (Detail, keine Qualitätsnote)", Number.isFinite(value) ? `${num(value, 6)} ${run.unit || ""}` : "kein VALID-Messwert"],
        ["Softwarestand", versionText(run.versions)],
      ]) { const div = el("div"); div.append(el("dt", label), el("dd", text)); facts.append(div); }
      td.append(facts);
      const files = el("div", null, "session-files");
      const size = run.files.reduce((sum, f) => sum + (f.size || 0), 0);
      files.append(el("p", `Originaldateien · ${run.files.length} Dateien · ${bytes(size)}`, "session-files-title"));
      const problem = el("p", null, "session-row-error"); problem.hidden = true; problem.setAttribute("role", "alert");
      for (const entry of run.files) {
        const item = el("div", null, "session-file"); item.append(el("span", `${entry.name} · ${bytes(entry.size)}`, "session-file-name"));
        const download = button("Original herunterladen", async () => {
          download.disabled = true; problem.hidden = true;
          try { const m = await window.SessionFiles.manifest(run, signal); const file = m.files.find(f => f.name === entry.name); if (!file) throw new Error("Datei fehlt im Manifest."); await window.SessionFiles.download(file, signal); }
          catch (error) { if (!signal.aborted) { problem.textContent = `${entry.name}: ${error.message}`; problem.hidden = false; } }
          finally { download.disabled = false; }
        }); item.append(download);
        const links = [];
        for (const [i, part] of entry.parts.entries()) {
          const link = el("a", entry.parts.length === 1 ? "gzip-Teil" : String(i + 1)); try { link.href = window.SessionFiles.member(part.path); } catch { continue; }
          link.download = ""; link.setAttribute("aria-label", `gzip-Teil ${i + 1} von ${entry.name}`); links.push(link);
        }
        if (links.length === 1) item.append(links[0]);
        else if (links.length) {
          const parts = el("details", null, "session-parts"); parts.append(el("summary", `${links.length} gzip-Teile`));
          const row = el("p"); links.forEach(link => row.append(link, " ")); parts.append(row); item.append(parts);
        }
        files.append(item);
      }
      const manifest = el("a", "Manifest mit Prüfsummen"); manifest.href = window.SessionFiles.member(run.manifest); files.append(manifest, problem);
      td.append(files);
      return tr;
    }
    function strip(run) {
      const bar = el("span", null, "session-strip");
      if (!run.stats?.frames) { bar.classList.add("session-strip--empty"); bar.setAttribute("aria-hidden", "true"); return bar; }
      for (const [key, , tone] of STATUS) {
        const v = share(run, key); if (!(v > 0)) continue;
        const part = el("span", null, `session-strip-part session-tone--${tone}`); part.style.width = v + "%"; bar.append(part);
      }
      bar.setAttribute("role", "img");
      bar.setAttribute("aria-label", "Statusanteile: " + STATUS.map(([key, label]) => `${label} ${num(share(run, key), 1)} %`).join(", "));
      return bar;
    }
    const SORTS = [["new", "Neueste zuerst"], ["old", "Älteste zuerst"], ["valid", "Niedrigster VALID-Anteil zuerst"], ["p95", "Längste Verarbeitung (p95) zuerst"], ["frames", "Meiste Frames zuerst"]];
    const sorter = {
      frames: (a, b) => (b.stats?.frames || 0) - (a.stats?.frames || 0),
      valid: (a, b) => (share(a, "valid") ?? Infinity) - (share(b, "valid") ?? Infinity),
      p95: (a, b) => (b.stats?.processing_ms?.p95 ?? -Infinity) - (a.stats?.processing_ms?.p95 ?? -Infinity),
    };
    // Zugänglicher Name mit Laufbezug; der sichtbare Text steht vorn (Label in Name).
    function named(node, run) { node.setAttribute("aria-label", `${node.textContent}: ${runName(run)} UTC`); return node; }
    function drawList() {
      if (!catalog?.runs.length) return;
      const focused = listHost.contains(document.activeElement) ? document.activeElement : null;
      const restore = focused && { session: focused.closest("tr")?.dataset.session || focused.closest("tr")?.dataset.detailFor, text: focused.textContent, input: focused.matches("input, select") ? focused.className || focused.tagName : null };
      listHost.replaceChildren();
      const controls = el("div", null, "session-controls");
      const searchLabel = el("label", "Läufe durchsuchen"); const search = el("input"); search.type = "search"; search.value = query; search.className = "session-search";
      search.placeholder = "Datum, Kennung, „auffällig“";
      search.addEventListener("input", () => { query = search.value; drawList(); });
      searchLabel.append(search);
      const group = catalog.groups.find(g => g.id === selectedGroup);
      const scopeLabel = el("label", "Zeigen"); const scopeSelect = el("select"); scopeSelect.className = "session-scope";
      const scopes = [["group", `Gewählte Gruppe (${catalog.runs.filter(r => r.group === selectedGroup).length})`], ["all", `Alle Läufe einschließlich Tests (${catalog.runs.length})`]];
      if (notable.size) scopes.splice(1, 0, ["notable", `Nur auffällige der Gruppe (${notable.size})`]);
      if (scope === "notable" && !notable.size) scope = "group";
      for (const [value, text] of scopes) {
        const option = el("option", text); option.value = value; scopeSelect.append(option);
      }
      if (!group) scope = "all";
      scopeSelect.value = scope; scopeSelect.disabled = !group;
      scopeSelect.addEventListener("change", () => { scope = scopeSelect.value; drawList(); }); scopeLabel.append(scopeSelect);
      const orderLabel = el("label", "Sortierung"); const order = el("select"); order.className = "session-order";
      for (const [value, text] of SORTS) { const option = el("option", text); option.value = value; order.append(option); }
      order.value = sort; order.addEventListener("change", () => { sort = order.value; drawList(); }); orderLabel.append(order);
      controls.append(searchLabel, scopeLabel, orderLabel); listHost.append(controls);
      listHost.append(el("p", slotA ? "„Als B daneben“ stellt einen zweiten Lauf zum Vergleich neben A." : "„Ansehen“ öffnet einen Lauf unten Frame für Frame; danach lässt sich ein zweiter als B danebenstellen.", "session-howto"));
      const runs = catalog.runs.filter(r => scope === "all" || (scope === "notable" ? notable.has(r.id) : r.group === selectedGroup))
        .filter(r => [r.id, runName(r), r.device_id ?? "", r.test_run ? "Testlauf" : "", ...(r.warnings || []),
          ...(notable.get(r.id) || []).map(n => n.label + " auffällig")].join(" ").toLowerCase().includes(query.toLowerCase()));
      runs.sort(sorter[sort] || ((a, b) => chronological(a, b, sort !== "old")));
      // wiki-chart liefert die Diagrammtöne auch für die Statusstreifen.
      const table = el("table", null, "session-matrix wiki-chart");
      const caption = el("caption", `${runs.length} ${runs.length === 1 ? "Lauf" : "Läufe"} · ${SORTS.find(([v]) => v === sort)[1]}`); table.append(caption);
      const head = el("thead"), hr = el("tr");
      for (const [text, cls, sub] of [["Lauf", "session-col-run", "Start UTC"], ["Status", "session-col-strip"], ["VALID", "session-col-num"], ["Verarbeitung", "session-col-num", "Median / p95"], ["Leserate", "session-col-num"], ["Auswahl", "session-col-act"]]) {
        const th = el("th", text, cls); th.scope = "col"; if (sub) th.append(el("span", sub, "session-th-sub")); hr.append(th);
      }
      head.append(hr); table.append(head);
      const rows = el("tbody"); table.append(rows); listHost.append(table);
      for (const run of runs) {
        const tr = el("tr", null, "session-row"); tr.dataset.session = run.id;
        if (run.id === slotA || run.id === slotB) tr.classList.add("session-row--picked");
        if (run.id === activeRun) tr.classList.add("session-row--active");
        tr.addEventListener("pointerenter", () => highlight(run.id));
        tr.addEventListener("focusin", () => highlight(run.id));
        const name = el("th"); name.scope = "row"; name.dataset.label = "Lauf";
        const title = el("p", null, "session-run-title");
        if (run.id === slotA) title.append(chip("A", "a"), " "); if (run.id === slotB) title.append(chip("B", "b"), " ");
        title.append(el("strong", runName(run)));
        name.append(title, el("span", run.id, "session-id"));
        const flags = el("p", null, "session-flags");
        if (run.test_run) flags.append(chip("Testlauf – nicht für Messungen verwenden", "test"));
        for (const n of notable.get(run.id) || []) { const c = chip(`${n.label} auffällig`, "warn"); c.title = notableText(n); flags.append(c); }
        for (const warning of run.warnings || []) flags.append(chip(window.SessionFiles.warning(warning), "warn"));
        if (run.stats?.invalid_lines) flags.append(chip(`${num(run.stats.invalid_lines, 0)} nicht auswertbare Zeilen`, "warn"));
        if (flags.childNodes.length) name.append(flags);
        const stripCell = el("td", null, "session-col-strip"); stripCell.dataset.label = "Status"; stripCell.append(strip(run));
        const cells = [
          ["VALID", withUnit(share(run, "valid"), "%", 1)],
          ["Verarbeitung (Median / p95)", `${num(run.stats?.processing_ms?.median, 1)} / ${withUnit(run.stats?.processing_ms?.p95, "ms", 1)}`],
          ["Leserate", withUnit(run.stats?.rate_hz, "Hz", 1)],
        ].map(([label, text]) => { const td = el("td", text, "session-col-num"); td.dataset.label = label; return td; });
        const act = el("td", null, "session-col-act"); act.dataset.label = "Auswahl";
        const actions = el("div", null, "session-actions");
        if (run.id === slotA) actions.append(el("span", "In der Ansicht (A)", "session-picked-note"));
        else actions.append(named(button("Ansehen", () => launch(run.id, null), "session-open"), run));
        if (slotA && run.id !== slotA) actions.append(run.id === slotB ? el("span", "Daneben (B)", "session-picked-note") : named(button("Als B daneben", () => launch(slotA, run.id), "session-compare"), run));
        const open = openDetails.has(run.id);
        const more = button(open ? "Details schließen" : "Details und Dateien", () => {
          openDetails.has(run.id) ? openDetails.delete(run.id) : openDetails.add(run.id); drawList();
          rowFor(run.id)?.querySelector(".session-more")?.focus();
        }, "session-more session-textbutton");
        more.setAttribute("aria-expanded", String(open)); named(more, run);
        name.append(more); act.append(actions);
        tr.append(name, stripCell, ...cells, act); rows.append(tr);
        if (open) { const detail = detailRow(run, 6); more.setAttribute("aria-controls", detail.id = "session-detail-" + rows.children.length); rows.append(detail); }
      }
      if (!runs.length) { const row = el("tr"), cell = el("td", "Keine Läufe passen zur Suche."); cell.colSpan = 6; row.append(cell); rows.append(row); }
      if (restore?.input) { const again = listHost.querySelector("." + restore.input.split(" ")[0]); again?.focus(); if (again?.type === "search") again.setSelectionRange(again.value.length, again.value.length); }
      else if (restore?.session) {
        const buttons = [...listHost.querySelectorAll("tr button")].filter(b => (b.closest("tr").dataset.session || b.closest("tr").dataset.detailFor) === restore.session);
        (buttons.find(b => b.textContent === restore.text) || buttons[0])?.focus();
      }
    }

    // Ohne Katalog gibt es nur eine Meldung im Überblick; Verlauf und Tabelle bleiben leer statt sie zu wiederholen.
    function unavailable() {
      for (const node of [trendsHost, listHost]) node.replaceChildren();
      const plain = el("p", "Lokale Aufnahmen lassen sich weiterhin im Explorer öffnen. ", "session-viewer-empty"), link = el("a", "Explorer ohne Lauf öffnen");
      link.href = window.wiki.siteUrl("assets/records-explorer/index.html"); link.target = "_blank"; link.rel = "noopener"; plain.append(link);
      viewerHost.replaceChildren(plain);
    }
    window.SessionFiles.catalog(signal).then(data => {
      if (signal.aborted) return; catalog = data; host.setAttribute("aria-busy", "false");
      if (!data.runs.length) {
        const empty = el("div", null, "session-empty-state");
        empty.append(chip("Leer", "test"), el("p", "Noch keine Läufe im veröffentlichten Archiv. Ein Lauf erscheint hier, nachdem die Workbench beendet ist und das Wiki das nächste Mal veröffentlicht wird."));
        host.replaceChildren(empty); unavailable(); return;
      }
      const newest = [...data.runs].filter(r => !r.test_run && r.stats?.frames > 0).sort((a, b) => chronological(a, b, true))[0];
      selectedGroup = newest?.group || data.groups[0]?.id;
      const controls = el("div", null, "session-controls");
      const groupLabel = el("label", "Gerät und Einstellungen"), groupSelect = el("select");
      for (const group of data.groups) {
        const option = el("option", (group.test_run ? "Testläufe · " : "") + group.label + ` · ${group.session_count} ${group.session_count === 1 ? "Lauf" : "Läufe"}`); option.value = group.id; groupSelect.append(option);
      }
      const groupDetail = el("span", null, "session-hint");
      const describeGroup = () => { const group = data.groups.find(g => g.id === selectedGroup);
        groupDetail.textContent = (group?.test_run ? "Testläufe, nicht für Messungen verwenden. " : "") + "Verglichen werden nur Läufe mit gleichen Einstellungen: " + configText(group?.config) + "."; };
      groupSelect.value = selectedGroup; groupSelect.addEventListener("change", () => { selectedGroup = groupSelect.value; scope = "group"; activeRun = null; describeGroup(); draw(); });
      // Hinweis außerhalb des Labels, damit der zugängliche Name nur das Label bleibt.
      groupDetail.id = "session-group-hint"; groupSelect.setAttribute("aria-describedby", groupDetail.id);
      groupLabel.append(groupSelect); describeGroup();
      const groupField = el("div", null, "session-field"); groupField.append(groupLabel, groupDetail);
      controls.append(groupField);
      host.replaceChildren(controls);
      const params = new URLSearchParams(location.search); const ids = new Set(data.runs.map(r => r.id));
      slotA = ids.has(params.get("a")) ? params.get("a") : null; slotB = slotA && ids.has(params.get("b")) && params.get("b") !== slotA ? params.get("b") : null;
      draw(); renderViewer(); chartWidth = trendsHost.clientWidth;
      // Geteilter Link: direkt zur Einzelansicht statt an den Seitenanfang.
      if (slotA) requestAnimationFrame(() => { if (!signal.aborted) revealViewer(false); });
      resizeObserver = new ResizeObserver(() => { if (Math.abs(trendsHost.clientWidth - chartWidth) > 2) { chartWidth = trendsHost.clientWidth; draw(); } });
      resizeObserver.observe(trendsHost);
      themeObserver = new MutationObserver(sendTheme); themeObserver.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
    }).catch(error => {
      if (signal.aborted) return;
      host.setAttribute("aria-busy", "false");
      const failed = el("div", null, "session-empty-state"); failed.setAttribute("role", "alert");
      const source = article.querySelector("details.session-source");
      failed.append(chip("Nicht geladen", "error"), el("p", `Das Archiv ließ sich nicht laden (${error.message}).${source ? " Die Tabelle „Archivkennzahlen und Dateien“ oben ist aufgeklappt und bietet alle Downloads." : ""}`),
        button("Seite neu laden", () => location.reload()));
      host.replaceChildren(failed);
      if (source) source.open = true;
      unavailable();
    });
    return () => { abort.abort(); themeObserver?.disconnect(); resizeObserver?.disconnect(); highlighters.clear(); announcer.remove(); if (frame) frame.src = "about:blank"; document.documentElement.classList.remove("session-page"); };
  });
})();
