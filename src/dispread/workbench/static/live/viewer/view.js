// Grafikfenster der Live-Seite: Bildquelle, Zoom/Verschieben, HUD und
// Markierungs-Info. createViewer() ist die reine Ansicht auf einer Canvas
// (ohne DOM-Annahmen, in node testbar); mountViewer() baut Werkzeugleiste,
// Ebenen-Menue, Legende, Chips und Popover drumherum.
//
// Bildkoordinaten sind die der gezeigten Quelle; fuer Live und Standbild
// das Kamerabild (hud.w × hud.h). Das 960 px breite Vorschau-JPEG wird auf
// diese Groesse gezogen, damit HUD und Bild denselben Raum teilen.
// Bildschirmkoordinaten sind CSS-px relativ zur Canvas.
import {ALL_LAYERS, LAYERS, drawHud, hitTest, markerInfo} from './hud.js';
import {renderLegend} from './legend.js';

const ZOOM_MIN = 0.05;
const ZOOM_MAX = 16;
const STILL_NAMES = {still: 'overlay_source', abtast: 'overlay_sampling', entz: 'overlay_rectified'};
const SOURCES = [['live', 'Live'], ['still', 'Standbild'], ['abtast', 'Abtastbild'], ['entz', 'Entzerrt']];
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

export function createViewer(canvas, opts = {}) {
  const dprOf = () => opts.dpr || Math.min(globalThis.devicePixelRatio || 1, 2);
  const schedule = opts.schedule || ((fn) => globalThis.requestAnimationFrame(fn));
  const now = opts.now || (() => globalThis.performance.now());
  const ctx = canvas.getContext('2d');
  const state = {
    src: 'live', layers: new Set(ALL_LAYERS), hud: null, frame: null, frameAt: null, frames: [],
    stills: {}, views: {}, auto: {live: true}, hover: null, pinned: null, pointer: null, queued: false,
  };
  const viewKey = () => (state.src === 'still' ? 'live' : state.src);
  const size = () => [canvas.clientWidth || 0, canvas.clientHeight || 0];

  function image() {
    if (state.src === 'live') return state.frame;
    const still = state.stills[state.src];
    return still?.ready ? still.img : null;
  }

  function dims() {
    if (state.src === 'live' || state.src === 'still') {
      if (finite(state.hud?.w) && finite(state.hud?.h)) return [state.hud.w, state.hud.h];
      const img = state.src === 'live' ? state.frame : state.stills.still?.ready && state.stills.still.img;
      const w = img?.naturalWidth || img?.width, h = img?.naturalHeight || img?.height;
      return w && h ? [w, h] : null;
    }
    const still = state.stills[state.src];
    return still?.ready ? [still.img.naturalWidth || still.img.width, still.img.naturalHeight || still.img.height] : null;
  }

  function fitRect([x0, y0, x1, y1]) {
    const [W, H] = size();
    const s = Math.min(W / (x1 - x0), H / (y1 - y0)) * 0.98;
    return {s, ox: W / 2 - ((x0 + x1) / 2) * s, oy: H / 2 - ((y0 + y1) / 2) * s};
  }

  // Erster Blick auf die Anzeige: Viereck und Rahmenbereiche mit Rand,
  // solange der Bediener nichts verschoben hat. Sonst das ganze Bild.
  function autoView() {
    const d = dims();
    if (!d) return null;
    const quad = state.hud?.track?.quad;
    if (viewKey() === 'live' && Array.isArray(quad) && quad.length === 4) {
      const pts = [...quad, ...(state.hud.track.regions || []).map((r) => r?.c).filter(Array.isArray)]
        .filter((p) => finite(p[0]) && finite(p[1]));
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const pad = Math.max(60, 0.15 * (Math.max(...xs) - Math.min(...xs)));
      return fitRect([Math.max(0, Math.min(...xs) - pad), Math.max(0, Math.min(...ys) - pad),
        Math.min(d[0], Math.max(...xs) + pad), Math.min(d[1], Math.max(...ys) + pad)]);
    }
    return fitRect([0, 0, d[0], d[1]]);
  }

  function view() {
    const key = viewKey();
    const [W, H] = size();
    if (!state.views[key] || state.views[key].W !== W || state.views[key].H !== H) {
      const previous = state.views[key];
      if (previous && !state.auto[key]) {
        // Groessenaenderung: Bildmitte bleibt in der Mitte.
        previous.ox += (W - previous.W) / 2;
        previous.oy += (H - previous.H) / 2;
        previous.W = W;
        previous.H = H;
      } else {
        const next = autoView();
        if (next) state.views[key] = {...next, W, H};
      }
    }
    return state.views[key] || {s: 1, ox: 0, oy: 0, W, H};
  }

  function setView(next) {
    const key = viewKey();
    const [W, H] = size();
    state.views[key] = {...next, W, H};
    state.auto[key] = false;
    // Angeheftetes Popover wandert mit dem Bildpunkt.
    if (state.pinned) refreshMarker();
    redraw();
    opts.onView?.(api.zoom());
  }

  const imageToScreen = ([x, y]) => { const v = view(); return [v.ox + x * v.s, v.oy + y * v.s]; };
  const screenToImage = ([x, y]) => { const v = view(); return [(x - v.ox) / v.s, (y - v.oy) / v.s]; };
  const frameAgeS = () => (state.frameAt == null ? 0 : (now() - state.frameAt) / 1000);

  function viewState() {
    const v = view();
    return {imageToScreen, screenToImage, width: v.W, height: v.H, scale: v.s, dpr: dprOf(),
      hover: state.pinned || state.hover, frameAgeS: frameAgeS(), source: state.src};
  }

  function draw() {
    state.queued = false;
    const dpr = dprOf();
    const [W, H] = size();
    const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
    if (canvas.width !== bw) canvas.width = bw;
    if (canvas.height !== bh) canvas.height = bh;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = '#0d0c0b';
    ctx.fillRect(0, 0, bw, bh);
    const img = image();
    const d = dims();
    const v = view();
    if (img && d) {
      ctx.setTransform(dpr * v.s, 0, 0, dpr * v.s, dpr * v.ox, dpr * v.oy);
      // Ab 2,2 Geraetepixeln je Quellpixel ohne Glaetten: Bildpunkte bleiben sichtbar.
      ctx.imageSmoothingEnabled = (v.s * dpr * d[0]) / (img.width || d[0]) < 2.2;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, 0, 0, d[0], d[1]);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Live-HUD gehoert nur zum Live-Bild: Standbilder tragen ihre eigene
    // Geometrie, ein Live-Viereck darueber laege auf einem anderen Bild.
    if (state.src === 'live' && state.hud) drawHud(ctx, state.hud, viewState(), state.layers);
    opts.paint?.(ctx, viewState());
  }

  function redraw() {
    if (state.queued) return;
    state.queued = true;
    schedule(draw);
  }

  // Nach neuem Bild oder neuer Ansicht: angeheftete Info aus dem neuen HUD
  // neu bauen (Zahlen laufen mit), gezeigte Info am Zeiger neu treffen.
  function refreshMarker() {
    if (!state.pinned && !state.hover) return;
    if (!state.pinned) {
      state.hover = state.pointer ? hitAt(state.pointer) : null;
      opts.onMarker?.(state.hover, {screen: state.pointer, pinned: false});
      return;
    }
    const info = state.src === 'live' ? markerInfo(state.hud, state.pinned.kind, state.pinned.index) : null;
    if (!info) {
      state.pinned = null;
      opts.onMarker?.(null, {});
      return;
    }
    state.pinned = {...state.pinned, ...info};
    opts.onMarker?.(info, {screen: imageToScreen(state.pinned.anchor), pinned: true});
  }

  function hitAt(screen) {
    if (state.src !== 'live' || !state.hud) return null;
    return hitTest(state.hud, screenToImage(screen), {scale: view().s, layers: state.layers});
  }

  function unpin() {
    if (!state.pinned) return;
    state.pinned = null;
    state.hover = state.pointer ? hitAt(state.pointer) : null;
    opts.onMarker?.(state.hover, {screen: state.pointer, pinned: false});
    redraw();
  }

  const api = {
    setFrame(bitmap, hud) {
      if (state.frame && state.frame !== bitmap) state.frame.close?.();
      const firstQuad = !state.hud?.track?.quad && hud?.track?.quad;
      state.frame = bitmap;
      state.hud = hud || null;
      const t = now();
      state.frameAt = t;
      state.frames.push(t);
      while (state.frames.length && t - state.frames[0] > 2000) state.frames.shift();
      if (canvas.dataset) {
        canvas.dataset.seq = String(hud?.seq ?? '');
        canvas.dataset.hud = hud?.track ? 'track' : 'none';
      }
      // Erstes Viereck: Ansicht auf die Anzeige legen, solange unberuehrt.
      if (firstQuad && state.auto.live) delete state.views.live;
      if (state.src === 'live' || state.src === 'still') {
        refreshMarker();
        redraw();
      }
    },
    setStill(url) {
      const src = state.src;
      if (src === 'live') return;
      const current = state.stills[src];
      if (current?.url === url) return;
      const ImageCtor = globalThis.Image;
      if (!ImageCtor) return;
      const img = new ImageCtor();
      const entry = {url, img, ready: false, failed: false};
      state.stills[src] = entry;
      img.onload = () => {
        entry.ready = true;
        if (src !== 'still' && state.auto[src] !== false) delete state.views[src];
        opts.onStill?.(src, entry);
        redraw();
      };
      img.onerror = () => {
        entry.failed = true;
        opts.onStill?.(src, entry);
        redraw();
      };
      img.src = url;
    },
    stillInfo: (src) => state.stills[src] || null,
    setSource(src) {
      if (!SOURCES.some(([key]) => key === src) || src === state.src) return;
      state.src = src;
      state.hover = null;
      state.pinned = null;
      opts.onMarker?.(null, {});
      redraw();
      opts.onView?.(api.zoom());
    },
    source: () => state.src,
    setLayers(layers) {
      state.layers = new Set(layers);
      if (state.pinned && !hitLayerOn(state.pinned.kind)) state.pinned = null;
      if (state.hover && !hitLayerOn(state.hover.kind)) state.hover = null;
      if (!state.pinned && !state.hover) opts.onMarker?.(null, {});
      redraw();
    },
    layers: () => new Set(state.layers),
    zoomBy(factor, [sx, sy] = [size()[0] / 2, size()[1] / 2]) {
      const v = view();
      const dpr = dprOf();
      const s = clamp(v.s * factor * dpr, ZOOM_MIN, ZOOM_MAX) / dpr;
      const k = s / v.s;
      setView({s, ox: sx - (sx - v.ox) * k, oy: sy - (sy - v.oy) * k});
    },
    panBy(dx, dy) {
      const v = view();
      setView({s: v.s, ox: v.ox + dx, oy: v.oy + dy});
    },
    fit() {
      const d = dims();
      if (d) setView(fitRect([0, 0, d[0], d[1]]));
    },
    // 1:1 = ein Bildpunkt auf einem Geraetepixel; die Bildmitte bleibt stehen.
    oneToOne() {
      const [W, H] = size();
      const [cx, cy] = screenToImage([W / 2, H / 2]);
      const s = 1 / dprOf();
      setView({s, ox: W / 2 - cx * s, oy: H / 2 - cy * s});
    },
    zoom: () => view().s * dprOf(),
    imageToScreen,
    screenToImage,
    viewState,
    redraw,
    hud: () => state.hud,
    frameAgeS,
    // Gemessene Bildrate der Vorschau ueber die letzten 2 s (0 ohne Bilder).
    measuredFps() {
      const t = now();
      const recent = state.frames.filter((f) => t - f <= 2000);
      if (recent.length < 2) return 0;
      // Eine Bildperiode Spielraum: bei stetigem Strom die echte Rate, bei
      // ausbleibenden Bildern faellt sie ab.
      const span = recent[recent.length - 1] - recent[0];
      return ((recent.length - 1) * 1000) / Math.max(span, t - recent[0] - span / (recent.length - 1));
    },
    // Zeiger-Ereignisse (Bildschirmkoordinaten). mountViewer verdrahtet sie.
    pointerMove(screen) {
      state.pointer = screen;
      opts.onPointer?.(screen ? screenToImage(screen) : null);
      if (state.pinned) return;
      const hit = screen ? hitAt(screen) : null;
      const changed = hit?.kind !== state.hover?.kind || hit?.index !== state.hover?.index;
      state.hover = hit;
      opts.onMarker?.(hit, {screen, pinned: false});
      if (changed) redraw();
    },
    click(screen) {
      const point = screenToImage(screen);
      const hit = hitAt(screen);
      if (opts.onClick?.(point, hit) === true) return;
      if (hit) {
        state.pinned = {...hit, anchor: point};
        state.hover = null;
        opts.onMarker?.(hit, {screen, pinned: true});
      } else if (state.pinned) {
        unpin();
        return;
      }
      redraw();
    },
    unpin,
    pinned: () => state.pinned,
  };

  function hitLayerOn(kind) {
    if (kind === 'region') return state.layers.has('rahmen');
    if (kind === 'corner') return state.layers.has('anzeige');
    return ['zellen', 'raster', 'anzeige'].some((key) => state.layers.has(key));
  }

  return api;
}

const ICON = (name) => `<svg class="i" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const TONE_CLASS = {sel: 'sel', mag: 'mag', err: 'err', warn: 'warn'};

function esc(value) {
  return String(value ?? '').replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function popHTML(info, pinned) {
  const rows = info.rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd${k === 'Zustand' ? ' class="t"' : ''}>${esc(v)}</dd>`).join('');
  const hintTone = info.tone === 'err' ? ' err-t' : info.tone === 'warn' ? ' warn-t' : '';
  return `<div class="ph"><span class="sq ${TONE_CLASS[info.tone] || 'sel'}"></span>${esc(info.title)}</div>` +
    (rows ? `<dl>${rows}</dl>` : '') +
    (info.hint ? `<div class="hint${hintTone}">${esc(info.hint)}</div>` : '') +
    (pinned ? '<div class="hint">Angeheftet · Esc oder Klick daneben löst</div>' : '');
}

// Baut das Grafikfenster in host (viewerHost der Huelle). Rueckgabe:
// {viewer, canvas, setStatus(status), setFrame(bitmap, hud), setStream(state)}.
// statusbar: Knoten der Statusleiste mit [data-slot="preview-fps"].
export function mountViewer(host, {statusbar = null, onClick = null, paint = null} = {}) {
  host.innerHTML = `
    <div class="vt" role="toolbar" aria-label="Werkzeuge der Bildansicht">
      <button type="button" data-act="out" title="Verkleinern" aria-label="Verkleinern">${ICON('zm')}</button>
      <span class="zv" data-part="zoom" aria-live="off">–</span>
      <button type="button" data-act="in" title="Vergrößern" aria-label="Vergrößern">${ICON('zp')}</button>
      <button type="button" data-act="one" title="Originalgröße (1 Bildpunkt = 1 Pixel)">1:1</button>
      <button type="button" data-act="fit" title="Ganzes Bild einpassen">${ICON('fit')}<span class="lbl">Einpassen</span></button>
      <span class="vsep"></span>
      <div class="menuwrap">
        <button type="button" data-act="layers" aria-haspopup="menu" aria-expanded="false" title="Ebenen im Bild">${ICON('lay')}<span class="lbl">Ebenen</span>${ICON('down')}</button>
        <div class="menu" role="menu" aria-label="Ebenen" hidden><div class="mh">Im Bild zeigen</div>${LAYERS.map(([key, label]) =>
          `<button type="button" role="menuitemcheckbox" data-layer="${key}" aria-checked="true">` +
          `<span class="ck" aria-hidden="true"></span>${label}</button>`).join('')}</div>
      </div>
      <button type="button" data-act="legend" aria-pressed="false" title="Legende">${ICON('lg')}<span class="lbl">Legende</span></button>
      <span class="vsep"></span>
      <div class="seg" role="group" aria-label="Bildquelle">${SOURCES.map(([key, label]) =>
        `<button type="button" data-src="${key}" aria-pressed="${key === 'live'}"${key === 'live' ? '' : ' disabled title="Erst mit dem Vorschlag"'}>${label}</button>`).join('')}</div>
    </div>
    <div class="vstage">
      <canvas class="vcanvas" role="img" aria-label="Kamerabild mit Markierungen"></canvas>
      <div class="vchip" data-part="chip"></div>
      <div class="vchip coordc" data-part="coord"></div>
      <div class="legend" hidden></div>
      <div class="popover vpop" role="tooltip" hidden></div>
    </div>`;
  const q = (selector) => host.querySelector(selector);
  const canvas = q('.vcanvas');
  const stage = q('.vstage');
  const pop = q('.vpop');
  const zoomLabel = q('[data-part="zoom"]');
  const chip = q('[data-part="chip"]');
  const coord = q('[data-part="coord"]');
  const legend = q('.legend');
  const menu = q('.menu');
  const layersButton = q('[data-act="layers"]');
  renderLegend(legend);
  let stream = 'verbindet';
  let status = null;
  let lastPop = null;

  function placePop(info, {screen, pinned} = {}) {
    if (!info || !screen) {
      pop.hidden = true;
      lastPop = null;
      return;
    }
    const html = popHTML(info, pinned);
    if (html !== lastPop) {
      pop.innerHTML = html;
      lastPop = html;
    }
    pop.hidden = false;
    pop.classList.toggle('pinned', Boolean(pinned));
    const w = pop.offsetWidth, h = pop.offsetHeight;
    const W = stage.clientWidth, H = stage.clientHeight;
    let x = screen[0] + 16, y = screen[1] + 16;
    if (x + w > W - 8) x = screen[0] - w - 12;
    if (y + h > H - 8) y = screen[1] - h - 12;
    pop.style.left = `${Math.max(4, Math.round(x))}px`;
    pop.style.top = `${Math.max(4, Math.round(y))}px`;
  }

  const viewer = createViewer(canvas, {
    onMarker: placePop,
    onClick,
    paint,
    onView: (zoom) => { zoomLabel.textContent = `${Math.round(zoom * 100)} %`; },
    onPointer: (point) => {
      if (!point) { coord.textContent = ''; return; }
      const suffix = viewer.source() === 'abtast' || viewer.source() === 'entz' ? ' (entzerrt)' : '';
      coord.textContent = `x ${Math.round(point[0])} · y ${Math.round(point[1])}${suffix}`;
    },
    onStill: () => updateChip(),
  });
  canvas.viewer = viewer;

  // Zeiger: Rad zoomt um den Zeiger, Ziehen verschiebt, Klick heftet an.
  const local = (event) => {
    const rect = canvas.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  };
  let drag = null;
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    viewer.zoomBy(1.0018 ** -event.deltaY, local(event));
  }, {passive: false});
  canvas.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    drag = {start: [event.clientX, event.clientY], last: null, moved: false};
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (drag) {
      if (!drag.moved && Math.abs(event.clientX - drag.start[0]) + Math.abs(event.clientY - drag.start[1]) > 3) {
        // Ab der Schwelle zaehlt der ganze Weg seit dem Druecken.
        drag.moved = true;
        drag.last = drag.start;
        stage.classList.add('drag');
        placePop(null);
      }
      if (drag.moved) {
        viewer.panBy(event.clientX - drag.last[0], event.clientY - drag.last[1]);
        drag.last = [event.clientX, event.clientY];
        return;
      }
    }
    viewer.pointerMove(local(event));
  });
  canvas.addEventListener('pointerup', (event) => {
    const was = drag;
    drag = null;
    stage.classList.remove('drag');
    if (was && !was.moved) viewer.click(local(event));
    else viewer.pointerMove(local(event));
  });
  canvas.addEventListener('pointercancel', () => { drag = null; stage.classList.remove('drag'); });
  canvas.addEventListener('pointerleave', () => {
    if (drag) return;
    viewer.pointerMove(null);
    if (!viewer.pinned()) placePop(null);
  });
  const doc = host.ownerDocument;
  doc.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!menu.hidden) { toggleMenu(false); layersButton.focus(); return; }
    viewer.unpin();
    if (!viewer.pinned()) placePop(null);
  });
  doc.addEventListener('pointerdown', (event) => {
    if (!menu.hidden && !event.target.closest?.('.menuwrap')) toggleMenu(false);
  });

  function toggleMenu(open) {
    menu.hidden = !open;
    layersButton.setAttribute('aria-expanded', String(open));
    if (open) menu.querySelector('[role="menuitemcheckbox"]:not([aria-disabled="true"])')?.focus();
  }

  q('.vt').addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    const act = button.dataset.act;
    const [W, H] = [canvas.clientWidth, canvas.clientHeight];
    if (act === 'in') viewer.zoomBy(1.25, [W / 2, H / 2]);
    else if (act === 'out') viewer.zoomBy(0.8, [W / 2, H / 2]);
    else if (act === 'one') viewer.oneToOne();
    else if (act === 'fit') viewer.fit();
    else if (act === 'layers') toggleMenu(menu.hidden);
    else if (act === 'legend') {
      legend.hidden = !legend.hidden;
      button.setAttribute('aria-pressed', String(!legend.hidden));
    } else if (button.dataset.layer) {
      if (button.getAttribute('aria-disabled') === 'true') return;
      const layers = viewer.layers();
      const on = !layers.has(button.dataset.layer);
      if (on) layers.add(button.dataset.layer); else layers.delete(button.dataset.layer);
      button.setAttribute('aria-checked', String(on));
      viewer.setLayers(layers);
    } else if (button.dataset.src) {
      selectSource(button.dataset.src);
    }
  });
  menu.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const items = [...menu.querySelectorAll('[role="menuitemcheckbox"]:not([aria-disabled="true"])')];
    const index = items.indexOf(doc.activeElement);
    items[(index + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length]?.focus();
  });
  // Die Lage der Fokus-ROI steht weder im Status noch im HUD.
  const roi = menu.querySelector('[data-layer="fokus"]');
  roi.setAttribute('aria-disabled', 'true');
  roi.setAttribute('aria-checked', 'false');
  roi.title = 'Nur in der Einrichtung; die Lage der Fokus-ROI meldet der Server noch nicht';

  function stillUrl(src) {
    const key = status?.setup?.proposal_revision || status?.session_id || '';
    return `/live/setup/${STILL_NAMES[src]}.png?r=${encodeURIComponent(key)}`;
  }

  function selectSource(src) {
    host.querySelectorAll('.seg [data-src]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.src === src)));
    viewer.setSource(src);
    if (src !== 'live') viewer.setStill(stillUrl(src));
    updateChip();
  }

  function updateChip() {
    const src = viewer.source();
    let html;
    if (src === 'live') {
      const age = viewer.frameAgeS();
      if (!viewer.hud() && stream !== 'offen') html = '<span class="sq stale"></span><b>Live</b> · verbindet …';
      else if (age > 1.5) html = '<span class="sq stale"></span><b>Live</b> · kein neues Bild';
      else html = `<span class="sq ok"></span><b>Live</b> · <span class="num">${Math.round(viewer.measuredFps())} fps</span>`;
    } else {
      const still = viewer.stillInfo(src);
      const label = SOURCES.find(([key]) => key === src)[1];
      const note = still?.failed ? 'nicht verfügbar' : !still?.ready ? 'lädt …'
        : src === 'still' ? 'aus der Einrichtung, mit deren Markierungen'
          : src === 'abtast' ? 'entzerrt, Abtastpunkte je Zelle'
            : `<span class="num">${still.img.naturalWidth} × ${still.img.naturalHeight}</span>`;
      html = `<b>${label}</b> · ${note}`;
    }
    if (chip._html !== html) { chip._html = html; chip.innerHTML = html; }
  }

  function updateRate(hud) {
    if (!statusbar) return;
    const slot = statusbar.querySelector('[data-slot="preview-fps"]');
    const note = statusbar.querySelector('[data-slot="preview-note"]');
    const fps = `${Math.round(viewer.measuredFps())} fps`;
    if (slot && slot.textContent !== fps) slot.textContent = fps;
    const reason = hud?.preview?.throttled;
    const text = reason === 'messung' ? ' – Messung hat Vorrang' : reason === 'kodierung' ? ' – Kodierung ausgelastet' : '';
    if (note && note.textContent !== text) note.textContent = text;
  }

  // Ruhiger Takt: Alter und Rate weiterzaehlen, auch wenn keine Bilder kommen.
  let lastStale = false;
  setInterval(() => {
    const stale = viewer.frameAgeS() > 1.5;
    if (stale !== lastStale) { lastStale = stale; viewer.redraw(); }
    updateChip();
    updateRate(viewer.hud());
  }, 500);

  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => viewer.redraw()).observe(stage);
  zoomLabel.textContent = '–';

  return {
    viewer,
    canvas,
    setFrame(bitmap, hud) {
      viewer.setFrame(bitmap, hud);
      zoomLabel.textContent = `${Math.round(viewer.zoom() * 100)} %`;
      updateChip();
      updateRate(hud);
    },
    setStream(next) { stream = next; updateChip(); },
    // Quellenumschalter aus setup.overlays; fehlt das Bild, ist die Quelle
    // gesperrt und traegt den Grund. Faellt die gewaehlte Quelle weg, zurueck auf Live.
    setStatus(next) {
      const previousKey = status?.setup?.proposal_revision || status?.session_id;
      status = next;
      const overlays = next?.setup?.overlays || [];
      for (const button of host.querySelectorAll('.seg [data-src]')) {
        const src = button.dataset.src;
        if (src === 'live') continue;
        const ok = overlays.includes(STILL_NAMES[src]);
        button.disabled = !ok;
        if (ok) button.removeAttribute('title'); else button.title = 'Erst mit dem Vorschlag';
      }
      const current = viewer.source();
      if (current !== 'live' && !overlays.includes(STILL_NAMES[current])) selectSource('live');
      else if (current !== 'live' && (next?.setup?.proposal_revision || next?.session_id) !== previousKey) {
        viewer.setStill(stillUrl(current));
      }
    },
  };
}
