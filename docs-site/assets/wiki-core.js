/* Shared page lifecycle and helpers for the wiki enhancements. */
(function () {
  "use strict";

  // Capture the script URL before instant navigation changes the current page.
  const SITE_ROOT = new URL("../", document.currentScript.src);
  const callbacks = [];
  const htmlCache = new Map();
  const jsonCache = new Map();
  const OQ_STATUS = {
    "offen": "open",
    "in arbeit": "progress",
    "teilweise geklärt": "partial",
    "weitgehend geklärt": "partial",
    "geklärt": "resolved",
    "beantwortet": "resolved",
    "verworfen": "discarded",
  };
  const PHASE_STATUS = { erreicht: "resolved", teilweise: "partial", blockiert: "blocked", offen: "open" };
  let oqIndexPromise;
  let phasesPromise;
  const NS = "http://www.w3.org/2000/svg";
  const ICONS = {
    bedienen: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM10 8l6 4-6 4z",
    konfigurieren: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
    entwickeln: "M16 18l6-6-6-6M8 6l-6 6 6 6",
    projekt: "M4 22V4M4 4h13l-2 4 2 4H4",
    zeit: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 7v5l3 2",
    weiter: "M5 12h14M13 6l6 6-6 6",
    zurueck: "M19 12H5M11 6l-6 6 6 6",
  };
  let currentArticle = null;

  function run(entry) {
    try {
      const cleanup = entry.fn(currentArticle);
      entry.cleanup = typeof cleanup === "function" ? cleanup : null;
    } catch (error) {
      console.warn(`wiki: Seitenaufbau für ${entry.fn.name || "anonymen Baustein"} fehlgeschlagen`, entry.fn, error);
    }
  }

  function onPage(fn) {
    const entry = { fn, cleanup: null };
    callbacks.push(entry);
    if (currentArticle) run(entry);
  }

  function buildPage() {
    const article = document.querySelector(".md-content__inner");
    if (article === currentArticle) return;
    for (const entry of callbacks) {
      try {
        if (entry.cleanup) entry.cleanup();
      } catch (error) {
        console.warn(`wiki: Aufräumen für ${entry.fn.name || "anonymen Baustein"} fehlgeschlagen`, entry.fn, error);
      }
      entry.cleanup = null;
    }
    currentArticle = article;
    if (article) callbacks.forEach(run);
  }

  function siteUrl(path) {
    return new URL(path, SITE_ROOT).href;
  }

  function loadCached(cache, path, parse) {
    const url = siteUrl(path);
    if (!cache.has(url)) {
      cache.set(url, fetch(url).then((response) => {
        if (!response.ok) throw new Error(`${response.status}: ${url}`);
        return parse(response);
      }).catch((error) => {
        cache.delete(url);
        throw error;
      }));
    }
    return cache.get(url);
  }

  function loadHtml(path) {
    return loadCached(htmlCache, path, (response) =>
      response.text().then((html) => new DOMParser().parseFromString(html, "text/html")));
  }

  function loadJson(path) {
    return loadCached(jsonCache, path, (response) => response.json());
  }

  function loadOqIndex() {
    if (!oqIndexPromise) {
      oqIndexPromise = loadHtml("docs/open-questions.html").then((doc) => {
        const index = new Map();
        for (const row of doc.querySelector("table")?.querySelectorAll("tbody tr") || []) {
          if (row.cells.length !== 4) continue;
          const [id, focus, status, title] = Array.from(row.cells, (cell) => cell.textContent.trim());
          const number = /^OQ-(\d{2})$/.exec(id)?.[1];
          const key = status.toLocaleLowerCase("de");
          if (!number || !Object.hasOwn(OQ_STATUS, key)) continue;
          index.set(number, { id, title, status, category: OQ_STATUS[key], focus: focus === "Jetzt" });
        }
        return index;
      }).catch(() => new Map());
    }
    return oqIndexPromise;
  }

  function loadPhases() {
    if (!phasesPromise) {
      phasesPromise = loadHtml("docs/ROADMAP.html").then((doc) => {
        const phases = new Map();
        for (const row of doc.querySelector("table")?.querySelectorAll("tbody tr") || []) {
          if (row.cells.length !== 6) continue;
          const id = row.cells[0].textContent.trim();
          const state = /\b(erreicht|teilweise|blockiert|offen)\b/i.exec(row.cells[5].textContent)?.[0];
          if (!/^P[0-8]$/.test(id) || !state) continue;
          phases.set(id, {
            id, title: row.cells[1].textContent.trim(), state,
            category: PHASE_STATUS[state.toLocaleLowerCase("de")],
          });
        }
        return phases;
      }).catch(() => new Map());
    }
    return phasesPromise;
  }

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function icon(name) {
    const svg = document.createElementNS(NS, "svg");
    const attributes = {
      viewBox: "0 0 24 24", width: "14", height: "14", fill: "none",
      stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round",
      "stroke-linejoin": "round", "aria-hidden": "true",
    };
    for (const [key, value] of Object.entries(attributes)) svg.setAttribute(key, value);
    if (ICONS[name]) {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", ICONS[name]);
      svg.append(path);
    }
    return svg;
  }

  window.wiki = { onPage, siteUrl, loadHtml, loadJson, loadOqIndex, loadPhases, OQ_STATUS, make, icon };

  if (typeof document$ !== "undefined") document$.subscribe(buildPage);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", buildPage);
  else buildPage();
})();
