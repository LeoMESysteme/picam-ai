# Räumliche Roadmap — Umsetzungsplan

**Ziel:** Eine frei verschiebbare Zensical-Roadmap mit Meilenstein- und
Schrittkarten, deren Zoom die Kartenbegrenzung nahtlos zur Bühne macht.

**Entwurf:** [Räumlicher Zoom](../specs/2026-10-23-roadmap-spatial-zoom-design.md).

**Technik:** Markdown als Datenquelle, DOM-Karten, SVG-Verbindungen und
Randpunkte, Pointer Events, lokale Anime.js-Version 4.5.0.

## Aufgaben

- [x] 1. Bestehenden strengen Doku-Build und die betroffenen Browsertests
  als Ausgangspunkt prüfen. Neue Verhaltenstests für Quellen, Karten und
  den Ebenenwechsel zuerst fehlschlagen lassen.
- [x] 2. Belegte Schritte zu P0–P8 im Markdown ergänzen. Einen getrennten
  Roadmap-Controller und eigene Styles einbinden; Quelltabellen nur nach
  erfolgreicher Initialisierung verbergen.
- [x] 3. Kameraführung, Knotenziehen, Verbindungen, Suche, Minimap,
  Ebenenwechsel, lokale Positionen und fehlerfeste Rücksetzungen bauen.
- [x] 4. Den Kartenumriss zum Bühnenrand führen, Inhalt/Füllung auflösen
  und einzelne Schrittkarten mit Anime.js gestaffelt einblenden.
  Randlicht und feste Punktwolke kennzeichnen die innere Ebene.
- [x] 5. Tastatur, Touch, reduzierte Bewegung, mobile Ansichten,
  Sofortnavigation und Ausfälle gezielt prüfen. Desktop und Mobil in
  einer gebündelten visuellen Runde sichten, Befunde gemeinsam beheben.
- [x] 6. Unabhängige Schlussprüfung, strengen Build und alle Doku-
  Browsertests ausführen. Pflegehinweise, Projektgeschichte, Changelog
  und Status aktualisieren; bestehende fremde Änderungen bewahren.

## Schnittstellen und Abnahme

Die erste Roadmap-Tabelle behält ihre sechs Spalten. Die zusätzliche
Schrittetabelle hat `Phase`, `ID`, `Schritt`, `Stand`, `Aktualisiert`,
`Beleg`; IDs sind innerhalb des Dokuments stabil und eindeutig. Die
Positionen speichern nur endliche Kartenkoordinaten, getrennt nach Ebene.

Ein Klick oder Wheel-Zoom muss dieselben Schritte sichtbar machen. Der
Übergang erzeugt keinen Dialog: Karteninhalt verblasst, der Umriss erreicht
die Bühne, einzelne Schritte bleiben als Karten pan- und verschiebbar.
Herauszoomen führt in den vorherigen Ausschnitt zurück. Phasenstatus,
Exit-Kriterium und Belege entsprechen dem Markdown; synthetische
Zeitpunkte und Fortschrittsquoten werden nicht erzeugt.

Pflichtprüfungen: `./scripts/docs-site.sh build -s` und
`npx playwright test -c playwright.docs.config.ts`. Python ausschließlich
über die Projekt-venv; Messpfad und Hardware sind von dieser Aufgabe
unberührt.
