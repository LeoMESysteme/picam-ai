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
  const MIN_ZOOM = 0.18;
  const MAX_ZOOM = 4.5;
  const ENTER_MS = 720;
  const EXIT_MS = 580;
  const FLY_MS = 480;
  const RESET_MS = 560;
  const WHEEL_MS = 260;
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
  // Rounded style values let unchanged frames skip their DOM writes.
  const fixed = (n) => String(Math.round(n * 1000) / 1000);
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
      this.parts = new Map();
      // Node geometry is cached so a frame never reads layout after writing styles.
      this.rects = new Map();
      this.written = new WeakMap();
      this.camera = { x: 0, y: 0, z: 1 };
      this.innerCamera = { x: 0, y: 0, z: 1 };
      this.progress = 0;
      this.phase = null;
      this.pointers = new Map();
      this.zoomState = { z: 1 };
      this.lastZoom = 1;
      this.zoomGoal = 1;
      this.zoomDirection = 0;
      this.motionDirection = 0;
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
      if (document.fonts) document.fonts.ready.then(() => { if (!this.disposed) this.relayout(); });
      loadAnime().then((A) => {
        if (this.disposed) return;
        this.A = A;
        if (A) {
          this.ease = A.cubicBezier(0.3, 0, 0.1, 1);
          // One animatable carries wheel, button and key zoom; retargeting it keeps the motion continuous.
          this.zoomer = A.createAnimatable(this.zoomState, { z: WHEEL_MS, ease: "out(3)", onUpdate: () => this.wheelStep() });
        }
        if (this.phase) { this.makeReveal(); this.render(); }
      });
    }

    listen(target, event, handler, options = {}) {
      target.addEventListener(event, handler, { ...options, signal: this.abort.signal });
    }

    css(el, prop, value) {
      let cache = this.written.get(el);
      if (!cache) this.written.set(el, cache = {});
      if (cache[prop] === value) return;
      cache[prop] = value;
      el.style[prop] = value;
    }

    flag(el, name, value) {
      if (el[name] !== value) el[name] = value;
    }

    view(name) {
      // Rewriting the same value would still invalidate every [data-roadmap-view] rule.
      if (this.root.dataset.roadmapView !== name) this.root.dataset.roadmapView = name;
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
      this.parts.set(phase.id, { content, drag: handle });
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
      for (const node of this.stepNodes.values()) this.rects.delete(node);
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
      this.measure(this.stepNodes);
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
      this.revealAt = -1;
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

    place(node, pos) {
      node.style.left = `${pos.x}px`;
      node.style.top = `${pos.y}px`;
      const r = this.rects.get(node);
      if (r) { r.x = pos.x; r.y = pos.y; } else this.rects.set(node, { x: pos.x, y: pos.y, w: 0, h: 0 });
    }

    rect(node) {
      const r = this.rects.get(node);
      if (!r.w) { r.w = node.offsetWidth; r.h = node.offsetHeight; }
      return r;
    }

    measure(nodes) {
      for (const node of nodes.values()) {
        const r = this.rects.get(node);
        r.w = node.offsetWidth;
        r.h = node.offsetHeight;
      }
    }

    bounds(nodes) {
      const rects = Array.from(nodes.values(), (node) => this.rect(node));
      return { x: Math.min(...rects.map((r) => r.x)), y: Math.min(...rects.map((r) => r.y)),
        right: Math.max(...rects.map((r) => r.x + r.w)), bottom: Math.max(...rects.map((r) => r.y + r.h)) };
    }

    fitCamera(nodes, inside = false) {
      const b = this.bounds(nodes);
      const left = inside && this.size.w >= 950 ? 330 : 26;
      const top = inside ? 92 : 32;
      const w = this.size.w - left - 26;
      const h = this.size.h - top - 112;
      let z = clamp(Math.min(w / (b.right - b.x), h / (b.bottom - b.y)), MIN_ZOOM, 1.12);
      if (this.size.w < 640) {
        z = Math.min(1.05, (this.size.w - 42) / (inside ? STEP_WIDTH : WIDTH));
        const first = this.rect(inside ? nodes.values().next().value : this.nodes.get(this.phases.find((p) => p.state !== "erreicht").id));
        return { x: (this.size.w - first.w * z) / 2 - first.x * z, y: top + 30 - first.y * z, z };
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
      this.measure(this.nodes);
      if (this.phase && !this.stepWorld.hidden) this.measure(this.stepNodes);
      if (!previous) this.camera = this.fitCamera(this.nodes);
      else if (previous.w !== rect.width || previous.h !== rect.height) {
        this.stop();
        if (this.phase) {
          this.innerCamera = this.fitCamera(this.stepNodes, true);
          this.innerBaseZoom = this.innerCamera.z;
        } else this.camera = this.fitCamera(this.nodes);
      }
      this.connect(this.nodes, this.lines);
      this.drawParticles();
      this.render();
    }

    relayout() {
      // Late web fonts change card heights; the cached geometry follows them.
      if (!this.size) return;
      this.measure(this.nodes);
      this.connect(this.nodes, this.lines);
      if (this.phase && !this.stepWorld.hidden) {
        this.measure(this.stepNodes);
        this.connect(this.stepNodes, this.stepLines);
      }
      this.render();
    }

    connect(nodes, layer) {
      this.miniDirty = true;
      const entries = Array.from(nodes.entries());
      while (layer.children.length > Math.max(0, entries.length - 1)) layer.lastElementChild.remove();
      for (let i = 0; i < entries.length - 1; i += 1) {
        const [id, node] = entries[i];
        const [nextId, next] = entries[i + 1];
        const a = this.rect(node), b = this.rect(next);
        const ax = a.x + a.w / 2, ay = a.y + a.h / 2;
        const bx = b.x + b.w / 2, by = b.y + b.h / 2;
        let d;
        if (Math.abs(by - ay) > Math.abs(bx - ax) * 1.2) {
          const sign = by >= ay ? 1 : -1;
          const sy = ay + sign * a.h / 2;
          const ey = by - sign * b.h / 2;
          const bend = Math.max(46, Math.abs(ey - sy) * 0.6);
          d = `M${ax} ${sy}C${ax} ${sy + sign * bend} ${bx} ${ey - sign * bend} ${bx} ${ey}`;
        } else {
          const sign = bx >= ax ? 1 : -1;
          const sx = ax + sign * a.w / 2;
          const ex = bx - sign * b.w / 2;
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
      const r = this.rect(node);
      return { x: this.camera.x + r.x * this.camera.z, y: this.camera.y + r.y * this.camera.z,
        w: r.w * this.camera.z, h: r.h * this.camera.z };
    }

    inside() {
      return Boolean(this.phase) && this.progress > 0.99;
    }

    activeCamera() {
      return this.inside() ? this.innerCamera : this.camera;
    }

    render() {
      if (!this.size || this.disposed) return;
      const p = clamp(this.progress);
      const deep = Boolean(this.phase) && p > 0;
      this.css(this.phaseWorld, "transform", `translate(${this.camera.x}px,${this.camera.y}px) scale(${this.camera.z})`);
      this.flag(this.frame, "hidden", !deep);
      this.flag(this.stepWorld, "hidden", !deep);
      this.flag(this.context, "hidden", !this.phase || p < 0.94);
      this.flag(this.back, "hidden", !this.phase || p < 0.1);
      this.flag(this.phaseWorld, "inert", p > 0.1);
      this.flag(this.stepWorld, "inert", p < 0.98);
      this.css(this.phaseWorld, "visibility", p >= 0.999 ? "hidden" : "");
      const others = fixed(1 - smooth(0.02, 0.72, p));
      for (const [id, node] of this.nodes) {
        const selected = Boolean(this.phase) && this.phase.id === id;
        const part = this.parts.get(id);
        this.css(node, "opacity", selected ? "1" : others);
        this.css(node, "borderColor", selected && p > 0 ? "transparent" : "");
        this.css(node, "backgroundColor", selected && p > 0
          ? `color-mix(in srgb, var(--roadmap-surface) ${fixed((1 - smooth(0.08, 0.58, p)) * 100)}%, transparent)` : "");
        this.css(part.content, "opacity", selected ? fixed(1 - smooth(0.04, 0.45, p)) : "");
        this.css(part.drag, "opacity", selected ? fixed(0.65 * (1 - smooth(0.04, 0.35, p))) : "");
      }
      this.css(this.lines, "opacity", fixed(1 - smooth(0.04, 0.65, p)));
      this.css(this.stepWorld, "opacity", fixed(smooth(0.32, 0.86, p)));
      this.css(this.context, "opacity", fixed(smooth(0.82, 1, p)));
      this.css(this.boundary, "opacity", fixed(smooth(0.55, 1, p)));
      this.css(this.particles, "opacity", fixed(smooth(0.55, 1, p)));
      if (deep) {
        const node = this.nodes.get(this.phase.id);
        const r = this.transformedRect(node);
        const t = smooth(0, 1, p);
        this.css(this.frame, "transform", `translate(${mix(r.x, 0, t)}px,${mix(r.y, 0, t)}px)`);
        this.css(this.frame, "width", `${mix(r.w, this.size.w, t)}px`);
        this.css(this.frame, "height", `${mix(r.h, this.size.h, t)}px`);
        // The card outline hands over to the stage outline: radius and colour meet in the middle.
        this.css(this.frame, "borderRadius", `${fixed(mix(15 * this.camera.z, 9, t))}px`);
        this.css(this.frame, "borderColor", `color-mix(in srgb, var(--roadmap-current) ${Math.round(smooth(0, 0.3, p) * 100)}%, var(--roadmap-edge))`);
        const stepBounds = this.bounds(this.stepNodes);
        const tinyZ = Math.min(264 / Math.max(1, stepBounds.right - stepBounds.x), 64 / Math.max(1, stepBounds.bottom - stepBounds.y)) * this.camera.z;
        const start = { x: r.x + 18 * this.camera.z - stepBounds.x * tinyZ,
          y: r.y + (this.rect(node).h - 73) * this.camera.z - stepBounds.y * tinyZ, z: tinyZ };
        const u = smooth(0.22, 1, p);
        const inner = p >= 1 ? this.innerCamera
          : { x: mix(start.x, this.innerCamera.x, u), y: mix(start.y, this.innerCamera.y, u), z: mix(start.z, this.innerCamera.z, u) };
        this.css(this.stepWorld, "transform", `translate(${inner.x}px,${inner.y}px) scale(${inner.z})`);
        if (this.reveal) {
          const at = smooth(0.3, 0.9, p) * this.reveal.duration;
          if (at !== this.revealAt) { this.revealAt = at; this.reveal.seek(at); }
        }
      }
      const zoom = `${Math.round(this.activeCamera().z * 100)} %`;
      if (zoom !== this.zoomText) { this.zoomText = zoom; this.zoomOutput.textContent = zoom; }
      this.drawMinimap();
    }

    requestRender() {
      if (!this.raf) this.raf = requestAnimationFrame(() => { this.raf = null; this.render(); });
    }

    drawMinimap() {
      const inside = this.inside();
      const nodes = inside ? this.stepNodes : this.nodes;
      const camera = inside ? this.innerCamera : this.camera;
      const key = `${inside ? "steps" : "phases"}:${this.phase ? this.phase.id : ""}`;
      // The miniature is rebuilt only when its level or layout changes; frames move the view box.
      if (this.miniDirty || this.miniKey !== key) {
        this.miniDirty = false;
        this.miniKey = key;
        const b = this.bounds(nodes);
        // Include the fitted view so its frame stays inside the miniature.
        const fit = this.fitCamera(nodes, inside);
        const fx = -fit.x / fit.z, fy = -fit.y / fit.z;
        b.x = Math.min(b.x, fx); b.y = Math.min(b.y, fy);
        b.right = Math.max(b.right, fx + this.size.w / fit.z); b.bottom = Math.max(b.bottom, fy + this.size.h / fit.z);
        const scale = Math.min(140 / (b.right - b.x), 76 / (b.bottom - b.y));
        const ox = 10 - b.x * scale, oy = 12 - b.y * scale;
        this.miniSvg.replaceChildren();
        for (const [id, node] of nodes) {
          const r = this.rect(node);
          svg("rect", { x: r.x * scale + ox, y: r.y * scale + oy, width: r.w * scale, height: r.h * scale, rx: 2,
            class: !inside && this.phase && this.phase.id === id ? "roadmap-mini-current" : "roadmap-mini-node" }, this.miniSvg);
        }
        this.mini = { scale, ox, oy, view: svg("rect", { rx: 3, class: "roadmap-mini-view" }, this.miniSvg) };
      }
      const { scale, ox, oy, view } = this.mini;
      view.setAttribute("x", fixed(-camera.x / camera.z * scale + ox));
      view.setAttribute("y", fixed(-camera.y / camera.z * scale + oy));
      view.setAttribute("width", fixed(this.size.w / camera.z * scale));
      view.setAttribute("height", fixed(this.size.h / camera.z * scale));
    }

    prepare(phase) {
      if (this.phase && this.phase.id === phase.id) return;
      this.stop();
      this.phase = phase;
      this.origin = { ...this.camera };
      this.returnFocus = this.nodes.get(phase.id).querySelector(".roadmap-enter");
      this.root.dataset.roadmapPhase = phase.id;
      this.view("entering");
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
      // A wheel zoom can stop just short of the end; complete it instead of ignoring the request.
      if (this.inside()) {
        if (this.root.dataset.roadmapView !== "inside") this.finishEnter();
        return;
      }
      this.prepare(phase);
      this.view("entering");
      const r = this.rect(this.nodes.get(phase.id));
      const z = this.endZoom();
      const target = { x: this.size.w / 2 - (r.x + r.w / 2) * z, y: this.size.h / 2 - (r.y + r.h / 2) * z, z };
      this.transition(1, target, () => this.finishEnter());
    }

    cameraPath(from, to, anchor) {
      // Zoom runs in log space, so every frame scales by the same ratio, and the
      // anchor travels on a straight screen line instead of swinging out first.
      const s0 = { x: from.x + anchor.x * from.z, y: from.y + anchor.y * from.z };
      const s1 = { x: to.x + anchor.x * to.z, y: to.y + anchor.y * to.z };
      const l0 = Math.log(from.z), l1 = Math.log(to.z);
      return (e, out) => {
        const z = Math.exp(mix(l0, l1, e));
        out.x = mix(s0.x, s1.x, e) - anchor.x * z;
        out.y = mix(s0.y, s1.y, e) - anchor.y * z;
        out.z = z;
      };
    }

    centerAnchor(camera) {
      return { x: (this.size.w / 2 - camera.x) / camera.z, y: (this.size.h / 2 - camera.y) / camera.z };
    }

    run(duration, step, finish, direction = 0, ease = this.ease) {
      // Shared driver for every camera flight; direct input cancels it through stop().
      this.stop();
      this.wheelLive = false;
      if (!this.A || this.reduced) { finish(); return; }
      const state = { t: 0 };
      this.motionDirection = direction;
      this.motionEnd = finish;
      this.motion = this.A.animate(state, { t: 1, duration, ease, onUpdate: () => step(state.t), onComplete: () => {
        this.motion = null;
        this.motionEnd = null;
        this.motionDirection = 0;
        this.layers(false);
        finish();
      } });
    }

    transition(progress, camera, done) {
      const node = this.phase && this.nodes.get(this.phase.id);
      const r = node && this.rect(node);
      const path = this.cameraPath({ ...this.camera }, camera, r ? { x: r.x + r.w / 2, y: r.y + r.h / 2 } : this.centerAnchor(camera));
      const p0 = this.progress;
      const entering = progress > p0;
      this.run(entering ? ENTER_MS : EXIT_MS, (e) => {
        path(e, this.camera);
        this.progress = mix(p0, progress, e);
        this.render();
      }, () => {
        this.progress = progress;
        Object.assign(this.camera, camera);
        this.render();
        done();
      }, entering ? 1 : -1);
      if (this.motion) this.layers(true);
    }

    fly(camera, target, duration = FLY_MS, ease = this.ease) {
      const path = this.cameraPath({ ...camera }, target, this.centerAnchor(target));
      this.run(duration, (e) => { path(e, camera); this.render(); }, () => {
        this.flyGoal = null;
        Object.assign(camera, target);
        this.render();
      }, 0, ease);
      if (this.motion) this.flyGoal = target;
    }

    glide(dx, dy, duration = 220) {
      const camera = this.activeCamera();
      const base = this.motion && this.flyGoal ? this.flyGoal : camera;
      this.fly(camera, { x: base.x + dx, y: base.y + dy, z: camera.z }, duration, "out(3)");
    }

    finishEnter() {
      this.stop();
      // Leftover wheel momentum must not keep zooming the inner map.
      this.wheelLive = false;
      this.progress = 1;
      this.view("inside");
      this.live.textContent = `${this.phase.id}: ${this.phase.steps.length} Arbeitsschritte`;
      this.render();
      // The phase button becomes inert as its surface dissolves.
      this.viewport.focus({ preventScroll: true });
    }

    exit() {
      if (!this.phase || (this.motion && this.motionDirection < 0)) return;
      this.view("leaving");
      this.transition(0, this.origin, () => this.finishExit());
    }

    backOut() {
      // A zoom that stopped half-way returns to the overview around the same card.
      const r = this.rect(this.nodes.get(this.phase.id));
      const z = Math.min(this.camera.z, Math.min(WIDTH, this.size.w - 40) * 1.3 / WIDTH);
      const anchor = { x: r.x + r.w / 2, y: r.y + r.h / 2 };
      const sx = this.camera.x + anchor.x * this.camera.z, sy = this.camera.y + anchor.y * this.camera.z;
      this.view("leaving");
      this.transition(0, { x: sx - anchor.x * z, y: sy - anchor.y * z, z }, () => this.finishExit(false, false));
    }

    finishExit(focus = true, restore = true) {
      this.stop();
      if (restore && this.origin) Object.assign(this.camera, this.origin);
      this.progress = 0;
      this.phase = null;
      this.view("overview");
      delete this.root.dataset.roadmapPhase;
      this.crumb.textContent = "Meilensteine";
      this.live.textContent = "Meilensteine";
      this.render();
      if (focus && this.returnFocus) this.returnFocus.focus({ preventScroll: true });
    }

    stop() {
      if (this.motion) { this.motion.cancel(); this.motion = null; }
      this.motionEnd = null;
      this.motionDirection = 0;
      this.flyGoal = null;
      if (!this.wheelLive) this.layers(false);
    }

    layers(on) {
      // Both map levels move as cached layers while a flight or gesture runs;
      // dropping the hint afterwards lets the browser redraw the text sharply.
      this.css(this.phaseWorld, "willChange", on ? "transform" : "");
      this.css(this.stepWorld, "willChange", on ? "transform" : "");
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
      const from = new Map();
      for (const [i, phase] of this.phases.entries()) {
        from.set(phase.id, { ...this.positions.overview[phase.id] });
        this.positions.overview[phase.id] = { x: POSITIONS[i][0], y: POSITIONS[i][1] };
        this.place(this.nodes.get(phase.id), this.positions.overview[phase.id]);
      }
      this.positions.steps = {};
      this.save();
      const target = this.fitCamera(this.nodes);
      if (this.phase) {
        this.makeSteps(this.phase);
        this.camera = target;
        this.connect(this.nodes, this.lines);
        this.render();
        return;
      }
      // Cards slide home together while the camera frames the default layout.
      const path = this.cameraPath({ ...this.camera }, target, this.centerAnchor(target));
      const move = (e) => {
        for (const [id, node] of this.nodes) {
          const a = from.get(id), b = this.positions.overview[id];
          this.place(node, { x: mix(a.x, b.x, e), y: mix(a.y, b.y, e) });
        }
        this.connect(this.nodes, this.lines);
      };
      move(0);
      this.run(RESET_MS, (e) => { move(e); path(e, this.camera); this.render(); }, () => {
        move(1);
        Object.assign(this.camera, target);
        this.render();
      });
    }

    fitCurrent() {
      if (this.inside()) {
        const target = this.fitCamera(this.stepNodes, true);
        this.innerBaseZoom = target.z;
        this.fly(this.innerCamera, target);
      } else {
        if (this.phase) this.finishExit(false, false);
        this.fly(this.camera, this.fitCamera(this.nodes));
      }
    }

    showTables(show) {
      this.stop();
      this.wheelLive = false;
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
      const z = clamp(camera.z * factor, MIN_ZOOM, MAX_ZOOM);
      const ratio = z / camera.z;
      camera.x = point.x - (point.x - camera.x) * ratio;
      camera.y = point.y - (point.y - camera.y) * ratio;
      camera.z = z;
    }

    applyZoom(factor, point, target) {
      if (this.motion) this.stop();
      if (this.inside()) {
        if (factor < 1 && this.innerCamera.z <= this.innerBaseZoom * 1.04) { this.exit(); return; }
        this.zoom(this.innerCamera, factor, point);
        this.render();
        return;
      }
      const before = { ...this.camera };
      this.zoom(this.camera, factor, point);
      const reference = Math.min(WIDTH, this.size.w - 40);
      const progress = smooth(reference * 1.35, reference * 2.6, WIDTH * this.camera.z);
      if (!this.phase && factor > 1 && progress > 0) {
        const node = target && target.closest ? target.closest(".roadmap-node[data-phase]") : null;
        const phase = node && this.phases.find((p) => p.id === node.dataset.phase);
        if (phase) {
          this.prepare(phase);
          this.origin = before;
          // Already past the threshold (zoomed in on the background): fly instead of jumping.
          if (progress >= 0.999) { this.enter(phase); return; }
        }
      }
      if (this.phase) {
        this.progress = progress;
        if (progress >= 0.999) { this.finishEnter(); return; }
        if (progress === 0) { this.finishExit(false, false); return; }
        this.view("entering");
      }
      this.render();
    }

    smoothZoom(factor, point, target) {
      this.zoomDirection = Math.sign(factor - 1);
      clearTimeout(this.settleTimer);
      this.settleTimer = setTimeout(() => this.settle(), WHEEL_MS + 90);
      if (!this.zoomer || this.reduced) { this.applyZoom(factor, point, target); return; }
      if (!this.wheelLive) {
        this.wheelLive = true;
        this.lastZoom = this.zoomState.z;
        this.zoomGoal = this.zoomState.z;
        this.layers(true);
      }
      this.wheelPoint = point;
      this.wheelTarget = target;
      // Clamp the goal so zooming past a limit never has to be "unwound" later.
      const camera = this.activeCamera();
      const pending = this.zoomGoal / this.zoomState.z;
      const final = clamp(camera.z * pending * factor, MIN_ZOOM, MAX_ZOOM);
      this.zoomGoal = this.zoomState.z * final / camera.z;
      this.zoomer.z(this.zoomGoal);
    }

    wheelStep() {
      const z = this.zoomState.z;
      const factor = z / this.lastZoom;
      this.lastZoom = z;
      if (!this.wheelLive || !Number.isFinite(factor) || Math.abs(factor - 1) < 1e-6) return;
      this.applyZoom(factor, this.wheelPoint, this.wheelTarget);
    }

    settle() {
      clearTimeout(this.settleTimer);
      this.settleTimer = null;
      this.wheelLive = false;
      if (!this.motion) this.layers(false);
      if (!this.phase || this.motion || this.progress >= 0.999) return;
      if (this.progress <= 0) this.finishExit(false, false);
      else if (this.zoomDirection > 0 && this.progress > 0.12) this.enter(this.phase);
      else this.backOut();
    }

    zoomButton(direction) {
      const center = { x: this.size.w / 2, y: this.size.h / 2 };
      let node = this.phase && this.nodes.get(this.phase.id);
      if (!node && direction > 0) {
        node = Array.from(this.nodes.values()).sort((a, b) => {
          const ra = this.transformedRect(a), rb = this.transformedRect(b);
          return Math.hypot(ra.x + ra.w / 2 - center.x, ra.y + ra.h / 2 - center.y) - Math.hypot(rb.x + rb.w / 2 - center.x, rb.y + rb.h / 2 - center.y);
        })[0];
      }
      this.smoothZoom(direction > 0 ? 1.5 : 1 / 1.5, center, node);
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
        const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.size.h : 1;
        const dx = event.deltaX * unit, dy = event.deltaY * unit;
        // Sideways trackpad swipes pan; vertical wheel and trackpad pinch (ctrlKey) zoom.
        if (!event.ctrlKey && Math.abs(dx) > Math.abs(dy) * 1.5) {
          if (this.motion) this.stop();
          const camera = this.activeCamera();
          camera.x -= dx;
          this.requestRender();
          return;
        }
        const factor = Math.exp(clamp(-dy * (event.ctrlKey ? 0.01 : 0.0022), -1.2, 1.2));
        // Momentum that keeps pushing in the direction of a running level change is absorbed.
        if (this.motion && Math.sign(factor - 1) === this.motionDirection) return;
        this.smoothZoom(factor, this.point(event), event.target);
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
          const inside = this.inside();
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
          this.glide(event.key === "ArrowLeft" ? 60 : event.key === "ArrowRight" ? -60 : 0,
            event.key === "ArrowUp" ? 60 : event.key === "ArrowDown" ? -60 : 0);
        }
      });
      this.listen(this.reducedQuery, "change", (event) => {
        this.reduced = event.matches;
        this.makeReveal();
        // A running flight jumps to its end; its finish step sets the final level.
        const end = this.motionEnd;
        this.stop();
        if (end) end();
        else this.render();
      });
    }

    pointerDown(event) {
      if (event.button !== 0 && event.pointerType !== "touch") return;
      const point = this.point(event);
      this.pointers.set(event.pointerId, point);
      if (this.pointers.size === 2) {
        this.stop();
        this.wheelLive = false;
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
      this.wheelLive = false;
      const inside = this.inside();
      const camera = inside ? this.innerCamera : this.camera;
      const id = handle && handle.dataset.roadmapDrag;
      const positions = inside ? this.positions.steps[this.phase.id] : this.positions.overview;
      this.drag = { id, inside, pointer: event.pointerId, point, camera: { ...camera }, pos: id ? { ...positions[id] } : null,
        moved: false, samples: [{ t: event.timeStamp, x: point.x, y: point.y }] };
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
        if (distance > 0 && this.pinch.distance > 0 && distance !== this.pinch.distance) {
          this.zoomDirection = Math.sign(distance - this.pinch.distance);
          this.applyZoom(distance / this.pinch.distance, center, this.pinch.target);
        }
        this.pinch.distance = distance;
        event.preventDefault(); return;
      }
      const drag = this.drag;
      if (!drag || drag.pointer !== event.pointerId) return;
      const dx = point.x - drag.point.x, dy = point.y - drag.point.y;
      drag.samples.push({ t: event.timeStamp, x: point.x, y: point.y });
      if (drag.samples.length > 5) drag.samples.shift();
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
      this.requestRender();
    }

    pointerUp(event) {
      this.pointers.delete(event.pointerId);
      if (this.pinch && this.pointers.size < 2) { this.pinch = null; this.settle(); }
      const drag = this.drag;
      if (drag && drag.pointer === event.pointerId) {
        if (drag.id && drag.moved) this.save();
        this.drag = null;
        // A flicked background keeps a little momentum and coasts to rest.
        const first = drag.samples[0], last = drag.samples[drag.samples.length - 1];
        const dt = last.t - first.t;
        if (!drag.id && drag.moved && dt > 0 && event.timeStamp - last.t < 80) {
          const vx = (last.x - first.x) / dt, vy = (last.y - first.y) / dt;
          if (Math.hypot(vx, vy) > 0.25) this.glide(clamp(vx * 200, -600, 600), clamp(vy * 200, -600, 600), 600);
        }
      }
      if (this.viewport.hasPointerCapture(event.pointerId)) this.viewport.releasePointerCapture(event.pointerId);
      this.viewport.classList.remove("roadmap-viewport--dragging");
      this.requestRender();
    }

    dispose() {
      this.disposed = true;
      this.stop();
      clearTimeout(this.settleTimer);
      if (this.zoomer) this.zoomer.revert();
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
