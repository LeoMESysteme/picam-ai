// Dialog "Aktuellen Wert der Anzeige eingeben": Referenz der Einrichtung von
// Hand, wenn kein RS232-Anschluss zum GSV-2AS da ist (Produktion) oder der
// Bediener es waehlt. Die Anzeige (Displaytech 161A) zeigt Zelle 0 '+', in
// den Zellen 1–7 genau 6 Ziffern und einen Punkt, Zelle 8 leer, dann mV/V.
// normalizeCellText spiegelt dispread.gsv2as_cell_text.normalize_cell_text;
// der Server prueft trotzdem selbst (Wahrheitsregel: Entscheidungen im Server).
// Werkbank-Dialogstil (.modalbg/.modal), Fokusfalle, Esc bricht ab.

export const UNIT = 'mV/V';
export const DISPLAY_DIGITS = 6;
export const BLOCK_CELLS = 7;
export const MIN_COMPARABLE_CELLS = 5;
const ALLOWED = '0123456789.? ';

const fail = (error) => ({ok: false, error});

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
    back.className = 'modalbg';
    const lead = serialPresent === false
      ? `Kein RS232-Anschluss zum GSV-2AS gefunden (${port}). Die Einrichtung vergleicht den Leser deshalb mit dem Wert, den Sie hier eintragen.`
      : 'Die Einrichtung vergleicht den Leser mit dem Wert, den Sie hier eintragen, statt ihn über RS232 vom GSV-2AS zu lesen.';
    back.innerHTML = '<div class="modal celltext" role="dialog" aria-modal="true" aria-labelledby="ct-t" aria-describedby="ct-lead">' +
      '<div class="mt" id="ct-t">Aktuellen Wert der Anzeige eingeben</div><div class="mbody">' +
      `<p id="ct-lead">${esc(lead)}</p>` +
      (reason && serialPresent !== false ? `<p class="sub" data-part="reason">${esc(reason)}</p>` : '') +
      '<p class="sub">Nur eintragen, wenn die Anzeige ruhig steht. Eine Ziffer, die schwankt, mit ? markieren.</p>' +
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
    let done = false;
    function finish(value) {
      if (done) return;
      done = true;
      doc.removeEventListener('keydown', onKey, true);
      back.remove();
      for (const el of siblings) el.removeAttribute('inert');
      if (before && before.isConnected && typeof before.focus === 'function') before.focus();
      resolve(value);
    }
    function onKey(event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finish(null); return; }
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
