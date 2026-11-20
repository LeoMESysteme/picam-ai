// Dialog "Aktuellen Wert der Anzeige eingeben": Referenz der Einrichtung von
// Hand, wenn kein RS232-Anschluss zum GSV-2AS da ist (Produktion) oder der
// Bediener es waehlt. Die Anzeige (Displaytech 161A) zeigt Zelle 0 '+', in
// den Zellen 1–7 genau 6 Ziffern und einen Punkt, Zelle 8 leer, dann mV/V.
// normalizeCellText spiegelt dispread.gsv2as_cell_text.normalize_cell_text;
// der Server prueft trotzdem selbst (Wahrheitsregel: Entscheidungen im Server).
// Werkbank-Dialogstil (.modal), Fokusfalle, Esc bricht ab. Ohne Abdunkeln
// und verschiebbar (Titelleiste ziehen, Alt+Pfeiltasten oder Knopf
// "Verschieben"), damit das Kamerabild mit der Anzeige sichtbar bleibt; die
// letzte Lage merkt sich sessionStorage (ohne Speicher: Mitte).

export const UNIT = 'mV/V';
export const DISPLAY_DIGITS = 6;
export const BLOCK_CELLS = 7;
export const MIN_COMPARABLE_CELLS = 5;
const ALLOWED = '0123456789.? ';

const fail = (error) => ({ok: false, error});

// Lage des Dialogs: im Fenster halten, Andockstellen fuer die Tastatur.
export const POSITION_KEY = 'dispread.live.celltext.position';
export const MOVE_STEP = 24;
export const DOCKS = ['links', 'rechts', 'unten', 'mitte'];
const DOCK_MARGIN = 16;

export function clampPosition({left, top}, {width, height}, {vw, vh}) {
  const maxLeft = Math.max(0, vw - width);
  const maxTop = Math.max(0, vh - height);
  return {left: Math.round(Math.min(Math.max(0, left), maxLeft)), top: Math.round(Math.min(Math.max(0, top), maxTop))};
}

export function dockPosition(dock, size, view) {
  const centreLeft = (view.vw - size.width) / 2;
  const centreTop = (view.vh - size.height) / 2;
  const at = {links: {left: DOCK_MARGIN, top: centreTop}, rechts: {left: view.vw - size.width - DOCK_MARGIN, top: centreTop},
    unten: {left: centreLeft, top: view.vh - size.height - DOCK_MARGIN}, mitte: {left: centreLeft, top: centreTop}}[dock];
  return clampPosition(at ?? {left: centreLeft, top: centreTop}, size, view);
}

function sessionStore() {
  try { return globalThis.sessionStorage ?? null; } catch { return null; }
}

export function loadPosition(store = sessionStore()) {
  try {
    const value = JSON.parse(store?.getItem(POSITION_KEY) ?? 'null');
    return value && Number.isFinite(value.left) && Number.isFinite(value.top) ? {left: value.left, top: value.top} : null;
  } catch { return null; }
}

export function savePosition(position, store = sessionStore()) {
  try {
    if (position) store?.setItem(POSITION_KEY, JSON.stringify({left: position.left, top: position.top}));
    else store?.removeItem(POSITION_KEY);
  } catch { /* ohne Speicher: naechstes Oeffnen in der Mitte */ }
}

// Leading-zero-Regel des GSV-2AS (leading_zeros.py): fuehrende Nullen leer,
// ausser der direkt vor dem Punkt; mehr als zwei sind an der Anzeige nicht gemessen.
function blankLeadingZeros(padded) {
  let intLen = 0;
  while (intLen < padded.length && /[0-9]/.test(padded[intLen])) intLen++;
  let zeros = 0;
  while (zeros < intLen - 1 && padded[zeros] === '0') zeros++;
  if (zeros > 2) return null;
  return ' '.repeat(zeros) + padded.slice(zeros);
}

// Eingabe -> {ok, text: neun Zellen 0–8} oder {ok: false, error}. Nimmt den
// Zellentext ("+ 1.2193") und getippte Werte ("0,4678", "+0.4678 mV/V").
export function normalizeCellText(raw) {
  if (typeof raw !== 'string') return fail('Eingabe muss Text sein.');
  const text = raw.replace(/,/g, '.').replace(/\s*mv\/v\s*$/i, '').replace(/\s+$/, '');
  const stripped = text.replace(/^\s+/, '');
  if (stripped.startsWith('-')) return fail('Minuszeichen: Negative Werte zeigt dieses GSV-2AS nicht an, Zelle 0 ist immer „+“.');
  // Ohne Plus zaehlen fuehrende Leerzeichen als Leerzellen nach der Vorzeichenzelle.
  const body = stripped.startsWith('+') ? stripped.slice(1) : text;
  if (!body.trim()) return fail('Noch kein Wert eingegeben.');
  const bad = [...body].find((ch) => !ALLOWED.includes(ch));
  if (bad !== undefined) return fail(`Zeichen „${bad}“ ist nicht erlaubt. Erlaubt: Ziffern, ein Komma oder Punkt, Leerzelle und ?.`);
  const core = body.replace(/^ +/, '');
  const leading = body.length - core.length;
  if (core.includes(' ')) return fail('Leerzelle zwischen den Ziffern: Die Anzeige zeigt die Ziffern ohne Lücke.');
  const points = core.split('.').length - 1;
  if (points === 0) return fail('Es fehlt der Dezimalpunkt (genau einer).');
  if (points > 1) return fail('Mehr als ein Dezimalpunkt – genau einer ist nötig.');
  const digits = core.length - 1;
  if (digits > DISPLAY_DIGITS) return fail(`${digits} Ziffern – die Anzeige zeigt genau ${DISPLAY_DIGITS}.`);
  if (core.startsWith('.')) return fail('Vor dem Punkt steht an der Anzeige immer eine Ziffer.');
  let block;
  if (leading) {
    // Abgelesene Zellen: genau so, wie der Bediener sie sieht.
    if (leading + core.length !== BLOCK_CELLS) {
      return fail(`${leading + core.length} Zellen nach dem Plus – die Anzeige hat genau ${BLOCK_CELLS} (${DISPLAY_DIGITS} Ziffern und den Punkt).`);
    }
    const integer = core.split('.')[0];
    if (integer.length > 1 && integer[0] === '0') return fail(`Führende Null in Zelle ${leading + 1}: Die Anzeige zeigt sie als Leerzelle.`);
    block = body;
  } else {
    const padded = '0'.repeat(DISPLAY_DIGITS - digits) + core;
    const integer = padded.split('.')[0];
    if (integer.includes('?') && integer.length > 1 && integer[0] === '0') {
      return fail('„?“ vor dem Punkt neben führenden Nullen ist mehrdeutig. Zellen genau wie angezeigt eingeben.');
    }
    block = blankLeadingZeros(padded);
    if (block === null) {
      return fail('Drei oder mehr führende Nullen: Wie die Anzeige sie zeigt, ist nicht gemessen. Zellen genau wie angezeigt eingeben (Leerzelle mit der Leertaste).');
    }
  }
  const comparable = [...block].filter((ch) => ch !== '?').length;
  if (comparable < MIN_COMPARABLE_CELLS) {
    return fail(`Nur ${comparable} vergleichbare Zellen – höchstens ${BLOCK_CELLS - MIN_COMPARABLE_CELLS} Zellen mit ? markieren.`);
  }
  return {ok: true, text: `+${block} `};
}

// Lesbare Form fuer Vorschau und Vorlesen: Leerzellen als „Leerzelle“.
export function spokenCells(text) {
  return [...text.slice(0, 8)].map((ch) => (ch === ' ' ? 'Leerzelle' : ch === '?' ? 'schwankend' : ch === '.' ? 'Punkt' : ch))
    .join(', ');
}

const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const FOCUSABLE = 'button:not(:disabled), input:not(:disabled)';
const KEY_HELP = 'Ziffer tippen springt weiter · Komma oder Punkt setzt den Dezimalpunkt · Leertaste = Leerzelle · ? = schwankende Ziffer · Rücktaste geht zurück';

const previewCells = (text) => [...text.slice(0, 9)].map((ch) =>
  `<span class="lcdp${ch === ' ' ? ' b' : ''}${ch === '?' ? ' q' : ''}">${ch === ' ' ? '' : esc(ch)}</span>`).join('');

// Oeffnet den Dialog. reason: Anlass (Text oder null), initial: letzter
// Zellentext. Liefert ein Promise mit dem normalisierten Zellentext oder null.
export function openCellTextDialog({reason = null, initial = null, serialPresent = null, port = '/dev/ttyUSB0',
  doc = globalThis.document} = {}) {
  return new Promise((resolve) => {
    const back = doc.createElement('div');
    // Kein Abdunkeln: das Kamerabild mit der Anzeige muss beim Ablesen sichtbar bleiben.
    back.className = 'modalbg celltextbg';
    const lead = serialPresent === false
      ? `Kein RS232-Anschluss zum GSV-2AS gefunden (${port}). Die Einrichtung vergleicht den Leser deshalb mit dem Wert, den Sie hier eintragen.`
      : 'Die Einrichtung vergleicht den Leser mit dem Wert, den Sie hier eintragen, statt ihn über RS232 vom GSV-2AS zu lesen.';
    back.innerHTML = '<div class="modal celltext" role="dialog" aria-modal="true" aria-labelledby="ct-t" aria-describedby="ct-lead">' +
      '<div class="mt" data-part="handle" title="Zum Verschieben ziehen (oder Alt+Pfeiltasten)">' +
      '<span id="ct-t">Aktuellen Wert der Anzeige eingeben</span>' +
      '<button type="button" class="ghost mv" data-part="move" aria-label="Dialog verschieben" ' +
      'title="Dialog verschieben: links, rechts, unten, Mitte (auch Titelleiste ziehen oder Alt+Pfeiltasten)">Verschieben</button>' +
      '</div><div class="mbody">' +
      `<p id="ct-lead">${esc(lead)}</p>` +
      (reason && serialPresent !== false ? `<p class="sub" data-part="reason">${esc(reason)}</p>` : '') +
      '<p class="sub">Nur eintragen, wenn die Anzeige ruhig steht. Eine Ziffer, die schwankt, mit ? markieren. ' +
      'Springt nur die letzte Ziffer um eins, reicht einer der beiden Werte.</p>' +
      '<div class="lcdin" role="group" aria-labelledby="ct-cells-l" aria-describedby="ct-keys">' +
      '<span class="f" id="ct-cells-l">Zellen der Anzeige</span>' +
      '<div class="lcdrow">' +
      '<span class="lcdc fixed" aria-hidden="true"><span>+</span><i>0</i></span>' +
      Array.from({length: BLOCK_CELLS}, (_, i) =>
        `<span class="lcdc" data-cell="${i}" data-state="unset"><input type="text" class="mono" inputmode="decimal" ` +
        `autocomplete="off" spellcheck="false" aria-label="Zelle ${i + 1} von 7" data-i="${i}"><i aria-hidden="true">${i + 1}</i></span>`).join('') +
      '<span class="lcdunit" aria-hidden="true">mV/V</span>' +
      '</div>' +
      `<p class="note" id="ct-keys">${esc(KEY_HELP)}</p></div>` +
      '<label class="f" for="ct-free">oder Wert eintippen</label>' +
      '<input type="text" id="ct-free" class="mono" data-part="free" placeholder="z. B. 0,4678 oder +0.4678 mV/V" ' +
      'autocomplete="off" spellcheck="false" aria-describedby="ct-free-msg">' +
      '<p class="note err-t" id="ct-free-msg" data-part="free-msg" aria-live="polite"></p>' +
      '<div class="lcdprev" data-part="preview-box"><span class="f">So muss die Anzeige aussehen:</span>' +
      '<div class="lcdrow pv" data-part="preview" aria-hidden="true"></div>' +
      '<span class="sr" data-part="preview-text"></span>' +
      '<p class="msg" data-part="check" aria-live="polite"></p></div>' +
      '</div><div class="mf"><button type="button" data-part="cancel">Abbrechen</button>' +
      '<button type="button" class="primary" data-part="submit" disabled>Einrichtung starten</button></div></div>';
    const part = (name) => back.querySelector(`[data-part="${name}"]`);
    const inputs = [...back.querySelectorAll('.lcdc input')];
    const cells = Array(BLOCK_CELLS).fill('');
    let result = fail('Noch kein Wert eingegeben.');

    const typed = () => cells.some((c) => c !== '');
    const paintCell = (i) => {
      const value = cells[i];
      inputs[i].value = value === ' ' ? '' : value;
      inputs[i].parentElement.dataset.state = value === '' ? 'unset' : value === ' ' ? 'blank' : 'char';
      inputs[i].setAttribute('aria-label', `Zelle ${i + 1} von 7: ${value === '' ? 'leer' : value === ' ' ? 'Leerzelle'
        : value === '?' ? 'schwankende Ziffer' : value === '.' ? 'Punkt' : value}`);
    };
    const validate = () => {
      result = normalizeCellText(`+${cells.map((c) => c || ' ').join('')}`);
      const submit = part('submit');
      submit.disabled = !result.ok;
      const preview = part('preview');
      const check = part('check');
      if (result.ok) {
        preview.innerHTML = `${previewCells(result.text)}<span class="lcdunit">${UNIT}</span>`;
        const shown = result.text.slice(1, 8);
        const entered = cells.map((c) => c || ' ').join('');
        check.className = 'msg ok-t';
        // Sichtbar knapp; vorgelesen Zelle fuer Zelle (Leerzellen hoert man sonst nicht).
        check.innerHTML = (shown === entered ? 'Gültig – mit der Anzeige vergleichen, dann starten.'
          : 'Gültig – übernommen wie gezeigt (rechtsbündig, führende Nullen als Leerzelle).') +
          `<span class="sr"> Zellen: ${esc(spokenCells(result.text))}.</span>`;
        part('preview-text').textContent = `${result.text.trimEnd()} ${UNIT}`;
      } else {
        preview.innerHTML = `${previewCells(`+${cells.map((c) => c || ' ').join('')} `)}<span class="lcdunit">${UNIT}</span>`;
        part('preview-text').textContent = 'noch ungültig';
        check.className = typed() ? 'msg err-t' : 'msg mut';
        check.textContent = typed() ? result.error : 'Wert in die Zellen oder ins Feld darunter eintragen.';
      }
      preview.classList.toggle('bad', !result.ok && typed());
    };
    const setCells = (block) => {
      for (let i = 0; i < BLOCK_CELLS; i++) { cells[i] = block[i] ?? ''; paintCell(i); }
      validate();
    };
    const focusCell = (i) => inputs[Math.max(0, Math.min(BLOCK_CELLS - 1, i))].focus();
    const put = (i, value) => {
      cells[i] = value;
      paintCell(i);
      part('free-msg').textContent = '';
      validate();
      if (i < BLOCK_CELLS - 1) focusCell(i + 1);
    };
    const KEYS = {',': '.', '.': '.', ' ': ' ', '?': '?'};
    inputs.forEach((input, i) => {
      input.addEventListener('keydown', (event) => {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        const key = event.key;
        if (/^[0-9]$/.test(key) || key in KEYS) {
          event.preventDefault();
          put(i, KEYS[key] ?? key);
        } else if (key === 'Backspace') {
          event.preventDefault();
          if (cells[i] !== '') { cells[i] = ''; paintCell(i); validate(); }
          else if (i > 0) { cells[i - 1] = ''; paintCell(i - 1); validate(); focusCell(i - 1); }
        } else if (key === 'Delete') {
          event.preventDefault();
          cells[i] = '';
          paintCell(i);
          validate();
        } else if (key === 'ArrowLeft') { event.preventDefault(); focusCell(i - 1); }
        else if (key === 'ArrowRight') { event.preventDefault(); focusCell(i + 1); }
        else if (key === 'Home') { event.preventDefault(); focusCell(0); }
        else if (key === 'End') { event.preventDefault(); focusCell(BLOCK_CELLS - 1); }
        else if (key === 'Enter') { event.preventDefault(); if (result.ok) finish(result.text); }
        else if (key.length === 1) event.preventDefault();
      });
      // Bildschirmtastatur und Einfuegen: was ankommt, wie getippt behandeln.
      input.addEventListener('input', () => {
        const value = input.value;
        if (value.length > 1 || (value && !(/^[0-9]$/.test(value) || value in KEYS))) {
          // Eingefuegter Wert: ueber das freie Feld deuten.
          part('free').value = value;
          if (!applyFree()) { paintCell(i); part('free').focus(); }
          return;
        }
        if (value === '') { cells[i] = ''; paintCell(i); validate(); return; }
        put(i, KEYS[value] ?? value);
      });
      input.addEventListener('focus', () => input.select());
    });
    // Klick auf die Zellbox (auch Rand und Nummer) setzt den Fokus in die Zelle.
    back.querySelectorAll('.lcdc[data-cell]').forEach((box) => {
      box.addEventListener('mousedown', (event) => {
        if (event.target === box || event.target.tagName === 'I') { event.preventDefault(); focusCell(Number(box.dataset.cell)); }
      });
    });
    const applyFree = () => {
      const value = part('free').value;
      const msg = part('free-msg');
      if (!value.trim()) { msg.textContent = ''; return false; }
      const free = normalizeCellText(value);
      if (free.ok) {
        msg.textContent = '';
        setCells(free.text.slice(1, 8));
      } else msg.textContent = free.error;
      return free.ok;
    };
    part('free').addEventListener('input', applyFree);
    part('free').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); if (result.ok) finish(result.text); }
    });

    const before = doc.activeElement;
    const siblings = [...doc.body.children].filter((el) => el !== back && !el.hasAttribute('inert'));
    doc.body.append(back);
    for (const el of siblings) el.setAttribute('inert', '');

    // Verschieben: Zeiger (Maus/Touch) an der Titelleiste, Alt+Pfeiltasten, Knopf.
    const modal = back.querySelector('.modal');
    const handle = part('handle');
    const view = () => ({vw: doc.documentElement.clientWidth || globalThis.innerWidth || 0,
      vh: doc.documentElement.clientHeight || globalThis.innerHeight || 0});
    const size = () => { const r = modal.getBoundingClientRect(); return {width: r.width, height: r.height}; };
    let position = null;
    let dock = 'mitte';
    const place = (next, {remember = true} = {}) => {
      position = clampPosition(next, size(), view());
      modal.style.position = 'fixed';
      modal.style.margin = '0';
      modal.style.left = `${position.left}px`;
      modal.style.top = `${position.top}px`;
      modal.dataset.placed = 'true';
      if (remember) savePosition(position);
    };
    const current = () => { const r = modal.getBoundingClientRect(); return {left: r.left, top: r.top}; };
    let drag = null;
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || event.target.closest('button')) return;
      event.preventDefault();
      const at = current();
      drag = {id: event.pointerId, dx: event.clientX - at.left, dy: event.clientY - at.top};
      try { handle.setPointerCapture(event.pointerId); } catch { /* Zeiger schon weg */ }
      handle.classList.add('dragging');
    });
    handle.addEventListener('pointermove', (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      place({left: event.clientX - drag.dx, top: event.clientY - drag.dy}, {remember: false});
    });
    const endDrag = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      drag = null;
      handle.classList.remove('dragging');
      if (position) savePosition(position);
    };
    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);
    part('move').addEventListener('click', () => {
      dock = DOCKS[(DOCKS.indexOf(dock) + 1) % DOCKS.length];
      place(dockPosition(dock, size(), view()));
      part('move').setAttribute('aria-label', `Dialog verschieben (jetzt ${dock})`);
    });
    const onResize = () => { if (position) place(position, {remember: false}); };
    globalThis.addEventListener?.('resize', onResize);
    const stored = loadPosition();
    if (stored) place(stored, {remember: false});

    let done = false;
    function finish(value) {
      if (done) return;
      done = true;
      doc.removeEventListener('keydown', onKey, true);
      globalThis.removeEventListener?.('resize', onResize);
      back.remove();
      for (const el of siblings) el.removeAttribute('inert');
      if (before && before.isConnected && typeof before.focus === 'function') before.focus();
      resolve(value);
    }
    function onKey(event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finish(null); return; }
      const arrow = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[event.key];
      if (event.altKey && arrow && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        event.stopPropagation();
        const at = current();
        place({left: at.left + arrow[0] * MOVE_STEP, top: at.top + arrow[1] * MOVE_STEP});
        return;
      }
      if (event.key !== 'Tab') return;
      const focusables = [...back.querySelectorAll(FOCUSABLE)];
      const index = focusables.indexOf(doc.activeElement);
      const next = event.shiftKey ? (index <= 0 ? focusables.length - 1 : index - 1)
        : (index < 0 || index === focusables.length - 1 ? 0 : index + 1);
      event.preventDefault();
      focusables[next]?.focus();
    }
    doc.addEventListener('keydown', onKey, true);
    part('cancel').addEventListener('click', () => finish(null));
    part('submit').addEventListener('click', () => { if (result.ok) finish(result.text); });
    const start = typeof initial === 'string' && normalizeCellText(initial).ok ? normalizeCellText(initial).text.slice(1, 8) : '';
    setCells(start);
    for (let i = 0; i < BLOCK_CELLS; i++) paintCell(i);
    focusCell(start ? BLOCK_CELLS - 1 : 0);
  });
}
