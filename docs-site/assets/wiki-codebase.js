/* Codebase-Seite (docs/uebersicht/codebase.md): bettet die Bühne
 * assets/codebase/index.html ein, solange die lebendige Darstellung gilt.
 * In der ruhigen Darstellung bleibt es bei Text, Tabellen und den Diagrammen
 * aus wiki-chart.js; die Bühne ist dann nur über „Vollbild öffnen“ erreichbar.
 * Die Bühne folgt dem Farbschema des Wikis per postMessage. */
(function () {
  "use strict";

  const { onPage, siteUrl, make } = window.wiki;

  onPage(function codebasePage(article) {
    const host = article.querySelector("#codebase-stage");
    if (!host) return;
    document.body.classList.add("codebase-page");
    let frame = null;
    let observer = null;

    const theme = () => (document.body.dataset.mdColorScheme === "slate" ? "dark" : "light");
    const look = () => (window.wikiLook ? window.wikiLook.get() : "ruhig");
    const stageUrl = (extra) => {
      const url = new URL(siteUrl("assets/codebase/index.html"));
      for (const [key, value] of Object.entries(extra || {})) url.searchParams.set(key, value);
      return url;
    };
    const sendTheme = () => frame?.contentWindow?.postMessage({ type: "codebase:theme", theme: theme() }, location.origin);

    function fullLink() {
      const link = make("a", "wiki-codebase-full", "Bühne im Vollbild öffnen");
      link.href = stageUrl({ theme: theme() }).href;
      link.target = "_blank";
      link.rel = "noopener";
      return link;
    }

    function render() {
      host.replaceChildren();
      frame = null;
      if (look() !== "lebendig") {
        const note = make("p", "wiki-codebase-note");
        note.append("Die interaktive Bühne zeigt dieselben Zahlen als Animation in sieben Kapiteln. ", fullLink());
        host.append(note);
        return;
      }
      const bar = make("p", "wiki-codebase-bar");
      bar.append(make("span", "wiki-codebase-help", "Kapitel in der Leiste wählen, die Zeitschiene unten ziehen oder mit den Pfeiltasten bedienen."), fullLink());
      frame = make("iframe", "wiki-codebase-frame");
      frame.title = "Codebase-Bühne: Wachstum, Branches, Rhythmus, Struktur, Komplexität, Zustand, Maschine";
      frame.src = stageUrl({ embed: "1", theme: theme() }).href;
      frame.addEventListener("load", sendTheme);
      host.append(bar, frame);
    }

    // Abschnitt unten → Kapitel auf der Bühne.
    const sections = ["wachstum", "branches", "rhythmus", "struktur", "komplexitaet", "zustand", "maschine"];
    const jumps = [];
    for (const id of sections) {
      const heading = article.querySelector(`h2#${id}`);
      if (!heading) continue;
      const jump = make("button", "wiki-codebase-jump", "Auf der Bühne zeigen");
      jump.type = "button";
      jump.addEventListener("click", () => {
        if (!frame) return void window.open(stageUrl({ theme: theme() }).href + "#" + id, "_blank", "noopener");
        frame.contentWindow?.postMessage({ type: "codebase:chapter", id }, location.origin);
        host.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
        frame.focus();
      });
      heading.append(jump);
      jumps.push(jump);
    }

    const onLook = () => render();
    window.addEventListener("wiki:look", onLook);
    observer = new MutationObserver(sendTheme);
    observer.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
    render();

    return function cleanup() {
      window.removeEventListener("wiki:look", onLook);
      observer?.disconnect();
      jumps.forEach((jump) => jump.remove());
      host.replaceChildren();
      frame = null;
      document.body.classList.remove("codebase-page");
    };
  });
})();
