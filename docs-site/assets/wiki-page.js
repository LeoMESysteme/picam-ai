/* Enhance the template marker with reading time and reading-path links. */
(function () {
  "use strict";

  const { onPage, siteUrl, make, icon } = window.wiki;

  function convention(article, label, firstOnly = false) {
    for (const paragraph of article.querySelectorAll("p")) {
      const markers = firstOnly ? [paragraph.firstElementChild] : Array.from(paragraph.querySelectorAll("strong"));
      const link = paragraph.querySelector("a[href]");
      if (link && markers.some((marker) => marker && marker.matches("strong") && marker.textContent === label)) {
        return { paragraph, link };
      }
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
})();
