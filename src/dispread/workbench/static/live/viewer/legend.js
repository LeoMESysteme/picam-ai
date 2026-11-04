// Legende des Viewers: erklaert jedes Markierungs-Symbol (Mock "Legende").
// Die Symbole sind kleine Inline-SVGs in denselben Farben wie das HUD.
// Nur Symbole, die Viewer und Effektebene zeichnen (Texte aus dem Mock).

export const LEGEND_ROWS = [
  ['<path d="M1 6h20" stroke="#55c46e" stroke-width="1.5"/><rect x="0" y="3.5" width="5" height="5" fill="#55c46e"/>',
    'Anzeige-Viereck mit Ecken, Farbe = Status'],
  ['<path d="M1 1.5h20v9H1zM11 1.5v9" fill="none" stroke="#ebe7e0" stroke-opacity=".45"/>',
    'Raster: Zellen des Lesers (Nummer beim Zeigen)', 'grid'],
  ['<rect x="5" y="1.5" width="12" height="9" fill="rgba(229,165,53,.25)" stroke="#e5a535" stroke-width="1.5"/>',
    'Unsichere Zelle (Abstand unter null)', 'grid'],
  ['<rect x="6" y="1.5" width="9" height="9" fill="none" stroke="#d65ccf" stroke-width="1.5"/>', 'Rahmenbereich mit Treffer'],
  ['<rect x="6" y="1.5" width="9" height="9" fill="rgba(238,91,77,.25)" stroke="#ee5b4d" stroke-width="1.5"/>',
    'Rahmenbereich ohne Treffer'],
  ['<rect x="2" y=".5" width="17" height="11" fill="none" stroke="#d65ccf" stroke-opacity=".6" stroke-dasharray="2 2"/>',
    'Suchfenster des Rahmenbereichs'],
  ['<g fill="#30c6b7"><circle cx="4" cy="6" r="1.6"/><circle cx="10" cy="5" r="1.2"/><circle cx="16" cy="7" r="1.6"/></g>',
    'Korrektur läuft (Nachregistrierung)'],
  ['<g fill="#ff6250" opacity=".8"><circle cx="5" cy="4" r="1.3"/><circle cx="9" cy="8" r="1.8"/><circle cx="15" cy="5" r="1.2"/><circle cx="18" cy="9" r="1"/></g>',
    'Fehlerort (Wolke an betroffenen Ecken)'],
  ['<rect x="1" y="1.5" width="20" height="9" fill="#121110" stroke="#55c46e"/>', 'Wert-Etikett: Wert, Status, Spur'],
];

// Zeilen mit 'grid' nur, wenn der Status ein Leser-Raster liefert; ohne
// Raster zeichnet der Viewer keine Zellen und die Legende verspricht keine.
export function legendRows({grid = false} = {}) {
  return LEGEND_ROWS.filter(([, , needs]) => needs !== 'grid' || grid);
}

export function renderLegend(el, {grid = false} = {}) {
  el.innerHTML = '<div class="lh">Legende</div>' + legendRows({grid}).map(([svg, label]) =>
    `<div class="r"><svg viewBox="0 0 22 12" aria-hidden="true">${svg}</svg>${label}</div>`).join('');
}
