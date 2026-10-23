/* Charts enhance their source tables; invalid plotted values leave them untouched. */
(function () {
  "use strict";

  const { onPage, make, hint } = window.wiki;
  const NS = "http://www.w3.org/2000/svg";
  const records = new WeakMap();
  let animePromise;

  function loadAnime() {
    if (window.anime?.animate) return Promise.resolve(window.anime);
    if (!animePromise) animePromise = new Promise((resolve) => {
      const script = make("script");
      script.src = window.wiki.siteUrl("assets/vendor/anime-4.5.0.umd.min.js");
      script.onload = () => resolve(window.anime?.animate ? window.anime : null);
      script.onerror = () => resolve(null);
      document.head.append(script);
    });
    return animePromise;
  }

  function parseNumber(text) {
    const value = text.trim().replace(/\s*%$/, "");
    if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+|\d{1,3}(?:[ \u00a0\u202f]\d{3})+)(?:,\d+)?$/.test(value)) return null;
    const number = Number(value.replace(/[. \u00a0\u202f]/g, "").replace(",", "."));
    return Number.isFinite(number) ? number : null;
  }

  function readTable(table, kind) {
    if (!["bar", "stacked"].includes(kind)) return null;
    const headers = Array.from(table.querySelectorAll("thead th"), (cell) => cell.textContent.trim());
    if (headers.length < 2) return null;
    const rows = [];
    for (const row of table.tBodies[0]?.rows || []) {
      const cells = Array.from(row.cells, (cell) => cell.textContent.trim());
      if (cells.length !== headers.length || !cells[0]) return null;
      const original = cells.slice(1);
      const values = (kind === "bar" ? original.slice(0, 1) : original).map(parseNumber);
      if (values.some((value) => value === null) || !Number.isFinite(values.reduce((a, b) => a + b, 0))) return null;
      if (kind === "stacked" && !values.some((value) => value > 0)) return null;
      rows.push({ label: cells[0], original, values });
    }
    if (!rows.length || !rows.some((row) => row.values.some((value) => value > 0))) return null;
    return { kind, headers, rows };
  }

  function chartRows(data, width, maximum = Math.max(...data.rows.map((row) => row.values[0]))) {
    return data.rows.map((row) => {
      const total = data.kind === "stacked" ? row.values.reduce((a, b) => a + b, 0) : maximum;
      let x = 0;
      return row.values.flatMap((value, index) => {
        if (data.kind === "stacked" && value === 0) return [];
        const segment = { x, width: value / total * width, value, index };
        x += segment.width;
        return [segment];
      });
    });
  }

  function svgNode(tag, attributes = {}, text) {
    const node = document.createElementNS(NS, tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function seriesRole(header) {
    switch (header) {
      case "VALID": return "good";
      case "TRANSITION": return "warning";
      case "UNREADABLE": return "critical";
      default: return "series";
    }
  }

  const format = (value) => value.toLocaleString("de-DE", { maximumFractionDigits: 3 });

  hint.register("chart", (node) => {
    const record = records.get(node);
    if (!record) return null;
    const content = make("div");
    content.append(make("strong", "", record.row.label));
    record.row.original.forEach((value, index) => {
      content.append(make("div", "", `${record.headers[index + 1]}: ${value}`));
    });
    return content;
  });

  function mount(host, table, data) {
    const title = host.dataset.title || data.headers[1];
    const unit = host.dataset.unit || "";
    const figure = make("figure", "wiki-chart-figure");
    figure.append(make("figcaption", "", title));
    if (data.kind === "stacked") {
      const legend = make("div", "wiki-chart-legend");
      data.headers.slice(1).forEach((header) => {
        const item = make("span");
        const key = make("i", `wiki-chart-key wiki-chart-color--${seriesRole(header)}`);
        key.setAttribute("aria-hidden", "true");
        item.append(key, document.createTextNode(header));
        legend.append(item);
      });
      figure.append(legend);
    }
    const svg = svgNode("svg", { role: "img", class: "wiki-chart-svg",
      "aria-label": `${data.kind === "bar" ? "Balkendiagramm" : "100-%-Stapeldiagramm"}: ${title}, ${data.rows.length} Kategorien` });
    figure.append(svg);
    // Zensical may wrap a table during page setup. Preserve those wrappers, too.
    let source = table;
    while (source.parentElement !== host) source = source.parentElement;
    const details = make("details", "wiki-chart-table");
    details.append(make("summary", "", "Werte als Tabelle"));
    source.before(figure, details);
    details.append(source);

    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const canvas = document.createElement("canvas").getContext("2d");
    let disposed = false;
    let seen = false;
    let revision = 0;
    let lastWidth = 0;
    let animation;
    let intersection;
    let targets = [];
    let frame;

    function finish() {
      animation?.revert();
      animation = null;
      targets.forEach((target) => target.removeAttribute("transform"));
    }

    function measure(text, className) {
      const sample = svgNode("text", { class: className });
      svg.append(sample);
      const style = getComputedStyle(sample);
      if (canvas) canvas.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const size = parseFloat(style.fontSize);
      sample.remove();
      return { width: (value) => canvas ? canvas.measureText(value).width : value.length * size * .6,
        line: size * 1.25 };
    }

    function wrap(text, width, metric) {
      const lines = [];
      let line = "";
      // Character fallback also wraps a single long category without overflow.
      for (const word of text.split(/\s+/)) {
        if (line && metric.width(`${line} ${word}`) > width) { lines.push(line); line = ""; }
        for (const char of (line ? ` ${word}` : word)) {
          if (line && metric.width(line + char) > width) { lines.push(line); line = ""; }
          line += char;
        }
      }
      if (line) lines.push(line);
      return lines;
    }

    function textLines(lines, x, y, metric, className) {
      const text = svgNode("text", { x, y, class: className });
      lines.forEach((line, index) => text.append(svgNode("tspan", { x, dy: index ? metric.line : 0 }, line)));
      svg.append(text);
    }

    function draw() {
      const width = host.getBoundingClientRect().width;
      if (disposed || width <= 0 || width === lastWidth) return;
      lastWidth = width;
      revision += 1;
      const active = document.activeElement;
      const focusIndex = svg.contains(active) ? Array.from(svg.querySelectorAll('[data-hint="chart"]')).indexOf(active) : -1;
      finish();
      svg.replaceChildren();
      targets = [];
      const category = measure("", "wiki-chart-category");
      const axis = measure("", "wiki-chart-axis-label");
      const valueMetric = measure("", "wiki-chart-value");
      const longest = Math.max(...data.rows.map((row) => category.width(row.label)));
      const left = Math.min(width * .4, longest + 12);
      const maximum = data.kind === "stacked" ? 100 : Math.max(...data.rows.map((row) => row.values[0]));
      const step = 10 ** Math.floor(Math.log10(maximum));
      const domain = data.kind === "stacked" ? 100 : Math.ceil(maximum / step) * step;
      const lastTick = `${format(domain)}${unit ? ` ${unit}` : ""}`;
      const right = Math.max(axis.width(lastTick), valueMetric.width(format(maximum)) + 6) + 4;
      const plot = Math.max(1, width - left - right);
      const rows = chartRows(data, plot, domain);
      const positions = [];
      let y = 4;
      data.rows.forEach((row) => {
        const labels = wrap(row.label, Math.max(1, left - 12), category);
        const note = data.kind === "bar" ? row.original.slice(1).map((value, index) => `${data.headers[index + 2]}: ${value}`).join(" · ") : "";
        const notes = note ? wrap(note, width - left - 4, axis) : [];
        const height = Math.max(18 + (notes.length ? 5 + notes.length * axis.line : 0), labels.length * category.line);
        positions.push({ y, labels, notes });
        y += height + 10;
      });
      const bottom = y - 10;
      svg.setAttribute("viewBox", `0 0 ${width} ${y + axis.line + 8}`);
      svg.setAttribute("width", width);
      svg.setAttribute("height", y + axis.line + 8);
      const divisions = data.kind === "bar" ? 3 : 4;
      for (let index = 0; index <= divisions; index += 1) {
        const x = left + plot * index / divisions;
        svg.append(svgNode("line", { x1: x, x2: x, y1: 1, y2: bottom,
          class: index ? "wiki-chart-grid" : "wiki-chart-axis" }));
        svg.append(svgNode("text", { x, y: y + axis.line, class: "wiki-chart-axis-label",
          "text-anchor": index === divisions ? "start" : index ? "middle" : "start" },
        index === divisions ? lastTick : format(domain * index / divisions)));
      }
      data.rows.forEach((row, rowIndex) => {
        const pos = positions[rowIndex];
        textLines(pos.labels, 0, pos.y + category.line * .8, category, "wiki-chart-category");
        if (pos.notes.length) textLines(pos.notes, left, pos.y + 23 + axis.line * .8, axis, "wiki-chart-note");
        rows[rowIndex].forEach((segment, segmentIndex, segments) => {
          const x = left + segment.x;
          const group = svgNode("g", { tabindex: "0", "data-hint": "chart",
            "aria-label": `${row.label}, ${data.headers[segment.index + 1]}: ${row.original[segment.index]}` });
          records.set(group, { row, headers: data.headers });
          // The hit target remains stationary while the mark grows.
          group.append(svgNode("rect", { x, y: pos.y - 3, width: Math.max(.01, segment.width), height: 24,
            class: "wiki-chart-hit" }));
          const growth = svgNode("g", { class: "wiki-chart-growth", style: `transform-origin: ${x}px ${pos.y}px` });
          const gap = data.kind === "stacked" && segmentIndex < segments.length - 1 ? Math.min(2, segment.width / 2) : 0;
          const w = Math.max(0, segment.width - gap);
          const radius = segmentIndex === segments.length - 1 ? Math.min(4, w / 2) : 0;
          const path = `M${x},${pos.y}h${w - radius}q${radius},0 ${radius},${radius}v${18 - radius * 2}q0,${radius} -${radius},${radius}h-${w - radius}z`;
          const role = data.kind === "bar" ? "series" : seriesRole(data.headers[segment.index + 1]);
          growth.append(svgNode("path", { d: path, class: `wiki-chart-mark wiki-chart-color--${role}` }));
          group.append(growth);
          targets.push(growth);
          if (data.kind === "bar") {
            group.append(svgNode("text", { x: x + segment.width + 6, y: pos.y + 13, class: "wiki-chart-value" }, format(segment.value)));
          } else {
            const label = `${format(segment.value)} %`;
            if (w >= 36 && valueMetric.width(label) + 8 <= w) group.append(svgNode("text", {
              x: x + w / 2, y: pos.y + 13, "text-anchor": "middle",
              class: `wiki-chart-value wiki-chart-value--inside${role === "warning" ? " wiki-chart-value--warning" : ""}`,
            }, label));
          }
          svg.append(group);
        });
      });
      if (focusIndex >= 0) svg.querySelectorAll('[data-hint="chart"]')[focusIndex]?.focus();
    }

    async function reveal() {
      if (disposed || seen) return;
      seen = true;
      intersection?.disconnect();
      if (motion.matches) return;
      const version = revision;
      const anime = await loadAnime();
      if (disposed || motion.matches || !anime || version !== revision) return;
      try {
        animation = anime.animate(targets, { scaleX: [0, 1], duration: 420, delay: anime.stagger(60), ease: "outExpo" });
      } catch { finish(); }
    }

    draw();
    const resize = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(draw);
    }) : null;
    resize?.observe(host);
    if (typeof IntersectionObserver !== "undefined") {
      intersection = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) reveal();
      });
      intersection.observe(figure);
    }
    function motionChanged() { if (motion.matches) finish(); }
    motion.addEventListener("change", motionChanged);
    if (document.fonts) document.fonts.ready.then(() => {
      if (!disposed) { lastWidth = 0; draw(); }
    });
    return () => {
      disposed = true;
      revision += 1;
      cancelAnimationFrame(frame);
      resize?.disconnect();
      intersection?.disconnect();
      motion.removeEventListener("change", motionChanged);
      finish();
      details.before(source);
      details.remove();
      figure.remove();
    };
  }

  onPage((article) => {
    const cleanups = [];
    for (const host of article.querySelectorAll(".wiki-chart")) {
      const table = host.querySelector("table");
      const data = table && readTable(table, host.dataset.chart);
      if (data) cleanups.push(mount(host, table, data));
    }
    return () => cleanups.forEach((cleanup) => cleanup());
  });
})();
