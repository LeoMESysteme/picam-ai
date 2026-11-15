/* Federn und Zähler der lebendigen Darstellung (Teil von wiki.css, Abschnitt
 * „Lebendig: Federn und Zähler“).
 *
 * - Aufklappen: Die Höhenfeder liefert CSS (interpolate-size + ::details-content).
 *   Hier steht nur der Rückfall für Browser ohne diese Technik: FLIP über die
 *   Web Animations API, die Höhe des details-Elements wird kurz animiert und
 *   danach wieder auf „auto“ gelassen.
 * - Zahlen: Kennzahlen in Kernsätzen und Wertpillen der Diagramme zählen beim
 *   ersten Sichtbarwerden einmal hoch. Danach steht der Originaltext wieder
 *   unverändert da; Screenreader bekommen immer den Endwert.
 * In der ruhigen Darstellung und bei reduzierter Bewegung passiert nichts. */
(function () {
  "use strict";

  const { onPage } = window.wiki;
  const root = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const lively = () => root.getAttribute("data-wiki-look") === "lebendig";
  const active = () => lively() && !reduce.matches;

  const FEDER = "details.wiki-layer, details.wiki-chart-table, details.wiki-allpages, .wiki-occ details, details.mkdocstrings-source";
  const EASE_OPEN = "cubic-bezier(.22, 1.02, .36, 1)";
  const EASE_CLOSE = "cubic-bezier(.16, 1, .3, 1)";
  const supportsCss = () => !!(window.CSS && CSS.supports
    && CSS.supports("selector(::details-content)") && CSS.supports("interpolate-size: allow-keywords"));

  /* ---------------------------------------------------------- Aufklappen ---- */
  function flipDetails(details, opening) {
    details.getAnimations().forEach((animation) => animation.cancel());
    const from = details.getBoundingClientRect().height;
    if (opening) details.open = true;
    else details.setAttribute("data-closing", "");
    // Geschlossen = Höhe der Zusammenfassung samt Rahmen.
    const summary = details.querySelector(":scope > summary");
    const closedHeight = () => {
      const style = getComputedStyle(details);
      return summary.getBoundingClientRect().height + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
    };
    const to = opening ? details.getBoundingClientRect().height : closedHeight();
    const animation = details.animate(
      [{ height: `${from}px`, overflow: "hidden" }, { height: `${to}px`, overflow: "hidden" }],
      { duration: opening ? 360 : 220, easing: opening ? EASE_OPEN : EASE_CLOSE },
    );
    const done = () => {
      details.removeAttribute("data-closing");
      if (!opening) details.open = false;
    };
    animation.addEventListener("finish", done, { once: true });
    animation.addEventListener("cancel", () => details.removeAttribute("data-closing"), { once: true });
  }

  function details(signal) {
    document.addEventListener("click", (event) => {
      if (!active() || supportsCss() || event.defaultPrevented) return;
      const summary = event.target instanceof Element ? event.target.closest("summary") : null;
      const host = summary?.parentElement;
      if (!host || host.tagName !== "DETAILS" || !host.matches(FEDER) || host.querySelector(":scope > summary") !== summary) return;
      // Links in der Zusammenfassung behalten ihr Verhalten.
      if (event.target.closest("a[href]")) return;
      event.preventDefault();
      flipDetails(host, !host.open || host.hasAttribute("data-closing"));
    }, { capture: true, signal });
  }

  /* -------------------------------------------------------------- Zahlen ---- */
  const UNITS = "Zeilen|Dateien|Code|Tests|Doku|Stufen|Workflows|Systemd-Units|Units|Definitionen|Skripte|Branches|Quelldateien|Commits|Funktionen|Stellen|Seiten|Module";
  const NUMBER_IN_TEXT = new RegExp(`(?<![\\d.,\\w-])(\\d{1,3}(?:\\.\\d{3})+|\\d+)(,\\d+)?(?=[\\s\\u00a0\\u202f](?:${UNITS})(?![\\w-]))`, "g");
  const NUMBER_ONLY = /^(\d{1,3}(?:\.\d{3})+|\d+)(,\d+)?(\s?%)?$/;
  const running = new Set();

  function clearly(int) {
    // Vierstellige Zahlen ohne Tausenderpunkt sind Jahre oder Nummern.
    return int.includes(".") || int.length < 4;
  }

  function target(int, frac) {
    return { value: Number(`${int.replace(/\./g, "")}.${frac ? frac.slice(1) : "0"}`), decimals: frac ? frac.length - 1 : 0 };
  }

  function format(value, decimals) {
    return value.toLocaleString("de-DE", { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: true });
  }

  /* Zählt `item.show(text)` von 0 auf den Endwert; `item.finish()` setzt den Original. */
  function count(item, delay = 0, duration = 800) {
    const t0 = performance.now() + delay;
    let frame = 0;
    const entry = { stop() { cancelAnimationFrame(frame); running.delete(entry); item.finish(); } };
    running.add(entry);
    function tick(now) {
      if (!active()) { entry.stop(); return; }
      const t = Math.min(1, Math.max(0, (now - t0) / duration));
      if (t >= 1) { entry.stop(); return; }
      // outExpo wie die Balken der Diagramme.
      const eased = t === 0 ? 0 : 1 - 2 ** (-10 * t);
      item.show(format(item.value * eased, item.decimals));
      frame = requestAnimationFrame(tick);
    }
    item.show(format(0, item.decimals));
    frame = requestAnimationFrame(tick);
    return entry;
  }

  /* Zahlen im Fließtext in <span class="wiki-zahl"> hüllen (Zählung erst beim Sichtbarwerden). */
  function wrapNumbers(host) {
    const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => node.parentElement.closest("code, pre, a, svg, .wiki-zahl, script, style")
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const items = [];
    for (const node of nodes) {
      const text = node.nodeValue;
      NUMBER_IN_TEXT.lastIndex = 0;
      const parts = [];
      let last = 0;
      for (let match; (match = NUMBER_IN_TEXT.exec(text));) {
        if (!clearly(match[1])) continue;
        parts.push({ start: match.index, end: match.index + match[0].length, text: match[0], ...target(match[1], match[2]) });
      }
      if (!parts.length) continue;
      const fragment = document.createDocumentFragment();
      for (const part of parts) {
        if (part.start > last) fragment.append(text.slice(last, part.start));
        const span = document.createElement("span");
        span.className = "wiki-zahl";
        span.textContent = part.text;
        fragment.append(span);
        items.push({ span, original: part.text, value: part.value, decimals: part.decimals });
        last = part.end;
      }
      if (last < text.length) fragment.append(text.slice(last));
      node.replaceWith(fragment);
    }
    return items;
  }

  function proseItem(raw) {
    const { span, original } = raw;
    let visible = null;
    let hidden = null;
    return {
      value: raw.value, decimals: raw.decimals,
      show(text) {
        if (!visible) {
          // Breite des Endwerts halten, damit der Satz nicht wackelt.
          span.style.minWidth = `${span.getBoundingClientRect().width}px`;
          span.classList.add("is-counting");
          visible = document.createElement("span");
          visible.setAttribute("aria-hidden", "true");
          hidden = document.createElement("span");
          hidden.className = "wiki-zahl-sr";
          hidden.textContent = original;
          span.replaceChildren(visible, hidden);
        }
        visible.textContent = text;
      },
      finish() {
        if (!span.isConnected && !span.parentNode) return;
        span.replaceChildren(document.createTextNode(original));
        span.classList.remove("is-counting");
        span.style.minWidth = "";
        visible = hidden = null;
      },
    };
  }

  function pillItem(textNode) {
    const original = textNode.textContent;
    const match = NUMBER_ONLY.exec(original.trim());
    if (!match) return null;
    const { value, decimals } = target(match[1], match[2]);
    return {
      value, decimals,
      show(text) { textNode.textContent = match[3] ? `${text}${match[3]}` : text; },
      finish() { textNode.textContent = original; },
    };
  }

  function visibleFirst(elements, start) {
    if (typeof IntersectionObserver === "undefined") { elements.forEach(start); return () => {}; }
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        start(entry.target);
      }
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.01 });
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }

  function numbers(article, cleanups) {
    // Kernsätze: Absatz direkt unter jeder Überschrift der Codebase-Seite sowie die Statusreihe.
    const hosts = [];
    if (article.querySelector("#codebase-stage")) {
      article.querySelectorAll("h2").forEach((heading) => {
        const next = heading.nextElementSibling;
        if (next?.tagName === "P") hosts.push(next);
      });
    }
    article.querySelectorAll(".wiki-stand-text").forEach((element) => hosts.push(element));
    // Eingehüllt wird erst beim Sichtbarwerden und nur in der lebendigen
    // Darstellung; sonst bleibt das DOM der Seite unberührt.
    const wrapped = [];
    for (const host of hosts) {
      cleanups.push(visibleFirst([host], () => {
        if (!active()) return;
        const items = wrapNumbers(host).map(proseItem);
        wrapped.push(...items);
        items.forEach((item, index) => count(item, index * 60, 800));
      }));
    }
    cleanups.push(() => wrapped.forEach((item) => item.finish()));

    // Wertpillen: starten, sobald ihr Balken sie einblendet (Opazität steigt).
    // Die Diagramme baut wiki-chart.js, das nach diesem Skript geladen wird.
    let figureCleanup = () => {};
    const figureFrame = requestAnimationFrame(() => {
      figureCleanup = pillsOf([...article.querySelectorAll(".wiki-chart-figure")]);
    });
    cleanups.push(() => { cancelAnimationFrame(figureFrame); figureCleanup(); });
  }

  function pillsOf(figures) {
    return visibleFirst(figures, (figure) => {
      if (!active()) return;
      const pills = [...figure.querySelectorAll(".wiki-chart-pill")]
        .map((pill) => ({ pill, item: pillItem(pill.querySelector(".wiki-chart-value")) }))
        .filter((entry) => entry.item);
      if (!pills.length) return;
      const began = performance.now();
      let growing = false;
      let frame = 0;
      const entry = {
        stop() {
          cancelAnimationFrame(frame);
          running.delete(entry);
          // Nie auf einem Zählerstand stehen bleiben.
          pills.forEach((current) => { if (!current.started) current.item.finish(); });
        },
      };
      running.add(entry);
      function poll(now) {
        if (!active() || !figure.isConnected || now - began > 4000) { entry.stop(); return; }
        const opacity = pills.map(({ pill }) => Number(getComputedStyle(pill).opacity));
        if (!growing) {
          if (opacity.some((value) => value < 0.99)) {
            growing = true;
            pills.forEach(({ item }) => item.show(format(0, item.decimals)));
          } else if (now - began > 1500) { entry.stop(); return; }
        }
        if (growing) {
          pills.forEach((current, index) => {
            if (current.started || opacity[index] < 0.05) return;
            current.started = true;
            current.stopCount = count(current.item, 0, 700);
          });
          if (pills.every((current) => current.started)) { entry.stop(); return; }
        }
        frame = requestAnimationFrame(poll);
      }
      frame = requestAnimationFrame(poll);
    });
  }

  onPage((article) => {
    const controller = new AbortController();
    const cleanups = [];
    details(controller.signal);
    numbers(article, cleanups);
    const settle = () => {
      if (!active()) [...running].forEach((entry) => entry.stop());
    };
    window.addEventListener("wiki:look", settle, { signal: controller.signal });
    reduce.addEventListener("change", settle, { signal: controller.signal });
    return () => {
      controller.abort();
      [...running].forEach((entry) => entry.stop());
      cleanups.forEach((cleanup) => cleanup());
      document.querySelectorAll("details[data-closing]").forEach((element) => element.removeAttribute("data-closing"));
    };
  });
})();
