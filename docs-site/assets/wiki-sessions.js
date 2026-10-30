/* Prepared statistics only; raw records are loaded solely by the selected explorer. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  // Reihenfolge = Stapelreihenfolge von unten; Farben sind die Diagrammtöne des Wikis.
  const STATUS = [["valid", "VALID", "good"], ["transition", "TRANSITION", "warning"], ["unreadable", "UNREADABLE", "critical"], ["stale", "STALE", "muted"]];
  const num = (v, digits = 2) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("de-DE", { maximumFractionDigits: digits }) : "—";
  const withUnit = (v, unit, digits) => Number.isFinite(v) ? num(v, digits) + (unit ? " " + unit : "") : "—";
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
  function button(text, callback) { const b = el("button", text); b.type = "button"; b.addEventListener("click", callback); return b; }
  function chip(text, kind) { return el("span", text, "session-chip session-chip--" + kind); }
  function svg(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; return n;
  }
  const share = (run, key) => run.stats?.frames ? (run.stats.counts?.[key] || 0) / run.stats.frames * 100 : null;
  // Runde Achsenobergrenze (1, 2, 2,5, 5 × 10^k) statt max × 1,1.
  function niceMax(value) {
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
  function configText(config = {}) {
    const camera = config.camera || {};
    const tolerance = config.tolerance == null ? "Toleranz unbekannt" : typeof config.tolerance === "number" ? "Toleranz ×" + num(config.tolerance) : "Toleranz " + config.tolerance;
    return [config.reader_family || "Leser unbekannt", tolerance, (config.confirm_frames ?? "?") + " Bestätigungen",
      (Array.isArray(camera.size) ? camera.size.join("×") : "Größe unbekannt") + " / " + (camera.fps ?? "?") + " Hz"].join(" · ");
  }

  window.wiki.onPage(function sessionsPage(article) {
    const host = article.querySelector("#session-dashboard"), trendsHost = article.querySelector("#session-trends");
    const listHost = article.querySelector("#session-list"), viewerHost = article.querySelector("#session-viewer");
    if (!host || !trendsHost || !listHost || !viewerHost) return;
    const viewerHeading = article.querySelector("#untersuchen");
    const abort = new AbortController(); const signal = abort.signal;
    let frame = null, catalog = null, selectedGroup = null, slotA = null, slotB = null, weight = "run_equal";
    let query = "", sort = "new", scope = "group", activeRun = null;
    let themeObserver = null, resizeObserver = null, chartWidth = 0, versionIndex = new Map();
    const highlighters = new Set();
    document.documentElement.classList.add("session-page");
    const loading = el("p", "Archivübersicht wird geladen …", "session-load-status"); loading.setAttribute("role", "status");
    host.replaceChildren(loading);
    function theme() { return document.body.dataset.mdColorScheme === "slate" ? "dark" : "light"; }
    function sendTheme() { if (frame?.contentWindow) frame.contentWindow.postMessage({ type: "records-explorer:theme", theme: theme() }, location.origin); }
    const runById = id => catalog.runs.find(r => r.id === id);

    function launch(a, b, reveal = true) {
      slotA = a; slotB = a ? b : null;
      const url = new URL(location.href);
      for (const [key, value] of [["a", slotA], ["b", slotB]]) value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
      history.replaceState(history.state, "", url);
      renderViewer(); drawList();
      if (reveal && slotA) {
        const target = viewerHeading || viewerHost;
        target.scrollIntoView({ block: "start", behavior: "instant" });
        if (viewerHeading) { viewerHeading.tabIndex = -1; viewerHeading.focus({ preventScroll: true }); }
      }
    }
    function renderViewer() {
      viewerHost.replaceChildren(); frame = null;
      if (!slotA) {
        viewerHost.append(el("p", "Noch keine Session gewählt. „Öffnen“ in der Liste oder ein Lauf im Verlauf lädt sie hier; „Als B vergleichen“ stellt eine zweite daneben.", "session-viewer-empty"));
        return;
      }
      const head = el("div", null, "session-viewer-head");
      const picked = el("p", null, "session-viewer-picked");
      picked.append(chip("A", "a"), el("span", " " + slotA));
      if (slotB) picked.append(el("span", "  "), chip("B", "b"), el("span", " " + slotB));
      const actions = el("div", null, "session-viewer-actions");
      const url = new URL(window.wiki.siteUrl("assets/records-explorer/index.html"));
      url.searchParams.set("a", slotA); if (slotB) url.searchParams.set("b", slotB);
      const full = el("a", "In voller Fenstergröße öffnen"); full.href = url.href; full.target = "_blank"; full.rel = "noopener";
      // Der gedrückte Knopf verschwindet beim Neuzeichnen; der Fokus geht an die Abschnittsüberschrift.
      const keepFocus = () => { if (viewerHeading) { viewerHeading.tabIndex = -1; viewerHeading.focus({ preventScroll: true }); } };
      if (slotB) actions.append(button("B entfernen", () => { launch(slotA, null, false); keepFocus(); }));
      actions.append(button("Ansicht schließen", () => { launch(null, null, false); keepFocus(); }), full);
      head.append(picked, actions); viewerHost.append(head);
      url.searchParams.set("theme", theme()); url.searchParams.set("embed", "1");
      frame = el("iframe"); frame.title = slotB ? "Records Explorer, Vergleich zweier Aufnahmen" : "Records Explorer";
      frame.src = url.href; frame.loading = "lazy"; frame.addEventListener("load", sendTheme, { signal });
      const box = el("div", null, "session-viewer"); box.append(frame); viewerHost.append(box);
    }
    function highlight(id) { activeRun = id; for (const fn of highlighters) fn(id); }

    /* Ein Diagramm = eine Spalte je Lauf in Startreihenfolge. kind: status | range | dot. */
    function chart({ title, headline, runs, kind, series, unit, baselines, describe }) {
      // wiki-chart liefert die Diagrammtöne des Wikis (hell und dunkel).
      const figure = el("figure", null, "session-trend wiki-chart"); figure.append(el("figcaption", title));
      if (headline) figure.append(el("p", headline, "session-headline"));
      const legend = el("p", null, "session-legend");
      for (const [, label, tone, shape] of series) {
        const item = el("span", null, "session-key"); const swatch = el("span", null, `session-swatch session-swatch--${shape || kind} session-tone--${tone}`);
        swatch.setAttribute("aria-hidden", "true"); item.append(swatch, document.createTextNode(label)); legend.append(item);
      }
      for (const [label, value, tone] of baselines) {
        if (!Number.isFinite(value)) continue;
        const item = el("span", null, "session-key session-key--baseline"); const swatch = el("span", null, `session-swatch session-swatch--baseline session-tone--${tone}`);
        swatch.setAttribute("aria-hidden", "true"); item.append(swatch, document.createTextNode(`${label}: ${withUnit(value, unit, 1)}`)); legend.append(item);
      }
      figure.append(legend);
      const rows = runs.filter(r => startTime(r) !== null);
      const values = rows.flatMap(r => series.map(([read]) => read(r))).filter(Number.isFinite);
      if (!rows.length || !values.length) { figure.append(el("p", "Für diese Kennzahl fehlen auswertbare Daten.", "session-empty")); return figure; }
      const W = Math.max(300, Math.min(1000, trendsHost.clientWidth)), H = 230, L = 46, R = 10, T = 24, B = 44;
      const slot = (W - L - R) / rows.length, X = i => L + slot * (i + .5);
      const top = unit === "%" ? 100 : niceMax(Math.max(...values, ...baselines.map(b => b[1]).filter(Number.isFinite)));
      const Y = v => H - B - v / top * (H - B - T);
      const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, tabindex: "0", role: "group",
        "aria-label": `${title}. ${rows.length} Läufe. Pfeiltasten wählen einen Lauf, Enter öffnet ihn im Explorer.` });
      for (let i = 0; i <= 4; i++) {
        const v = top * i / 4;
        plot.append(svg("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), class: i ? "session-grid" : "session-axis" }),
          svg("text", { x: L - 7, y: Y(v) + 4, "text-anchor": "end", class: "session-tick" }, num(v, 1) + (i === 4 ? " " + unit : "")));
      }
      // Tagesgruppen unter der Achse; Trennlinie zwischen Tagen.
      let dayStart = 0;
      rows.forEach((run, i) => {
        const day = dayOnly.format(new Date(startTime(run)));
        const next = rows[i + 1] ? dayOnly.format(new Date(startTime(rows[i + 1]))) : null;
        if (slot >= 34) plot.append(svg("text", { x: X(i), y: H - B + 15, "text-anchor": "middle", class: "session-tick" }, clockOnly.format(new Date(startTime(run)))));
        if (next !== day) {
          const mid = (X(dayStart) + X(i)) / 2;
          plot.append(svg("text", { x: mid, y: H - 8, "text-anchor": "middle", class: "session-day" }, day));
          if (next) plot.append(svg("line", { x1: L + slot * (i + 1), x2: L + slot * (i + 1), y1: T - 6, y2: H - 4, class: "session-daybreak" }));
          dayStart = i + 1;
        }
      });
      // Softwarestand: Marke am ersten Lauf jedes Stands.
      rows.forEach((run, i) => {
        const number = versionIndex.get(run.id), before = i ? versionIndex.get(rows[i - 1].id) : null;
        if (number === before) return;
        const mark = svg("g", { class: "session-version" });
        mark.append(svg("line", { x1: L + slot * i, x2: L + slot * i, y1: T - 4, y2: H - B }), svg("text", { x: L + slot * i + 3, y: T - 9 }, "V" + number));
        plot.append(mark);
      });
      const band = svg("rect", { y: T - 4, height: H - B - T + 4, width: slot, class: "session-band", visibility: "hidden" }); plot.append(band);
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
      for (const [, value, tone] of baselines) if (Number.isFinite(value)) plot.append(svg("line", { x1: L, x2: W - R, y1: Y(value), y2: Y(value), class: `session-baseline session-tone--${tone}` }));
      // Trefferflächen je Spalte; als Link, damit Mittelklick und „Link kopieren“ funktionieren.
      rows.forEach((run, i) => {
        const hit = svg("a", { href: "?a=" + encodeURIComponent(run.id), tabindex: "-1", "aria-hidden": "true" });
        hit.append(svg("rect", { x: L + slot * i, y: T - 4, width: slot, height: H - B - T + 4, class: "session-hit" }));
        hit.addEventListener("pointerenter", () => highlight(run.id));
        // Zensicals Link-Handler läuft auch bei defaultPrevented-Klicks.
        hit.addEventListener("click", e => { if (e.button || e.ctrlKey || e.metaKey || e.shiftKey) return; e.preventDefault(); e.stopPropagation(); launch(run.id, null); });
        plot.append(hit);
      });
      const readout = el("p", "Lauf überfahren oder Diagramm fokussieren und mit den Pfeiltasten wählen. Ein Klick oder Enter öffnet den Lauf im Explorer.", "session-point-readout");
      readout.setAttribute("aria-live", "polite");
      const show = id => {
        const i = rows.findIndex(r => r.id === id);
        if (i < 0) { band.setAttribute("visibility", "hidden"); return; }
        band.setAttribute("x", L + slot * i); band.setAttribute("visibility", "visible");
        const run = rows[i];
        readout.replaceChildren(el("strong", run.id), document.createTextNode(` · ${date(run.started_at_utc)} — ${describe(run)}. ${configText(run.config)} · Software V${versionIndex.get(run.id)}`));
      };
      highlighters.add(show); if (activeRun) show(activeRun);
      plot.addEventListener("focus", () => { if (!rows.some(r => r.id === activeRun)) highlight(rows[rows.length - 1].id); else show(activeRun); });
      plot.addEventListener("keydown", e => {
        const i = Math.max(0, rows.findIndex(r => r.id === activeRun));
        const next = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: rows.length - 1 }[e.key];
        if (next !== undefined) { e.preventDefault(); highlight(rows[Math.max(0, Math.min(rows.length - 1, next))].id); }
        else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); launch(rows[i].id, null); }
      });
      figure.append(plot, readout); return figure;
    }

    function drawOverview(group, runs) {
      const body = el("div", null, "session-overview");
      if (!group) { body.append(el("p", "Keine auswertbare Vergleichsgruppe vorhanden. Alle archivierten Dateien stehen unter „Sessions und Dateien“.", "session-empty")); return body; }
      const values = group[weight] || {}, equal = weight === "run_equal";
      const valid = runs.map(r => share(r, "valid")), range = spread(valid);
      const days = runs.map(startTime).filter(t => t !== null);
      const span = days.length ? `vom ${dayOnly.format(new Date(Math.min(...days)))} bis ${fmt({ day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(Math.max(...days)))}` : "ohne dokumentierten Start";
      const lead = el("p", null, "session-lead");
      lead.append(el("strong", `${group.session_count} ${group.test_run ? "Testläufe" : "Läufe"} ${span}`),
        document.createTextNode(`, zusammen ${num(group.frames, 0)} Frames. VALID ${equal ? "im Mittel der Läufe" : "über alle Frames"} ${withUnit((values.shares?.valid ?? NaN) * 100, "%", 1)}` +
          (range && runs.length > 1 ? `, je Lauf zwischen ${num(range.min, 0)} % und ${num(range.max, 0)} %.` : ".")));
      if (group.test_run) lead.append(" ", chip("Testläufe – nicht für Messungen verwenden", "test"));
      body.append(lead);
      const dl = el("dl", null, "session-metrics");
      const entries = [
        ["VALID-Anteil der Frames", (values.shares?.valid ?? (group.frames ? 0 : NaN)) * 100, "%"],
        [equal ? "Verarbeitung, Median der Läufe" : "Verarbeitung, Median aller Frames", values.processing_median_ms, "ms"],
        [equal ? "Verarbeitung p95, Median der Läufe" : "Verarbeitung p95 aller Frames", values.processing_p95_ms, "ms"],
        [equal ? "Konfidenzmedian VALID, Median der Läufe" : "Konfidenzmedian aller VALID", (values.confidence_median ?? NaN) * 100, "%"],
        [equal ? "Leserate, Mittel der Läufe" : "Leserate, Frames je Aufnahmedauer", values.rate_hz, "Hz"],
        ["Trackingverluste je 1.000 Frames", values.tracking_per_1000, ""],
      ];
      for (const [label, value, unit] of entries) { const div = el("div"); div.append(el("dt", label), el("dd", withUnit(value, unit, 1))); dl.append(div); }
      body.append(dl);
      return body;
    }

    function draw() {
      highlighters.clear();
      const group = catalog.groups.find(g => g.id === selectedGroup);
      const runs = group ? catalog.runs.filter(r => r.group === group.id).sort(chronological) : [];
      host.querySelector(".session-overview")?.remove();
      host.append(drawOverview(group, runs));
      trendsHost.replaceChildren();
      if (!group) { trendsHost.append(el("p", "Keine Vergleichsgruppe mit auswertbaren Läufen.", "session-empty")); drawList(); return; }
      const values = group[weight] || {}, total = weight === "run_equal" ? "Mittel der Läufe" : "alle Frames";
      versionIndex = new Map(); const versions = [];
      for (const run of runs) {
        const key = JSON.stringify(run.versions || {}); let index = versions.indexOf(key);
        if (index < 0) { versions.push(key); index = versions.length - 1; }
        versionIndex.set(run.id, index + 1);
      }
      const valid = spread(runs.map(r => share(r, "valid")));
      trendsHost.append(chart({
        title: "Statusanteile je Lauf", kind: "status", runs, unit: "%",
        headline: valid ? `VALID je Lauf ${num(valid.min, 0)} bis ${num(valid.max, 0)} %; gestrichelt der Gesamtwert (${total}).` : null,
        series: STATUS.map(([key, label, tone]) => [r => share(r, key), label, tone]),
        baselines: [["VALID gesamt", (values.shares?.valid ?? NaN) * 100, "good"]],
        describe: run => run.stats?.frames ? STATUS.map(([key, label]) => `${label} ${num(share(run, key), 1)} %`).join(" · ") : "keine auswertbaren Frames",
      }));
      const proc = spread(runs.map(r => r.stats?.processing_ms?.median)), p95 = spread(runs.map(r => r.stats?.processing_ms?.p95));
      trendsHost.append(chart({
        title: "Verarbeitungsdauer je Lauf", kind: "range", runs, unit: "ms",
        headline: proc && p95 ? `Median je Lauf ${num(proc.min, 1)} bis ${num(proc.max, 1)} ms, p95 bis ${num(p95.max, 1)} ms.` : null,
        series: [[r => r.stats?.processing_ms?.median, "Median", "series", "dot"], [r => r.stats?.processing_ms?.p95, "p95", "warning", "tick"]],
        baselines: [["Median gesamt", values.processing_median_ms, "series"], ["p95 gesamt", values.processing_p95_ms, "warning"]],
        describe: run => `Verarbeitung Median ${withUnit(run.stats?.processing_ms?.median, "ms")}, p95 ${withUnit(run.stats?.processing_ms?.p95, "ms")}`,
      }));
      const rate = spread(runs.map(r => r.stats?.rate_hz));
      trendsHost.append(chart({
        title: "Aufgezeichnete Datensätze pro Sekunde", kind: "dot", runs, unit: "Hz",
        headline: rate ? `Leserate je Lauf ${num(rate.min, 1)} bis ${num(rate.max, 1)} Hz.` : null,
        series: [[r => r.stats?.rate_hz, "Leserate", "series"]],
        baselines: [["Leserate gesamt", values.rate_hz, "series"]],
        describe: run => Number.isFinite(run.stats?.rate_hz) ? `Leserate ${withUnit(run.stats.rate_hz, "Hz")}` : "Leserate unbekannt (keine belastbare Aufnahmezeitbasis)",
      }));
      const note = el("div", null, "session-versions");
      note.append(el("p", versions.length === 1 ? "Alle Läufe dieser Gruppe haben denselben dokumentierten Softwarestand:" : `${versions.length} dokumentierte Softwarestände; die Marke V… steht am ersten Lauf jedes Stands:`));
      const list = el("ul"); versions.forEach((key, i) => list.append(el("li", `V${i + 1}: ${versionText(JSON.parse(key))}`))); note.append(list);
      note.append(el("p", "Ein Trend ist noch kein Nachweis einer Verbesserung der Messrichtigkeit."));
      trendsHost.append(note);
      drawList();
    }

    function drawList() {
      if (!catalog?.runs.length) return;
      const focused = listHost.contains(document.activeElement) ? document.activeElement : null;
      const restore = focused && { session: focused.closest("tr")?.dataset.session, text: focused.textContent, input: focused.matches("input, select") ? focused.className || focused.tagName : null };
      listHost.replaceChildren();
      const controls = el("div", null, "session-controls");
      const searchLabel = el("label", "Sessions durchsuchen"); const search = el("input"); search.type = "search"; search.value = query; search.className = "session-search";
      search.addEventListener("input", () => { query = search.value; drawList(); });
      searchLabel.append(search);
      const group = catalog.groups.find(g => g.id === selectedGroup);
      const scopeLabel = el("label", "Zeigen"); const scopeSelect = el("select"); scopeSelect.className = "session-scope";
      for (const [value, text] of [["group", `Gewählte Vergleichsgruppe (${catalog.runs.filter(r => r.group === selectedGroup).length})`], ["all", `Alle Sessions (${catalog.runs.length})`]]) {
        const option = el("option", text); option.value = value; scopeSelect.append(option);
      }
      if (!group) scope = "all";
      scopeSelect.value = scope; scopeSelect.disabled = !group;
      scopeSelect.addEventListener("change", () => { scope = scopeSelect.value; drawList(); }); scopeLabel.append(scopeSelect);
      const orderLabel = el("label", "Sortierung"); const order = el("select"); order.className = "session-order";
      for (const [value, text] of [["new", "Neueste zuerst"], ["old", "Älteste zuerst"], ["frames", "Meiste Frames zuerst"]]) { const option = el("option", text); option.value = value; order.append(option); }
      order.value = sort; order.addEventListener("change", () => { sort = order.value; drawList(); }); orderLabel.append(order);
      controls.append(searchLabel, scopeLabel, orderLabel); listHost.append(controls);
      const table = el("table", null, "session-table"); const head = el("thead"), hr = el("tr");
      ["Lauf", "Kennzahlen", "Dateien"].forEach(t => hr.append(el("th", t))); head.append(hr); table.append(head);
      const rows = el("tbody"); table.append(rows); listHost.append(table);
      const runs = catalog.runs.filter(r => scope === "all" || r.group === selectedGroup)
        .filter(r => (r.id + " " + (r.device_id ?? "") + " " + (r.test_run ? "Testlauf" : "") + " " + (r.warnings || []).join(" ")).toLowerCase().includes(query.toLowerCase()));
      runs.sort((a, b) => sort === "frames" ? (b.stats?.frames || 0) - (a.stats?.frames || 0) : chronological(a, b, sort !== "old"));
      for (const run of runs) {
        const tr = el("tr"); tr.dataset.session = run.id;
        if (run.id === slotA || run.id === slotB) tr.classList.add("session-row--picked");
        const name = el("td"); name.dataset.label = "Lauf";
        const title = el("p", null, "session-run-title");
        if (run.id === slotA) title.append(chip("A", "a"), " "); if (run.id === slotB) title.append(chip("B", "b"), " ");
        // Umbruch nur nach dem Schrägstrich, nicht mitten in der Kennung.
        const id = el("strong"); run.id.split("/").forEach((part, i) => { if (i) id.append("/", document.createElement("wbr")); id.append(part); });
        title.append(id); name.append(title, el("p", `${run.device_id ?? "Gerät unbekannt"} · ${date(run.started_at_utc)}`, "session-meta"));
        const flags = el("p", null, "session-flags");
        if (run.test_run) flags.append(chip("Testlauf – nicht für Messungen verwenden", "test"));
        for (const warning of run.warnings || []) flags.append(chip(window.SessionFiles.warning(warning), "warn"));
        if (flags.childNodes.length) name.append(flags);
        const stats = el("td"); stats.dataset.label = "Kennzahlen";
        const value = run.stats?.value?.median;
        stats.append(el("p", `${num(run.stats?.frames, 0)} Frames · VALID ${withUnit(share(run, "valid"), "%", 1)} · ${withUnit(run.stats?.rate_hz, "Hz")}`),
          el("p", `Verarbeitung ${num(run.stats?.processing_ms?.median, 1)} / ${num(run.stats?.processing_ms?.p95, 1)} ms (Median / p95)`, "session-meta"),
          el("p", Number.isFinite(value) ? `Messwertmedian VALID ${num(value, 6)} ${run.unit || ""}` : "kein VALID-Messwert", "session-meta"));
        if (run.stats?.invalid_lines) { const flag = el("p", null, "session-flags"); flag.append(chip(`${num(run.stats.invalid_lines, 0)} nicht auswertbare Zeilen`, "warn")); stats.append(flag); }
        const files = el("td"); files.dataset.label = "Dateien";
        const details = el("details", null, "session-files"), size = run.files.reduce((sum, f) => sum + (f.size || 0), 0);
        details.append(el("summary", `${run.files.length} Dateien · ${bytes(size)}`));
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
          details.append(item);
        }
        const manifest = el("a", "Manifest mit Prüfsummen"); manifest.href = window.SessionFiles.member(run.manifest); details.append(manifest);
        files.append(details, problem);
        const actions = el("p", null, "session-actions");
        const compare = button("Als B vergleichen", () => launch(slotA, run.id));
        compare.disabled = !slotA || slotA === run.id;
        compare.title = !slotA ? "Zuerst eine Session öffnen; sie wird A." : slotA === run.id ? "Diese Session ist schon A." : `Neben ${slotA} stellen`;
        actions.append(button("Öffnen", () => launch(run.id, null)), compare); name.append(actions);
        tr.append(name, stats, files); rows.append(tr);
      }
      if (!runs.length) { const row = el("tr"), cell = el("td", "Keine Sessions passen zur Suche."); cell.colSpan = 3; row.append(cell); rows.append(row); }
      if (restore?.input) { const again = listHost.querySelector("." + restore.input.split(" ")[0]); again?.focus(); if (again?.type === "search") again.setSelectionRange(again.value.length, again.value.length); }
      else if (restore?.session) [...listHost.querySelectorAll(`tr[data-session] button`)].find(b => b.closest("tr").dataset.session === restore.session && b.textContent === restore.text)?.focus();
    }

    window.SessionFiles.catalog(signal).then(data => {
      if (signal.aborted) return; catalog = data; host.setAttribute("aria-busy", "false");
      if (!data.runs.length) {
        const empty = el("div", null, "session-empty-state");
        empty.append(chip("Leer", "test"), el("p", "Noch keine Sessions im veröffentlichten Archiv. Ein Lauf erscheint hier, nachdem die Workbench beendet ist und das Wiki das nächste Mal veröffentlicht wird."));
        host.replaceChildren(empty);
        for (const node of [trendsHost, listHost]) node.replaceChildren(el("p", "Noch keine Daten.", "session-empty"));
        renderViewer(); return;
      }
      const newest = [...data.runs].filter(r => !r.test_run && r.stats?.frames > 0).sort((a, b) => chronological(a, b, true))[0];
      selectedGroup = newest?.group || data.groups[0]?.id;
      const controls = el("div", null, "session-controls");
      const groupLabel = el("label", "Vergleichsgruppe"), groupSelect = el("select");
      for (const group of data.groups) {
        const option = el("option", (group.test_run ? "Testläufe · " : "") + group.label + ` (${group.session_count})`); option.value = group.id; groupSelect.append(option);
      }
      const groupDetail = el("span", null, "session-hint");
      const describeGroup = () => { groupDetail.textContent = configText(data.groups.find(g => g.id === selectedGroup)?.config); };
      groupSelect.value = selectedGroup; groupSelect.addEventListener("change", () => { selectedGroup = groupSelect.value; scope = "group"; describeGroup(); draw(); });
      // Hinweis außerhalb des Labels, damit der zugängliche Name nur „Vergleichsgruppe“ bleibt.
      groupDetail.id = "session-group-hint"; groupSelect.setAttribute("aria-describedby", groupDetail.id);
      groupLabel.append(groupSelect); describeGroup();
      const groupField = el("div", null, "session-field"); groupField.append(groupLabel, groupDetail);
      const weightLabel = el("label", "Gewichtung"), weightSelect = el("select");
      for (const [value, text] of [["run_equal", "Jeder Lauf zählt gleich"], ["frame_weighted", "Alle Frames gemeinsam"]]) { const option = el("option", text); option.value = value; weightSelect.append(option); }
      const weightHint = el("span", null, "session-hint");
      const describeWeight = () => { weightHint.textContent = weight === "run_equal" ? "Mittel bzw. Median über die Läufe; kurze Läufe zählen wie lange." : "Addierte Frames und echte Quantile; lange Läufe wiegen mehr."; };
      weightSelect.addEventListener("change", () => { weight = weightSelect.value; describeWeight(); draw(); }); weightLabel.append(weightSelect); describeWeight();
      weightHint.id = "session-weight-hint"; weightSelect.setAttribute("aria-describedby", weightHint.id);
      const weightField = el("div", null, "session-field"); weightField.append(weightLabel, weightHint);
      controls.append(groupField, weightField);
      host.replaceChildren(controls);
      const params = new URLSearchParams(location.search); const ids = new Set(data.runs.map(r => r.id));
      slotA = ids.has(params.get("a")) ? params.get("a") : null; slotB = slotA && ids.has(params.get("b")) && params.get("b") !== slotA ? params.get("b") : null;
      draw(); renderViewer(); chartWidth = trendsHost.clientWidth;
      resizeObserver = new ResizeObserver(() => { if (Math.abs(trendsHost.clientWidth - chartWidth) > 2) { chartWidth = trendsHost.clientWidth; draw(); } });
      resizeObserver.observe(trendsHost);
      themeObserver = new MutationObserver(sendTheme); themeObserver.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
    }).catch(error => {
      if (signal.aborted) return;
      host.setAttribute("aria-busy", "false");
      const failed = el("div", null, "session-empty-state");
      failed.append(chip("Nicht geladen", "error"), el("p", `Die interaktive Archivansicht ist nicht verfügbar (${error.message}). Die Archivtabelle oben und ihre Downloads bleiben nutzbar; bei abgelaufener Anmeldung die Seite neu laden.`));
      host.replaceChildren(failed);
    });
    return () => { abort.abort(); themeObserver?.disconnect(); resizeObserver?.disconnect(); highlighters.clear(); if (frame) frame.src = "about:blank"; document.documentElement.classList.remove("session-page"); };
  });
})();
