/* Shared, delegated hints with pointer, keyboard and touch support. */
(function () {
  "use strict";

  const { onPage, make } = window.wiki;
  const providers = new Map();
  const hint = window.wiki.hint = {
    register: (kind, provider) => providers.set(kind, provider),
    closeWithin: () => {},
  };

  onPage(() => {
    const popup = make("div", "wiki-hint");
    popup.id = "wiki-hint";
    popup.setAttribute("role", "tooltip");
    popup.hidden = true;
    document.body.append(popup);
    const listeners = new AbortController();
    let target = null;
    // Owns both the hover delay and the asynchronous provider request.
    let requestedTarget = null;
    let dismissedFocusTarget = null;
    let touchIntent = null;
    let openTimer = null;
    let closeTimer;
    let positionFrame = null;
    let hideTimer = null;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)");
    const lively = () => document.documentElement.getAttribute("data-wiki-look") === "lebendig";
    let requestId = 0;

    function findTarget(node) {
      const element = node instanceof Element ? node.closest("[data-hint]") : null;
      return element && providers.has(element.dataset.hint) ? element : null;
    }

    function cancelClose() {
      clearTimeout(closeTimer);
    }

    function close() {
      clearTimeout(openTimer);
      openTimer = null;
      cancelClose();
      if (positionFrame !== null) cancelAnimationFrame(positionFrame);
      positionFrame = null;
      requestId += 1;
      requestedTarget = null;
      if (target) {
        const ids = (target.getAttribute("aria-describedby") || "").split(/\s+/)
          .filter((id) => id && id !== popup.id);
        if (ids.length) target.setAttribute("aria-describedby", ids.join(" "));
        else target.removeAttribute("aria-describedby");
      }
      target = null;
      popup.removeAttribute("data-open");
      clearTimeout(hideTimer);
      if (lively() && !reduce.matches && !popup.hidden) {
        // Lebendig: kurz zurück in den Begriff schrumpfen, dann erst verbergen.
        hideTimer = setTimeout(() => { popup.hidden = true; }, 130);
      } else {
        popup.hidden = true;
      }
    }

    hint.closeWithin = (container) => {
      if (container.contains(target) || container.contains(requestedTarget)) close();
    };

    function position(element) {
      const rect = element.getBoundingClientRect();
      // Layoutmaß statt Rechteck: das Pop-up wächst per scale aus dem Begriff.
      const size = { width: popup.offsetWidth, height: popup.offsetHeight };
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - size.width - 8));
      const below = rect.bottom + 8;
      const top = below + size.height <= window.innerHeight - 8 ? below : rect.top - size.height - 8;
      const placedTop = Math.max(8, Math.min(top, window.innerHeight - size.height - 8));
      popup.style.left = `${left + window.scrollX}px`;
      popup.style.top = `${placedTop + window.scrollY}px`;
      // Ursprung der lebendigen Wachstumsbewegung: Mitte des Begriffs, an seiner nächsten Kante.
      const anchorX = Math.max(0, Math.min(size.width, rect.left + Math.min(rect.width / 2, 40) - left));
      const anchorY = Math.max(0, Math.min(size.height, (placedTop + 1 >= rect.bottom ? rect.bottom : rect.top) - placedTop));
      popup.style.transformOrigin = `${anchorX}px ${anchorY}px`;
    }

    function schedulePosition(event) {
      if (event.target instanceof Node && popup.contains(event.target)) return;
      if (!target || positionFrame !== null) return;
      positionFrame = requestAnimationFrame(() => {
        positionFrame = null;
        if (!target?.isConnected) { close(); return; }
        const rect = target.getBoundingClientRect();
        if (rect.bottom <= 0 || rect.top >= window.innerHeight
          || rect.right <= 0 || rect.left >= window.innerWidth) {
          close();
          return;
        }
        position(target);
      });
    }

    function open(element, delay = 0) {
      cancelClose();
      if (target === element) return;
      if (requestedTarget === element) {
        // Focus can advance its own hover delay, but cannot duplicate a provider.
        if (delay || openTimer === null) return;
        clearTimeout(openTimer);
      } else {
        // Supersede an older provider as soon as a new intent arrives.
        close();
        requestedTarget = element;
      }
      const id = requestId;
      if (delay) {
        openTimer = setTimeout(() => {
          if (id !== requestId || requestedTarget !== element) return;
          openTimer = null;
          load(element, id);
        }, delay);
      } else {
        openTimer = null;
        load(element, id);
      }
    }

    async function load(element, id) {
      if (id !== requestId || requestedTarget !== element || !element.isConnected) return;
      let timeout;
      const content = await Promise.race([
        Promise.resolve().then(() => providers.get(element.dataset.hint)(element)).catch(() => null),
        new Promise((resolve) => { timeout = setTimeout(() => resolve(null), 2000); }),
      ]);
      clearTimeout(timeout);
      if (id !== requestId || requestedTarget !== element || !element.isConnected) return;
      requestedTarget = null;
      if (!content) return;
      clearTimeout(hideTimer);
      popup.replaceChildren(content);
      popup.hidden = false;
      position(element);
      popup.dataset.open = "true";
      target = element;
      const ids = (element.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
      element.setAttribute("aria-describedby", [...new Set([...ids, popup.id])].join(" "));
    }

    function scheduleClose(element) {
      // A late leave from another target must not cancel the current intent.
      if (element !== target && element !== requestedTarget) return;
      // No popup exists during the hover delay; retire this intent completely
      // so re-entering can start a fresh delay instead of reusing a dead one.
      if (openTimer !== null) { close(); return; }
      cancelClose();
      const id = requestId;
      closeTimer = setTimeout(() => {
        if (id === requestId && (element === target || element === requestedTarget)) close();
      }, 150);
    }

    function listen(element, event, handler, capture = false) {
      element.addEventListener(event, handler, { capture, signal: listeners.signal });
    }

    listen(document, "pointerenter", (event) => {
      const element = findTarget(event.target);
      if (!element || event.target !== element || event.pointerType === "touch") return;
      touchIntent = null;
      open(element, 300);
    }, true);
    listen(document, "pointerleave", (event) => {
      const element = findTarget(event.target);
      if (!element || event.target !== element || event.pointerType === "touch") return;
      if (popup.contains(event.relatedTarget)) return;
      scheduleClose(element);
    }, true);
    listen(popup, "pointerenter", cancelClose);
    listen(popup, "pointerleave", (event) => {
      const element = target || requestedTarget;
      if (element && !element.contains(event.relatedTarget)) scheduleClose(element);
    });
    listen(document, "focusin", (event) => {
      if (popup.contains(event.target)) { cancelClose(); return; }
      const element = findTarget(event.target);
      if (element !== dismissedFocusTarget) dismissedFocusTarget = null;
      if (element && element !== touchIntent && element !== dismissedFocusTarget) open(element);
    });
    listen(document, "focusout", (event) => {
      const element = findTarget(event.target);
      if (!element && !popup.contains(event.target)) return;
      if (element?.contains(event.relatedTarget)) return;
      if (element === dismissedFocusTarget) dismissedFocusTarget = null;
      if (popup.contains(event.relatedTarget)) return;
      if (element && element !== target && element !== requestedTarget) return;
      close();
    });
    listen(document, "keydown", (event) => {
      if (event.key !== "Escape") return;
      dismissedFocusTarget = findTarget(document.activeElement);
      close();
    });
    listen(document, "pointerdown", (event) => {
      const element = findTarget(event.target);
      touchIntent = event.pointerType === "touch" && element !== target ? element : null;
      if (touchIntent || (!element && !popup.contains(event.target))) close();
    }, true);
    listen(document, "pointercancel", () => { touchIntent = null; }, true);
    listen(document, "click", (event) => {
      const element = findTarget(event.target);
      if (element && element === touchIntent) {
        event.preventDefault();
        // Zensical's body click handler does not check defaultPrevented.
        event.stopPropagation();
        open(element);
      }
      touchIntent = null;
    }, true);
    listen(window, "scroll", schedulePosition, true);
    listen(window, "resize", schedulePosition);

    return () => {
      close();
      hint.closeWithin = () => {};
      listeners.abort();
      clearTimeout(hideTimer);
      popup.remove();
    };
  });
})();
