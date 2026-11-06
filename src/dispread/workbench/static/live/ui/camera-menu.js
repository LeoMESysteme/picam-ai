// Menue der Kamera in der Statusleiste (Spec "Aufbau der Oberflaeche":
// "Kamera neu verbinden steht im Statusleisten-Menü der Kamera"). Der
// Knopf ist das Kamerafeld selbst; das Menue haengt ausserhalb der
// Statusleiste (die schneidet ab) und oeffnet nach oben. Ob die Kamera neu
// verbunden werden darf, entscheidet der Server (POST /live/camera/start).
//
// mountCameraMenu(button, menu, {onReconnect}) -> {update(status), close()}
import {cameraView} from '../model.js';

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

export function mountCameraMenu(button, menu, {onReconnect = () => {}} = {}) {
  const doc = button.ownerDocument;
  let status = null;

  function paint() {
    const camera = status?.camera || {};
    const tone = camera.stalled || !camera.running ? 'err-t' : 'mut';
    const html = '<div class="mh" role="presentation">Kamera</div>' +
      `<p class="mstate ${tone}" role="presentation">${esc(cameraView(camera))}</p>` +
      '<button type="button" role="menuitem" data-camera="reconnect">Kamera neu verbinden</button>';
    if (menu._html !== html) { menu._html = html; menu.innerHTML = html; }
  }

  function place() {
    const box = button.getBoundingClientRect();
    const width = menu.offsetWidth;
    const left = Math.max(4, Math.min(box.left, doc.documentElement.clientWidth - width - 4));
    menu.style.left = `${Math.round(left)}px`;
    menu.style.bottom = `${Math.round(doc.documentElement.clientHeight - box.top + 4)}px`;
  }

  function open(on) {
    menu.hidden = !on;
    button.setAttribute('aria-expanded', String(on));
    if (on) {
      paint();
      place();
      menu.querySelector('[role="menuitem"]')?.focus();
    }
  }

  button.addEventListener('click', () => open(menu.hidden));
  menu.addEventListener('click', (event) => {
    const item = event.target.closest('[data-camera]');
    if (!item) return;
    open(false);
    button.focus();
    onReconnect();
  });
  menu.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); open(false); button.focus(); }
  });
  doc.addEventListener('pointerdown', (event) => {
    if (!menu.hidden && !menu.contains(event.target) && !button.contains(event.target)) open(false);
  });
  doc.defaultView?.addEventListener('resize', () => { if (!menu.hidden) place(); });

  return {
    update(next) {
      status = next;
      if (!menu.hidden) paint();
    },
    close: () => open(false),
  };
}
