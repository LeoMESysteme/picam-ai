// Blockierender Dialog im Seitenstil (Spec "Meldungen"), loest window.confirm ab.
// openModal({title, text, actions: [{label, value, primary, escape, cls, icon}]})
// liefert ein Promise mit dem value der gewaehlten Aktion. cls ist eine
// Knopfklasse (danger, ghost), icon ein Symbol der Huelle (stop, redo).
// * Fokusfalle: Tab/Umschalt+Tab bleiben im Dialog, der Rest der Seite ist inert.
// * Esc waehlt die Aktion mit escape: true; ohne sie schliesst Esc nicht.
// * Der Fokus startet auf der Esc-Aktion (sicherer Standard), sonst auf der
//   Primaeraktion, und kehrt danach zum vorher fokussierten Element zurueck.
// * Mehrere Aufrufe werden nacheinander gezeigt, nie gestapelt.
// * promise.close(value) schliesst den Dialog von aussen (z. B. wenn der
//   Anlass verschwindet) und loest mit value auf.
// text: Absaetze durch Leerzeile getrennt; der erste ist die Aussage, weitere
// sind Nebentext.

let queue = Promise.resolve();
let counter = 0;

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

export function openModal({title = '', text = '', actions = [{label: 'OK', value: true, primary: true}], tone = null} = {}) {
  let closeNow = null;
  let pendingClose;
  const result = queue.then(() => new Promise((resolve) => {
    // Vor dem Zeigen geschlossen: nichts aufbauen, keinen Tastatur-Haken setzen.
    if (pendingClose) {
      resolve(pendingClose.value);
      return;
    }
    const doc = globalThis.document;
    const id = `modal-${++counter}`;
    const back = doc.createElement('div');
    back.className = 'modalbg';
    const paragraphs = String(text).split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    back.innerHTML = `<div class="modal${tone ? ` ${esc(tone)}` : ''}" role="dialog" aria-modal="true" ` +
      `aria-labelledby="${id}-t" aria-describedby="${id}-b">` +
      `<div class="mt" id="${id}-t">${tone ? `<span class="sq ${esc(tone)}"></span>` : ''}${esc(title)}</div>` +
      `<div class="mbody" id="${id}-b">${paragraphs.map((p, i) =>
        `<p${i ? ' class="sub"' : ''}>${esc(p).replace(/\n/g, '<br>')}</p>`).join('')}</div>` +
      `<div class="mf">${actions.map((a, i) => {
        const cls = [a.primary ? 'primary' : '', a.cls || ''].filter(Boolean).join(' ');
        const icon = a.icon ? `<svg class="i" aria-hidden="true"><use href="#i-${esc(a.icon)}"/></svg>` : '';
        return `<button type="button" data-i="${i}"${cls ? ` class="${esc(cls)}"` : ''}>${icon}${esc(a.label)}</button>`;
      }).join('')}</div></div>`;
    const before = doc.activeElement;
    // Hintergrund sperren: alle anderen Kinder von body inert (Klicks, Fokus, Vorlesen).
    const siblings = [...doc.body.children].filter((el) => el !== back && !el.hasAttribute('inert'));
    doc.body.append(back);
    for (const el of siblings) el.setAttribute('inert', '');
    const buttons = [...back.querySelectorAll('button')];
    const escapeIndex = actions.findIndex((a) => a.escape);
    const primaryIndex = actions.findIndex((a) => a.primary);
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      doc.removeEventListener('keydown', onKey, true);
      back.remove();
      for (const el of siblings) el.removeAttribute('inert');
      if (before && before.isConnected && typeof before.focus === 'function') before.focus();
      resolve(value);
    };
    closeNow = finish;
    function onKey(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        if (escapeIndex >= 0) finish(actions[escapeIndex].value);
        return;
      }
      if (event.key !== 'Tab' || !buttons.length) return;
      const index = buttons.indexOf(doc.activeElement);
      const next = event.shiftKey ? (index <= 0 ? buttons.length - 1 : index - 1)
        : (index < 0 || index === buttons.length - 1 ? 0 : index + 1);
      event.preventDefault();
      buttons[next].focus();
    }
    doc.addEventListener('keydown', onKey, true);
    buttons.forEach((button, i) => { button.onclick = () => finish(actions[i].value); });
    (buttons[escapeIndex >= 0 ? escapeIndex : Math.max(0, primaryIndex)] || back).focus();
  }));
  queue = result.catch(() => {});
  result.close = (value) => {
    if (closeNow) closeNow(value);
    else pendingClose = {value};
  };
  return result;
}
