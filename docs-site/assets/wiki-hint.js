/* Shared, delegated hints with pointer, keyboard and touch support. */
(function () {
  "use strict";

  const { onPage, make } = window.wiki;
  const providers = new Map();
  window.wiki.hint = { register: (kind, provider) => providers.set(kind, provider) };

  onPage(() => {
    const popup = make("div", "wiki-hint");
    popup.id = "wiki-hint";
    popup.setAttribute("role", "tooltip");
    popup.hidden = true;
    document.body.append(popup);
    const listeners = new AbortController();
    let target = null;
    let requestedTarget = null;
    let touchIntent = null;
    let openTimer;
    let closeTimer;
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
      cancelClose();
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
      popup.hidden = true;
    }

    function position(element) {
      const rect = element.getBoundingClientRect();
      const size = popup.getBoundingClientRect();
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - size.width - 8));
      const below = rect.bottom + 8;
      const top = below + size.height <= window.innerHeight - 8 ? below : rect.top - size.height - 8;
      popup.style.left = `${left + window.scrollX}px`;
      popup.style.top = `${Math.max(8, Math.min(top, window.innerHeight - size.height - 8)) + window.scrollY}px`;
    }

    async function open(element) {
      clearTimeout(openTimer);
      cancelClose();
      if (target === element || requestedTarget === element) return;
      close();
      const id = requestId;
      requestedTarget = element;
      let timeout;
      const content = await Promise.race([
        Promise.resolve().then(() => providers.get(element.dataset.hint)(element)).catch(() => null),
        new Promise((resolve) => { timeout = setTimeout(() => resolve(null), 2000); }),
      ]);
      clearTimeout(timeout);
      if (id !== requestId || !element.isConnected) return;
      requestedTarget = null;
      if (!content) return;
      popup.replaceChildren(content);
      popup.hidden = false;
      position(element);
      popup.dataset.open = "true";
      target = element;
      const ids = (element.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
      element.setAttribute("aria-describedby", [...new Set([...ids, popup.id])].join(" "));
    }

    function scheduleClose() {
      clearTimeout(openTimer);
      cancelClose();
      closeTimer = setTimeout(close, 150);
    }

    function listen(element, event, handler, capture = false) {
      element.addEventListener(event, handler, { capture, signal: listeners.signal });
    }

    listen(document, "pointerenter", (event) => {
      const element = findTarget(event.target);
      if (!element || event.target !== element || event.pointerType === "touch") return;
      cancelClose();
      clearTimeout(openTimer);
      openTimer = setTimeout(() => open(element), 300);
    }, true);
    listen(document, "pointerleave", (event) => {
      const element = findTarget(event.target);
      if (!element || event.target !== element || event.pointerType === "touch") return;
      if (popup.contains(event.relatedTarget)) return;
      scheduleClose();
    }, true);
    listen(popup, "pointerenter", cancelClose);
    listen(popup, "pointerleave", (event) => {
      if (!target?.contains(event.relatedTarget)) scheduleClose();
    });
    listen(document, "focusin", (event) => {
      if (popup.contains(event.target)) { cancelClose(); return; }
      const element = findTarget(event.target);
      if (element && element !== touchIntent) open(element);
    });
    listen(document, "focusout", (event) => {
      const element = findTarget(event.target);
      if (!element && !popup.contains(event.target)) return;
      if (popup.contains(event.relatedTarget) || element?.contains(event.relatedTarget)) return;
      close();
    });
    listen(document, "keydown", (event) => {
      if (event.key === "Escape") close();
    });
    listen(document, "pointerdown", (event) => {
      const element = findTarget(event.target);
      touchIntent = event.pointerType === "touch" && element !== target ? element : null;
      if (!element && !popup.contains(event.target)) close();
    }, true);
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
    listen(window, "scroll", close, true);
    listen(window, "resize", close);

    return () => {
      close();
      listeners.abort();
      popup.remove();
    };
  });
})();
