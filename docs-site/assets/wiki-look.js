/* Darstellung umschalten: „ruhig“ (Zensical wie gehabt) und „lebendig“
 * (Glas, Atmosphäre, Bewegung, assets/wiki-lebendig.css).
 *
 * Das Attribut data-wiki-look auf <html> setzt schon docs-overrides/main.html
 * vor dem ersten Zeichnen. Dieses Skript baut den Umschalter in den Kopf,
 * speichert die Wahl und meldet Wechsel als Ereignis „wiki:look“
 * (detail.look), damit Bausteine wie die Codebase-Seite mitziehen. */
(function () {
  "use strict";

  const KEY = "wiki-look";
  const LOOKS = ["ruhig", "lebendig"];
  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");

  function current() {
    return root.getAttribute("data-wiki-look") === "lebendig" ? "lebendig" : "ruhig";
  }

  function apply(look) {
    root.setAttribute("data-wiki-look", look);
    try { localStorage.setItem(KEY, look); } catch (error) { /* privates Fenster: nur diese Seite */ }
    syncSwitch();
    window.dispatchEvent(new CustomEvent("wiki:look", { detail: { look } }));
  }

  function set(look) {
    if (!LOOKS.includes(look) || look === current()) return;
    if (document.startViewTransition && !reduce.matches) {
      root.classList.add("wiki-look-wechsel");
      const transition = document.startViewTransition(() => apply(look));
      transition.finished.finally(() => root.classList.remove("wiki-look-wechsel"));
    } else {
      apply(look);
    }
  }

  const SVG = (d) => `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
  const ICON_RUHIG = "M5 8h14M5 12h14M5 16h9";
  const ICON_LEBENDIG = "M3 13c2.5-5 5-5 7.5 0s5 5 7.5 0 2.5-3 3-3";

  function title(look) {
    return look === "lebendig"
      ? "Darstellung: lebendig (Glas, Übergänge, bewegte Diagramme). Klicken für die ruhige Darstellung."
      : "Darstellung: ruhig (schlicht, ohne Effekte). Klicken für die lebendige Darstellung.";
  }

  function syncSwitch() {
    const button = document.querySelector(".wiki-look-switch");
    if (!button) return;
    const look = current();
    button.setAttribute("aria-checked", String(look === "lebendig"));
    button.title = title(look);
  }

  function build() {
    if (document.querySelector(".wiki-look-switch")) return syncSwitch();
    const inner = document.querySelector(".md-header__inner");
    if (!inner) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "wiki-look-switch md-header__button";
    button.setAttribute("role", "switch");
    button.setAttribute("aria-label", "Lebendige Darstellung");
    button.innerHTML = `<span class="wiki-look-track" aria-hidden="true">`
      + `<span class="wiki-look-end wiki-look-end--ruhig">${SVG(ICON_RUHIG)}</span>`
      + `<span class="wiki-look-end wiki-look-end--lebendig">${SVG(ICON_LEBENDIG)}</span>`
      + `<span class="wiki-look-knob"></span></span>`;
    button.addEventListener("click", () => set(current() === "lebendig" ? "ruhig" : "lebendig"));
    const palette = inner.querySelector('[data-md-component="palette"]');
    inner.insertBefore(button, palette || inner.querySelector(".md-header__source"));
    syncSwitch();
  }

  // Wahl aus einem anderen Tab übernehmen.
  window.addEventListener("storage", (event) => {
    if (event.key === KEY && LOOKS.includes(event.newValue) && event.newValue !== current()) apply(event.newValue);
  });

  window.wikiLook = { get: current, set };
  // Der Kopf bleibt bei Sofortnavigation stehen; build() ist idempotent.
  if (window.wiki?.onPage) window.wiki.onPage(build);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
