// Hinweise unten rechts im Viewer (Spec "Meldungen", Mock-Kapitel 8a–8d).
// toast({level, title, text, sticky = false, key}) zeigt einen Hinweis:
// * Gleicher key ersetzt den Hinweis an seiner Stelle, statt ihn zu stapeln.
//   Ohne key gilt Stufe + Titel + Text als Schluessel (kein Doppel).
// * Hoechstens 3 sind sichtbar, die neuesten; aeltere warten verborgen.
// * Nicht stehende Hinweise schliessen nach 4 s, stehende (sticky) erst
//   durch closeToast(key), den Bediener oder ihren Anlass.
// * Per Tastatur schliessbar: Schliessen-Knopf, Esc im Hinweis.
// level: info | ok | warn | err | teal (teal nur "Korrektur").
// onClose(reason) meldet 'user' (Bediener), 'timeout' oder 'code'.

export const TOAST_MS = 4000;
export const MAX_VISIBLE = 3;
const LEVELS = ['info', 'ok', 'warn', 'err', 'teal'];

let host = null;
let timers = globalThis;
const entries = [];

export function mountToasts(el, {timers: injected} = {}) {
  host = el;
  if (injected) timers = injected;
  el.classList.add('toasts');
  el.setAttribute('aria-live', 'polite');
  el.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const node = event.target.closest?.('.toast');
    const entry = entries.find((e) => e.el === node);
    if (!entry) return;
    event.preventDefault();
    event.stopPropagation();
    remove(entry, 'user');
  });
  return el;
}

function render() {
  const shown = new Set(entries.slice(-MAX_VISIBLE));
  for (const entry of entries) entry.el.hidden = !shown.has(entry);
}

function remove(entry, reason) {
  const index = entries.indexOf(entry);
  if (index < 0) return;
  // Fokus nicht ins Leere fallen lassen: zum naechsten Hinweis oder freigeben.
  const hadFocus = entry.el.contains(entry.el.ownerDocument?.activeElement);
  entries.splice(index, 1);
  timers.clearTimeout(entry.timer);
  entry.el.remove();
  render();
  if (hadFocus) entries.at(-1)?.el.querySelector('button')?.focus();
  entry.onClose?.(reason);
}

// Aufbau einmal je Hinweis; danach werden nur geaenderte Teile nachgezogen.
// So bleibt der Fokus auf dem Schliessen-Knopf, und die Live-Region liest
// einen unveraenderten Hinweis nicht bei jedem Statusabruf erneut vor.
function build(entry) {
  const doc = host.ownerDocument;
  const el = entry.el;
  const sq = doc.createElement('span');
  const b = doc.createElement('b');
  const button = doc.createElement('button');
  button.type = 'button';
  button.className = 'ghost';
  button.setAttribute('aria-label', 'Schließen');
  button.title = 'Schließen';
  button.innerHTML = '<svg class="i" aria-hidden="true" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
  button.onclick = () => remove(entry, 'user');
  const p = doc.createElement('p');
  el.append(sq, b, button, p);
  entry.parts = {sq, b, p};
}

function fill(entry, previous) {
  const {level, title, text} = entry;
  const {sq, b, p} = entry.parts;
  if (previous?.level !== level) {
    entry.el.className = `toast ${level}`;
    entry.el.setAttribute('role', level === 'err' ? 'alert' : 'status');
    sq.className = `sq ${level === 'info' ? 'sel' : level}`;
  }
  if (previous?.title !== title) b.textContent = title;
  if (previous?.text !== text) {
    p.textContent = text;
    p.hidden = !text;
  }
}

export function toast({level = 'info', title = '', text = '', sticky = false, key = null, onClose = null} = {}) {
  if (!host) return {close() {}};
  const lvl = LEVELS.includes(level) ? level : 'info';
  const id = key ?? `${lvl}|${title}|${text}`;
  let entry = entries.find((e) => e.key === id);
  let previous = null;
  if (entry) {
    timers.clearTimeout(entry.timer);
    previous = {level: entry.level, title: entry.title, text: entry.text};
    Object.assign(entry, {level: lvl, title, text, sticky, onClose});
  } else {
    entry = {key: id, level: lvl, title, text, sticky, onClose, el: host.ownerDocument.createElement('div')};
    build(entry);
    entries.push(entry);
    host.append(entry.el);
  }
  fill(entry, previous);
  if (!sticky) entry.timer = timers.setTimeout(() => remove(entry, 'timeout'), TOAST_MS);
  render();
  return {close: () => remove(entry, 'code'), el: entry.el};
}

export function closeToast(key) {
  const entry = entries.find((e) => e.key === key);
  if (entry) remove(entry, 'code');
}

export const toastKeys = () => entries.map((e) => e.key);
