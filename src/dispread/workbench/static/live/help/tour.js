// Rundgang und Uebungs-Auftraege (Spec "Einarbeitung" 1 und 2).
// * startTour(stops, {storage}): 8 Stationen, je ein hervorgehobener Bereich
//   mit 1–3 Saetzen; Weiter/Zurueck, Ueberspringen (Esc). Ueberspringen und
//   Fertig merkt sich localStorage (try/catch: ohne Speicher fragt die Seite
//   beim naechsten Besuch eben wieder).
// * offerTour(...): Angebot beim ersten Besuch („Rundgang starten / Später“).
//   Die Seite ruft es nie ueber einem laufenden Lauf auf.
// * createCoach(): Auftrag im Rundgang-Stil fuer den Uebungslauf, ohne den
//   Rest der Seite zu sperren; practiceTask(status) waehlt den Auftrag.
// * practiceLock(status): Grund, warum der Uebungslauf gerade gesperrt ist.

export const TOUR_KEY = 'werkbank.rundgang';
const LATER_KEY = 'werkbank.rundgang.spaeter';

export const TOUR_STOPS = [
  {key: 'titel', title: 'Titelleiste und Aktionen', target: '.titlebar',
    text: 'Oben stehen Ablauf und Gerät, rechts die Aktion, die gerade dran ist: Einrichtung starten, Bestätigen, Lauf starten oder stoppen. Unter Hilfe liegen Rundgang, Übungslauf und Glossar.'},
  {key: 'ablauf', title: 'Ablauf-Dock', target: '.ldock',
    text: 'Links steht, wo die Einrichtung gerade ist, mit Dauer und Ergebnis je Schritt. Im Lauf stehen hier Laufdaten, Statusanteile und Referenz.'},
  {key: 'viewer', title: 'Viewer mit Werkzeugleiste', target: '.viewer-host',
    text: 'Das Kamerabild mit Markierungen. Mausrad zoomt, Ziehen verschiebt. Die Werkzeugleiste schaltet Ebenen und Bildquelle.'},
  {key: 'legende', title: 'HUD-Legende', target: '.legend', legend: true,
    text: 'Die Legende erklärt jede Markierung im Bild. Zeigen auf eine Markierung nennt ihre Zahlen, Klicken heftet sie an.'},
  {key: 'inspektor', title: 'Inspektor', target: '.inspector',
    text: 'Rechts stehen die Einzelheiten: Fokuskurve, Prüfungen und Bestätigen mit Namen. Im Lauf folgen Datensätze, Ursachen, Nachführung und Referenz.'},
  {key: 'ergebnis', title: 'Ergebnisanzeige', target: '.judge', fallback: '.rdock', fallbackHeight: 170,
    text: 'Im Lauf steht oben rechts der aktuelle Wert mit Status: Freigegeben, Wechselt, Unlesbar oder Veraltet. Nur Freigegeben ist ein Messwert.'},
  {key: 'zeitleiste', title: 'Zeitleiste', target: '.strip',
    text: 'Die letzten 40 s als Statusband, darüber die Wertspur nur aus freigegebenen Werten. Marken zeigen Werteplan, Bedienermarken und Störungen.'},
  {key: 'statusleiste', title: 'Statusleiste', target: '.statusbar',
    text: 'Kamera, Vorschaurate, Bilder, Lücken, Speicher und Referenz auf einen Blick. Hinweise ohne Aktion stehen ebenfalls hier.'},
];

// Nur bei Bereit, Lauf beendet oder abgebrochener Einrichtung (Spec).
const PRACTICE_LOCK = {
  running: 'Gesperrt, solange ein Lauf läuft',
  setup_running: 'Gesperrt, solange die Einrichtung läuft',
  setup_ready: 'Gesperrt, solange ein Vorschlag auf Bestätigung wartet',
  confirmed: 'Gesperrt: Einrichtung bestätigt, Lauf noch nicht gestartet',
  error: 'Gesperrt: Die Werkbank meldet einen Fehler',
};
export function practiceLock(status, {offline = false} = {}) {
  if (!status || offline) return 'Gesperrt: kein Status von der Werkbank';
  if (['idle', 'stopped', 'setup_failed'].includes(status.state)) return null;
  return PRACTICE_LOCK[status.state] || 'Gesperrt in diesem Zustand';
}

export function localStore() {
  try { return globalThis.localStorage ?? null; } catch { return null; }
}
function sessionStore() {
  try { return globalThis.sessionStorage ?? null; } catch { return null; }
}
export function tourSeen(storage) {
  try { return Boolean(storage?.getItem(TOUR_KEY)); } catch { return false; }
}
export function rememberTour(storage, value) {
  try { storage?.setItem(TOUR_KEY, value); } catch { /* ohne Speicher: nur fuer diese Seite */ }
}
function laterThisSession() {
  try { return Boolean(sessionStore()?.getItem(LATER_KEY)); } catch { return false; }
}

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// Rechteck eines Ziels (Selektor, Element) im Fenster, oder null.
function targetRect(doc, stop) {
  const el = typeof stop.target === 'string' ? doc.querySelector(stop.target) : stop.target;
  if (el && !el.hidden && el.getClientRects().length) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return {x: r.left, y: r.top, w: r.width, h: r.height};
  }
  const fallback = stop.fallback ? doc.querySelector(stop.fallback) : null;
  if (fallback) {
    const r = fallback.getBoundingClientRect();
    return {x: r.left, y: r.top, w: r.width, h: Math.min(r.height, stop.fallbackHeight || r.height)};
  }
  return null;
}

// Pop-up neben dem Ziel: rechts, links, darunter, darueber; im Fenster gehalten.
// side 'inside': oben rechts im Ziel, unter dessen Werkzeugleiste.
function place(pop, rect, win, side = null) {
  const W = win.innerWidth, H = win.innerHeight, m = 12, gap = 14;
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x, y;
  if (rect && side === 'inside') { x = rect.x + rect.w - w - m; y = rect.y + 46; }
  else if (!rect) { x = (W - w) / 2; y = (H - h) / 2; } else if (rect.x + rect.w + gap + w <= W - m) {
    x = rect.x + rect.w + gap; y = rect.y + Math.min(24, rect.h / 2 - 10);
  } else if (rect.x - gap - w >= m) {
    x = rect.x - gap - w; y = rect.y + Math.min(24, rect.h / 2 - 10);
  } else if (rect.y + rect.h + gap + h <= H - m) {
    x = rect.x + rect.w - w; y = rect.y + rect.h + gap;
  } else {
    x = rect.x + rect.w - w; y = rect.y - gap - h;
  }
  pop.style.left = `${Math.round(Math.max(m, Math.min(x, W - w - m)))}px`;
  pop.style.top = `${Math.round(Math.max(m, Math.min(y, H - h - m)))}px`;
}

function frame(el, rect, pad = 3) {
  el.hidden = !rect;
  if (!rect) return;
  el.style.left = `${Math.round(rect.x - pad)}px`;
  el.style.top = `${Math.round(rect.y - pad)}px`;
  el.style.width = `${Math.round(rect.w + 2 * pad)}px`;
  el.style.height = `${Math.round(rect.h + 2 * pad)}px`;
}

let activeTour = null;

// Rundgang; Rueckgabe {next, prev, skip, finish, index(), done} (done: Promise
// mit 'fertig' oder 'übersprungen'). Ein zweiter Aufruf beendet den ersten nicht,
// sondern liefert ihn.
export function startTour(stops = TOUR_STOPS, {storage = localStore(), doc = globalThis.document, onEnd = () => {}} = {}) {
  if (activeTour) return activeTour;
  const win = doc.defaultView || globalThis;
  const block = doc.createElement('div');
  block.className = 'tour-block';
  const hl = doc.createElement('div');
  hl.className = 'tour-hl';
  hl.setAttribute('aria-hidden', 'true');
  const pop = doc.createElement('div');
  pop.className = 'tour-pop';
  pop.setAttribute('role', 'dialog');
  pop.setAttribute('aria-label', 'Rundgang');
  pop.setAttribute('aria-describedby', 'tour-text');
  doc.body.append(block, hl, pop);
  const before = doc.activeElement;
  let index = 0;
  let restore = null;
  let resolveDone;
  const done = new Promise((resolve) => { resolveDone = resolve; });

  function leave() {
    restore?.();
    restore = null;
  }
  function enter(stop) {
    // Station Legende: die Legende zeigen und danach wieder wie vorher.
    if (stop.legend) {
      const legend = doc.querySelector('.legend');
      const button = doc.querySelector('[data-act="legend"]');
      if (legend?.hidden && button) {
        button.click();
        restore = () => { if (!legend.hidden) button.click(); };
      }
    }
  }
  function show() {
    leave();
    const stop = stops[index];
    enter(stop);
    const last = index === stops.length - 1;
    pop.innerHTML = `<div class="th"><span class="sq selc"></span>Rundgang<span class="n mono">${index + 1}/${stops.length}</span></div>` +
      `<h3>${esc(stop.title)}</h3><p id="tour-text">${esc(stop.text)}</p>` +
      '<div class="fa"><button type="button" class="ghost" data-tour="skip">Überspringen</button><span class="sp"></span>' +
      `<button type="button" data-tour="prev"${index ? '' : ' disabled'}>Zurück</button>` +
      `<button type="button" class="primary" data-tour="next">${last ? 'Fertig' : 'Weiter'}</button></div>`;
    position();
    pop.querySelector('[data-tour="next"]').focus();
  }
  function position() {
    const rect = targetRect(doc, stops[index]);
    frame(hl, rect);
    place(pop, rect, win);
  }
  function end(result) {
    leave();
    rememberTour(storage, result);
    doc.removeEventListener('keydown', onKey, true);
    win.removeEventListener('resize', position);
    block.remove(); hl.remove(); pop.remove();
    activeTour = null;
    if (before?.isConnected && typeof before.focus === 'function') before.focus();
    onEnd(result);
    resolveDone(result);
  }
  function onKey(event) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); api.skip(); }
    else if (event.key === 'ArrowRight' && !event.target.closest?.('input')) { event.preventDefault(); api.next(); }
    else if (event.key === 'ArrowLeft' && !event.target.closest?.('input')) { event.preventDefault(); api.prev(); }
    else if (event.key === 'Tab') {
      // Fokus bleibt im Rundgang (die Seite dahinter ist abgedeckt).
      const buttons = [...pop.querySelectorAll('button:not(:disabled)')];
      const i = buttons.indexOf(doc.activeElement);
      event.preventDefault();
      buttons[(i + (event.shiftKey ? buttons.length - 1 : 1)) % buttons.length]?.focus();
    }
  }
  pop.addEventListener('click', (event) => {
    const action = event.target.closest('[data-tour]')?.dataset.tour;
    if (action) api[action]?.();
  });
  doc.addEventListener('keydown', onKey, true);
  win.addEventListener('resize', position);

  const api = {
    next() { if (index === stops.length - 1) end('fertig'); else { index++; show(); } },
    prev() { if (index > 0) { index--; show(); } },
    skip() { end('übersprungen'); },
    finish() { end('fertig'); },
    index: () => index,
    done,
  };
  activeTour = api;
  show();
  return api;
}

export const tourActive = () => Boolean(activeTour);

// Angebot beim ersten Besuch. Rueckgabe {close()} oder null (schon gesehen,
// "Später" in dieser Sitzung, Rundgang laeuft).
export function offerTour({storage = localStore(), doc = globalThis.document, onStart = () => {}} = {}) {
  if (tourSeen(storage) || laterThisSession() || activeTour || doc.querySelector('.tour-offer')) return null;
  const box = doc.createElement('div');
  box.className = 'tour-offer';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', 'Rundgang anbieten');
  box.innerHTML = '<div class="th"><span class="sq selc"></span>Neu an der Werkbank?</div>' +
    '<p>Ein Rundgang zeigt in acht Stationen, wo was steht. Er dauert etwa eine Minute.</p>' +
    '<div class="fa"><button type="button" class="ghost" data-offer="later">Später</button>' +
    '<button type="button" class="primary" data-offer="start">Rundgang starten</button></div>';
  doc.body.append(box);
  const close = () => box.remove();
  box.addEventListener('click', (event) => {
    const action = event.target.closest('[data-offer]')?.dataset.offer;
    if (!action) return;
    close();
    if (action === 'start') onStart();
    // "Später": in dieser Sitzung nicht noch einmal; beim naechsten Besuch wieder.
    else try { sessionStore()?.setItem(LATER_KEY, '1'); } catch { /* ohne Speicher */ }
  });
  box.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.stopPropagation(); box.querySelector('[data-offer="later"]').click(); }
  });
  return {close, el: box};
}

// Auftrag im Uebungslauf (Rundgang-Stil, ohne Sperre). show({key, title,
// text, target}) zeigt ihn neben dem Ziel; gleicher Inhalt baut nicht neu.
export function createCoach({doc = globalThis.document} = {}) {
  const win = doc.defaultView || globalThis;
  const hl = doc.createElement('div');
  hl.className = 'coach-hl';
  hl.setAttribute('aria-hidden', 'true');
  hl.hidden = true;
  const box = doc.createElement('div');
  box.className = 'coach';
  box.setAttribute('role', 'status');
  box.setAttribute('aria-live', 'polite');
  box.hidden = true;
  doc.body.append(hl, box);
  let current = null;
  const position = () => {
    if (!current) return;
    const rect = targetRect(doc, current);
    frame(hl, rect, 2);
    // Der Auftrag steht immer oben rechts im Viewer; der gestrichelte Rahmen
    // zeigt das Ziel. So bleiben Titelleiste, Docks und Ergebnis frei.
    place(box, targetRect(doc, {target: '.viewer-host'}) || rect, win, 'inside');
  };
  win.addEventListener('resize', position);
  return {
    show(task) {
      if (!task) return this.hide();
      const html = '<div class="th"><span class="sq hatch"></span>Übungslauf · Auftrag</div>' +
        `<h3>${esc(task.title)}</h3><p>${esc(task.text)}</p>`;
      if (box._html !== html) { box._html = html; box.innerHTML = html; }
      current = task;
      box.hidden = false;
      position();
      return undefined;
    },
    hide() {
      current = null;
      box.hidden = true;
      hl.hidden = true;
      box._html = null;
    },
    el: box,
  };
}

// Auftrag zum Stand des Uebungslaufs. ctx: {offline, frameAgeS, correcting, modalOpen}.
export function practiceTask(status, ctx = {}) {
  const state = status?.state;
  if (ctx.offline) {
    return {key: 'offline', title: 'Verbindung verloren', target: '.viewer-host',
      text: 'Ohne Status von der Werkbank gilt jeder Wert als veraltet. Die Oberfläche bleibt gedimmt, bis die Verbindung zurück ist.'};
  }
  if (state === 'idle' || state === 'setup_failed') {
    return {key: 'start', title: 'Einrichtung starten', target: '.hdr-act',
      text: 'Klicke oben rechts auf Einrichtung starten. Die Einrichtung läuft dann selbsttätig.'};
  }
  if (state === 'setup_running') {
    return {key: 'setup', title: 'Zuschauen', target: '.ldock',
      text: 'Die Einrichtung läuft selbsttätig: links die Schritte, rechts Fokuskurve und Prüfungen. Im echten Betrieb jetzt den Aufbau nicht berühren.'};
  }
  if (state === 'setup_ready') {
    return {key: 'confirm', title: 'Prüfen & Bestätigen', target: '.inspector',
      text: 'Prüfe den Vorschlag im Bild. Ein Klick auf freien Rahmen fügt einen Rahmenbereich hinzu. Dann Namen eintragen, Haken setzen und auf Bestätigen klicken.'};
  }
  if (state === 'confirmed') {
    return {key: 'run', title: 'Lauf starten', target: '.hdr-act',
      text: 'Klicke auf Lauf starten. Der Pfeil daneben öffnet Optionen wie Referenz und Werteplan.'};
  }
  if (state === 'stopped') {
    return {key: 'done', title: 'Geschafft', target: '.ldock',
      text: 'Links steht die Zusammenfassung des Laufs. Zum Wiederholen Neu einrichten, sonst oben auf Übung beenden klicken.'};
  }
  if (state !== 'running') return null;
  const hint = status.run?.tracking_hint?.kind;
  if (hint === 'anzeige_bewegt') {
    return ctx.modalOpen
      ? {key: 'moved', title: 'Anzeige bewegt', target: '.viewer-host',
        text: 'Die Anzeige ist verrutscht. Wähle im Dialog: neu einrichten, Lauf stoppen oder weiter beobachten.'}
      : {key: 'stop', title: 'Lauf stoppen', target: '.hdr-act',
        text: 'Die Werkbank gibt nichts mehr frei. Klicke auf Lauf stoppen; danach zeigt das linke Dock die Zusammenfassung.'};
  }
  if (hint === 'rahmen_verdeckt') {
    return {key: 'hand', title: 'Rahmen verdeckt', target: '.viewer-host',
      text: 'Eine Hand verdeckt Rahmenbereiche. Rot zeigt, wo. Bis die Sicht frei ist, wird nichts freigegeben.'};
  }
  if (status.camera?.stalled || ctx.frameAgeS > 1.5) {
    return {key: 'stall', title: 'Streamstillstand', target: '.viewer-host',
      text: 'Kein neues Kamerabild: Das Bild friert ein, der Wert wird Veraltet.'};
  }
  if (ctx.correcting) {
    return {key: 'corr', title: 'Korrektur läuft', target: '.viewer-host',
      text: 'Türkis: Die Nachführung holt das Viereck zurück. Danach gibt die Werkbank wieder frei.'};
  }
  return {key: 'watch', title: 'Lauf beobachten', target: '.judge',
    text: 'Oben rechts steht der Wert mit Status, unten die Zeitleiste. Mit Ereignis markieren setzt du eine Marke.'};
}
