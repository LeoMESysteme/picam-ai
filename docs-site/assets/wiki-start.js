/* Turn the start page's Markdown into three paths and a compact directory. */
(function () {
  "use strict";

  const { onPage, siteUrl, make, icon } = window.wiki;
  const ways = ["bedienen", "konfigurieren", "entwickeln"];

  function isStartPage(url) {
    const path = new URL(url).pathname;
    return path === new URL(siteUrl("index.html")).pathname || path === new URL(siteUrl("./")).pathname;
  }

  function standRow(host) {
    const list = host?.querySelector(":scope > ul");
    if (!list) return;
    const row = make("div", "wiki-stand-row");
    for (const entry of list.children) {
      const strong = entry.querySelector("strong");
      if (!strong) return;
      const item = make("div", "wiki-stand-item");
      const label = make("span", "wiki-stand-label", strong.textContent.trim().replace(/:$/, ""));
      strong.remove();
      const text = make("span", "wiki-stand-text");
      text.append(...entry.childNodes);
      item.append(label, text);
      row.append(item);
    }
    list.replaceWith(row);
  }

  function linkHint(entry) {
    const link = entry.querySelector(":scope > a[href]");
    if (!link || !link.nextSibling) return;
    const hint = make("span", "wiki-weg-hint");
    // Move the suffix as nodes so links and inline markup survive.
    while (link.nextSibling) hint.append(link.nextSibling);
    if (hint.firstChild?.nodeType === Node.TEXT_NODE) {
      hint.firstChild.textContent = hint.firstChild.textContent.replace(/^\s*—\s*/, "");
    }
    entry.append(hint);
  }

  function paths(host) {
    if (!host || host.querySelector(".wiki-weg")) return;
    const headings = [...host.querySelectorAll(":scope > h3")];
    if (headings.length !== ways.length) return;
    headings.forEach((heading, index) => {
      const section = make("section", "wiki-weg");
      section.id = "weg-" + ways[index];
      const symbol = icon(ways[index]);
      symbol.setAttribute("width", "20");
      symbol.setAttribute("height", "20");
      heading.prepend(symbol);
      heading.before(section);
      section.append(heading);
      while (section.nextElementSibling && section.nextElementSibling.tagName !== "H3") {
        section.append(section.nextElementSibling);
      }
      for (const list of section.querySelectorAll("ul")) {
        list.classList.add("wiki-weg-links");
        [...list.children].forEach(linkHint);
      }
    });
  }

  function directory(article) {
    const heading = article.querySelector("h2#alle-seiten");
    if (!heading || heading.nextElementSibling?.matches("details.wiki-allpages")) return;
    const details = make("details", "wiki-allpages");
    heading.after(details);
    while (details.nextElementSibling && details.nextElementSibling.tagName !== "H2") {
      details.append(details.nextElementSibling);
    }
    // Heading permalinks and automatically marked terms are not page entries.
    const count = details.querySelectorAll("a[href]:not(.headerlink):not(.wiki-term)").length;
    details.prepend(make("summary", "", `Alle ${count} Seiten anzeigen`));
  }

  onPage((article) => {
    if (!isStartPage(window.location.href)) return;
    standRow(article.querySelector(".wiki-stand"));
    paths(article.querySelector(".wiki-wege"));
    directory(article);
  });
})();
