/* Data-driven processing chain with shared hints and page-scoped motion. */
(function () {
  "use strict";

  const { onPage, siteUrl, loadJson, make, hint } = window.wiki;
  const ANIME_URL = new URL("vendor/anime-4.5.0.umd.min.js", document.currentScript.src).href;
  const IDS = ["frames", "detect", "track", "rectify", "ocr", "validate", "sink"];
  const STATES = { fertig: "resolved", gebaut: "progress", teilweise: "partial", "außer Betrieb": "discarded" };
  const stagesByNode = new WeakMap();
  let animePromise;

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
    const figure = make("figure", "wiki-kette-figure");
    const list = make("ol", "wiki-kette-list");
    for (const stage of stages) {
      const item = make("li");
      const node = make("a", "wiki-kette-node");
      node.href = siteUrl(stage.api);
      node.dataset.hint = "kette";
      node.dataset.stufe = stage.id;
      node.append(make("span", "wiki-kette-id", `${stage.id}/`),
        make("span", "wiki-kette-titel", stage.titel), chip(stage));
      stagesByNode.set(node, stage);
      item.append(node);
      list.append(item);
    }
    figure.append(list);
    if (host.dataset.variant !== "kompakt") {
      figure.append(make("figcaption", "", "Verarbeitungskette · Überfahren zeigt Zweck und Anbindung"));
    }
    host.replaceChildren(figure);

    const lines = Array.from(list.children).slice(1);
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let stopped = false;
    let animation = null;
    let seen = false;
    let layoutVersion = 0;
    let intersection;
    let resize;

    function finish() {
      animation?.revert();
      animation = null;
      lines.forEach((line) => line.style.removeProperty("--wiki-kette-progress"));
    }

    function setWidth(width) {
      const horizontal = width >= 600;
      if (horizontal !== figure.classList.contains("wiki-kette--quer")) {
        layoutVersion += 1;
        finish();
      }
      host.classList.toggle("wiki-kette--quer", horizontal);
      figure.classList.toggle("wiki-kette--quer", horizontal);
    }
    setWidth(host.getBoundingClientRect().width);
    if (typeof ResizeObserver !== "undefined") {
      resize = new ResizeObserver((entries) => {
        if (!stopped) setWidth(entries[0].contentRect.width);
      });
      resize.observe(host);
    }

    async function reveal() {
      if (seen || stopped) return;
      seen = true;
      intersection?.disconnect();
      if (motion.matches) return;
      const version = layoutVersion;
      const anime = await loadAnime();
      if (stopped || motion.matches || !anime || version !== layoutVersion) return;
      try {
        // The inherited property scales only the connector pseudo-elements.
        animation = anime.animate(lines, {
          "--wiki-kette-progress": [0, 1],
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
    function motionChanged() {
      if (motion.matches) finish();
    }
    motion.addEventListener("change", motionChanged);

    return () => {
      stopped = true;
      intersection?.disconnect();
      resize?.disconnect();
      motion.removeEventListener("change", motionChanged);
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
