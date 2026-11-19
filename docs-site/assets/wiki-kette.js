/* Data-driven processing chain with shared hints and page-scoped motion. */
(function () {
  "use strict";

  const { onPage, siteUrl, loadJson, make, icon, hint } = window.wiki;
  const ANIME_URL = new URL("vendor/anime-4.5.0.umd.min.js", document.currentScript.src).href;
  const IDS = ["frames", "detect", "track", "rectify", "ocr", "validate", "sink"];
  const STATES = { fertig: "resolved", gebaut: "progress", teilweise: "partial", "außer Betrieb": "discarded" };
  const stagesByNode = new WeakMap();
  let animePromise;

  // Lebendige Darstellung (wiki-look.js): Glasknoten, wandernder Puls.
  const lively = () => document.documentElement.getAttribute("data-wiki-look") === "lebendig";
  // Ein Umlauf des Pulses; er wandert in den ersten 80 % von der ersten zur
  // letzten Stufe und verblasst dann, bevor er oben neu beginnt.
  const PULSE_MS = 5600;
  const PULSE_TRAVEL = .8;

  function loadAnime() {
    if (window.anime?.animate) return Promise.resolve(window.anime);
    if (!animePromise) animePromise = new Promise((resolve) => {
      const script = make("script");
      script.src = ANIME_URL;
      script.onload = () => resolve(window.anime?.animate ? window.anime : null);
      script.onerror = () => resolve(null);
      document.head.append(script);
    });
    return animePromise;
  }

  function chip(stage) {
    return make("span", `wiki-chip wiki-chip--${STATES[stage.zustand]}`, stage.zustand);
  }

  hint.register("kette", (node) => {
    const stage = stagesByNode.get(node);
    if (!stage) return null;
    const content = make("div");
    content.append(make("strong", "", `${stage.titel} · ${stage.id}/`), make("p", "", stage.zweck),
      make("p", "", `Einstellung: ${stage.einstellung}`));
    const binding = make("p", "", "Anbindung: ");
    binding.append(make("code", "", stage.anbindung));
    content.append(binding, chip(stage));
    return content;
  });

  function mount(host, stages) {
    const compact = host.dataset.variant === "kompakt";
    const figure = make("figure", "wiki-kette-figure");
    const list = make("ol", "wiki-kette-list");
    if (compact) list.setAttribute("role", "list");
    const arrows = [];
    for (const stage of stages) {
      const item = make("li");
      item.dataset.zustand = STATES[stage.zustand];
      if (compact && list.children.length) {
        const arrow = icon("weiter");
        arrow.classList.add("wiki-kette-pfeil");
        arrow.setAttribute("width", "12");
        arrow.setAttribute("height", "12");
        // Takt für das Signal entlang der Pfeile (nur lebendig, wiki.css).
        arrow.style.setProperty("--k", String(arrows.length));
        item.append(arrow);
        arrows.push(arrow);
      }
      const node = make("a", "wiki-kette-node");
      node.href = siteUrl(stage.api);
      node.dataset.hint = "kette";
      node.dataset.stufe = stage.id;
      if (compact) {
        const dot = make("span", `wiki-kette-punkt wiki-kette-punkt--${STATES[stage.zustand]}`);
        dot.setAttribute("aria-hidden", "true");
        node.append(dot, make("span", "wiki-kette-titel", stage.titel),
          make("span", "wiki-kette-zustand", `, Zustand: ${stage.zustand}`));
      } else {
        node.append(make("span", "wiki-kette-id", `${stage.id}/`),
          make("span", "wiki-kette-titel", stage.titel), chip(stage));
      }
      stagesByNode.set(node, stage);
      item.append(node);
      list.append(item);
    }
    figure.append(list);
    if (!compact) {
      figure.append(make("figcaption", "", "Verarbeitungskette · Überfahren zeigt Zweck und Anbindung"));
    }
    host.replaceChildren(figure);

    const targets = compact ? arrows : Array.from(list.children).slice(1);
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let stopped = false;
    let animation = null;
    let seen = false;
    let intersection;
    let visibility;
    let visible = false;
    let rail = null;
    let railResize = null;
    let railFrame = 0;
    let pulses = [];

    function finish() {
      animation?.revert();
      animation = null;
      if (compact) targets.forEach((target) => target.style.removeProperty("opacity"));
      else Array.from(list.children).forEach((item) => item.style.removeProperty("--wiki-kette-progress"));
    }

    function stopPulse() {
      pulses.forEach((pulse) => pulse.cancel());
      pulses = [];
    }

    // Schiene von der Mitte der ersten bis zur Mitte der letzten Stufe; der
    // Puls läuft darauf, und jede Stufe leuchtet kurz auf, wenn er sie erreicht.
    function layoutRail() {
      railFrame = 0;
      if (!rail || stopped) return;
      stopPulse();
      const nodes = Array.from(list.querySelectorAll(".wiki-kette-node"));
      const box = figure.getBoundingClientRect();
      const centers = nodes.map((node) => {
        const rect = node.getBoundingClientRect();
        return rect.top + rect.height / 2 - box.top;
      });
      const top = centers[0];
      const span = centers[centers.length - 1] - top;
      rail.style.top = `${top}px`;
      rail.style.height = `${Math.max(0, span)}px`;
      if (motion.matches || span <= 0 || typeof rail.animate !== "function") return;
      const end = `translateY(${span}px)`;
      pulses.push(rail.firstElementChild.animate([
        { transform: "translateY(0)", opacity: 0, offset: 0 },
        { opacity: 1, offset: .04 },
        { transform: end, opacity: 1, offset: PULSE_TRAVEL },
        { transform: end, opacity: 0, offset: .9 },
        { transform: end, opacity: 0, offset: 1 },
      ], { duration: PULSE_MS, iterations: Infinity }));
      nodes.forEach((node, index) => {
        const arrival = (centers[index] - top) / span * PULSE_TRAVEL * PULSE_MS;
        pulses.push(node.animate([
          { backgroundColor: "transparent", offset: 0 },
          { backgroundColor: "var(--wiki-kette-glut)", offset: .05 },
          { backgroundColor: "transparent", offset: .22 },
          { backgroundColor: "transparent", offset: 1 },
        ], { duration: PULSE_MS, iterations: Infinity, delay: arrival - .05 * PULSE_MS }));
      });
      if (!visible) pulses.forEach((pulse) => pulse.pause());
    }

    function scheduleRail() {
      if (!railFrame) railFrame = requestAnimationFrame(layoutRail);
    }

    function dropRail() {
      stopPulse();
      cancelAnimationFrame(railFrame);
      railFrame = 0;
      railResize?.disconnect();
      railResize = null;
      rail?.remove();
      rail = null;
    }

    function applyLook() {
      if (stopped) return;
      if (compact || !lively()) { dropRail(); return; }
      if (!rail) {
        rail = make("span", "wiki-kette-schiene");
        rail.setAttribute("aria-hidden", "true");
        rail.append(make("i", "wiki-kette-puls"));
        figure.append(rail);
        if (typeof ResizeObserver !== "undefined") {
          railResize = new ResizeObserver(scheduleRail);
          railResize.observe(list);
        }
      }
      layoutRail();
    }

    async function reveal() {
      if (seen || stopped) return;
      seen = true;
      intersection?.disconnect();
      if (motion.matches) return;
      const anime = await loadAnime();
      if (stopped || motion.matches || !anime) return;
      try {
        // Labels stay visible; only arrows or connector pseudo-elements animate.
        // Lebendig sind die Verbinder Stationspunkte, auch an der ersten Stufe.
        const items = compact || !lively() ? targets : Array.from(list.children);
        animation = anime.animate(items, {
          ...(compact ? { opacity: [0, 1] } : { "--wiki-kette-progress": [0, 1] }),
          duration: 220, delay: anime.stagger(70), ease: "outExpo",
        });
      } catch {
        finish();
      }
    }
    if (typeof IntersectionObserver !== "undefined") {
      intersection = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= .3)) reveal();
      }, { threshold: .3 });
      intersection.observe(host);
    }
    // Signal und Puls laufen nur, solange die Kette im Blick ist.
    if (typeof IntersectionObserver !== "undefined") {
      visibility = new IntersectionObserver((entries) => {
        visible = entries.some((entry) => entry.isIntersecting);
        figure.classList.toggle("wiki-kette--sichtbar", visible);
        pulses.forEach((pulse) => (visible ? pulse.play() : pulse.pause()));
      });
      visibility.observe(figure);
    } else {
      visible = true;
      figure.classList.add("wiki-kette--sichtbar");
    }
    function motionChanged() {
      if (motion.matches) finish();
      if (rail) layoutRail();
    }
    motion.addEventListener("change", motionChanged);
    window.addEventListener("wiki:look", applyLook);
    applyLook();

    return () => {
      stopped = true;
      intersection?.disconnect();
      visibility?.disconnect();
      motion.removeEventListener("change", motionChanged);
      window.removeEventListener("wiki:look", applyLook);
      dropRail();
      finish();
    };
  }

  onPage((article) => {
    const hosts = Array.from(article.querySelectorAll(".wiki-kette"));
    if (!hosts.length) return;
    let stopped = false;
    const cleanups = [];
    loadJson("assets/data/kette.json").then((data) => {
      if (stopped || data?.schema !== "kette_v1" || !Array.isArray(data.stufen)
        || data.stufen.length !== IDS.length) return;
      const fields = ["titel", "zweck", "einstellung", "anbindung", "api", "doku"];
      if (!data.stufen.every((stage, index) => stage?.id === IDS[index]
        && Object.hasOwn(STATES, stage.zustand)
        && fields.every((field) => typeof stage[field] === "string" && stage[field].trim()))) return;
      hosts.forEach((host) => cleanups.push(mount(host, data.stufen)));
    }).catch(() => { /* Keep the Markdown fallback when data is unavailable. */ });
    return () => {
      stopped = true;
      cleanups.forEach((cleanup) => cleanup());
    };
  });
})();
