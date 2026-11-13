/* Bewegung und Atmosphäre der lebendigen Darstellung (wiki-lebendig.css).
 *
 * - Atmosphäre: zwei feste Tönungsschichten, Farbe nach Weg der Seite
 *   (bedienen, konfigurieren, entwickeln, projekt), Überblendung beim Wechsel.
 * - Linse: Beim Klick in der Navigation merkt sich das Skript, wo die Linse
 *   stand, und lässt sie nach dem Seitenwechsel zum neuen Eintrag gleiten.
 * - Seiteneintritt: ein Glanzstreif über die Lesefläche, Titel und erste
 *   Blöcke tauchen gestaffelt auf. Inhalt ist ohne Animation sichtbar.
 * In der ruhigen Darstellung und bei reduzierter Bewegung passiert nichts
 * davon (Tönung bleibt, springt aber ohne Überblendung). */
(function () {
  "use strict";

  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const OUT = "cubic-bezier(.16, 1, .3, 1)";
  const lively = () => root.getAttribute("data-wiki-look") === "lebendig";

  const TINTS = {
    light: {
      start: ["#bcd7ff", "#dccbff", "#c9f2e3"],
      bedienen: ["#c9f2e3", "#d3e8ff", "#e6f6d6"],
      konfigurieren: ["#bfd8ff", "#cfe0ff", "#d9d0ff"],
      entwickeln: ["#dccbff", "#d6ccff", "#ffd9ec"],
      projekt: ["#ffe0c7", "#cfe0ff", "#e3d3ff"],
    },
    dark: {
      start: ["rgb(64 110 230 / .30)", "rgb(130 90 230 / .26)", "rgb(40 170 140 / .18)"],
      bedienen: ["rgb(40 170 140 / .24)", "rgb(64 110 230 / .22)", "rgb(90 170 80 / .16)"],
      konfigurieren: ["rgb(64 110 230 / .32)", "rgb(80 130 240 / .2)", "rgb(120 100 230 / .2)"],
      entwickeln: ["rgb(130 90 230 / .3)", "rgb(110 90 220 / .22)", "rgb(220 90 160 / .16)"],
      projekt: ["rgb(230 140 70 / .2)", "rgb(64 110 230 / .24)", "rgb(140 100 230 / .2)"],
    },
  };

  let atmo = null;
  let atmoOn = 0;
  let lastTint = "";

  function ensureAtmo() {
    if (atmo?.isConnected) return atmo;
    atmo = document.createElement("div");
    atmo.className = "wiki-atmo";
    atmo.setAttribute("aria-hidden", "true");
    atmo.append(document.createElement("div"), document.createElement("div"));
    atmo.children[0].className = atmo.children[1].className = "wiki-atmo-layer";
    document.body.prepend(atmo);
    lastTint = "";
    return atmo;
  }

  function weg(article) {
    const head = article?.querySelector(".wiki-pagehead[data-weg]");
    if (head) return head.dataset.weg;
    return article?.querySelector("#codebase-stage") ? "projekt" : "start";
  }

  function tint(name) {
    const scheme = document.body.dataset.mdColorScheme === "slate" ? "dark" : "light";
    const key = scheme + ":" + name;
    if (key === lastTint) return;
    lastTint = key;
    const colors = TINTS[scheme][name] || TINTS[scheme].start;
    const layers = ensureAtmo().children;
    const next = layers[atmoOn ^= 1];
    next.style.setProperty("--a", colors[0]);
    next.style.setProperty("--b", colors[1]);
    next.style.setProperty("--c", colors[2]);
    next.setAttribute("data-on", "");
    layers[atmoOn ^ 1].removeAttribute("data-on");
  }

  // Linse: Ausgangslage beim Klick merken, in Koordinaten des Scrollbereichs
  // der Navigation (die Seitenleiste bleibt bei Sofortnavigation stehen,
  // kann aber zum neuen Eintrag scrollen).
  let lensFrom = null;
  const activeLink = () => {
    const links = document.querySelectorAll(".md-nav--primary a.md-nav__link--active");
    return links[links.length - 1] || null;
  };
  const navWrap = () => document.querySelector(".md-sidebar--primary .md-sidebar__scrollwrap");
  function inWrap(link, wrap) {
    const r = link.getBoundingClientRect();
    const w = wrap.getBoundingClientRect();
    return { x: r.left - w.left + wrap.scrollLeft, y: r.top - w.top + wrap.scrollTop, w: r.width, h: r.height };
  }
  document.addEventListener("click", (event) => {
    if (!event.target.closest?.(".md-nav--primary a")) return;
    const link = activeLink();
    const wrap = navWrap();
    lensFrom = link && wrap && link.offsetParent ? inWrap(link, wrap) : null;
  }, true);

  function glideLens() {
    const from = lensFrom;
    lensFrom = null;
    const link = activeLink();
    const wrap = navWrap();
    if (!from || !link || !wrap || reduce.matches || !lively() || !link.offsetParent) return;
    const to = inWrap(link, wrap);
    if (Math.abs(to.y - from.y) < 1 && Math.abs(to.x - from.x) < 1) return;
    const ghost = document.createElement("div");
    ghost.className = "wiki-lens-geist";
    Object.assign(ghost.style, { width: from.w + "px", height: from.h + "px", transform: `translate(${from.x}px, ${from.y}px)` });
    wrap.append(ghost);
    link.classList.add("wiki-lens-wartet");
    void ghost.offsetWidth;
    Object.assign(ghost.style, { width: to.w + "px", height: to.h + "px", transform: `translate(${to.x}px, ${to.y}px)` });
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      ghost.remove();
      link.classList.remove("wiki-lens-wartet");
    };
    ghost.addEventListener("transitionend", (event) => { if (event.propertyName === "transform") done(); });
    setTimeout(done, 900);
  }

  function enter(article) {
    if (reduce.matches || !lively() || !article) return;
    const paper = document.querySelector(".md-content");
    if (paper) {
      paper.classList.remove("wiki-sheen");
      void paper.offsetWidth;
      paper.classList.add("wiki-sheen");
      paper.addEventListener("animationend", () => paper.classList.remove("wiki-sheen"), { once: true });
    }
    const blocks = Array.from(article.children).filter((el) => el.offsetParent !== null).slice(0, 6);
    // Ausgangslage bleibt lesbar: nur Versatz und leichte Aufhellung.
    blocks.forEach((el, k) => el.animate(
      [{ transform: "translateY(14px)", opacity: .35 }, { transform: "none", opacity: 1 }],
      { duration: 760, delay: k * 45, easing: OUT, fill: "backwards" },
    ));
  }

  let currentArticle = null;
  function page(article) {
    currentArticle = article;
    tint(weg(article));
    glideLens();
    enter(article);
  }

  window.addEventListener("wiki:look", () => { lastTint = ""; tint(weg(currentArticle)); });
  new MutationObserver(() => tint(weg(currentArticle)))
    .observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });

  if (window.wiki?.onPage) window.wiki.onPage(page);
})();
