// Ergebnisanzeige des Laufs (Spec "Aufbau der Oberflaeche", Mock-Kapitel 8):
// Statuswort mit Codewort, grosser Wert mit Einheit, Grund, Referenz, Spur,
// Alter. Das Statuswort folgt derselben Regel wie das Wert-Etikett im HUD
// (readoutTag), damit beide nie auseinanderlaufen. Wahrheitsregeln: Veraltet
// erscheint grau und durchgestrichen, Unlesbar als "Kein Wert", im Testlauf
// nie ein Wert, Konfidenz heisst "Spur".
import {FRAME_MAX_AGE_S, VALUE_MAX_AGE_S, readoutTag} from '../viewer/hud.js';

const META = {
  valid: {cls: 'V', word: 'Freigegeben', code: 'VALID'},
  transition: {cls: 'T', word: 'Wechselt', code: 'TRANSITION'},
  unreadable: {cls: 'U', word: 'Unlesbar', code: 'UNREADABLE'},
  stale: {cls: 'S', word: 'Veraltet', code: 'STALE'},
};
const TONE_KEY = {ok: 'valid', warn: 'transition', err: 'unreadable', stale: 'stale'};
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const dec = (x, digits) => x.toFixed(digits).replace('.', ',').replace(/^-/, '−');
const esc = (value) => String(value ?? '').replace(/[&<>"]/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// Bedienertext ohne Kennungen: "Wert wechselt (anzeige_wechselt)" -> "Wert wechselt".
// Entfernt nur Klammern, deren Inhalt eine Kennung ist (Kleinbuchstaben mit _ oder :),
// auch verschachtelt. Die Kennungen stehen weiter in Ursachen und Glossar.
const CODE_SUFFIX = /\s*\((?:[a-z0-9]+[_:])+[a-z0-9_:]*\)/g;
export function withoutCodes(text) {
  let out = String(text ?? '');
  for (let previous = null; previous !== out;) { previous = out; out = out.replace(CODE_SUFFIX, ''); }
  return out;
}
export const isCode = (text) => /^(?:[a-z0-9]+[_:])+[a-z0-9_:]*$/.test(String(text ?? ''));

const pad2 = (n) => String(n).padStart(2, '0');
// Zeit des neuesten Datensatzes (run.latest) als hh:mm:ss,s in Ortszeit, nur aus
// Serverangaben: Laufstart (Wanduhr) + Laufzeit - Alter des Datensatzes (beide
// monoton im selben Abruf). Nie die Browseruhr; nach dem Stopp nicht mehr
// (die Laufzeit steht, das Alter zaehlt weiter).
export function recordClock(status) {
  const run = status?.run;
  if (status?.state !== 'running' || !run?.latest) return null;
  const start = Date.parse(run.started_at_utc);
  if (!Number.isFinite(start) || !finite(run.elapsed_s) || !finite(run.latest_age_s)) return null;
  const d = new Date(start + (run.elapsed_s - run.latest_age_s) * 1000);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())},${Math.floor(d.getMilliseconds() / 100)}`;
}

function ageText(s) {
  if (!finite(s)) return '–';
  return s < 1 ? `${Math.round(s * 1000)} ms` : `${dec(s, 1)} s`;
}

// Neuester Referenztext (reference.latest = {cell_text, raw, value, age_s}); sonst "–".
export function referenceText(reference) {
  const latest = reference?.enabled ? reference.latest : null;
  return latest?.cell_text ?? latest?.raw ?? '–';
}

// Referenz mit Alter; aelter als 0,5 s (oder Statusabruf verloren) ist sie
// veraltet wie der Pruefling-Wert (Wahrheitsregel 1). Die Referenz darf auch
// im Testlauf erscheinen: sie ist kein freigegebener Pruefling-Wert.
export function referenceModel(reference, {offline = false} = {}) {
  const latest = reference?.enabled ? reference.latest : null;
  if (!latest) return {text: '–', age: '', stale: false};
  const age = latest.age_s;
  return {text: referenceText(reference), age: ageText(age), stale: offline || !finite(age) || age > VALUE_MAX_AGE_S};
}

// Reines Modell der Anzeige. hudRec = X-Hud.rec des gezeigten Bilds (oder
// null), track = X-Hud.track, frameAgeS = Sekunden seit diesem Bild,
// offline = Statusabruf verloren (connectionLost).
export function resultModel(status, view, hudRec, {frameAgeS = 0, offline = false, track = null} = {}) {
  const run = status?.run || {};
  const latest = run.latest || null;
  const testRun = Boolean(status?.test_run);
  const base = {ref: referenceModel(status?.reference, {offline}), spur: finite(track?.score) ? dec(track.score, 2) : '–',
    seq: hudRec?.seq ?? latest?.frame_sequence ?? null, time: recordClock(status), released: ''};
  if (status?.state === 'stopped') {
    return {...base, cls: 'X', word: 'Lauf beendet', code: '', value: '–', unit: '', struck: false,
      sub: 'Kein Wert freigegeben: Lauf gestoppt.', subErr: false, age: '–', spur: '–'};
  }
  let key = null;
  // Dieselbe Regel und dieselben Eingaben wie das Wert-Etikett im HUD (auch offline).
  if (hudRec) key = TONE_KEY[readoutTag({rec: hudRec, track}, {frameAgeS, offline})?.tone] || 'unreadable';
  else if (latest) key = offline ? 'stale' : META[view?.cls] ? view.cls : 'unreadable';
  if (!key) {
    return {...base, cls: 'X', word: view?.headline || 'Lauf startet …', code: '', value: '–', unit: '',
      struck: false, sub: '', subErr: false, age: '–'};
  }
  // Im Testlauf gibt es keine Freigabe (Wahrheitsregel 2).
  const withheld = testRun && key === 'valid';
  if (withheld) key = 'unreadable';
  const text = hudRec ? hudRec.text : latest?.raw_text;
  const unit = (hudRec ? hudRec.unit : latest?.unit) || '';
  const wasValid = hudRec ? ['valid', 'stale'].includes(hudRec.status) : latest?.status === 'valid';
  let value = '–';
  let valueUnit = '';
  if (key === 'valid') { value = text || '–'; valueUnit = unit; }
  else if (key === 'transition') value = 'Wert wechselt';
  else if (key === 'unreadable') value = 'Kein Wert';
  else if (!testRun && wasValid && text) { value = text; valueUnit = unit; }
  const age = hudRec && finite(hudRec.age_s) ? hudRec.age_s + Math.max(0, frameAgeS) : run.latest_age_s;
  const reasons = hudRec?.reasons || latest?.reject_reasons || [];
  let sub;
  // Testlauf: der Server schreibt VALID auf UNREADABLE um (testlauf_keine_freigabe);
  // Text wie statusView fuer diesen Fall.
  if (testRun && (key === 'stale' || withheld || reasons.includes('testlauf_keine_freigabe'))) {
    sub = 'Testlauf: keine Wertfreigabe';
  } else if (key === 'valid') {
    // "Bild N" steht schon im Raster darunter; nur ein Toleranzhinweis bleibt.
    sub = key === view?.cls ? (view.detail || '').replace(/(?:^| · )Bild \d+$/, '') : '';
  } else if (key === view?.cls && view.detail) sub = view.detail;
  else if (key === 'transition') sub = 'Wert wechselt';
  else if (key === 'unreadable') {
    // Klartext je Grund; ohne Erklaerung bleibt nur die Kennung (sie wird unten nicht gekuerzt).
    sub = reasons.map((reason) => {
      const short = reason.startsWith('tracking_lost:') ? reason.slice('tracking_lost:'.length) : reason;
      return status?.tracking_reasons?.[short] || status?.cause_texts?.[reason] || reason;
    }).join(', ');
  } else if (offline) sub = 'Keine Verbindung zur Werkbank – letzter bekannter Wert, nicht freigegeben.';
  else if (status?.camera?.stalled || frameAgeS > FRAME_MAX_AGE_S) {
    sub = `Letzter Wert, veraltet · kein neues Kamerabild seit ${dec(Math.max(frameAgeS, finite(age) ? age : 0), 1)} s`;
  } else sub = 'Letzter Wert, veraltet';
  // Kennungen in Klammern gehoeren in die Ursachenliste, nicht in die Anzeige.
  sub = withoutCodes(sub);
  // Leser-Vermutung im Testlauf nur bei Wechselt oder Unlesbar (Wahrheitsregel 2),
  // woertlich aus statusView und dort ausdruecklich als nicht freigegeben bezeichnet.
  if (testRun && ['transition', 'unreadable'].includes(key) && view?.detail && !sub.includes('Leser-Vermutung')) {
    const guess = view.detail.split('\n').filter((line) => /^(Leser-Vermutung|unsichere Zellen)/.test(line));
    if (guess.length) sub = [sub, ...guess].join('\n');
  }
  // "Freigegeben hh:mm:ss,s" nur neben einem freigegebenen Wert, dessen Datensatz
  // auch im Status freigegeben ist (Wahrheitsregel 1: Veraltet ist nie freigegeben).
  const released = key === 'valid' && latest?.status === 'valid' && base.time ? `Freigegeben ${base.time}` : '';
  return {...base, ...META[key], value, unit: valueUnit, struck: key === 'stale', sub, released,
    subErr: key === 'unreadable' && !testRun, age: ageText(age)};
}

// Zeichnet die Anzeige in host (.judge der Huelle); nur im Lauf und danach sichtbar.
export function renderResult(host, view, status, hudRec, opts = {}) {
  const visible = ['running', 'stopped'].includes(status?.state);
  host.hidden = !visible;
  if (!visible) return null;
  const model = resultModel(status, view, hudRec, opts);
  const numeric = model.cls === 'V' || (model.cls === 'S' && model.value !== '–');
  for (const cls of ['V', 'T', 'U', 'S', 'X']) host.classList.toggle(cls, model.cls === cls);
  // Uhrzeit im Kopf ist die Zeit des Datensatzes (recordClock), nie eine laufende
  // Browseruhr: die wuerde neben einem alten Wert Frische vortaeuschen.
  const ref = model.ref;
  const sub = [model.released ? `<span class="rel">${esc(model.released)}</span>` : '', esc(model.sub)]
    .filter(Boolean).join(' · ');
  const html = `<div class="jh"><span class="jw">${esc(model.word)}</span><span class="code">${esc(model.code)}</span>` +
    `${model.time ? `<span class="tm" title="Zeit des neuesten Datensatzes">${esc(model.time)}</span>` : ''}</div>` +
    `<div class="jb"><div class="jv"><span class="num${numeric ? ' mono' : ' word'}${model.struck ? ' struck' : ''}">` +
    `${esc(model.value)}</span><span class="unit">${esc(model.unit)}</span></div>` +
    `<div class="jsub${model.subErr ? ' err' : ''}">${sub}</div>` +
    `<dl class="jref"><dt>Referenz</dt><dd class="wide"><span class="ref${ref.stale ? ' struck' : ''}"` +
    `${ref.stale ? ' title="Referenz veraltet"' : ''}>${esc(ref.text)}</span>` +
    `${ref.age ? ` <span class="age${ref.stale ? ' stale' : ''}">${esc(ref.age)}</span>` : ''}</dd>` +
    `<dt>Spur</dt><dd>${esc(model.spur)}</dd>` +
    `<dt>Alter</dt><dd>${esc(model.age)}</dd><dt>Bild</dt><dd>${esc(model.seq ?? '–')}</dd></dl></div>`;
  if (host._html !== html) { host._html = html; host.innerHTML = html; }
  return model;
}
