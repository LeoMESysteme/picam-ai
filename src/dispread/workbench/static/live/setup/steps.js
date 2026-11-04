// Schrittliste der Einrichtung im linken Dock (Spec "Einrichtungs-Fortschritt",
// Mock-Kapitel 2–7). Die Zeilen kommen fertig aus model.stepRows; hier wird
// nur gezeichnet: Quadrat plus Wort, Dauer, eine Zeile Ergebnis und beim
// laufenden Schritt die Teilschritte.
import {esc} from '../shell.js';

const SQUARE_WORD = {ok: 'erledigt', warn: 'erledigt mit Warnung', err: 'fehlgeschlagen', run: 'läuft', pend: 'ausstehend'};
const SUB_SQUARE = {done: 'ok', running: 'run', failed: 'err', pending: 'pend'};

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export function squareHTML(kind) {
  return `<span class="sq ${kind}" role="img" aria-label="${SQUARE_WORD[kind]}"></span>`;
}

// Quadrat neben einem ausgeschriebenen Zustandswort: nur Schmuck fuer Vorleser.
export const dotHTML = (kind) => `<span class="sq ${kind}" aria-hidden="true"></span>`;

function duration(row) {
  if (!finite(row.elapsed_s)) return '';
  const s = row.state === 'running' ? Math.floor(row.elapsed_s) : Math.round(row.elapsed_s);
  return s < 60 ? `${s} s` : mmss(s);
}

function square(row) {
  if (row.state === 'done') return row.tone === 'warn' ? 'warn' : row.tone === 'err' ? 'err' : 'ok';
  return row.state === 'running' ? 'run' : row.state === 'failed' ? 'err' : 'pend';
}

export function stepsHTML(rows) {
  return rows.map((row) => {
    const bar = finite(row.progress)
      ? `<div class="prog" role="progressbar" aria-label="Ruhezeit" aria-valuemin="0" aria-valuemax="100" ` +
        `aria-valuenow="${Math.round(row.progress * 100)}"><i style="width:${Math.round(row.progress * 100)}%"></i></div>`
      : '';
    const sub = row.sub.length ? `<ul class="subl">${row.sub.map((item) =>
      `<li class="${item.state}" data-sub="${esc(item.key)}">${squareHTML(SUB_SQUARE[item.state] || 'pend')}` +
      `<span class="l">${esc(item.label)}</span><span class="r">${esc(item.value)}</span></li>`).join('')}</ul>` : '';
    return `<div class="step ${row.state}" data-step="${esc(row.key)}" data-state="${row.state}">` +
      `${squareHTML(square(row))}<b>${esc(row.label)}</b><span class="dur">${duration(row)}</span>` +
      `${row.detail ? `<div class="sum">${esc(row.detail)}</div>` : ''}${bar}${sub}</div>`;
  }).join('');
}

// dock: Knoten fuer die Schrittliste (im linken Dock unter dem Lead).
export function renderSteps(dock, rows) {
  const html = stepsHTML(rows);
  if (dock._html !== html) {
    dock._html = html;
    dock.innerHTML = html;
  }
}
