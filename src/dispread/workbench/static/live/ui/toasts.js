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

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

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

function fill(entry) {
  const {level, title, text} = entry;
  entry.el.className = `toast ${level}`;
  entry.el.setAttribute('role', level === 'err' ? 'alert' : 'status');
  entry.el.innerHTML = `<span class="sq ${level === 'info' ? 'sel' : level}"></span><b>${esc(title)}</b>` +
    '<button type="button" class="ghost" aria-label="Schließen" title="Schließen">' +
    '<svg class="i" aria-hidden="true" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8"/></svg></button>' +
    (text ? `<p>${esc(text).replace(/\n/g, '<br>')}</p>` : '');
  entry.el.querySelector('button').onclick = () => remove(entry, 'user');
}

export function toast({level = 'info', title = '', text = '', sticky = false, key = null, onClose = null} = {}) {
  if (!host) return {close() {}};
  const lvl = LEVELS.includes(level) ? level : 'info';
  const id = key ?? `${lvl}|${title}|${text}`;
  let entry = entries.find((e) => e.key === id);
  if (entry) {
    timers.clearTimeout(entry.timer);
    Object.assign(entry, {level: lvl, title, text, sticky, onClose});
  } else {
    entry = {key: id, level: lvl, title, text, sticky, onClose, el: host.ownerDocument.createElement('div')};
    entries.push(entry);
    host.append(entry.el);
  }
  fill(entry);
  if (!sticky) entry.timer = timers.setTimeout(() => remove(entry, 'timeout'), TOAST_MS);
  render();
  return {close: () => remove(entry, 'code'), el: entry.el};
}

export function closeToast(key) {
  const entry = entries.find((e) => e.key === key);
  if (entry) remove(entry, 'code');
}

export const toastKeys = () => entries.map((e) => e.key);
