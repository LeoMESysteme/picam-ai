/* Spatial roadmap. The Markdown tables are the source and the no-JS view.
 * A phase contains a second map: the phase's outline becomes its boundary.
 * Anime.js is the same local v4 runtime used by the project tour. */
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const SCRIPT = document.currentScript ? document.currentScript.src : document.baseURI;
  const ANIME_URL = new URL("vendor/anime-4.5.0.umd.min.js", SCRIPT).href;
  const STORAGE = "dispread.roadmap.layout.v1";
  const WIDTH = 300;
  const STEP_WIDTH = 270;
  const POSITIONS = [[0, 80], [355, 0], [710, 70], [1065, 30], [1100, 370],
    [970, 680], [610, 650], [250, 675], [-100, 660]];
  const PHASE_STATE = { erreicht: "done", teilweise: "partial", blockiert: "blocked", offen: "open" };
  const STEP_STATE = { gebaut: "done", belegt: "done", vorhanden: "done", offen: "open", blockiert: "blocked", ruht: "quiet" };
  const ICONS = {
    back: "M15 18l-6-6 6-6M9 12h12",
    plus: "M12 5v14M5 12h14",
    minus: "M5 12h14",
    fit: "M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5M8 8h8v8H8z",
    full: "M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5",
    reset: "M3 11a9 9 0 1 1 2.5 7M3 4v7h7",
    table: "M3 4h18v16H3zM3 9h18M9 9v11",
    map: "M3 5l6-2 6 2 6-2v16l-6 2-6-2-6 2zM9 3v16M15 5v16",
    grip: "M8 5h.01M16 5h.01M8 12h.01M16 12h.01M8 19h.01M16 19h.01",
    search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
    link: "M14 3h7v7M21 3L10 14M10 3H3v18h18v-7",
    layers: "M3 8l9-5 9 5-9 5zM3 12l9 5 9-5M3 16l9 5 9-5",
  };
  let animePromise = null;
  let active = null;

  const clamp = (n, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, n));
  const mix = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, n) => { const t = clamp((n - a) / (b - a)); return t * t * (3 - 2 * t); };
  const make = (tag, name, text) => {
    const el = document.createElement(tag);
    if (name) el.className = name;
    if (text !== undefined) el.textContent = text;
    return el;
  };
  function svg(tag, attrs, parent) {
    const el = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) el.setAttribute(key, String(value));
    if (parent) parent.append(el);
    return el;
  }
  function icon(name) {
    const el = svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": name === "grip" ? 3 : 1.6,
      "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
    svg("path", { d: ICONS[name] }, el);
    return el;
  }
  function button(label, name, callback, className = "roadmap-control") {
    const el = make("button", className);
    el.type = "button";
    el.setAttribute("aria-label", label);
    el.title = label;
    el.append(icon(name));
    if (callback) el.addEventListener("click", callback);
    return el;
  }
  function copyContent(target, source) {
    for (const child of source.childNodes) target.append(child.cloneNode(true));
  }
  function oqText(target, text) {
    let end = 0;
    for (const match of text.matchAll(/\bOQ-\d+\b/g)) {
      target.append(document.createTextNode(text.slice(end, match.index)));
      const link = make("a", "", match[0]);
      link.href = `open-questions.html#oq-${match[0].slice(3)}`;
      target.append(link);
      end = match.index + match[0].length;
    }
    target.append(document.createTextNode(text.slice(end)));
  }
  function loadAnime() {
    if (window.anime && window.anime.createTimeline) return Promise.resolve(window.anime);
    if (!animePromise) animePromise = new Promise((resolve) => {
      const script = make("script");
      script.src = ANIME_URL;
      script.onload = () => resolve(window.anime && window.anime.createTimeline ? window.anime : null);
      script.onerror = () => resolve(null);
      document.head.append(script);
    });
    return animePromise;
  }
  function readData(article) {
    const table = article.querySelector("table");
    const stepSource = article.querySelector(".roadmap-steps-source");
    if (!table || !stepSource) return null;
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    if (rows.length !== 9 || rows.some((row, i) => row.cells.length !== 6 || row.cells[0].textContent.trim() !== `P${i}`)) return null;
    const phases = rows.map((row) => {
      const c = row.cells;
      const found = c[5].textContent.match(/\b(erreicht|teilweise|blockiert|offen)\b/i);
      if (!found) return null;
      return { id: c[0].textContent.trim(), title: c[1].textContent.trim(), titleCell: c[1],
        camera: c[2].textContent.trim(), gsv: c[3].textContent.trim(), exitCell: c[4],
        note: c[5].textContent.trim(), state: found[1].toLocaleLowerCase("de"), steps: [] };
    });
    if (phases.some((p) => !p)) return null;
    const ids = new Set();
    const stepRows = Array.from(stepSource.querySelectorAll("tbody tr"));
    if (!stepRows.length) return null;
    for (const row of stepRows) {
      const c = row.cells;
      if (c.length !== 6) return null;
      const phase = phases.find((p) => p.id === c[0].textContent.trim());
      const id = c[1].textContent.trim();
      const state = c[3].textContent.trim();
      const rawDate = c[4].textContent.trim();
      const date = rawDate === "—" || rawDate === "" ? null : rawDate;
      if (!phase || !new RegExp(`^${phase.id.toLowerCase()}-[a-z0-9-]+$`).test(id) || ids.has(id) || !STEP_STATE[state]) return null;
      if (date && (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date)) return null;
      if (!c[2].textContent.trim() || !c[5].querySelector("a[href]")) return null;
      ids.add(id);
      phase.steps.push({ id, title: c[2].textContent.trim(), titleCell: c[2], state, date, evidence: c[5] });
    }
    if (phases.some((p) => !p.steps.length)) return null;
    return { table, stepSource, phases };
  }
  function storedLayout() {
    try {
      const data = JSON.parse(window.localStorage.getItem(STORAGE));
      if (data && data.version === 1 && data.positions && typeof data.positions === "object") return data.positions;
    } catch (_) { /* A map is usable without browser storage. */ }
    return {};
  }
  function validPosition(value) {
    return value && Number.isFinite(value.x) && Number.isFinite(value.y) && Math.abs(value.x) < 50000 && Math.abs(value.y) < 50000;
  }

  class Roadmap {
    constructor(article, data) {
      this.article = article;
      this.data = data;
      this.phases = data.phases;
      this.abort = new AbortController();
      this.saved = storedLayout();
      this.positions = { overview: {}, steps: {} };
      this.nodes = new Map();
      this.stepNodes = new Map();
      this.camera = { x: 0, y: 0, z: 1 };
      this.innerCamera = { x: 0, y: 0, z: 1 };
      this.progress = 0;
      this.phase = null;
      this.pointers = new Map();
      this.reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.reduced = this.reducedQuery.matches;
      this.root = make("section", "roadmap");
      this.root.dataset.roadmap = "";
      this.root.dataset.roadmapView = "overview";
      this.root.setAttribute("aria-label", "Interaktive Roadmap");
      this.build();
      article.querySelector("h1#roadmap").after(this.root);
      data.table.id = "roadmap-phases";
      data.table.dataset.enhanced = "true";
      this.sourceHeading = article.querySelector("#roadmap-schritte");
      this.sourceIntro = this.sourceHeading && this.sourceHeading.nextElementSibling;
      this.sources = [data.table, data.stepSource, this.sourceHeading, this.sourceIntro].filter(Boolean);
      this.sources.forEach((source) => { source.hidden = true; });
      const lead = this.root.nextElementSibling;
      if (lead && lead.tagName === "P") {
        this.note = make("details", "roadmap-about");
        this.note.append(make("summary", "", "Einordnung und Reihenfolge"));
        lead.before(this.note);
        this.note.append(lead);
      }
      document.body.classList.add("roadmap-page");
      this.bind();
      this.resize();
      this.observer = new ResizeObserver(() => this.resize());
      this.observer.observe(this.viewport);
      loadAnime().then((A) => {
        if (this.disposed) return;
        this.A = A;
        if (this.phase) { this.makeReveal(); this.render(); }
      });
    }

    listen(target, event, handler, options = {}) {
      target.addEventListener(event, handler, { ...options, signal: this.abort.signal });
    }

    build() {
      const header = make("div", "roadmap-header");
      this.breadcrumb = make("nav", "roadmap-breadcrumb");
      this.breadcrumb.setAttribute("aria-label", "Kartenebene");
      this.back = button("Zur Roadmap", "back", () => this.exit());
      this.back.hidden = true;
      this.crumb = make("span", "roadmap-location", "Meilensteine");
      this.breadcrumb.append(this.back, this.crumb);
      const searchWrap = make("div", "roadmap-search-wrap");
      searchWrap.append(icon("search"));
      this.search = make("input", "roadmap-search");
      this.search.type = "search";
      this.search.placeholder = "Meilenstein suchen";
      this.search.setAttribute("aria-label", "Meilenstein suchen");
      this.searchState = make("span", "roadmap-search-state");
      this.searchState.hidden = true;
      this.searchState.setAttribute("role", "status");
      this.searchState.setAttribute("aria-label", "Suchergebnis");
      searchWrap.append(this.search, this.searchState);
      const views = make("div", "roadmap-views");
      this.mapButton = button("Kartenansicht", "map", () => this.showTables(false));
      this.tableButton = button("Tabellenansicht", "table", () => this.showTables(true));
      this.mapButton.setAttribute("aria-pressed", "true");
      this.tableButton.setAttribute("aria-pressed", "false");
      views.append(this.mapButton, this.tableButton);
      header.append(this.breadcrumb, searchWrap, views);
      this.viewport = make("div", "roadmap-viewport");
      this.viewport.tabIndex = 0;
      this.viewport.setAttribute("aria-label", "Roadmap-Karte");
      this.phaseWorld = make("div", "roadmap-world roadmap-phase-world");
      this.phaseWorld.dataset.roadmapLevel = "phases";
      this.lines = svg("svg", { class: "roadmap-connections", "aria-hidden": "true" });
      this.phaseWorld.append(this.lines);
      for (const [i, phase] of this.phases.entries()) {
        const pos = this.saved.overview && this.saved.overview[phase.id];
        this.positions.overview[phase.id] = validPosition(pos) ? { x: pos.x, y: pos.y } : { x: POSITIONS[i][0], y: POSITIONS[i][1] };
        this.makePhase(phase);
      }
      this.stepWorld = make("div", "roadmap-world roadmap-step-world");
      this.stepWorld.dataset.roadmapLevel = "steps";
      this.stepWorld.inert = true;
      this.stepWorld.hidden = true;
      this.stepLines = svg("svg", { class: "roadmap-connections", "aria-hidden": "true" });
      this.stepWorld.append(this.stepLines);
      this.context = make("details", "roadmap-phase-context");
      this.context.hidden = true;
      this.context.append(make("summary", "", "Ziel und Voraussetzungen"));
      this.contextBody = make("div", "roadmap-context-body");
      this.context.append(this.contextBody);
      this.frame = make("div", "roadmap-portal-frame");
      this.frame.setAttribute("aria-hidden", "true");
      this.frame.hidden = true;
      this.boundary = make("div", "roadmap-depth-boundary");
      this.boundary.setAttribute("aria-hidden", "true");
      this.particles = svg("svg", { class: "roadmap-edge-particles", "aria-hidden": "true" });
      this.minimap = button("Gesamtansicht", "map", () => this.fitCurrent());
      this.minimap.className = "roadmap-minimap";
      this.minimap.replaceChildren();
      this.miniSvg = svg("svg", { viewBox: "0 0 160 100", "aria-hidden": "true" }, this.minimap);
      const controls = make("div", "roadmap-navigation");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", "Kartenansicht steuern");
      this.zoomOutput = make("output", "roadmap-zoom", "100 %");
      this.zoomOutput.setAttribute("aria-label", "Vergrößerung");
      controls.append(button("Verkleinern", "minus", () => this.zoomButton(-1)), this.zoomOutput,
        button("Vergrößern", "plus", () => this.zoomButton(1)),
        button("Alles zeigen", "fit", () => this.fitCurrent()),
        button("Anordnung zurücksetzen", "reset", () => this.reset()),
        button("Vollbild", "full", () => this.fullscreen()));
      this.viewport.append(this.phaseWorld, this.stepWorld, this.frame, this.boundary, this.particles, this.context, this.minimap, controls);
      this.legend = make("div", "roadmap-legend");
      for (const [label, kind] of Object.entries(PHASE_STATE)) {
        const item = make("span", `roadmap-legend-item roadmap-state--${kind}`);
        item.append(make("i", "roadmap-state-dot"), document.createTextNode(label),
          make("span", "roadmap-legend-count", String(this.phases.filter((p) => p.state === label).length)));
        this.legend.append(item);
      }
      this.live = make("div", "roadmap-sr-only");
      this.live.setAttribute("role", "status");
      this.root.append(header, this.viewport, this.legend, this.live);
    }

    badge(label, kind) {
      return make("span", `roadmap-state roadmap-state--${kind}`, label);
    }

    makePhase(phase) {
      const node = make("article", `roadmap-node roadmap-node--${PHASE_STATE[phase.state]}${phase.id === "P8" ? " roadmap-node--optional" : ""}`);
      node.dataset.phase = phase.id;
      const handle = button(`${phase.id} verschieben`, "grip", null, "roadmap-drag");
      handle.dataset.roadmapDrag = phase.id;
      const enter = make("button", "roadmap-enter");
      enter.type = "button";
      enter.setAttribute("aria-label", `${phase.id}: ${phase.title} öffnen`);
      enter.addEventListener("click", () => this.enter(phase));
      const content = make("div", "roadmap-node-content");
      const meta = make("div", "roadmap-node-meta");
      meta.append(make("span", "roadmap-number", phase.id), this.badge(phase.state, PHASE_STATE[phase.state]));
      const title = make("h3", "roadmap-node-title", phase.title);
      const checkpoints = make("ul", "roadmap-checkpoints");
      const dated = phase.steps.filter((s) => s.date).sort((a, b) => b.date.localeCompare(a.date));
      const documented = [...dated, ...phase.steps.filter((s) => !s.date && STEP_STATE[s.state] === "done")];
      const recent = documented[0] || phase.steps[0];
      const next = phase.steps.find((s) => s.id !== recent.id && (s.state === "offen" || s.state === "blockiert"))
        || documented.find((s) => s.id !== recent.id) || phase.steps.find((s) => s.id !== recent.id);
      for (const step of [recent, next].filter(Boolean)) {
        const item = make("li", `roadmap-checkpoint roadmap-checkpoint--${STEP_STATE[step.state]}`);
        const marker = svg("svg", { class: "roadmap-checkpoint-marker", viewBox: "0 0 14 14", "aria-hidden": "true" });
        svg("circle", { cx: 7, cy: 7, r: 4.5 }, marker);
        if (STEP_STATE[step.state] === "done") svg("path", { d: "M4.7 7l1.5 1.6 3.2-3.5" }, marker);
        const label = make("span", "roadmap-checkpoint-label", step.state);
        item.append(marker, make("span", "roadmap-checkpoint-title", step.title), label);
        if (step.date) {
          const date = new Date(`${step.date}T12:00:00Z`).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
          const time = make("time", "roadmap-sr-only", `Aktualisiert am ${date}`);
          time.dateTime = step.date;
          item.title = `Aktualisiert am ${date}`;
          item.append(time);
        }
        checkpoints.append(item);
      }
      content.append(meta, title, checkpoints, this.preview(phase));
      enter.append(content);
      node.append(handle, enter);
      this.phaseWorld.append(node);
      this.nodes.set(phase.id, node);
      this.place(node, this.positions.overview[phase.id]);
    }

    preview(phase) {
      const preview = make("div", "roadmap-nested-preview");
      preview.setAttribute("aria-hidden", "true");
      const graph = svg("svg", { viewBox: "0 0 270 64", preserveAspectRatio: "xMidYMid slice" }, preview);
      for (const [i, step] of phase.steps.slice(0, 5).entries()) {
        const x = 8 + i * 76;
        const y = i % 2 ? 20 : 7;
        if (i) svg("path", { d: `M${x - 9} 28C${x - 4} 28 ${x + 1} ${y + 14} ${x + 8} ${y + 14}`, class: "roadmap-preview-link" }, graph);
        const group = svg("g", { class: `roadmap-preview-card roadmap-preview-card--${STEP_STATE[step.state]}` }, graph);
        svg("rect", { x, y, width: 66, height: 37, rx: 5 }, group);
        svg("circle", { cx: x + 9, cy: y + 9, r: 2 }, group);
        svg("path", { d: `M${x + 16} ${y + 9}h30M${x + 8} ${y + 20}h43M${x + 8} ${y + 26}h28`, class: "roadmap-preview-text" }, group);
      }
      return preview;
    }

    makeSteps(phase) {
      // Measure the real cards before fitting; hidden subtrees report zero size.
      this.stepWorld.hidden = false;
      this.stepWorld.replaceChildren(this.stepLines);
      this.stepLines.replaceChildren();
      this.stepNodes.clear();
      this.positions.steps[phase.id] = {};
      const columns = phase.steps.length <= 4 ? 2 : 3;
      for (const [i, step] of phase.steps.entries()) {
        const fallback = { x: i % columns * (STEP_WIDTH + 58), y: Math.floor(i / columns) * 230 + (i % 2 ? 22 : 0) };
        const stored = this.saved.steps && this.saved.steps[phase.id] && this.saved.steps[phase.id][step.id];
        const pos = validPosition(stored) ? { x: stored.x, y: stored.y } : fallback;
        this.positions.steps[phase.id][step.id] = pos;
        const node = make("article", `roadmap-step roadmap-node--${STEP_STATE[step.state]}`);
        node.dataset.step = step.id;
        const handle = button(`${step.title} verschieben`, "grip", null, "roadmap-drag");
        handle.dataset.roadmapDrag = step.id;
        const content = make("div", "roadmap-step-content");
        const meta = make("div", "roadmap-node-meta");
        meta.append(make("span", "roadmap-step-number", String(i + 1).padStart(2, "0")), this.badge(step.state, STEP_STATE[step.state]));
        const heading = make("h3", "roadmap-step-title");
        copyContent(heading, step.titleCell);
        const evidence = make("div", "roadmap-step-evidence");
        copyContent(evidence, step.evidence);
        content.append(meta, heading);
        if (step.date) {
          const time = make("time", "roadmap-step-date", new Date(`${step.date}T12:00:00Z`).toLocaleDateString("de-DE"));
          time.dateTime = step.date;
          content.append(time);
        }
        content.append(evidence);
        node.append(handle, content);
        this.stepWorld.append(node);
        this.stepNodes.set(step.id, node);
        this.place(node, pos);
      }
      this.contextBody.replaceChildren();
      const goal = make("p", "roadmap-context-exit");
      goal.append(make("strong", "", "Exit-Kriterium: "));
      copyContent(goal, phase.exitCell);
      const requirements = make("p", "roadmap-context-requirements", `Kamera: ${phase.camera} · GSVmulti-Spec: ${phase.gsv}`);
      const note = make("p", "roadmap-context-note");
      oqText(note, phase.note);
      this.contextBody.append(goal, requirements, note);
      this.context.open = this.size.w >= 950;
      this.innerCamera = this.fitCamera(this.stepNodes, true);
      this.innerBaseZoom = this.innerCamera.z;
      this.connect(this.stepNodes, this.stepLines);
      this.makeReveal();
    }

    makeReveal() {
      if (this.reveal) this.reveal.cancel();
      if (!this.A || this.reduced || !this.stepNodes.size) {
        this.stepNodes.forEach((node) => {
          const content = node.querySelector(".roadmap-step-content");
          content.style.opacity = "1";
          content.style.transform = "none";
        });
        this.reveal = null;
        return;
      }
      const contents = Array.from(this.stepNodes.values(), (node) => node.querySelector(".roadmap-step-content"));
      this.reveal = this.A.createTimeline({ autoplay: false });
      this.reveal.add(contents, { opacity: [0, 1], y: [16, 0], duration: 270,
        ease: "outExpo", delay: this.A.stagger(Math.min(35, 140 / Math.max(1, contents.length - 1))) }, 0);
    }

    place(node, pos) { node.style.left = `${pos.x}px`; node.style.top = `${pos.y}px`; }

    bounds(nodes) {
      const rects = Array.from(nodes.values(), (node) => ({ x: node.offsetLeft, y: node.offsetTop, w: node.offsetWidth, h: node.offsetHeight }));
      return { x: Math.min(...rects.map((r) => r.x)), y: Math.min(...rects.map((r) => r.y)),
        right: Math.max(...rects.map((r) => r.x + r.w)), bottom: Math.max(...rects.map((r) => r.y + r.h)) };
    }

    fitCamera(nodes, inside = false) {
      const b = this.bounds(nodes);
      const left = inside && this.size.w >= 950 ? 330 : 26;
      const top = inside ? 92 : 32;
      const w = this.size.w - left - 26;
      const h = this.size.h - top - 112;
      let z = clamp(Math.min(w / (b.right - b.x), h / (b.bottom - b.y)), 0.18, 1.12);
      if (this.size.w < 640) {
        z = Math.min(1.05, (this.size.w - 42) / (inside ? STEP_WIDTH : WIDTH));
        const first = inside ? nodes.values().next().value : this.nodes.get(this.phases.find((p) => p.state !== "erreicht").id);
        return { x: (this.size.w - first.offsetWidth * z) / 2 - first.offsetLeft * z, y: top + 30 - first.offsetTop * z, z };
      }
      return { x: left + (w - (b.right - b.x) * z) / 2 - b.x * z,
        y: top + (h - (b.bottom - b.y) * z) / 2 - b.y * z, z };
    }

    resize() {
      if (this.disposed || this.viewport.hidden) return;
      const rect = this.viewport.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const previous = this.size;
      this.size = { w: rect.width, h: rect.height };
      if (!previous) this.camera = this.fitCamera(this.nodes);
      else if (previous.w !== rect.width || previous.h !== rect.height) {
        if (this.phase) this.innerCamera = this.fitCamera(this.stepNodes, true);
        else this.camera = this.fitCamera(this.nodes);
      }
      this.connect(this.nodes, this.lines);
      this.drawParticles();
      this.render();
    }

    connect(nodes, layer) {
      const entries = Array.from(nodes.entries());
      while (layer.children.length > Math.max(0, entries.length - 1)) layer.lastElementChild.remove();
      for (let i = 0; i < entries.length - 1; i += 1) {
        const [id, node] = entries[i];
        const [nextId, next] = entries[i + 1];
        const ax = node.offsetLeft + node.offsetWidth / 2;
        const ay = node.offsetTop + node.offsetHeight / 2;
        const bx = next.offsetLeft + next.offsetWidth / 2;
        const by = next.offsetTop + next.offsetHeight / 2;
        let d;
        if (Math.abs(by - ay) > Math.abs(bx - ax) * 1.2) {
          const sign = by >= ay ? 1 : -1;
          const sy = ay + sign * node.offsetHeight / 2;
          const ey = by - sign * next.offsetHeight / 2;
          const bend = Math.max(46, Math.abs(ey - sy) * 0.6);
          d = `M${ax} ${sy}C${ax} ${sy + sign * bend} ${bx} ${ey - sign * bend} ${bx} ${ey}`;
        } else {
          const sign = bx >= ax ? 1 : -1;
          const sx = ax + sign * node.offsetWidth / 2;
          const ex = bx - sign * next.offsetWidth / 2;
          const bend = Math.max(46, Math.abs(ex - sx) * 0.6);
          d = `M${sx} ${ay}C${sx + sign * bend} ${ay} ${ex - sign * bend} ${by} ${ex} ${by}`;
        }
        const path = layer.children[i] || svg("path", {}, layer);
        path.setAttribute("d", d);
        path.dataset.from = id;
        path.dataset.to = nextId;
        path.classList.toggle("roadmap-connection--optional", nextId === "P8");
      }
    }

    drawParticles() {
      this.particles.replaceChildren();
      this.particles.setAttribute("viewBox", `0 0 ${this.size.w} ${this.size.h}`);
      for (let i = 0; i < 100; i += 1) {
        const fraction = (i * 0.61803398875) % 1;
        const inset = 3 + ((i * 17) % 29) * ((i % 4 + 1) / 4);
        let x, y;
        if (i % 4 === 0) { x = fraction * this.size.w; y = inset; }
        else if (i % 4 === 1) { x = this.size.w - inset; y = fraction * this.size.h; }
        else if (i % 4 === 2) { x = fraction * this.size.w; y = this.size.h - inset; }
        else { x = inset; y = fraction * this.size.h; }
        svg("circle", { cx: x, cy: y, r: 0.7 + i % 4 * 0.25, opacity: 0.12 + i % 5 * 0.055 }, this.particles);
      }
    }

    transformedRect(node) {
      return { x: this.camera.x + node.offsetLeft * this.camera.z,
        y: this.camera.y + node.offsetTop * this.camera.z,
        w: node.offsetWidth * this.camera.z, h: node.offsetHeight * this.camera.z };
    }

    render() {
      if (!this.size || this.disposed) return;
      const p = clamp(this.progress);
      this.phaseWorld.style.transform = `translate(${this.camera.x}px,${this.camera.y}px) scale(${this.camera.z})`;
      this.root.style.setProperty("--roadmap-depth", String(p));
      this.frame.hidden = !this.phase || p === 0;
      this.stepWorld.hidden = !this.phase || p === 0;
      this.context.hidden = !this.phase || p < 0.94;
      this.back.hidden = !this.phase || p < 0.1;
      this.phaseWorld.inert = p > 0.1;
      this.stepWorld.inert = p < 0.98;
      this.phaseWorld.style.visibility = p >= 0.999 ? "hidden" : "";
      for (const [id, node] of this.nodes) {
        const selected = this.phase && this.phase.id === id;
        node.style.opacity = String(selected ? 1 : 1 - smooth(0.02, 0.72, p));
        node.style.borderColor = selected && p > 0 ? "transparent" : "";
        node.style.backgroundColor = selected && p > 0
          ? `color-mix(in srgb, var(--roadmap-surface) ${(1 - smooth(0.08, 0.58, p)) * 100}%, transparent)` : "";
        const content = node.querySelector(".roadmap-node-content");
        content.style.opacity = String(selected ? 1 - smooth(0.04, 0.45, p) : 1);
        node.querySelector(".roadmap-drag").style.opacity = String(selected ? 1 - smooth(0.04, 0.35, p) : 1);
      }
      this.lines.style.opacity = String(1 - smooth(0.04, 0.65, p));
      this.stepWorld.style.opacity = String(smooth(0.32, 0.86, p));
      this.context.style.opacity = String(smooth(0.82, 1, p));
      this.boundary.style.opacity = String(smooth(0.55, 1, p));
      this.particles.style.opacity = String(smooth(0.55, 1, p));
      if (this.phase) {
        const node = this.nodes.get(this.phase.id);
        const r = this.transformedRect(node);
        const t = smooth(0, 1, p);
        const x = mix(r.x, 0, t), y = mix(r.y, 0, t);
        const w = mix(r.w, this.size.w, t), h = mix(r.h, this.size.h, t);
        Object.assign(this.frame.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px`,
          borderRadius: `${mix(15, 9, t)}px` });
        const stepBounds = this.bounds(this.stepNodes);
        const tinyZ = Math.min(264 / Math.max(1, stepBounds.right - stepBounds.x), 64 / Math.max(1, stepBounds.bottom - stepBounds.y)) * this.camera.z;
        const start = { x: r.x + 18 * this.camera.z - stepBounds.x * tinyZ,
          y: r.y + (node.offsetHeight - 73) * this.camera.z - stepBounds.y * tinyZ, z: tinyZ };
        const u = smooth(0.22, 1, p);
        const inner = { x: mix(start.x, this.innerCamera.x, u), y: mix(start.y, this.innerCamera.y, u), z: mix(start.z, this.innerCamera.z, u) };
        this.stepWorld.style.transform = `translate(${inner.x}px,${inner.y}px) scale(${inner.z})`;
        if (this.reveal) this.reveal.seek(smooth(0.3, 0.9, p) * this.reveal.duration);
      }
      const shownCamera = p > 0.99 ? this.innerCamera : this.camera;
      this.zoomOutput.textContent = `${Math.round(shownCamera.z * 100)} %`;
      this.drawMinimap();
    }

    drawMinimap() {
      const nodes = this.phase && this.progress > 0.99 ? this.stepNodes : this.nodes;
      const camera = this.phase && this.progress > 0.99 ? this.innerCamera : this.camera;
      const b = this.bounds(nodes);
      const scale = Math.min(140 / (b.right - b.x), 76 / (b.bottom - b.y));
      const ox = 10 - b.x * scale, oy = 12 - b.y * scale;
      this.miniSvg.replaceChildren();
      for (const [id, node] of nodes) svg("rect", { x: node.offsetLeft * scale + ox, y: node.offsetTop * scale + oy,
        width: node.offsetWidth * scale, height: node.offsetHeight * scale, rx: 2,
        class: this.phase && this.phase.id === id ? "roadmap-mini-current" : "roadmap-mini-node" }, this.miniSvg);
      svg("rect", { x: -camera.x / camera.z * scale + ox, y: -camera.y / camera.z * scale + oy,
        width: this.size.w / camera.z * scale, height: this.size.h / camera.z * scale, rx: 3,
        class: "roadmap-mini-view" }, this.miniSvg);
    }

    prepare(phase) {
      if (this.phase && this.phase.id === phase.id) return;
      this.stop();
      this.phase = phase;
      this.origin = { ...this.camera };
      this.returnFocus = this.nodes.get(phase.id).querySelector(".roadmap-enter");
      this.root.dataset.roadmapPhase = phase.id;
      this.root.dataset.roadmapView = "entering";
      this.root.style.setProperty("--roadmap-current", `var(--roadmap-${PHASE_STATE[phase.state]})`);
      this.crumb.textContent = `${phase.id} · ${phase.title}`;
      this.makeSteps(phase);
    }

    endZoom() {
      return Math.min(WIDTH, this.size.w - 40) * 2.6 / WIDTH;
    }

    enter(phase) {
      if (this.disposed || this.tableMode) return;
      if (this.phase && this.phase.id !== phase.id) this.finishExit(false);
      this.prepare(phase);
      const node = this.nodes.get(phase.id);
      const z = this.endZoom();
      const target = { x: this.size.w / 2 - (node.offsetLeft + node.offsetWidth / 2) * z,
        y: this.size.h / 2 - (node.offsetTop + node.offsetHeight / 2) * z, z };
      this.transition(1, target, () => this.finishEnter());
    }

    transition(progress, camera, done) {
      this.stop();
      if (!this.A || this.reduced) {
        this.progress = progress;
        Object.assign(this.camera, camera);
        this.render();
        done();
        return;
      }
      this.phaseWorld.style.willChange = "transform";
      this.stepWorld.style.willChange = "transform, opacity";
      const motion = { p: this.progress, ...this.camera };
      this.motion = this.A.createTimeline({ defaults: { ease: "outExpo" }, onUpdate: () => {
        this.progress = motion.p;
        Object.assign(this.camera, { x: motion.x, y: motion.y, z: motion.z });
        this.render();
      }, onComplete: () => {
        this.motion = null;
        this.progress = progress;
        Object.assign(this.camera, camera);
        this.phaseWorld.style.willChange = "";
        this.stepWorld.style.willChange = "";
        this.render();
        done();
      } });
      this.motion.add(motion, { p: progress, x: camera.x, y: camera.y, z: camera.z, duration: progress ? 620 : 470 }, 0);
    }

    finishEnter() {
      this.progress = 1;
      this.root.dataset.roadmapView = "inside";
      this.live.textContent = `${this.phase.id}: ${this.phase.steps.length} Arbeitsschritte`;
      this.render();
      // The phase button becomes inert as its surface dissolves.
      this.viewport.focus({ preventScroll: true });
    }

    exit() {
      if (!this.phase) return;
      this.root.dataset.roadmapView = "leaving";
      this.transition(0, this.origin, () => this.finishExit());
    }

    finishExit(focus = true) {
      this.stop();
      if (this.origin) Object.assign(this.camera, this.origin);
      this.progress = 0;
      this.phase = null;
      this.root.dataset.roadmapView = "overview";
      delete this.root.dataset.roadmapPhase;
      this.crumb.textContent = "Meilensteine";
      this.live.textContent = "Meilensteine";
      this.render();
      if (focus && this.returnFocus) this.returnFocus.focus({ preventScroll: true });
    }

    stop() {
      if (this.motion) { this.motion.cancel(); this.motion = null; }
      this.phaseWorld.style.willChange = "";
      this.stepWorld.style.willChange = "";
    }

    save() {
      // A level is built lazily; retain layouts not visited since this reload.
      this.positions.steps = { ...this.saved.steps, ...this.positions.steps };
      const serialized = JSON.stringify({ version: 1, positions: this.positions });
      // Rebuilding a level must not clear the snapshot it reads positions from.
      this.saved = JSON.parse(serialized).positions;
      try { window.localStorage.setItem(STORAGE, serialized); } catch (_) { /* Optional persistence. */ }
    }

    reset() {
      this.stop();
      this.saved = {};
      for (const [i, phase] of this.phases.entries()) {
        const pos = { x: POSITIONS[i][0], y: POSITIONS[i][1] };
        this.positions.overview[phase.id] = pos;
        this.place(this.nodes.get(phase.id), pos);
      }
      this.positions.steps = {};
      if (this.phase) this.makeSteps(this.phase);
      this.camera = this.fitCamera(this.nodes);
      this.connect(this.nodes, this.lines);
      this.save();
      this.render();
    }

    fitCurrent() {
      this.stop();
      if (this.phase && this.progress > 0.99) {
        this.innerCamera = this.fitCamera(this.stepNodes, true);
        this.innerBaseZoom = this.innerCamera.z;
      } else {
        if (this.phase) this.finishExit(false);
        this.camera = this.fitCamera(this.nodes);
      }
      this.render();
    }

    showTables(show) {
      this.stop();
      this.tableMode = show;
      this.sources.forEach((source) => { source.hidden = !show; });
      this.viewport.hidden = show;
      this.legend.hidden = show;
      this.search.disabled = show;
      this.mapButton.setAttribute("aria-pressed", String(!show));
      this.tableButton.setAttribute("aria-pressed", String(show));
      if (!show) this.resize();
    }

    fullscreen() {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (this.viewport.requestFullscreen) this.viewport.requestFullscreen().catch(() => {
        this.viewport.classList.toggle("roadmap-viewport--expanded"); this.resize();
      });
      else { this.viewport.classList.toggle("roadmap-viewport--expanded"); this.resize(); }
    }

    point(event) {
      const rect = this.viewport.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }

    zoom(camera, factor, point) {
      const z = clamp(camera.z * factor, 0.18, 4.5);
      const ratio = z / camera.z;
      camera.x = point.x - (point.x - camera.x) * ratio;
      camera.y = point.y - (point.y - camera.y) * ratio;
      camera.z = z;
    }

    applyZoom(factor, point, target) {
      this.stop();
      if (this.phase && this.progress > 0.99) {
        if (factor < 1 && this.innerCamera.z <= this.innerBaseZoom * 1.04) { this.exit(); return; }
        this.zoom(this.innerCamera, factor, point);
      } else {
        const phaseNode = target && target.closest ? target.closest(".roadmap-node[data-phase]") : null;
        const phase = this.phase || (phaseNode && this.phases.find((p) => p.id === phaseNode.dataset.phase));
        if (factor > 1 && phase && !this.phase) this.prepare(phase);
        this.zoom(this.camera, factor, point);
        if (this.phase) {
          const reference = Math.min(WIDTH, this.size.w - 40);
          this.progress = smooth(reference * 1.35, reference * 2.6, WIDTH * this.camera.z);
          if (this.progress >= 0.999) this.finishEnter();
          else if (this.progress === 0 && factor < 1) this.finishExit(false);
          else this.root.dataset.roadmapView = "entering";
        }
      }
      this.render();
    }

    zoomButton(direction) {
      if (direction < 0 && this.phase && this.progress >= 0.99) { this.applyZoom(0.7, { x: this.size.w / 2, y: this.size.h / 2 }); return; }
      let node = this.phase && this.nodes.get(this.phase.id);
      if (!node && direction > 0) {
        node = Array.from(this.nodes.values()).sort((a, b) => {
          const ra = this.transformedRect(a), rb = this.transformedRect(b);
          return Math.hypot(ra.x + ra.w / 2 - this.size.w / 2, ra.y + ra.h / 2 - this.size.h / 2) - Math.hypot(rb.x + rb.w / 2 - this.size.w / 2, rb.y + rb.h / 2 - this.size.h / 2);
        })[0];
      }
      this.applyZoom(direction > 0 ? 1.5 : 1 / 1.5, { x: this.size.w / 2, y: this.size.h / 2 }, node);
    }

    bind() {
      this.listen(this.search, "input", () => {
        this.searchState.hidden = true;
        this.search.removeAttribute("aria-invalid");
      });
      this.listen(this.search, "keydown", (event) => {
        if (event.key !== "Enter") return;
        const query = this.search.value.trim().toLocaleLowerCase("de");
        const phase = this.phases.find((p) => p.id.toLowerCase() === query) || this.phases.find((p) => p.title.toLocaleLowerCase("de").includes(query));
        if (query && phase) {
          event.preventDefault();
          this.searchState.hidden = true;
          this.search.removeAttribute("aria-invalid");
          this.enter(phase);
        } else if (query) {
          event.preventDefault();
          this.search.setAttribute("aria-invalid", "true");
          this.searchState.textContent = "Kein Treffer";
          this.searchState.hidden = false;
        }
      });
      this.listen(this.viewport, "wheel", (event) => {
        if (event.target.closest(".roadmap-phase-context") && !event.ctrlKey) return;
        event.preventDefault();
        this.applyZoom(Math.exp(clamp(-event.deltaY * 0.0022, -1.5, 1.5)), this.point(event), event.target);
      }, { passive: false });
      this.listen(this.viewport, "pointerdown", (event) => this.pointerDown(event));
      this.listen(this.viewport, "pointermove", (event) => this.pointerMove(event));
      this.listen(this.viewport, "pointerup", (event) => this.pointerUp(event));
      this.listen(this.viewport, "pointercancel", (event) => this.pointerUp(event));
      this.listen(this.root, "keydown", (event) => {
        if (event.target.matches("input, textarea, select")) return;
        if (event.key === "Escape") { this.exit(); event.preventDefault(); return; }
        const handle = event.target.closest("[data-roadmap-drag]");
        if (handle && event.shiftKey && /^Arrow/.test(event.key)) {
          event.preventDefault();
          const inside = this.progress > 0.99 && this.phase;
          const positions = inside ? this.positions.steps[this.phase.id] : this.positions.overview;
          const nodes = inside ? this.stepNodes : this.nodes;
          const pos = positions[handle.dataset.roadmapDrag];
          pos.x += event.key === "ArrowLeft" ? -20 : event.key === "ArrowRight" ? 20 : 0;
          pos.y += event.key === "ArrowUp" ? -20 : event.key === "ArrowDown" ? 20 : 0;
          this.place(nodes.get(handle.dataset.roadmapDrag), pos);
          this.connect(nodes, inside ? this.stepLines : this.lines);
          this.save(); this.render(); return;
        }
        if (event.key === "+" || event.key === "=") { event.preventDefault(); this.zoomButton(1); }
        else if (event.key === "-") { event.preventDefault(); this.zoomButton(-1); }
        else if (event.key === "Home") { event.preventDefault(); this.fitCurrent(); }
        else if (event.target === this.viewport && /^Arrow/.test(event.key)) {
          event.preventDefault();
          const camera = this.phase && this.progress > 0.99 ? this.innerCamera : this.camera;
          camera.x += event.key === "ArrowLeft" ? 50 : event.key === "ArrowRight" ? -50 : 0;
          camera.y += event.key === "ArrowUp" ? 50 : event.key === "ArrowDown" ? -50 : 0;
          this.render();
        }
      });
      this.listen(this.reducedQuery, "change", (event) => {
        this.reduced = event.matches;
        if (this.reduced && this.phase) { this.stop(); this.makeReveal(); this.finishEnter(); }
      });
    }

    pointerDown(event) {
      if (event.button !== 0 && event.pointerType !== "touch") return;
      const point = this.point(event);
      this.pointers.set(event.pointerId, point);
      if (this.pointers.size === 2) {
        this.stop();
        const points = Array.from(this.pointers.values());
        this.pinch = { distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y), target: event.target };
        this.drag = null;
        this.viewport.setPointerCapture(event.pointerId);
        event.preventDefault();
        return;
      }
      const handle = event.target.closest("[data-roadmap-drag]");
      if (!handle && event.target.closest("button, a, input, summary, .roadmap-phase-context")) return;
      this.stop();
      const inside = this.phase && this.progress > 0.99;
      const camera = inside ? this.innerCamera : this.camera;
      const id = handle && handle.dataset.roadmapDrag;
      const positions = inside ? this.positions.steps[this.phase.id] : this.positions.overview;
      this.drag = { id, inside, pointer: event.pointerId, point, camera: { ...camera }, pos: id ? { ...positions[id] } : null, moved: false };
      this.viewport.setPointerCapture(event.pointerId);
      this.viewport.classList.add("roadmap-viewport--dragging");
      if (!handle) this.viewport.focus({ preventScroll: true });
      event.preventDefault();
    }

    pointerMove(event) {
      if (!this.pointers.has(event.pointerId)) return;
      const point = this.point(event);
      this.pointers.set(event.pointerId, point);
      if (this.pinch && this.pointers.size >= 2) {
        const points = Array.from(this.pointers.values());
        const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
        const center = { x: (points[0].x + points[1].x) / 2, y: (points[0].y + points[1].y) / 2 };
        if (distance > 0 && this.pinch.distance > 0) this.applyZoom(distance / this.pinch.distance, center, this.pinch.target);
        this.pinch.distance = distance;
        event.preventDefault(); return;
      }
      const drag = this.drag;
      if (!drag || drag.pointer !== event.pointerId) return;
      const dx = point.x - drag.point.x, dy = point.y - drag.point.y;
      if (!drag.moved && Math.hypot(dx, dy) < 5) return;
      drag.moved = true;
      const camera = drag.inside ? this.innerCamera : this.camera;
      if (drag.id) {
        const positions = drag.inside ? this.positions.steps[this.phase.id] : this.positions.overview;
        const nodes = drag.inside ? this.stepNodes : this.nodes;
        positions[drag.id] = { x: drag.pos.x + dx / drag.camera.z, y: drag.pos.y + dy / drag.camera.z };
        this.place(nodes.get(drag.id), positions[drag.id]);
        this.connect(nodes, drag.inside ? this.stepLines : this.lines);
      } else {
        camera.x = drag.camera.x + dx;
        camera.y = drag.camera.y + dy;
      }
      if (!this.raf) this.raf = requestAnimationFrame(() => { this.raf = null; this.render(); });
    }

    pointerUp(event) {
      this.pointers.delete(event.pointerId);
      if (this.pinch && this.pointers.size < 2) this.pinch = null;
      if (this.drag && this.drag.pointer === event.pointerId) {
        if (this.drag.id && this.drag.moved) this.save();
        this.drag = null;
      }
      if (this.viewport.hasPointerCapture(event.pointerId)) this.viewport.releasePointerCapture(event.pointerId);
      this.viewport.classList.remove("roadmap-viewport--dragging");
      this.render();
    }

    dispose() {
      this.disposed = true;
      this.stop();
      if (this.reveal) this.reveal.cancel();
      if (this.raf) cancelAnimationFrame(this.raf);
      this.abort.abort();
      if (this.observer) this.observer.disconnect();
      this.pointers.clear();
      document.body.classList.remove("roadmap-page");
    }
  }

  function enhance() {
    const article = document.querySelector(".md-content__inner");
    if (active && active.article === article && active.root.isConnected) return;
    if (active) { active.dispose(); active = null; }
    if (!article || !article.querySelector("h1#roadmap")) return;
    const data = readData(article);
    if (data) active = new Roadmap(article, data);
  }
  if (typeof document$ !== "undefined") document$.subscribe(enhance);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance);
  else enhance();
})();
