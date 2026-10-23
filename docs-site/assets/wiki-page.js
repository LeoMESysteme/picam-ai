/* Enhance the template marker with reading time and reading-path links. */
(function () {
  "use strict";

  const { onPage, siteUrl, make, icon, loadOqIndex, loadPhases, hint } = window.wiki;

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
    way.href = siteUrl("index.html") + "#weg-" + weg;
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
    return () => { disposed = true; };
  });
})();
