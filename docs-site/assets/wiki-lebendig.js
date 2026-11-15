/* Bewegung und Atmosphäre der lebendigen Darstellung (wiki-lebendig.css).
 *
 * - Atmosphäre: zwei feste Tönungsschichten, Farbe nach Weg der Seite
 *   (bedienen, konfigurieren, entwickeln, projekt), Überblendung beim Wechsel;
 *   die Schichten driften sehr langsam (CSS, pausiert bei verborgenem Tab).
 * - Linse: Beim Klick in der Navigation merkt sich das Skript, wo die Linse
 *   stand, und lässt sie nach dem Seitenwechsel zum neuen Eintrag gleiten.
 * - Seitenwechsel als Morph (der eine Moment): Der angeklickte Linktext
 *   (Navigation, „Weiter mit“, Fußzeile, Rollenwege) geht in den Titel der
 *   neuen Seite über, der Text der Lesefläche blendet mit kurzer Unschärfe
 *   über, der Glanzstreif läuft dabei einmal über das Papier. Bevorzugt mit
 *   View Transitions; sonst fliegt ein Geist des Linktexts zum Titel.
 * - Lesefortschritt: feine Linie oben an der Lesefläche, Linse im
 *   Inhaltsverzeichnis unter dem aktuellen Abschnitt.
 * In der ruhigen Darstellung passiert nichts davon. Bei reduzierter Bewegung
 * entfallen Morph, Drift und Gleiten; Tönung, Fortschrittslinie und
 * Inhaltsverzeichnis-Linse springen ohne Übergang. */
(function () {
  "use strict";

  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const OUT = "cubic-bezier(.16, 1, .3, 1)";
  const lively = () => root.getAttribute("data-wiki-look") === "lebendig";
  const moving = () => lively() && !reduce.matches;

  const TINTS = {
    light: {
      start: ["#bcd7ff", "#dccbff", "#c9f2e3"],
      bedienen: ["#c9f2e3", "#d3e8ff", "#e6f6d6"],
      konfigurieren: ["#bfd8ff", "#cfe0ff", "#d9d0ff"],
      entwickeln: ["#dccbff", "#d6ccff", "#ffd9ec"],
      projekt: ["#ffe0c7", "#cfe0ff", "#e3d3ff"],
    },
    dark: {
      // Gedämpft: Alphawerte etwa halb so hoch wie zuerst, damit das Glas der
      // Seitenleisten nicht königsblau wird.
      start: ["rgb(64 110 230 / .16)", "rgb(130 90 230 / .14)", "rgb(40 170 140 / .1)"],
      bedienen: ["rgb(40 170 140 / .13)", "rgb(64 110 230 / .12)", "rgb(90 170 80 / .09)"],
      konfigurieren: ["rgb(64 110 230 / .17)", "rgb(80 130 240 / .11)", "rgb(120 100 230 / .11)"],
      entwickeln: ["rgb(130 90 230 / .16)", "rgb(110 90 220 / .12)", "rgb(220 90 160 / .09)"],
      projekt: ["rgb(230 140 70 / .11)", "rgb(64 110 230 / .13)", "rgb(140 100 230 / .11)"],
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

  // Drift der Atmosphäre ruht, solange der Tab verborgen ist.
  const syncHidden = () => root.classList.toggle("wiki-verborgen", document.hidden);
  document.addEventListener("visibilitychange", syncHidden);
  syncHidden();

  // Linse: Ausgangslage beim Klick merken, in Koordinaten des Scrollbereichs
  // der Navigation (die Seitenleiste bleibt bei Sofortnavigation stehen,
  // kann aber zum neuen Eintrag scrollen).
  let lensFrom = null;
  let navHeld = false;
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
    lensFrom = link && wrap && link.offsetParent ? { ...inWrap(link, wrap), scroll: wrap.scrollTop } : null;
  }, true);

  // startAfter: beim Morph das ready der View Transition. Erst dann ist das
  // neue Bild zu sehen; vorher hält der Browser das alte fest. Der Geist
  // entsteht deshalb erst dort (das neue Bild ist lebendig, er erscheint im
  // ersten Bild des Übergangs) und gleitet sofort los.
  function glideLens(startAfter) {
    let from = lensFrom;
    lensFrom = null;
    // Hält der Morph die Leiste fest (holdNav), gleitet die Linse von der
    // Stelle, an der sie zu sehen war, nicht von der alten Listenposition:
    // Die neue Liste kann darüber anders aufgeklappt sein.
    if (from && navHeld) from = { ...from, y: from.y - from.scroll + (navWrap()?.scrollTop || 0) };
    navHeld = false;
    if (!from) return;
    let started = false;
    const start = () => {
      if (started) return;
      started = true;
      const link = activeLink();
      const wrap = navWrap();
      if (!link || !wrap || !moving() || !link.offsetParent) return;
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
    };
    if (startAfter) {
      startAfter.then(start, start);
      setTimeout(start, 1500);
    } else {
      start();
    }
  }


  /* ------------------------------------------------ Seitenwechsel ---- */
  /* Ablauf mit View Transitions: Klick abfangen (bevor Zensical ihn sieht)
   * und sofort startViewTransition. Im Rückruf, also nachdem das alte Bild
   * aufgenommen ist, löst ein künstlicher Klick die Sofortnavigation von
   * Zensical aus; der Rückruf wartet, bis wiki.onPage die neue Seite meldet.
   * Kein Vorladen: Es hätte auf dem Pi 110–200 ms vor den Übergang gesetzt.
   * So steht das alte Bild genau so lange, wie Zensical ohnehin lädt. Dauert
   * das länger als SWAP_MS, gibt der Rückruf das Bild frei (Zensicals
   * Ladebalken wird sichtbar), und der neue Text blendet ein, sobald er da
   * ist (weiche Überblendung in enter()). */
  const MORPH_LINKS = [
    ".md-sidebar--primary a.md-nav__link[href]",
    "a.wiki-pagehead-weiter",
    "a.md-footer__link",
    ".wiki-weg-links > li > a[href]",
  ].join(", ");
  const SWAP_MS = 1500;

  function instantNavigation() {
    if (location.protocol === "file:" || typeof window.document$ === "undefined") return false;
    try {
      const config = JSON.parse(document.getElementById("__config")?.textContent || "{}");
      return (config.features || []).includes("navigation.instant");
    } catch (error) {
      return false;
    }
  }
  const instant = instantNavigation();

  let morph = null;      // laufender Morph: { token, url, hash, source, transition, arrive }
  let token = 0;
  let ghostData = null;  // Ersatzweg ohne View Transitions: Linktext und Lage
  let firstPage = true;  // Erstaufruf: nur Glanzstreif, keine Überblendung
  let synthetic = null;  // vom Skript ausgelöster Klick, nicht erneut abfangen

  function morphTarget(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
    const link = event.target.closest?.(MORPH_LINKS);
    if (!link || link.target || link.hasAttribute("download")) return null;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || url.pathname === location.pathname) return null;
    if (!/(\/|\.html)$/.test(url.pathname)) return null;
    return { link, url };
  }

  // Das Element, das den Titeltext trägt (ohne Pfeil, Richtung, Hinweis).
  function titleSource(link) {
    if (link.matches(".md-footer__link")) return link.querySelector(".md-footer__title .md-ellipsis") || link.querySelector(".md-footer__title") || link;
    if (link.matches(".md-nav__link")) return link.querySelector(".md-ellipsis") || link;
    if (link.matches(".wiki-pagehead-weiter")) {
      const done = link.querySelector(".wiki-morph-text");
      if (done) return done;
      const text = [...link.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      const prefix = /^\s*Weiter mit:\s*/.exec(text?.textContent || "");
      if (!text || !prefix) return link;
      const rest = text.splitText(prefix[0].length);
      const span = document.createElement("span");
      span.className = "wiki-morph-text";
      rest.replaceWith(span);
      span.append(rest);
      return span;
    }
    return link;
  }

  const visible = (el) => !!el && el.getClientRects().length > 0;
  function inView(el) {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.bottom > 0 && r.top < innerHeight;
  }

  function name(el, value) {
    el.style.viewTransitionName = value;
    el.setAttribute("data-wiki-morph", "");
  }
  function unname() {
    for (const el of document.querySelectorAll("[data-wiki-morph]")) {
      el.style.removeProperty("view-transition-name");
      el.style.removeProperty("display");
      el.style.removeProperty("width");
      el.removeAttribute("data-wiki-morph");
    }
  }

  function navigate(url) {
    const anchor = document.createElement("a");
    anchor.href = url.href;
    synthetic = anchor;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    synthetic = null;
  }

  function cancelMorph() {
    if (!morph) return;
    token += 1;
    morph.transition?.skipTransition();
    morph.arrive?.();
    morph = null;
    endMorph();
  }

  function endMorph() {
    root.classList.remove("wiki-morph");
    unname();
  }

  function startMorph(link, url) {
    const own = ++token;
    const source = titleSource(link);
    const wrap = navWrap();
    const inNav = wrap && wrap.contains(link);
    const nav = wrap ? {
      top: wrap.scrollTop, height: wrap.style.height, offset: wrap.closest(".md-sidebar")?.style.top || "",
      // Angeklickter Eintrag: wo er im Fenster der Leiste stand.
      anchor: inNav ? link.getBoundingClientRect().top - wrap.getBoundingClientRect().top : null,
    } : null;
    morph = { token: own, url: url.href, hash: url.hash, source, nav };
    if (document.hidden) {
      morph = null;
      navigate(url);
      return;
    }
    runTransition(own, url, source);
  }

  // View-Transition-Typen markieren den Morph, ohne eine Klasse am <html>
  // zu setzen (die zwingt auf großen Seiten eine Neuberechnung aller Stile,
  // auf dem Pi 100–250 ms). Ältere Browser bekommen die Klasse.
  const vtTypes = typeof CSS !== "undefined" && !!CSS.supports?.("selector(:active-view-transition-type(a))");

  function runTransition(own, url, source) {
    // Erst alles messen, dann schreiben: sonst rechnet der Browser mehrfach.
    const article = document.querySelector(".md-content__inner");
    const header = document.querySelector(".md-header");
    const kappe = article && header ? Math.max(0, header.getBoundingClientRect().bottom - article.getBoundingClientRect().top) : 0;
    const flying = visible(source) && inView(source);
    const inline = flying && getComputedStyle(source).display === "inline";
    if (!vtTypes) root.classList.add("wiki-morph");
    // Der alte Text verschwimmt an seiner Stelle; was unter dem Kopf lag,
    // bleibt abgeschnitten, statt kurz über dem Kopf zu stehen.
    if (article) name(article, "wiki-text-alt");
    if (flying) {
      if (inline) source.style.display = "inline-block";
      name(source, "wiki-titel");
    }
    const update = () => new Promise((resolve) => {
      // Der Rückruf läuft, nachdem das alte Bild aufgenommen ist.
      const timeout = setTimeout(finish, SWAP_MS);
      function finish() {
        clearTimeout(timeout);
        if (morph && morph.token === own) morph.arrive = null;
        setTimeout(resolve, 0);
      }
      // Navigiert wird immer, auch wenn der Morph inzwischen verworfen ist.
      unname();
      if (own !== token) {
        navigate(url);
        return finish();
      }
      morph.arrive = finish;
      navigate(url);
    });
    let transition;
    try {
      transition = vtTypes ? document.startViewTransition({ update, types: ["wiki-morph"] }) : document.startViewTransition(update);
    } catch (error) {
      morph = null;
      endMorph();
      navigate(url);
      return;
    }
    morph.transition = transition;
    // Text, der unter dem Kopf liegt, bleibt dort verborgen: Die Textgruppen
    // liegen über dem Wurzelbild und damit über dem Kopf. Der alte Text ist
    // vor der Aufnahme gemessen, der neue im lebenden neuen Bild (bei
    // Sprungzielen ist die Seite schon gescrollt).
    const clip = (group, px, duration) => {
      if (px > 0) root.animate({ clipPath: [`inset(${px}px 0 0 0)`, `inset(${px}px 0 0 0)`] }, { duration, fill: "both", pseudoElement: `::view-transition-group(${group})` });
    };
    transition.ready.then(() => {
      clip("wiki-text-alt", kappe, 140);
      const neu = document.querySelector(".md-content__inner");
      const kopf = document.querySelector(".md-header");
      if (neu && kopf && neu.style.viewTransitionName === "wiki-text-neu") {
        clip("wiki-text-neu", kopf.getBoundingClientRect().bottom - neu.getBoundingClientRect().top, 420);
      }
    }, () => {});
    transition.updateCallbackDone.catch(() => {});
    transition.finished.catch(() => {}).finally(() => {
      if (morph && morph.token === own) morph = null;
      if (!morph) endMorph();
    });
  }


  document.addEventListener("click", (event) => {
    if (!instant || event.target === synthetic || !lively()) return;
    const target = morphTarget(event);
    if (!target || reduce.matches) return;
    if (!document.startViewTransition) {
      // Ersatzweg: Zensical navigiert wie immer, der Geist fliegt danach.
      const source = titleSource(target.link);
      if (visible(source) && inView(source)) {
        const style = getComputedStyle(source);
        ghostData = {
          at: performance.now(), hash: target.url.hash, text: source.textContent.trim(), rect: source.getBoundingClientRect(),
          font: { fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight, letterSpacing: style.letterSpacing, color: style.color },
        };
      }
      return;
    }
    if (morph) {
      if (morph.url === target.url.href) {
        // Doppelklick auf denselben Link: der erste Klick reicht.
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      // Anderer Link während des Übergangs: Übergang beenden, Zensical
      // navigiert wie sonst.
      morph.transition?.skipTransition();
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    startMorph(target.link, target.url);
  }, true);

  // Zurück/Vor: kein Morph (Zensical lädt sofort), nur die weiche Überblendung.
  // Ein popstate während des Morphs bricht ihn nicht ab: Zensical springt
  // selbst zum Sprungziel, was auch popstate auslöst, und der Rückruf wartet
  // ohnehin nur auf die nächste Seite (höchstens SWAP_MS).


  // Ziel des Linktexts: der Titel der Seite, bei Sprungzielen die Überschrift.
  function arrivalTitle(article, hash) {
    if (!article) return null;
    let target = null;
    if (hash) {
      try { target = article.querySelector(`[id="${CSS.escape(decodeURIComponent(hash.slice(1)))}"]`); } catch (error) { target = null; }
      if (target && !/^H[1-6]$/.test(target.tagName)) target = null;
    }
    return target || article.querySelector("h1");
  }

  // Neue Seite unter laufender View Transition benennen: Titel und Text.
  function morphArrive(article) {
    if (!morph || !morph.arrive) return false;
    const arrive = morph.arrive;
    if (article) name(article, "wiki-text-neu");
    const title = arrivalTitle(article, morph.hash);
    if (title && visible(title)) {
      // Das Absatzzeichen (¶) fliegt nicht mit.
      for (const mark of title.querySelectorAll(".headerlink")) {
        mark.style.display = "none";
        mark.setAttribute("data-wiki-morph", "");
      }
      title.style.width = "fit-content";
      name(title, "wiki-titel");
    }
    arrive();
    return true;
  }

  // Navigation bleibt beim Morph stehen, wenn der neue Eintrag schon zu
  // sehen ist. Zensical zentriert sonst den aktiven Eintrag (scrollTo im
  // nächsten Frame): Die Liste spränge dann unter dem fliegenden Titel weg,
  // der Titel startete über einem fremden Eintrag, und die Linse glitte über
  // eine Liste, die sich selbst bewegt. Die Sperre gilt nur für diese eine,
  // neue Seitenleiste und nur bis zum Ende des Übergangs.
  function holdNav() {
    const old = morph?.nav;
    const wrap = navWrap();
    const link = activeLink();
    if (!old || !wrap || !link || !visible(link)) return;
    // Höhe und Lage setzt Zensical erst im nächsten Frame; bis dahin ist die
    // neue Leiste nicht scrollbar. Dieselben Werte wie vorher vorwegnehmen.
    if (!wrap.style.height && old.height) wrap.style.height = old.height;
    const sidebar = wrap.closest(".md-sidebar");
    if (sidebar && !sidebar.style.top && old.offset) sidebar.style.top = old.offset;
    const before = wrap.scrollTop;
    wrap.scrollTop = old.top;
    // Wurde in der Leiste geklickt, bleibt genau dieser Eintrag stehen, auch
    // wenn die neue Liste darüber anders aufgeklappt ist. Sonst bleibt die
    // Scrollposition, solange der neue Eintrag damit zu sehen ist.
    if (old.anchor != null) {
      wrap.scrollTop += link.getBoundingClientRect().top - wrap.getBoundingClientRect().top - old.anchor;
    }
    const r = link.getBoundingClientRect();
    const w = wrap.getBoundingClientRect();
    if (r.top < w.top || r.bottom > w.bottom) {
      wrap.scrollTop = before;
      return;
    }
    navHeld = true;
    wrap.scrollTo = () => {};
    const release = () => { delete wrap.scrollTo; };
    morph.transition?.finished.then(release, release);
    setTimeout(release, 1500);
  }

  // Wurde in der Navigation geklickt, startet der fliegende Titel genau über
  // dem neuen aktiven Eintrag. Dessen eigener Text (jetzt fett) bliebe sonst
  // als zweite, leicht versetzte Beschriftung darunter stehen; er erscheint
  // erst, wenn der Titel abgehoben hat.
  function quietSource() {
    if (morph?.nav?.anchor == null || !morph.transition) return;
    const link = activeLink();
    if (!link) return;
    // Ab dem ersten Bild des Übergangs: 160 ms leer, dann blendet er ein.
    morph.transition.ready.then(() => {
      link.animate([{ color: "transparent" }, { color: "transparent", offset: .5 }], { duration: 320, easing: "linear" });
    }, () => {});
  }

  // Ersatzweg ohne View Transitions: Linktext fliegt zur Lage des Titels.
  function flyGhost(article) {
    const data = ghostData;
    ghostData = null;
    if (!data || performance.now() - data.at > 4000 || !moving()) return;
    const title = arrivalTitle(article, data.hash);
    if (!title || !visible(title)) return;
    const range = document.createRange();
    range.selectNodeContents(title);
    const to = range.getBoundingClientRect();
    if (!to.width) return;
    const ghost = document.createElement("div");
    ghost.className = "wiki-morph-geist";
    ghost.setAttribute("aria-hidden", "true");
    ghost.textContent = data.text;
    Object.assign(ghost.style, data.font, { left: data.rect.left + "px", top: data.rect.top + "px" });
    document.body.append(ghost);
    const scale = parseFloat(getComputedStyle(title).fontSize) / parseFloat(data.font.fontSize) || 1;
    const dx = to.left - data.rect.left;
    const dy = to.top - data.rect.top;
    const flight = ghost.animate(
      [{ transform: "none", opacity: 1 }, { opacity: 1, offset: .5 }, { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0 }],
      { duration: 440, easing: OUT },
    );
    title.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 320, delay: 140, easing: OUT, fill: "backwards" });
    const done = () => ghost.remove();
    flight.onfinish = done;
    flight.oncancel = done;
  }

  function sheen() {
    const paper = document.querySelector(".md-content");
    if (!paper) return;
    paper.classList.remove("wiki-sheen");
    void paper.offsetWidth;
    paper.classList.add("wiki-sheen");
    paper.addEventListener("animationend", () => paper.classList.remove("wiki-sheen"), { once: true });
  }

  // Ein Moment je Seitenwechsel: unter View Transitions übernimmt der Morph
  // Titel und Text; sonst blendet der Text kurz aus der Unschärfe ein.
  function enter(article) {
    const instantEntry = !firstPage;
    firstPage = false;
    if (!moving() || !article) return;
    sheen();
    if (morphArrive(article)) return;
    flyGhost(article);
    if (!instantEntry) return;
    article.animate(
      [{ opacity: .3, filter: "blur(5px)" }, { opacity: 1, filter: "blur(0)" }],
      { duration: 380, easing: OUT },
    );
  }

  /* ---------------------------------------------- Lesefortschritt ---- */
  const scrollTimeline = typeof CSS !== "undefined" && CSS.supports?.("animation-timeline: scroll()");

  function progressLine() {
    const paper = document.querySelector(".md-content");
    if (!paper) return null;
    const bar = document.createElement("div");
    bar.className = "wiki-lesefortschritt";
    bar.setAttribute("aria-hidden", "true");
    paper.prepend(bar);
    const header = document.querySelector(".md-header");
    let frame = 0;
    function measure() {
      bar.style.setProperty("--wiki-kopf", (header ? header.getBoundingClientRect().height : 0) + "px");
    }
    function update() {
      frame = 0;
      const max = document.documentElement.scrollHeight - innerHeight;
      bar.style.setProperty("--p", max > 0 ? Math.min(1, Math.max(0, scrollY / max)).toFixed(4) : "0");
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    function mode() {
      // Scroll-getrieben, wo möglich; bei reduzierter Bewegung ohne Animation.
      const css = scrollTimeline && !reduce.matches;
      bar.classList.toggle("wiki-lesefortschritt--css", css);
      removeEventListener("scroll", schedule);
      if (!css) {
        addEventListener("scroll", schedule, { passive: true });
        update();
      }
    }
    const onResize = () => { measure(); schedule(); };
    measure();
    mode();
    addEventListener("resize", onResize);
    reduce.addEventListener("change", mode);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener("scroll", schedule);
      removeEventListener("resize", onResize);
      reduce.removeEventListener("change", mode);
      bar.remove();
    };
  }

  /* -------------------------------------- Inhaltsverzeichnis-Linse ---- */
  function tocLens() {
    const inner = document.querySelector(".md-sidebar--secondary .md-sidebar__inner");
    const nav = inner?.querySelector(".md-nav--secondary");
    if (!nav || !nav.querySelector("a.md-nav__link")) return null;
    const lens = document.createElement("div");
    lens.className = "wiki-toc-linse";
    lens.setAttribute("aria-hidden", "true");
    inner.prepend(lens);
    let placed = false;
    let frame = 0;
    function place(jump) {
      frame = 0;
      const links = nav.querySelectorAll("a.md-nav__link--active");
      const link = links[links.length - 1];
      if (!link || !visible(link)) {
        lens.removeAttribute("data-on");
        return;
      }
      const r = link.getBoundingClientRect();
      const w = inner.getBoundingClientRect();
      if (!r.width || !w.width) return;
      const instantly = jump || !placed || reduce.matches;
      if (instantly) lens.classList.add("wiki-toc-linse--sofort");
      Object.assign(lens.style, { width: r.width + "px", height: r.height + "px", transform: `translate(${r.left - w.left - inner.clientLeft}px, ${r.top - w.top - inner.clientTop}px)` });
      lens.setAttribute("data-on", "");
      if (instantly) {
        void lens.offsetWidth;
        lens.classList.remove("wiki-toc-linse--sofort");
      }
      placed = true;
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(() => place(false)); };
    const watch = new MutationObserver(schedule);
    watch.observe(nav, { subtree: true, attributes: true, attributeFilter: ["class"] });
    const resize = new ResizeObserver(() => place(true));
    resize.observe(inner);
    place(true);
    return () => {
      cancelAnimationFrame(frame);
      watch.disconnect();
      resize.disconnect();
      lens.remove();
    };
  }

  // Fortschrittslinie und Inhaltsverzeichnis-Linse gibt es nur in „lebendig“.
  let features = [];
  function teardown() {
    features.forEach((stop) => stop());
    features = [];
  }
  function setup() {
    teardown();
    if (!lively() || !currentArticle) return;
    features = [progressLine(), tocLens()].filter(Boolean);
  }

  let currentArticle = null;
  function page(article) {
    currentArticle = article;
    tint(weg(article));
    const morphing = !!(morph?.arrive && moving());
    if (morphing) holdNav();
    glideLens(morphing ? morph.transition?.ready : null);
    if (morphing) quietSource();
    enter(article);
    setup();
    return teardown;
  }

  window.addEventListener("wiki:look", () => {
    lastTint = "";
    tint(weg(currentArticle));
    if (!lively()) cancelMorph();
    setup();
  });
  new MutationObserver(() => tint(weg(currentArticle)))
    .observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });

  if (window.wiki?.onPage) window.wiki.onPage(page);
})();
