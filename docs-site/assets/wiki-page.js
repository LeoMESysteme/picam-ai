/* Enhance page markers, reference links and setting verdicts. */
(function () {
  "use strict";

  const { onPage, siteUrl, make, icon, loadOqIndex, loadPhases, hint } = window.wiki;

  function whenIdle(fn) {
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(fn, { timeout: 1500 });
      return () => window.cancelIdleCallback(id);
    }
    const id = setTimeout(fn, 200);
    return () => clearTimeout(id);
  }

  hint.register("term", async (link) => {
    const entries = await window.wiki.loadGlossary();
    const entry = entries.find((item) => item.id === new URL(link.href).hash.slice(1));
    if (!entry) return null;
    const content = make("div");
    const meta = make("div", "wiki-hint-meta");
    const way = make("span", "", entry.weg);
    way.prepend(icon(entry.weg.toLocaleLowerCase("de")));
    const target = make("a", "", "Im Glossar");
    target.href = link.href;
    meta.append(way, " · ", target);
    content.append(make("strong", "", entry.term), make("p", "", entry.short), meta);
    return content;
  });

  onPage((article) => {
    const path = new URL(window.location.href).pathname;
    if (/\/(?:docs\/anleitung\/glossar|CHANGELOG|TODO|AGENTS|CLAUDE)\.html$/.test(path)) return;
    let disposed = false;
    const cancelIdle = whenIdle(() => {
      if (disposed) return;
      window.wiki.loadGlossary().then((entries) => {
        if (disposed) return;
        const match = window.wiki.termMatcher(entries);
        const tasks = [];
        let seen = new Set();
        const excluded = "a, pre, summary, button, svg, .wiki-chart-figure, .fs-chart, .fs-status, [data-preview], .wiki-hint, .wiki-pagehead, .wiki-chip, .wiki-stand-label, .wiki-weg, .wiki-kette, .roadmap, nav, .md-typeset__table thead";
        const walker = document.createTreeWalker(article, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
          acceptNode(node) {
            const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
            if (element.closest(excluded)) return NodeFilter.FILTER_REJECT;
            for (let parent = element; parent && parent !== article; parent = parent.parentElement) {
              if ([...parent.classList].some((name) => name.startsWith("tour-"))) return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
          },
        });
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            if (node.matches("h2, h3")) seen = new Set();
            if (node.matches("code") && !node.closest("h1, h2, h3, h4, h5, h6")) {
              const hit = match(node.textContent).find((item) => item.entry.code && item.index === 0 && item.length === node.textContent.length);
              if (hit && !seen.has(hit.entry.id)) {
                seen.add(hit.entry.id);
                tasks.push({ node, hits: [hit], code: true });
              }
            }
            continue;
          }
          if (node.parentElement.closest("code, h1, h2, h3, h4, h5, h6")) continue;
          const hits = match(node.textContent).filter((hit) => {
            if (seen.has(hit.entry.id)) return false;
            seen.add(hit.entry.id);
            return true;
          });
          if (hits.length) tasks.push({ node, hits });
        }
        const linkFor = (hit) => {
          const link = make("a", "wiki-term", hit.match);
          link.href = siteUrl("docs/anleitung/glossar.html") + "#" + hit.entry.id;
          link.dataset.hint = "term";
          return link;
        };
        for (const { node, hits, code } of tasks) {
          if (code) {
            const link = linkFor(hits[0]);
            node.replaceWith(link);
            link.replaceChildren(node);
          } else {
            const fragment = document.createDocumentFragment();
            let start = 0;
            for (const hit of hits) {
              fragment.append(node.textContent.slice(start, hit.index), linkFor(hit));
              start = hit.index + hit.length;
            }
            fragment.append(node.textContent.slice(start));
            node.replaceWith(fragment);
          }
        }
        article.dataset.wikiTermsReady = "true";
      }).catch(() => { /* Definitions stay readable if the glossary cannot be loaded. */ });
    });
    return () => { disposed = true; cancelIdle(); };
  });

  function reference(link) {
    let url;
    try { url = new URL(link.href); }
    catch { return null; }
    const text = link.textContent.trim();
    if (url.pathname.endsWith("/docs/open-questions.html")) {
      const key = /^#oq-(\d{2})$/.exec(url.hash)?.[1] || /^OQ-(\d{2})$/.exec(text)?.[1];
      if (key) return { kind: "oq", key };
    }
    if (url.pathname.endsWith("/docs/ROADMAP.html")) {
      const key = /^(P[0-8])\b/.exec(text)?.[1];
      if (key) return { kind: "phase", key };
    }
    return null;
  }

  function chip(record) {
    return make("span", `wiki-chip wiki-chip--${record.category}`, record.status || record.state);
  }

  for (const kind of ["oq", "phase"]) {
    hint.register(kind, async (link) => {
      const ref = reference(link);
      if (!ref || ref.kind !== kind) return null;
      const index = await (kind === "oq" ? loadOqIndex() : loadPhases());
      const record = index.get(ref.key);
      if (!record) return null;
      const content = make("div");
      content.append(make("strong", "", `${record.id} · ${record.title}`), chip(record));
      if (record.focus) content.append(make("div", "wiki-hint-meta", "Im Fokus"));
      return content;
    });
  }

  function convention(article, label, firstOnly = false) {
    const selector = firstOnly
      ? ":scope > h1 ~ p:not(.wiki-pagehead)"
      : ":scope > p:not(.wiki-pagehead)";
    const paragraphs = article.querySelectorAll(selector);
    const paragraph = firstOnly ? paragraphs[0] : paragraphs[paragraphs.length - 1];
    const marker = paragraph?.firstElementChild;
    const link = paragraph?.querySelector("a[href]");
    if (link && marker && marker.matches("strong") && marker.textContent === label) {
      return { paragraph, link };
    }
    return null;
  }

  onPage((article) => {
    const verdicts = { nein: "Nein", nurwenn: "Nur wenn", ja: "Ja" };
    for (const row of article.querySelectorAll(".wiki-setting tbody tr")) {
      if (row.cells[0]?.textContent.trim() !== "Ändern?") continue;
      const cell = row.cells[1];
      const word = cell?.querySelector("strong");
      const label = word?.textContent.trim();
      const verdict = Object.entries(verdicts).find(([, text]) => text === label);
      if (!verdict || cell.querySelector(".wiki-verdict")) continue;
      const [suffix, text] = verdict;
      word.replaceWith(make("span", `wiki-verdict wiki-verdict--${suffix}`, text));
    }
  });

  onPage((article) => {
    const head = article.querySelector("p.wiki-pagehead");
    if (!head || head.dataset.ready === "true") return;
    const title = article.querySelector("h1");
    if (!title) return;
    const label = head.querySelector(".wiki-pagehead-weg").textContent.trim();
    const weg = head.dataset.weg;
    const text = article.cloneNode(true);
    text.querySelectorAll("pre, .wiki-pagehead").forEach((element) => element.remove());
    const words = text.textContent.trim().split(/\s+/).filter(Boolean).length;
    const minutes = Math.max(1, Math.ceil(words / 200));

    const way = make("a", "wiki-pagehead-weg", label);
    const anchor = ["bedienen", "konfigurieren", "entwickeln"].includes(weg) ? "#weg-" + weg : "";
    way.href = siteUrl("index.html") + anchor;
    way.prepend(icon(weg));
    const time = make("span", "wiki-pagehead-zeit", `${minutes} min Lesezeit`);
    time.prepend(icon("zeit"));
    const previous = convention(article, "Vorher lesen:", true);
    const next = convention(article, "Weiter mit:");
    head.replaceChildren(way, time);

    if (previous) {
      const link = make("a", "wiki-pagehead-vorher", `Vorher lesen: ${previous.link.textContent}`);
      link.setAttribute("href", previous.link.getAttribute("href"));
      link.prepend(icon("zurueck"));
      head.append(link);
    }
    if (next) {
      const link = make("a", "wiki-pagehead-weiter", `Weiter mit: ${next.link.textContent}`);
      link.setAttribute("href", next.link.getAttribute("href"));
      link.append(icon("weiter"));
      head.append(link);
      next.paragraph.classList.add("wiki-next");
    }
    title.after(head);
    head.dataset.ready = "true";
  });

  onPage((article) => {
    const path = new URL(window.location.href).pathname;
    if (path.endsWith("/docs/open-questions.html") || path.endsWith("/docs/ROADMAP.html")) return;
    let disposed = false;
    const cancelIdle = whenIdle(() => {
      if (disposed) return;
      for (const link of article.querySelectorAll("a[href]")) {
        if (link.dataset.wikiChip || link.closest("h1, h2, h3, h4, h5, h6, nav, .md-sidebar, .roadmap")) continue;
        const ref = reference(link);
        if (!ref) continue;
        (ref.kind === "oq" ? loadOqIndex() : loadPhases()).then((index) => {
          const record = index.get(ref.key);
          if (disposed || !record || link.dataset.wikiChip) return;
          link.after(chip(record));
          link.dataset.wikiChip = "1";
          link.dataset.hint = ref.kind;
        });
      }
    });
    return () => { disposed = true; cancelIdle(); };
  });
})();
