/* Prepared statistics only; raw records are loaded solely by the selected explorer. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const labels = { valid: "VALID", transition: "TRANSITION", unreadable: "UNREADABLE", stale: "STALE" };
  const num = (v, digits = 2) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("de-DE", { maximumFractionDigits: digits }) : "—";
  const date = value => {
    if (typeof value !== "string" || !value.trim()) return "Zeit unbekannt";
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? new Intl.DateTimeFormat("de-DE", { timeZone: "UTC", dateStyle: "short", timeStyle: "short" }).format(d) + " UTC" : "Zeit unbekannt";
  };
  const startTime = run => typeof run.started_at_utc === "string" && run.started_at_utc.trim() && Number.isFinite(Date.parse(run.started_at_utc)) ? Date.parse(run.started_at_utc) : null;
  function chronological(a, b, newest = false) {
    const left = startTime(a), right = startTime(b);
    if (left === null || right === null) return left === null ? (right === null ? a.id.localeCompare(b.id) : 1) : -1;
    return newest ? right - left : left - right;
  }
  function el(tag, text, cls) {
    const node = document.createElement(tag); if (text != null) node.textContent = text; if (cls) node.className = cls; return node;
  }
  function button(text, callback) { const b = el("button", text); b.type = "button"; b.addEventListener("click", callback); return b; }
  function svg(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; return n;
  }
  const metric = (run, key) => key.startsWith("share:") ? (run.stats?.frames ? (run.stats.counts[key.slice(6)] || 0) / run.stats.frames * 100 : null) :
    key === "proc" ? run.stats?.processing_ms?.median : key === "p95" ? run.stats?.processing_ms?.p95 : run.stats?.rate_hz;

  window.wiki.onPage(function sessionsPage(article) {
    const host = article.querySelector("#session-dashboard"); if (!host) return;
    const abort = new AbortController(); const signal = abort.signal;
    let frame = null, catalog = null, selectedGroup = null, slotA = null, slotB = null, weight = "run_equal", query = "", sort = "new";
    let themeObserver = null, resizeObserver = null, chartWidth = 0;
    document.documentElement.classList.add("session-page");
    const status = el("p", "Archivübersicht wird geladen …", "session-load-status"); host.append(status);
    function tell(text) { status.textContent = text; status.setAttribute("role", "status"); }
    function theme() { return document.body.dataset.mdColorScheme === "slate" ? "dark" : "light"; }
    function sendTheme() { if (frame?.contentWindow) frame.contentWindow.postMessage({ type: "records-explorer:theme", theme: theme() }, location.origin); }
    function launch(a, b) {
      slotA = a; slotB = b;
      const url = new URL(location.href); if (a) url.searchParams.set("a", a); else url.searchParams.delete("a");
      if (b) url.searchParams.set("b", b); else url.searchParams.delete("b"); history.replaceState(null, "", url);
      renderViewer();
    }
    const viewer = el("section", null, "session-viewer"); viewer.hidden = true;
    function renderViewer() {
      viewer.replaceChildren(); viewer.hidden = !slotA; frame = null;
      if (!slotA) return;
      viewer.append(el("h2", "Einzelne Frames untersuchen"));
      const url = new URL(window.wiki.siteUrl("assets/records-explorer/index.html"));
      url.searchParams.set("a", slotA); if (slotB) url.searchParams.set("b", slotB); url.searchParams.set("theme", theme());
      const full = el("a", "In voller Fenstergröße öffnen"); full.href = url.href; full.target = "_blank"; full.rel = "noopener";
      viewer.append(full);
      frame = el("iframe"); frame.title = slotB ? "Session-Explorer, Vergleich zweier Aufnahmen" : "Session-Explorer";
      frame.src = url.href; frame.loading = "lazy"; frame.addEventListener("load", sendTheme, { signal }); viewer.append(frame);
    }
    function chart(title, runs, series, unit, baselines) {
      const figure = el("figure", null, "session-trend"); figure.append(el("figcaption", title));
      const readout = el("p", "Datenpunkt berühren oder mit Tab fokussieren: Kennzahl, Einstellungen und Softwarestand. Enter öffnet den Lauf.", "session-point-readout");
      readout.setAttribute("role", "status");
      const legend = el("p", null, "session-legend");
      if (series[0][0].startsWith("share:")) figure.classList.add("session-status");
      series.forEach(([key, label], i) => { const item = el("span", label, "session-series-" + i); item.dataset.series = String(i); legend.append(item); }); figure.append(legend);
      const rows = runs.filter(r => typeof r.started_at_utc === "string" && r.started_at_utc.trim() && Number.isFinite(new Date(r.started_at_utc).getTime()));
      const points = series.flatMap(([key]) => rows.map(r => metric(r, key))).filter(v => Number.isFinite(v));
      if (!rows.length || !points.length) { figure.append(el("p", "Für diese Kennzahl fehlen auswertbare Daten.")); return figure; }
      const W = Math.max(300, Math.min(1000, host.clientWidth)), H = 250, L = 56, R = 16, T = 22, B = 42;
      const times = rows.map(r => new Date(r.started_at_utc).getTime());
      const lo = Math.min(...times), hi = Math.max(...times), maximum = unit === "%" ? 100 : Math.max(1, ...points) * 1.1;
      const x = t => hi === lo ? W / 2 : L + (t - lo) / (hi - lo) * (W - L - R);
      const y = v => H - B - v / maximum * (H - B - T);
      const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title + ". Jeder Punkt öffnet die zugehörige Session." });
      for (let i = 0; i <= 4; i++) {
        const v = maximum * i / 4;
        plot.append(svg("line", { x1: L, y1: y(v), x2: W - R, y2: y(v), class: "session-grid" }), svg("text", { x: L - 9, y: y(v) + 4, "text-anchor": "end" }, num(v, 1) + (i === 4 ? " " + unit : "")));
      }
      [0, 1].forEach(edge => {
        const time = new Date(edge ? hi : lo);
        const text = W < 560 ? new Intl.DateTimeFormat("de-DE", { timeZone: "UTC", day: "2-digit", month: "2-digit" }).format(time) : date(time.toISOString());
        plot.append(svg("text", { x: edge ? W - R : L, y: H - 10, "text-anchor": edge ? "end" : "start" }, text));
      });
      let priorVersion = null, versionNumber = 0;
      for (const run of rows) {
        const version = JSON.stringify(run.versions || {});
        if (version === priorVersion) continue;
        priorVersion = version; versionNumber++;
        const X = x(new Date(run.started_at_utc).getTime());
        const mark = svg("g", { class: "session-version", "aria-label": "Versionsstand " + versionNumber + ": " + version });
        mark.append(svg("line", { x1: X, x2: X, y1: T, y2: H - B }), svg("text", { x: X, y: T - 7, "text-anchor": "middle" }, "V" + versionNumber), svg("title", {}, version));
        plot.append(mark);
      }
      series.forEach(([key, label], index) => {
        let path = "", connected = false;
        for (const run of rows) {
          const value = metric(run, key);
          if (!Number.isFinite(value)) { connected = false; continue; }
          const X = x(new Date(run.started_at_utc).getTime()), Y = y(value);
          path += `${connected ? "L" : "M"}${X},${Y} `; connected = true;
          const a = svg("a", { href: "?a=" + encodeURIComponent(run.id), tabindex: "0", "aria-label": `${run.id}, ${date(run.started_at_utc)}, ${label}: ${num(value)} ${unit}` });
          a.append(svg("circle", { cx: X, cy: Y, r: 5, class: `session-point session-series-${index}` }));
          a.append(svg("title", {}, `${run.id}\n${date(run.started_at_utc)}\n${label}: ${num(value)} ${unit}\nVersionen: ${JSON.stringify(run.versions || {})}\n${JSON.stringify(run.config || {})}`));
          const describe = () => {
            const config = run.config || {}, camera = config.camera || {};
            readout.textContent = `${run.id} · ${date(run.started_at_utc)} · ${label}: ${num(value)} ${unit}. Toleranz ${config.tolerance ?? "unbekannt"}; ${config.confirm_frames ?? "unbekannt"} Bestätigungen; Kamera ${Array.isArray(camera.size) ? camera.size.join("×") : "Größe unbekannt"}, ${camera.fps ?? "unbekannt"} Hz. Software: ${Object.entries(run.versions || {}).map(([name, version]) => name + ": " + (Array.isArray(version) ? version.join(", ") : String(version))).join("; ") || "unbekannt"}.`;
          };
          a.addEventListener("focus", describe); a.addEventListener("pointerenter", describe);
          // Zensical's body link handler also runs on defaultPrevented clicks.
          const open = e => { e.preventDefault(); e.stopPropagation(); launch(run.id, null); viewer.scrollIntoView({ block: "start", behavior: "instant" }); };
          a.addEventListener("click", open);
          a.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") open(e); });
          plot.append(a);
        }
        plot.prepend(svg("path", { d: path, fill: "none", class: `session-line session-series-${index}` }));
        const baseline = baselines[index];
        if (Number.isFinite(baseline)) {
          const line = svg("line", { x1: L, x2: W - R, y1: y(baseline), y2: y(baseline), class: `session-baseline session-series-${index}` });
          line.append(svg("title", {}, `${label}, Gesamtwert: ${num(baseline)} ${unit}`)); plot.append(line);
          legend.append(el("span", `${label} gesamt: ${num(baseline)} ${unit} (gestrichelt)`));
        }
      });
      figure.append(plot, readout); return figure;
    }
    function draw() {
      const group = catalog.groups.find(g => g.id === selectedGroup);
      const body = host.querySelector(".session-body"); body.replaceChildren();
      if (!group) { body.append(el("p", "Keine auswertbare Vergleichsgruppe vorhanden. Alle archivierten Dateien stehen unten.")); }
      else {
        const values = group[weight] || {};
        const section = el("section"); section.append(el("h2", "Gesamtübersicht"));
        section.append(el("p", `${group.session_count} Läufe · ${num(group.frames, 0)} Frames · ${group.test_run ? "Testläufe, nicht für Messungen verwenden" : "reguläre Läufe"}`));
        const equal = weight === "run_equal", dl = el("dl", null, "session-metrics");
        const entries = [
          ["VALID, Frameanteil", (values.shares?.valid ?? (group.frames ? 0 : NaN)) * 100, "%"],
          [equal ? "Median der Verarbeitungsmediane" : "Verarbeitung, Median aller Frames", values.processing_median_ms, "ms"],
          [equal ? "Median der Session-p95" : "Verarbeitung, p95 aller Frames", values.processing_p95_ms, "ms"],
          [equal ? "Median der Konfidenzmediane (VALID)" : "Konfidenzmedian aller VALID", (values.confidence_median ?? NaN) * 100, "%"],
          [equal ? "Mittlere Leserate der Sessions" : "Leserate, Frames / Aufnahmedauer", values.rate_hz, "Hz"],
          ["Trackingverluste / 1.000 Frames", values.tracking_per_1000, ""],
        ];
        for (const [label, value, unit] of entries) { const div = el("div"); div.append(el("dt", label), el("dd", num(value) + (Number.isFinite(value) ? " " + unit : ""))); dl.append(div); }
        section.append(dl); body.append(section);
        const runs = catalog.runs.filter(r => r.group === group.id).sort(chronological);
        const trends = el("section"); trends.append(el("h2", "Entwicklung der Messläufe"), el("p", "Kalenderachse: dokumentierter Session-Start (UTC). Punkte öffnen den Lauf; gestrichelte Linien zeigen den Gesamtwert der gewählten Gewichtung."));
        trends.append(chart("Statusanteile je Session", runs, Object.entries(labels).map(([k, v]) => ["share:" + k, v]), "%", Object.keys(labels).map(k => (values.shares?.[k] ?? (group.frames ? 0 : NaN)) * 100)));
        trends.append(chart("Verarbeitungsdauer je Session", runs, [["proc", "Median"], ["p95", "p95"]], "ms", [values.processing_median_ms, values.processing_p95_ms]));
        trends.append(chart("Aufgezeichnete Datensätze pro Sekunde", runs, [["rate", "Leserate"]], "Hz", [values.rate_hz]));
        const versions = [...new Set(runs.map(r => JSON.stringify(r.versions || {})))];
        trends.append(el("p", `${versions.length} dokumentierte Versionsstände. Version und Einstellungen stehen am jeweiligen Datenpunkt; ein Trend ist noch kein Nachweis einer Verbesserung der Messrichtigkeit.`));
        body.append(trends);
      }
      drawList(body);
    }
    function drawList(body) {
      const section = el("section"); section.append(el("h2", "Sessions und Dateien"));
      const controls = el("div", null, "session-controls");
      const searchLabel = el("label", "Sessions durchsuchen "); const search = el("input"); search.type = "search"; search.value = query;
      searchLabel.append(search); controls.append(searchLabel);
      const orderLabel = el("label", "Sortierung "); const order = el("select");
      for (const [value, text] of [["new", "Neueste zuerst"], ["old", "Älteste zuerst"], ["frames", "Meiste Frames zuerst"]]) { const option = el("option", text); option.value = value; order.append(option); }
      order.value = sort; orderLabel.append(order); controls.append(orderLabel); section.append(controls);
      const table = el("table", null, "session-table"); const head = el("thead"), hr = el("tr");
      ["Session / Gerät", "Statistik", "Dateien", "Untersuchen"].forEach(t => hr.append(el("th", t))); head.append(hr); table.append(head);
      const rows = el("tbody"); table.append(rows); section.append(table);
      function list() {
        rows.replaceChildren();
        const runs = catalog.runs.filter(r => (r.id + " " + r.device_id + " " + (r.test_run ? "Testlauf" : "") + " " + (r.warnings || []).join(" ")).toLowerCase().includes(query.toLowerCase()));
        runs.sort((a, b) => sort === "frames" ? (b.stats?.frames || 0) - (a.stats?.frames || 0) : chronological(a, b, sort !== "old"));
        for (const run of runs) {
          const tr = el("tr"); tr.dataset.session = run.id;
          const name = el("td"); name.dataset.label = "Session"; name.append(el("strong", run.id), el("p", `${run.device_id} · ${date(run.started_at_utc)}`));
          if (run.test_run) name.append(el("p", "Testlauf – nicht für Messungen verwenden", "session-warning"));
          for (const warning of run.warnings || []) name.append(el("p", window.SessionFiles.warning(warning), "session-warning"));
          const stats = el("td"); stats.dataset.label = "Statistik";
          stats.append(el("p", `${num(run.stats?.frames, 0)} Frames · ${num(run.stats?.rate_hz)} Hz`), el("p", `Verarbeitung: Median ${num(run.stats?.processing_ms?.median)} ms · p95 ${num(run.stats?.processing_ms?.p95)} ms`), el("p", `Messwertmedian (VALID): ${num(run.stats?.value?.median, 6)} ${run.unit || ""}`));
          if (run.stats?.invalid_lines) stats.append(el("p", `${num(run.stats.invalid_lines, 0)} nicht auswertbare Zeilen`, "session-warning"));
          const files = el("td"); files.dataset.label = "Dateien";
          const details = el("details"), summary = el("summary", `${run.files.length} Dateien anzeigen`); details.append(summary);
          for (const entry of run.files) {
            const item = el("div", null, "session-file"); item.append(el("span", `${entry.name} · ${num(entry.size / 1024, 1)} KiB `));
            const download = button("Original herunterladen", async () => {
              download.disabled = true;
              try { const m = await window.SessionFiles.manifest(run, signal); const file = m.files.find(f => f.name === entry.name); if (!file) throw new Error("Datei fehlt im Manifest."); await window.SessionFiles.download(file, signal); }
              catch (error) { tell(error.message); } finally { download.disabled = false; }
            }); item.append(download);
            for (const [i, part] of entry.parts.entries()) { const link = el("a", `gzip-Teil ${i + 1}`); try { link.href = window.SessionFiles.member(part.path); } catch { continue; } link.download = ""; item.append(link); }
            details.append(item);
          }
          const manifest = el("a", "Manifest"); manifest.href = window.SessionFiles.member(run.manifest); details.append(manifest); files.append(details);
          const actions = el("td"); actions.dataset.label = "Untersuchen";
          actions.append(button("Öffnen", () => launch(run.id, null)), button("Als B vergleichen", () => {
            if (!slotA) { launch(run.id, null); tell("Aufnahme A gewählt. Jetzt eine weitere Session als B wählen."); } else launch(slotA, run.id);
          })); tr.append(name, stats, files, actions); rows.append(tr);
        }
        if (!runs.length) { const row = el("tr"), cell = el("td", "Keine Sessions passen zur Suche."); cell.colSpan = 4; row.append(cell); rows.append(row); }
      }
      search.addEventListener("input", () => { query = search.value; list(); }); order.addEventListener("change", () => { sort = order.value; list(); }); list(); body.append(section);
    }
    window.SessionFiles.catalog(signal).then(data => {
      if (signal.aborted) return; catalog = data; host.setAttribute("aria-busy", "false");
      if (!data.runs.length) { tell("Noch keine Sessions im veröffentlichten Archiv."); return; }
      const newest = [...data.runs].filter(r => !r.test_run && r.stats?.frames > 0).sort((a, b) => chronological(a, b, true))[0];
      selectedGroup = newest?.group || data.groups[0]?.id;
      tell(`Archivstand: ${date(data.generated_at)} · ${data.runs.length} Sessions. Angezeigt wird ausschließlich der veröffentlichte Stand.`);
      const controls = el("div", null, "session-controls"); const groupLabel = el("label", "Vergleichsgruppe "), groupSelect = el("select");
      for (const group of data.groups) {
        const config = group.config || {}, camera = config.camera || {};
        const tolerance = config.tolerance == null ? "unbekannt" : typeof config.tolerance === "number" ? "×" + num(config.tolerance) : String(config.tolerance);
        const detail = `${config.reader_family || "Leser unbekannt"} · Toleranz ${tolerance} · ${config.confirm_frames || "?"} Bestätigungen · ${Array.isArray(camera.size) ? camera.size.join("×") : "Größe unbekannt"} / ${camera.fps || "?"} Hz`;
        const option = el("option", (group.test_run ? "Testläufe · " : "") + group.label + " · " + detail); option.value = group.id; groupSelect.append(option);
      }
      groupSelect.value = selectedGroup; groupSelect.addEventListener("change", () => { selectedGroup = groupSelect.value; draw(); }); groupLabel.append(groupSelect);
      const weightLabel = el("label", "Gewichtung "), weightSelect = el("select");
      for (const [value, text] of [["run_equal", "Jeder Lauf zählt gleich"], ["frame_weighted", "Alle Frames gemeinsam"]]) { const option = el("option", text); option.value = value; weightSelect.append(option); }
      weightSelect.addEventListener("change", () => { weight = weightSelect.value; draw(); }); weightLabel.append(weightSelect); controls.append(groupLabel, weightLabel);
      host.append(controls, el("div", null, "session-body"), viewer);
      const params = new URLSearchParams(location.search); const ids = new Set(data.runs.map(r => r.id));
      slotA = ids.has(params.get("a")) ? params.get("a") : null; slotB = slotA && ids.has(params.get("b")) ? params.get("b") : null;
      draw(); renderViewer(); chartWidth = host.clientWidth;
      resizeObserver = new ResizeObserver(() => { if (Math.abs(host.clientWidth - chartWidth) > 2) { chartWidth = host.clientWidth; draw(); } });
      resizeObserver.observe(host);
      themeObserver = new MutationObserver(sendTheme); themeObserver.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
    }).catch(error => { if (!signal.aborted) { host.setAttribute("aria-busy", "false"); tell("Interaktive Archivansicht nicht verfügbar. Die Tabellen und Downloads darüber bleiben nutzbar. " + error.message); } });
    return () => { abort.abort(); themeObserver?.disconnect(); resizeObserver?.disconnect(); if (frame) frame.src = "about:blank"; document.documentElement.classList.remove("session-page"); };
  });
})();
