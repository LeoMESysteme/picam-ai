/* Glossary controls and a shared, chunked occurrence index. */
(function () {
  "use strict";
  const wiki = window.wiki;
  const { make, icon, siteUrl } = wiki;
  const glossaryPath = "docs/anleitung/glossar.html";
  const contexts = new WeakMap();
  let occurrencePromise;

  function htmlText(html) {
    const entities = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
    return html.replace(/<\/(?:p|div|li|h[1-6]|tr)>|<br\s*\/?>/gi, " ")
      .replace(/<[^>]*>/g, "")
      .replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (full, entity) => {
        if (entity[0] !== "#") return entities[entity.toLowerCase()] || full;
        const point = entity[1].toLowerCase() === "x" ? parseInt(entity.slice(2), 16) : Number(entity.slice(1));
        return point > 0 && point <= 0x10ffff ? String.fromCodePoint(point) : full;
      }).replace(/\s+/g, " ").trim();
  }

  function chunks(items, process) {
    return new Promise((resolve, reject) => {
      let offset = 0;
      function next() {
        try {
          const end = Math.min(offset + 200, items.length);
          for (; offset < end; offset += 1) process(items[offset], offset);
          if (offset < items.length) setTimeout(next, 0);
          else resolve();
        } catch (error) { reject(error); }
      }
      next();
    });
  }

  async function buildOccurrenceIndex(entries, documents) {
    const wordIndex = new Map();
    const records = [];
    const pageTitles = new Map();
    const occurrences = new Map(entries.map((entry) => [entry.id, []]));
    const words = (text) => text.toLocaleUpperCase("de").toLocaleLowerCase("de").match(/[\p{L}\p{N}_]+/gu) || [];
    await chunks(documents, (document) => {
      const { location, title, path } = document;
      if (location.replace(/^\.\//, "").startsWith(glossaryPath)) return;
      const page = location.split("#")[0];
      if (!location.includes("#")) pageTitles.set(page, title);
      const record = { location, title, page, path, text: htmlText(document.text || "") };
      const index = records.push(record) - 1;
      for (const word of new Set(words(record.text))) {
        if (!wordIndex.has(word)) wordIndex.set(word, []);
        wordIndex.get(word).push(index);
      }
    });
    // The inverted first-word index selects documents once; a combined matcher
    // checks all phrases without rescanning the whole wiki for each term.
    const candidates = new Set();
    for (const entry of entries) {
      for (const name of [entry.term, ...entry.aliases]) {
        for (const index of wordIndex.get(words(name)[0]) || []) candidates.add(index);
      }
    }
    const match = wiki.termMatcher(entries);
    await chunks([...candidates], (index) => {
      const record = records[index];
      record.pageTitle = pageTitles.get(record.page) || record.path?.at(-1) || record.title;
      for (const hit of match(record.text)) {
        occurrences.get(hit.entry.id).push({ record, index: hit.index, length: hit.length, match: hit.match });
      }
    });
    performance.mark("wiki-occ-index-ready");
    return occurrences;
  }
  // Exposed for the offline verification against the real search.json as well.
  wiki.buildOccurrenceIndex = buildOccurrenceIndex;

  function loadOccurrences(entries) {
    if (!occurrencePromise) {
      occurrencePromise = wiki.loadJson("search.json").then((index) => buildOccurrenceIndex(entries, index.items))
        .catch((error) => { occurrencePromise = null; throw error; });
    }
    return occurrencePromise;
  }

  function contextNodes(hit) {
    const { record: { text }, index, length } = hit;
    let start = Math.max(0, index - 90);
    let end = Math.min(text.length, index + length + 90);
    const left = text.slice(start, index);
    const boundaries = [...left.matchAll(/[.!?]\s+/g)];
    const boundary = boundaries.at(-1);
    if (boundary) start += boundary.index + boundary[0].length;
    const rightBoundary = /[.!?](?=\s|$)/.exec(text.slice(index + length, end));
    if (rightBoundary) end = index + length + rightBoundary.index + 1;
    const content = make("p");
    const sentenceStart = start === 0 || /[.!?]\s+$/.test(text.slice(0, start));
    const sentenceEnd = end === text.length || /[.!?]$/.test(text.slice(0, end));
    content.append((sentenceStart ? "" : "…") + text.slice(start, index),
      make("mark", "", text.slice(index, index + length)), text.slice(index + length, end) + (sentenceEnd ? "" : "…"));
    return content;
  }

  wiki.hint.register("fundstelle", (link) => {
    const hit = contexts.get(link);
    if (!hit) return null;
    const content = make("div");
    content.append(make("strong", "", `${hit.record.pageTitle} › ${hit.record.title}`), contextNodes(hit));
    return content;
  });

  function searchLink(query) {
    const link = make("a", "wiki-occ-search", "Alle Treffer in der Suche");
    // Keep a usable destination even if the theme search has not mounted yet.
    link.href = siteUrl("index.html");
    link.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      wiki.openSearch(query);
    });
    return link;
  }

  function counted(count, singular, plural) {
    return `${count} ${count === 1 ? singular : plural}`;
  }

  function occurrenceList(entry, hits) {
    const container = make("div", "wiki-occ");
    const pages = new Map();
    for (const hit of hits) {
      if (!pages.has(hit.record.page)) pages.set(hit.record.page, []);
      pages.get(hit.record.page).push(hit);
    }
    container.append(make("p", "wiki-occ-count", hits.length
      ? `Vorkommen: ${counted(hits.length, "Stelle", "Stellen")} auf ${counted(pages.size, "Seite", "Seiten")}` : "Keine weiteren Vorkommen im Wiki."));
    const working = (path) => /^(?:CHANGELOG|TODO|AGENTS|CLAUDE)\.html$|^docs\/(?:superpowers\/|PLAN_)/.test(path);
    const groups = [...pages.entries()].sort(([a, aa], [b, bb]) =>
      Number(working(a)) - Number(working(b)) || bb.length - aa.length || aa[0].record.pageTitle.localeCompare(bb[0].record.pageTitle, "de"));
    const list = make("ul", "wiki-occ-pages");
    const rest = make("ul", "wiki-occ-pages");
    groups.forEach(([page, places], index) => {
      const group = make("li", "wiki-occ-page");
      const title = make("a", "wiki-occ-title", places[0].record.pageTitle);
      title.href = siteUrl(page);
      group.append(title, make("span", "wiki-occ-number", ` (${places.length})`));
      const locations = make("ul", "wiki-occ-locations");
      for (const hit of places.slice(0, 5)) {
        const item = make("li");
        const link = make("a", "", hit.record.title);
        link.href = siteUrl(hit.record.location) + (hit.record.location.includes("#") ? ":~:text=" : "#:~:text=") + encodeURIComponent(hit.match);
        link.dataset.hint = "fundstelle";
        contexts.set(link, hit);
        item.append(link);
        locations.append(item);
      }
      if (places.length > 5) {
        const more = make("a", "", `+ ${places.length - 5} weitere`);
        more.href = siteUrl(page);
        const item = make("li");
        item.append(more);
        locations.append(item);
      }
      group.append(locations);
      (index < 8 ? list : rest).append(group);
    });
    if (list.childElementCount) container.append(list);
    if (groups.length > 8) {
      const details = make("details");
      const remaining = groups.slice(8).reduce((sum, [, places]) => sum + places.length, 0);
      details.append(make("summary", "", `und ${counted(remaining, "weitere Stelle", "weitere Stellen")} auf ${counted(groups.length - 8, "Seite", "Seiten")}`), rest);
      container.append(details);
    }
    container.append(searchLink(entry.term));
    return container;
  }

  function letter(term) {
    const first = term.normalize("NFD").replace(/\p{M}/gu, "").charAt(0).toUpperCase();
    return /^[A-Z]$/.test(first) ? first : "#";
  }

  wiki.onPage((article) => {
    if (!wiki.isPage(glossaryPath)) return;
    let disposed = false;
    let observer;
    const listeners = new AbortController();
    const listen = (target, name, handler) => target.addEventListener(name, handler, { signal: listeners.signal });
    wiki.loadGlossary().then((entries) => {
      if (disposed || article.querySelector(".wiki-glossar-controls")) return;
      const firstCategory = article.querySelector("h2");
      const controls = make("div", "wiki-glossar-controls");
      const row = make("div", "wiki-glossar-row");
      const input = make("input", "wiki-glossar-filter");
      input.type = "search";
      input.setAttribute("aria-label", "Begriffe filtern");
      input.placeholder = "Begriff oder Abkürzung filtern";
      const wayGroup = make("div", "wiki-glossar-wege");
      wayGroup.setAttribute("role", "group");
      wayGroup.setAttribute("aria-label", "Weg");
      const count = make("output", "wiki-glossar-count");
      count.setAttribute("aria-live", "polite");
      row.append(input, wayGroup, count);
      const az = make("nav", "wiki-glossar-az");
      az.setAttribute("aria-label", "Alphabet");
      controls.append(row, az);
      firstCategory.before(controls);
      const empty = make("div", "wiki-glossar-empty-wrap");
      const message = make("p", "wiki-glossar-empty");
      const fullSearch = make("button", "", "In der Volltextsuche suchen");
      fullSearch.type = "button";
      listen(fullSearch, "click", () => wiki.openSearch(input.value));
      empty.append(message, fullSearch);
      controls.after(empty);
      article.querySelectorAll(":scope > h2").forEach((heading) => { heading.hidden = true; });
      const sections = new Map();
      const pending = new Map();
      let occurrenceIndex;
      let firstRendered = false;
      let loading = true;
      let requestedJump = null;
      function renderOccurrences(section) {
        const entry = pending.get(section);
        if (disposed || !entry || !occurrenceIndex) return;
        section.querySelector('.wiki-occ[data-pending="true"]').replaceWith(occurrenceList(entry, occurrenceIndex.get(entry.id)));
        pending.delete(section);
        observer?.unobserve(section);
        if (!firstRendered) {
          performance.mark("wiki-occ-first-render");
          firstRendered = true;
        }
      }
      function jumpTo(anchor) {
        requestedJump = null;
        if (!anchor) return;
        const section = anchor.closest(".wiki-glossar-entry")
          || anchor.closest(".wiki-glossar-group")?.querySelector(".wiki-glossar-entry:not([hidden])");
        if (section) {
          if (!occurrenceIndex && loading) { requestedJump = anchor; return; }
          // Stabilize every preceding entry in DOM order before scrolling.
          for (const preceding of article.querySelectorAll(".wiki-glossar-entry")) {
            renderOccurrences(preceding);
            if (preceding === section) break;
          }
        }
        anchor.scrollIntoView({ block: "start", behavior: "instant" });
      }
      for (const entry of entries) {
        const heading = article.querySelector(`[id="${CSS.escape(entry.id)}"]`);
        const section = make("section", "wiki-glossar-entry");
        section.setAttribute("aria-labelledby", entry.id);
        heading.before(section);
        let node = heading;
        do {
          const next = node.nextSibling;
          section.append(node);
          node = next;
        } while (node && !(node.nodeType === Node.ELEMENT_NODE && node.matches("h2, h3")));
        const rawMeta = section.querySelector("h3 + p + p");
        const source = rawMeta.querySelector("a").cloneNode(true);
        const meta = make("div", "wiki-glossar-meta");
        const way = make("span", "wiki-chip wiki-chip--weg", entry.weg);
        way.prepend(icon(entry.weg.toLocaleLowerCase("de")));
        meta.append(way, make("span", "wiki-glossar-cat", entry.category));
        if (entry.aliases.length) meta.append(make("span", "wiki-glossar-aliases", `Auch: ${entry.aliases.join(", ")}`));
        const sourceLabel = make("span");
        sourceLabel.append("Quelle: ", source);
        meta.append(sourceLabel);
        rawMeta.replaceWith(meta);
        const placeholder = make("div", "wiki-occ");
        placeholder.dataset.pending = "true";
        section.append(placeholder);
        sections.set(entry.id, section);
        pending.set(section, entry);
      }
      const groups = new Map();
      const letters = ["#", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
      for (const initial of letters) {
        const items = entries.filter((entry) => letter(entry.term) === initial).sort((a, b) => a.term.localeCompare(b.term, "de"));
        if (items.length) {
          const group = make("div", "wiki-glossar-group");
          const heading = make("h2", "wiki-glossar-letter", initial);
          heading.id = "buchstabe-" + (initial === "#" ? "zeichen" : initial.toLowerCase());
          group.append(heading, ...items.map((entry) => sections.get(entry.id)));
          groups.set(initial, group);
          article.append(group);
        }
        const button = make("button", "", initial);
        button.type = "button";
        button.disabled = !items.length;
        listen(button, "click", () => {
          const first = groups.get(initial)?.querySelector(".wiki-glossar-entry:not([hidden]) h3");
          jumpTo(first);
        });
        az.append(button);
      }
      let activeWay = "Alle";
      function filter(renderMatch = false) {
        let visible = 0;
        const query = input.value.trim().toLocaleLowerCase("de");
        for (const entry of entries) {
          const section = sections.get(entry.id);
          const text = [entry.term, ...entry.aliases, entry.short].join(" ").toLocaleLowerCase("de");
          section.hidden = !(text.includes(query) && (activeWay === "Alle" || activeWay === entry.weg));
          if (!section.hidden) visible += 1;
        }
        for (const button of az.children) {
          const group = groups.get(button.textContent);
          const visibleGroup = group?.querySelector(".wiki-glossar-entry:not([hidden])");
          if (group) group.hidden = !visibleGroup;
          button.disabled = !visibleGroup;
        }
        count.textContent = `${visible} von ${counted(entries.length, "Begriff", "Begriffen")}` + (loading ? " · Vorkommen werden ermittelt …" : "");
        empty.hidden = visible > 0;
        message.textContent = `Kein Begriff passt zu „${input.value}“.`;
        if (renderMatch) jumpTo(article.querySelector(".wiki-glossar-entry:not([hidden]) h3"));
      }
      for (const way of ["Alle", "Bedienen", "Konfigurieren", "Entwickeln"]) {
        const button = make("button", "", way);
        button.type = "button";
        button.setAttribute("aria-pressed", String(way === activeWay));
        listen(button, "click", () => {
          activeWay = way;
          for (const sibling of wayGroup.children) sibling.setAttribute("aria-pressed", String(sibling === button));
          filter(true);
        });
        wayGroup.append(button);
      }
      listen(input, "input", () => filter(true));
      filter();
      // Preserve deep links after the alphabetical reordering has moved headings.
      function jumpToAnchor() {
        let anchor;
        try {
          anchor = document.getElementById(decodeURIComponent(window.location.hash.slice(1).split(":~:")[0]));
        } catch { /* Ignore malformed percent encoding in the hash. */ }
        if (!anchor || !article.contains(anchor)) { requestedJump = null; return; }
        jumpTo(anchor);
      }
      listen(window, "hashchange", jumpToAnchor);
      jumpToAnchor();
      loadOccurrences(entries).then((index) => {
        if (disposed) return;
        occurrenceIndex = index;
        observer = new IntersectionObserver((intersections) => {
          for (const item of intersections) {
            if (item.isIntersecting) renderOccurrences(item.target);
          }
        }, { rootMargin: "800px 0px" });
        if (requestedJump) jumpTo(requestedJump);
        for (const section of pending.keys()) observer.observe(section);
      }).catch(() => {
        if (!disposed) controls.after(make("p", "wiki-glossar-status", "Vorkommen nicht verfügbar: Suchindex konnte nicht geladen werden."));
      }).finally(() => {
        if (!disposed) {
          loading = false;
          filter();
          if (requestedJump) jumpTo(requestedJump);
        }
      });
    }).catch(() => {
      if (!disposed) article.querySelector("h1").after(make("p", "wiki-glossar-status", "Vorkommen nicht verfügbar: Glossar konnte nicht geladen werden."));
    });
    return () => { disposed = true; observer?.disconnect(); listeners.abort(); };
  });
})();
