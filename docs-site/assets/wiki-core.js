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

  // Cloudflare Pages leitet /x.html auf /x und /index.html auf / um; ein
  // Seitenvergleich darf deshalb nicht am rohen Pfad mit „.html“ hängen.
  function pageKey(url) {
    return new URL(url, window.location.href).pathname.replace(/\.html$/, "").replace(/\/index$/, "/");
  }

  function isPage(path) {
    return pageKey(window.location.href) === pageKey(siteUrl(path));
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

  let glossaryPromise;
  function loadGlossary() {
    if (!glossaryPromise) {
      const path = "docs/anleitung/glossar.html";
      const source = isPage(path) ? Promise.resolve(document) : loadHtml(path);
      // Parse the current glossary before its A–Z enhancement moves the entries.
      glossaryPromise = source.then((doc) => {
        const entries = [];
        let category = "";
        for (const heading of doc.querySelectorAll(".md-content__inner h2, .md-content__inner h3")) {
          const title = heading.cloneNode(true);
          title.querySelectorAll("a.headerlink").forEach((link) => link.remove());
          if (heading.tagName === "H2") { category = title.textContent.trim(); continue; }
          const short = heading.nextElementSibling;
          const meta = short?.nextElementSibling;
          const fields = /^Weg:\s*(.*?) · (?:Auch:\s*(.*?) · )?Quelle:/.exec(meta?.textContent.trim() || "");
          if (!heading.id || short?.tagName !== "P" || meta?.tagName !== "P" || !fields) continue;
          entries.push({
            id: heading.id, term: title.textContent.trim(), category,
            aliases: fields[2] ? fields[2].split(",").map((alias) => alias.trim()) : [],
            weg: fields[1], short: short.textContent.trim(),
            code: title.children.length === 1 && title.firstElementChild.tagName === "CODE"
              && title.textContent.trim() === title.firstElementChild.textContent,
          });
        }
        return entries;
      }).catch((error) => { glossaryPromise = null; throw error; });
    }
    return glossaryPromise;
  }

  function termMatcher(entries) {
    const exact = new Map();
    const folded = new Map();
    const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    for (const entry of entries) {
      for (const name of [entry.term, ...entry.aliases]) {
        const map = /^[\p{Lu}\p{Nd}]{1,5}$/u.test(name) ? exact : folded;
        map.set(map === exact ? name : name.toLocaleLowerCase("de"), entry);
      }
    }
    const patterns = [exact, folded].map((map, index) => {
      const names = [...map.keys()].sort((a, b) => b.length - a.length).map(escape);
      return names.length ? new RegExp(`(?<![\\p{L}\\p{N}_])(?=(${names.join("|")})(?![\\p{L}\\p{N}_]))`, index ? "giu" : "gu") : null;
    });
    return (text) => {
      const hits = [];
      patterns.forEach((pattern, index) => {
        if (!pattern) return;
        pattern.lastIndex = 0;
        for (const match of text.matchAll(pattern)) {
          let entry = index ? folded.get(match[1].toLocaleLowerCase("de")) : exact.get(match[1]);
          // Unicode /iu also folds characters such as long s, which lowercasing
          // alone does not map to the same dictionary key.
          if (!entry && index) entry = [...folded].find(([name]) => new RegExp(`^${escape(name)}$`, "iu").test(match[1]))?.[1];
          if (!entry) continue;
          hits.push({ entry, index: match.index, length: match[1].length, match: match[1] });
        }
      });
      hits.sort((a, b) => a.index - b.index || b.length - a.length);
      let end = 0;
      return hits.filter((hit) => {
        if (hit.index < end) return false;
        end = hit.index + hit.length;
        return true;
      });
    };
  }

  function openSearch(query) {
    // Zensical mounts its combobox in an open shadow root and has no ?q= reader.
    const roots = [document, ...Array.from(document.body.children, (child) => child.shadowRoot).filter(Boolean)];
    const input = roots.map((root) => root.querySelector('input[role="combobox"], input[data-md-component="search-query"]')).find(Boolean);
    if (!input) return;
    let visible = Boolean(input.getClientRects().length) && getComputedStyle(input).pointerEvents !== "none";
    for (let parent = input; parent; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      if (style.visibility === "hidden" || style.display === "none") visible = false;
    }
    if (!visible) {
      const toggle = document.querySelector("#__search");
      if (toggle) toggle.click();
    }
    requestAnimationFrame(() => {
      input.focus();
      input.value = query;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
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
      }).catch(() => { oqIndexPromise = null; return new Map(); });
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
      }).catch(() => { phasesPromise = null; return new Map(); });
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

  window.wiki = { onPage, siteUrl, pageKey, isPage, loadHtml, loadJson, loadGlossary, termMatcher, openSearch,
    loadOqIndex, loadPhases, OQ_STATUS, make, icon };

  if (typeof document$ !== "undefined") document$.subscribe(buildPage);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", buildPage);
  else buildPage();
})();
