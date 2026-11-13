/* Hilfen der Codebase-Bühne: Formate (de-DE, Europe/Berlin), Skalen, Treemap,
 * Gesten und Tweens. K.init(repo) bindet die geladenen Daten. */
(function () {
  "use strict";
  const K = (window.K = {});
  let R = null;
  K.init = (repo) => { R = repo; };
  K.DAY = 86400;

  const NUM = new Intl.NumberFormat("de-DE");
  K.fmt = (n) => NUM.format(Math.round(n));
  K.dec = (n, d) => n.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
  K.pct = (x) => Math.round(x * 100).toLocaleString("de-DE") + " %";
  /* Kurzform für große Zeilenzahlen: 13.210 → „13 Tsd.“, 1.664 → „1,7 Tsd.“ */
  K.kfmt = (n) => (n >= 1000 ? K.dec(n / 1000, n >= 10000 ? 0 : 1) + " Tsd." : String(Math.round(n)));

  const TZ = "Europe/Berlin";
  const fDate = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, day: "numeric", month: "short" });
  const fLong = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" });
  const fFull = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, day: "numeric", month: "long", year: "numeric" });
  const fTime = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const fParts = new Intl.DateTimeFormat("en-US", { timeZone: TZ, weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23" });
  const WD_EN = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };
  K.date = (t) => fDate.format(t * 1000);
  K.dateLong = (t) => fLong.format(t * 1000);
  K.dateFull = (t) => fFull.format(t * 1000);
  K.time = (t) => fTime.format(t * 1000);
  /** Stunde der Woche in Berlin, Montag 0:00 = 0 … Sonntag 23:59 ≈ 168. */
  K.weekHour = (t) => {
    const p = {};
    fParts.formatToParts(t * 1000).forEach((x) => (p[x.type] = x.value));
    return (WD_EN[p.weekday] ?? 0) * 24 + (+p.hour % 24) + (+p.minute) / 60;
  };
  K.WD = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
  K.WDS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  K.WDPL = ["Montags", "Dienstags", "Mittwochs", "Donnerstags", "Freitags", "Samstags", "Sonntags"];
  K.hh = (h) => String(h).padStart(2, "0") + ":00";

  K.clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  K.lerp = (a, b, t) => a + (b - a) * t;
  K.scale = (d0, d1, r0, r1) => { const f = (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0); f.inv = (p) => d0 + ((p - r0) / (r1 - r0 || 1)) * (d1 - d0); return f; };
  K.ease = (t) => 1 - Math.pow(1 - t, 4);
  K.base = (p) => p.slice(p.lastIndexOf("/") + 1);
  K.short = (s, n) => (s.length > n ? s.slice(0, Math.max(1, n - 1)) + "…" : s);
  K.esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  K.plural = (n, one, many) => (n === 1 ? one : many);

  /* Tween mit Abbruch; bei reduzierter Bewegung sofort am Ziel. */
  K.reduce = false;
  K.tween = function (ms, step, done) {
    if (K.reduce) { step(1, 1); if (done) done(); return () => {}; }
    const t0 = performance.now(); let raf;
    const tick = (now) => { const t = K.clamp((now - t0) / ms, 0, 1); step(K.ease(t), t); if (t < 1) raf = requestAnimationFrame(tick); else if (done) done(); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  };

  /* Zeilen je Kategorie zum Zeitpunkt t, linear zwischen den Tages-Schnappschüssen. */
  K.locAt = function (t) {
    const S = R.snapshots; const out = {}; const ids = R.cats.map((c) => c.id);
    if (!S.length || t <= S[0].t - K.DAY) { ids.forEach((id) => (out[id] = 0)); out.total = 0; return out; }
    let i = 0; while (i < S.length - 1 && S[i + 1].t <= t) i++;
    const a = t < S[0].t ? { t: S[0].t - K.DAY, loc: {} } : S[i]; const b = t < S[0].t ? S[0] : S[Math.min(i + 1, S.length - 1)];
    const u = b.t === a.t ? 1 : K.clamp((t - a.t) / (b.t - a.t), 0, 1); let tot = 0;
    ids.forEach((id) => { out[id] = K.lerp((a.loc || {})[id] || 0, (b.loc || {})[id] || 0, u); tot += out[id]; });
    out.total = tot; return out;
  };

  /* Squarified Treemap: items [{v,…}] → ergänzt x, y, w, h */
  K.treemap = function (items, x, y, w, h) {
    const list = items.filter((d) => d.v > 0).sort((a, b) => b.v - a.v);
    const total = list.reduce((s, d) => s + d.v, 0); if (!total) return list;
    const k = (w * h) / total; let i = 0;
    const worst = (row, side) => { const s = row.reduce((a, d) => a + d.v * k, 0); let mx = 0, mn = Infinity; row.forEach((d) => { const a = d.v * k; mx = Math.max(mx, a); mn = Math.min(mn, a); }); return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn)); };
    while (i < list.length) {
      const side = Math.min(w, h); const row = [list[i]]; let j = i + 1;
      while (j < list.length && worst(row.concat(list[j]), side) <= worst(row, side)) { row.push(list[j]); j++; }
      const s = row.reduce((a, d) => a + d.v * k, 0);
      if (w >= h) { const cw = s / h; let cy = y; row.forEach((d) => { const ch = (d.v * k) / cw; d.x = x; d.y = cy; d.w = cw; d.h = ch; cy += ch; }); x += cw; w -= cw; }
      else { const ch = s / w; let cx = x; row.forEach((d) => { const cw = (d.v * k) / ch; d.x = cx; d.y = y; d.w = cw; d.h = ch; cx += cw; }); y += ch; h -= ch; }
      i = j;
    }
    return list;
  };

  /* Zeigergesten: Tippen und Ziehen (mit Wurfgeschwindigkeit). Der Zeiger wird
   * erst beim Ziehen eingefangen, damit Klicks auf Buttons normal ankommen.
   * Das Mausrad wird nur horizontal (oder mit Umschalt) ausgewertet; vertikal
   * läuft es immer an die Seite weiter. h.skip(e) schließt Ziele aus. */
  K.gesture = function (el, h) {
    let st = null;
    el.addEventListener("pointerdown", (e) => {
      if (st || e.button > 0 || (h.skip && h.skip(e))) return;
      st = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, t: performance.now(), moved: false, target: e.target, vx: 0, vy: 0 };
      if (h.down) h.down({ x: e.clientX, y: e.clientY, target: e.target, type: e.pointerType });
    });
    el.addEventListener("pointermove", (e) => {
      if (!st || e.pointerId !== st.id) return;
      const now = performance.now(); const dx = e.clientX - st.x, dy = e.clientY - st.y; const dt = Math.max(1, now - st.t);
      if (!st.moved && Math.hypot(e.clientX - st.x0, e.clientY - st.y0) > 8) {
        st.moved = true;
        try { el.setPointerCapture(e.pointerId); } catch (_) { /* Zeiger schon weg */ }
        if (h.dragstart) h.dragstart({ x: st.x0, y: st.y0, target: st.target, tx: e.clientX - st.x0, ty: e.clientY - st.y0 });
      }
      if (st.moved) { st.vx = K.lerp(st.vx, dx / dt, 0.5); st.vy = K.lerp(st.vy, dy / dt, 0.5); if (h.drag) h.drag({ dx, dy, x: e.clientX, y: e.clientY, tx: e.clientX - st.x0, ty: e.clientY - st.y0, target: st.target }); }
      st.x = e.clientX; st.y = e.clientY; st.t = now;
    });
    el.addEventListener("pointerup", (e) => {
      if (!st || e.pointerId !== st.id) return;
      const idle = performance.now() - st.t > 90;
      if (st.moved) { if (h.dragend) h.dragend({ vx: idle ? 0 : st.vx, vy: idle ? 0 : st.vy, tx: st.x - st.x0, ty: st.y - st.y0, x: st.x, y: st.y }); }
      else if (h.tap) h.tap({ x: st.x, y: st.y, target: st.target });
      if (h.up) h.up(); st = null;
    });
    /* Abbruch, z. B. wenn der Browser das vertikale Wischen als Seitenscrollen übernimmt. */
    el.addEventListener("pointercancel", (e) => {
      if (!st || e.pointerId !== st.id) return;
      if (h.cancel) h.cancel(); st = null;
    });
    el.addEventListener("wheel", (e) => {
      if (e.ctrlKey || e.metaKey || !h.wheel) return;
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
      let dx = e.deltaX * unit, dy = e.deltaY * unit;
      if (e.shiftKey && !dx) { dx = dy; dy = 0; }
      if (!dx || Math.abs(dx) <= Math.abs(dy)) return;
      if (h.wheel({ dx: -dx }) !== false) e.preventDefault();
    }, { passive: false });
  };

  K.svg = function (tag, attrs, parent) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) for (const k in attrs) { if (k === "text") el.textContent = attrs[k]; else if (attrs[k] != null) el.setAttribute(k, attrs[k]); }
    if (parent) parent.appendChild(el); return el;
  };
  K.el = function (tag, cls, parent, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; };
})();
