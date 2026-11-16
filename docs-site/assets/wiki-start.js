/* Startseite: geführter Weg zum ersten Messwert, zwei Vertiefungswege und ein
 * kompaktes Verzeichnis.
 *
 * - .wiki-pfad (#weg-bedienen): fünf ###-Schritte werden eine Schrittleiste
 *   (WAI-ARIA Tabs: Pfeiltasten, Pos1/Ende, automatische Auswahl). Schmal
 *   (< 45em) dieselben Schritte als Akkordeon. Ohne JavaScript bleibt die
 *   Markdown-Liste lesbar. Der Hash #weg-bedienen oder der Anker eines
 *   Schritts (Inhaltsverzeichnis) wählt den Schritt und scrollt zur Leiste.
 * - .wiki-wege: Konfigurieren und Entwickeln als zwei Spalten.
 * - „lebendig“ (wiki-messkette.css): Glasband, Linse gleitet zum gewählten
 *   Schritt, Fortschrittslinie füllt sich, Panelwechsel als kurze
 *   Überblendung in Wechselrichtung. Reduzierte Bewegung: kein Gleiten. */
(function () {
  "use strict";

  const { onPage, siteUrl, pageKey, make, icon } = window.wiki;
  const ways = ["konfigurieren", "entwickeln"];
  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const narrowQuery = matchMedia("(max-width: 45em)");
  const OUT = "cubic-bezier(.16, 1, .3, 1)";
  const lively = () => root.getAttribute("data-wiki-look") === "lebendig";

  function isStartPage(url) {
    return pageKey(url) === pageKey(siteUrl("index.html"));
  }

  function standRow(host) {
    const list = host?.querySelector(":scope > ul");
    if (!list) return;
    const entries = [...list.children];
    const labels = entries.map((entry) => [...entry.childNodes].find((node) =>
      node.nodeType !== Node.TEXT_NODE || node.textContent.trim()));
    if (entries.some((entry, index) => !entry.matches("li")
      || labels[index]?.nodeType !== Node.ELEMENT_NODE || !labels[index].matches("strong"))) return;
    const row = make("div", "wiki-stand-row");
    for (const [index, entry] of entries.entries()) {
      const strong = labels[index];
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

  function linkHint(entry, className) {
    const link = entry.querySelector(":scope > a[href]");
    if (!link || !link.nextSibling) return;
    const hint = make("span", className);
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
        [...list.children].forEach((entry) => linkHint(entry, "wiki-weg-hint"));
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

  /* ------------------------------------------------ geführter Weg ---- */

  function stepTitle(heading) {
    const copy = heading.cloneNode(true);
    copy.querySelectorAll("a.headerlink").forEach((link) => link.remove());
    return copy.textContent.trim();
  }

  function guidedPath(host) {
    if (!host || host.dataset.ready === "true") return null;
    const headings = [...host.querySelectorAll(":scope > h3")];
    if (headings.length < 2) return null;

    // Abschnitte: Überschrift plus alles bis zur nächsten Überschrift.
    const steps = headings.map((heading, index) => {
      const panel = make("section", "wiki-pfad-schritt");
      panel.id = `wiki-pfad-schritt-${index + 1}`;
      heading.before(panel);
      panel.append(heading);
      const body = make("div", "wiki-pfad-inhalt");
      body.id = `wiki-pfad-inhalt-${index + 1}`;
      panel.append(body);
      while (panel.nextElementSibling && panel.nextElementSibling.tagName !== "H3") body.append(panel.nextElementSibling);
      for (const list of body.querySelectorAll("ul")) {
        list.classList.add("wiki-pfad-links");
        [...list.children].forEach((entry) => linkHint(entry, "wiki-pfad-hint"));
      }
      const title = stepTitle(heading);
      heading.querySelectorAll("a.headerlink").forEach((link) => link.remove());
      // Akkordeon (schmal): die Überschrift trägt den Knopf.
      const toggle = make("button", "wiki-pfad-auf");
      toggle.type = "button";
      toggle.id = `wiki-pfad-auf-${index + 1}`;
      toggle.setAttribute("aria-controls", body.id);
      toggle.append(make("span", "wiki-pfad-nr", String(index + 1)), make("span", "wiki-pfad-name", title));
      heading.replaceChildren(toggle);
      return { heading, panel, body, title, toggle };
    });

    steps.forEach((step, index) => {
      const next = steps[index + 1];
      if (!next) return;
      const row = make("p", "wiki-pfad-weiter");
      const button = make("button", "wiki-pfad-weiter-knopf", `Weiter: ${next.title}`);
      button.type = "button";
      button.append(icon("weiter"));
      button.addEventListener("click", () => select(index + 1, { focus: true, scroll: true }));
      row.append(button);
      step.body.append(row);
    });

    // Schrittleiste (breit): Tabs mit Punkt und Titel, Spur und Linse dahinter.
    const bar = make("div", "wiki-pfad-leiste");
    bar.setAttribute("role", "tablist");
    bar.setAttribute("aria-label", "Schritte zum ersten Messwert");
    const track = make("span", "wiki-pfad-spur");
    track.setAttribute("aria-hidden", "true");
    const fill = make("i", "wiki-pfad-fuellung");
    track.append(fill);
    const lens = make("span", "wiki-pfad-linse");
    lens.setAttribute("aria-hidden", "true");
    bar.append(lens, track);
    const tabs = steps.map((step, index) => {
      const tab = make("button", "wiki-pfad-tab");
      tab.type = "button";
      tab.id = `wiki-pfad-tab-${index + 1}`;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", step.panel.id);
      tab.append(make("span", "wiki-pfad-nr", String(index + 1)), make("span", "wiki-pfad-name", step.title));
      tab.addEventListener("click", () => select(index, { focus: false }));
      bar.append(tab);
      return tab;
    });
    host.prepend(bar);
    host.dataset.ready = "true";
    host.style.setProperty("--wiki-pfad-n", String(steps.length));

    let selected = 0;
    let expanded = true;
    let mode = "";
    let entering = null;

    function placeLens(glide) {
      if (mode !== "tabs") return;
      const tab = tabs[selected];
      const box = bar.getBoundingClientRect();
      const rect = tab.getBoundingClientRect();
      if (!box.width) return;
      const jump = !glide || reduce.matches || !lively() || lens.dataset.on !== "true";
      if (jump) lens.style.transition = "none";
      lens.style.width = `${rect.width}px`;
      lens.style.height = `${rect.height}px`;
      lens.style.transform = `translate(${(rect.left - box.left).toFixed(1)}px, ${(rect.top - box.top).toFixed(1)}px)`;
      lens.dataset.on = "true";
      if (jump) { void lens.offsetWidth; lens.style.removeProperty("transition"); }
      // Spur von der Mitte des ersten bis zur Mitte des letzten Punkts.
      const dots = tabs.map((item) => item.querySelector(".wiki-pfad-nr").getBoundingClientRect());
      const first = dots[0];
      const last = dots[dots.length - 1];
      track.style.left = `${first.left + first.width / 2 - box.left}px`;
      track.style.width = `${Math.max(0, last.left - first.left)}px`;
      track.style.top = `${first.top + first.height / 2 - box.top - 1}px`;
      if (jump) fill.style.transition = "none";
      fill.style.transform = `scaleX(${selected / Math.max(1, steps.length - 1)})`;
      if (jump) { void fill.offsetWidth; fill.style.removeProperty("transition"); }
    }

    function render(previous) {
      steps.forEach((step, index) => {
        const active = index === selected;
        step.panel.classList.toggle("wiki-pfad-schritt--an", active);
        step.panel.classList.toggle("wiki-pfad-schritt--erledigt", index < selected);
        if (mode === "tabs") {
          step.panel.hidden = !active;
          step.body.hidden = false;
          step.toggle.setAttribute("aria-expanded", String(active));
        } else {
          const open = active && expanded;
          step.panel.hidden = false;
          step.body.hidden = !open;
          step.toggle.setAttribute("aria-expanded", String(open));
        }
      });
      tabs.forEach((tab, index) => {
        const active = index === selected;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        tab.classList.toggle("wiki-pfad-tab--erledigt", index < selected);
      });
      host.dataset.schritt = String(selected + 1);
      placeLens(previous !== undefined);
      if (previous !== undefined && previous !== selected) crossfade(previous);
    }

    // Kurze Überblendung in Wechselrichtung; das alte Panel ist sofort weg,
    // damit kein Linktext doppelt steht.
    function crossfade(previous) {
      entering?.cancel();
      entering = null;
      if (!lively() || typeof steps[selected].body.animate !== "function") return;
      if (mode === "akkordeon" && !expanded) return;
      const shift = reduce.matches ? 0 : (selected > previous ? 14 : -14) * (mode === "tabs" ? 1 : 0);
      const target = mode === "tabs" ? steps[selected].panel : steps[selected].body;
      entering = target.animate([
        { opacity: 0, transform: `translateX(${shift}px)` },
        { opacity: 1, transform: "none" },
      ], { duration: reduce.matches ? 160 : 280, easing: OUT });
    }

    function select(index, { focus = false, scroll = false } = {}) {
      const next = Math.max(0, Math.min(steps.length - 1, index));
      const previous = selected;
      if (mode === "akkordeon" && next === selected && !focus && !scroll) expanded = !expanded;
      else expanded = true;
      selected = next;
      render(previous);
      if (focus) (mode === "tabs" ? tabs[selected] : steps[selected].toggle).focus({ preventScroll: true });
      if (scroll) {
        const target = mode === "tabs" ? host : steps[selected].heading;
        const rect = target.getBoundingClientRect();
        if (rect.top < 0 || rect.top > innerHeight * .6) target.scrollIntoView({ block: "start", behavior: reduce.matches ? "auto" : "smooth" });
      }
    }

    function applyMode() {
      const next = narrowQuery.matches ? "akkordeon" : "tabs";
      if (next === mode) return;
      mode = next;
      host.dataset.modus = mode;
      bar.hidden = mode !== "tabs";
      steps.forEach((step, index) => {
        if (mode === "tabs") {
          step.panel.setAttribute("role", "tabpanel");
          step.panel.setAttribute("aria-labelledby", tabs[index].id);
          step.body.removeAttribute("role");
          step.body.removeAttribute("aria-labelledby");
        } else {
          step.panel.removeAttribute("role");
          step.panel.removeAttribute("aria-labelledby");
          step.body.setAttribute("role", "region");
          step.body.setAttribute("aria-labelledby", step.toggle.id);
        }
      });
      expanded = true;
      lens.dataset.on = "false";
      render();
    }

    bar.addEventListener("keydown", (event) => {
      const keys = { ArrowRight: selected + 1, ArrowLeft: selected - 1, Home: 0, End: steps.length - 1 };
      if (!(event.key in keys)) return;
      event.preventDefault();
      let index = keys[event.key];
      if (index < 0) index = steps.length - 1;
      if (index >= steps.length) index = 0;
      select(index, { focus: true });
    });
    steps.forEach((step, index) => step.toggle.addEventListener("click", () => select(index)));

    // Hash: #weg-bedienen scrollt zur Leiste; der Anker eines Schritts wählt ihn.
    function followHash(behavior) {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!id) return;
      const index = steps.findIndex((step) => step.heading.id === id);
      if (id !== host.id && index < 0) return;
      if (index >= 0) select(index);
      const target = mode === "akkordeon" && index >= 0 ? steps[index].heading : host;
      target.scrollIntoView({ block: "start", behavior });
    }
    const onHash = () => followHash(reduce.matches ? "auto" : "smooth");
    window.addEventListener("hashchange", onHash);
    // Was über der Leiste nachträglich Platz nimmt (Messkette), verschiebt
    // sie; beim Einstieg über den Hash deshalb danach noch einmal ausrichten.
    const arrived = performance.now();
    const onAbove = () => { if (performance.now() - arrived < 4000) followHash("auto"); };
    window.addEventListener("wiki:messkette", onAbove);

    let frame = 0;
    const onResize = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => placeLens(false)); };
    const resize = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
    resize?.observe(bar);
    const onLook = () => placeLens(false);
    window.addEventListener("wiki:look", onLook);
    document.fonts?.addEventListener?.("loadingdone", onResize);
    narrowQuery.addEventListener("change", applyMode);

    applyMode();
    requestAnimationFrame(() => followHash("auto"));

    return () => {
      entering?.cancel();
      cancelAnimationFrame(frame);
      resize?.disconnect();
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("wiki:messkette", onAbove);
      window.removeEventListener("wiki:look", onLook);
      document.fonts?.removeEventListener?.("loadingdone", onResize);
      narrowQuery.removeEventListener("change", applyMode);
    };
  }

  onPage((article) => {
    if (!isStartPage(window.location.href)) return;
    standRow(article.querySelector(".wiki-stand"));
    const cleanup = guidedPath(article.querySelector(".wiki-pfad"));
    paths(article.querySelector(".wiki-wege"));
    directory(article);
    return cleanup || undefined;
  });
})();
