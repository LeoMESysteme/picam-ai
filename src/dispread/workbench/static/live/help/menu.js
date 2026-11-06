// Menue "Hilfe" in der Titelleiste: Rundgang, Übungslauf, Glossar.
// Der Übungslauf ist nur bei Bereit, Lauf beendet oder abgebrochener
// Einrichtung moeglich; sonst ist der Punkt gesperrt und nennt den Grund.
//
// mountHelpMenu(wrap, {onTour, onPractice, onGlossary}) -> {update({lock, practice, glossary})}
// lock: Grund der Sperre oder null; practice: Uebungslauf aktiv.

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

export function mountHelpMenu(wrap, {onTour = () => {}, onPractice = () => {}, onGlossary = () => {}} = {}) {
  const toggle = wrap.querySelector('[data-help-toggle]');
  const menu = wrap.querySelector('.menu');
  const doc = wrap.ownerDocument;
  let view = {lock: null, practice: false, glossary: false};

  function paint() {
    const practiceLabel = view.practice ? 'Übungslauf beenden' : 'Übungslauf';
    const practiceNote = view.practice ? 'Zurück zur Werkbank' : view.lock || 'Ohne Kamera, ohne Messung';
    const html = '<div class="mh" role="presentation">Hilfe</div>' +
      '<button type="button" role="menuitem" data-help="tour"><span class="mi"><b>Rundgang</b><span>8 Stationen, etwa eine Minute</span></span></button>' +
      `<button type="button" role="menuitem" data-help="practice"${!view.practice && view.lock ? ' disabled' : ''}` +
      `${!view.practice && view.lock ? ` title="${esc(view.lock)}"` : ''}><span class="mi"><b>${practiceLabel}</b>` +
      `<span class="${!view.practice && view.lock ? 'why' : ''}">${esc(practiceNote)}</span></span></button>` +
      `<button type="button" role="menuitem" data-help="glossary"><span class="mi"><b>Glossar und Gründe</b>` +
      `<span>${view.glossary ? 'Ist geöffnet (rechts)' : 'Begriffe, Prüfungen, Markierungen'}</span></span></button>`;
    if (menu._html !== html) { menu._html = html; menu.innerHTML = html; }
  }

  function open(on) {
    menu.hidden = !on;
    toggle.setAttribute('aria-expanded', String(on));
    if (on) {
      paint();
      menu.querySelector('[role="menuitem"]:not(:disabled)')?.focus();
    }
  }

  toggle.addEventListener('click', () => open(menu.hidden));
  menu.addEventListener('click', (event) => {
    const item = event.target.closest('[data-help]');
    if (!item || item.disabled) return;
    open(false);
    toggle.focus();
    ({tour: onTour, practice: onPractice, glossary: onGlossary})[item.dataset.help]?.();
  });
  menu.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); open(false); toggle.focus(); return; }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const items = [...menu.querySelectorAll('[role="menuitem"]:not(:disabled)')];
    const index = items.indexOf(doc.activeElement);
    items[(index + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length]?.focus();
  });
  doc.addEventListener('pointerdown', (event) => {
    if (!menu.hidden && !event.target.closest?.('.hdr-help')) open(false);
  });
  doc.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !menu.hidden) { open(false); toggle.focus(); }
  });

  return {
    update(next) {
      view = {...view, ...next};
      if (!menu.hidden) paint();
    },
    close: () => open(false),
  };
}
