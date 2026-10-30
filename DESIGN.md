---
name: picam-ai Wiki (Zensical)
description: Ruhiges, dokumentarisches Lesewiki auf dem Zensical-Theme, erweitert um Rollenwege, Tiefenebenen, Hinweise, Statuschips und datengetriebene Diagramme.
colors:
  primary: "#4051b5"
  accent: "#526cfe"
  surface: "#ffffff"
  surface-dark: "hsla(var(--md-hue), 15%, 5%, 1)"
  ink: "#000000de"
  ink-light: "#0000008c"
  hairline: "#0000000d"
  status-open-bg: "#fff2d0"
  status-open-fg: "#654700"
  status-progress-bg: "#dfedff"
  status-progress-fg: "#164578"
  status-partial-bg: "#efe5ff"
  status-partial-fg: "#56338a"
  status-resolved-bg: "#ddf3df"
  status-resolved-fg: "#205629"
  status-discarded-bg: "#ececec"
  status-discarded-fg: "#4f4f4f"
  status-blocked-bg: "#ffe0df"
  status-blocked-fg: "#842c28"
  chart-series: "#2a78d6"
  chart-good: "#0ca30c"
  chart-warning: "#fab219"
  chart-critical: "#d03b3b"
  chart-grid: "#e1e0d9"
  chart-axis: "#c3c2b7"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontSize: "1.5em"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 600
    lineHeight: 1.3
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 600
    lineHeight: 1.4
  code:
    fontFamily: "SFMono-Regular, Consolas, Menlo, monospace"
    fontSize: "0.62rem"
rounded:
  sm: "0.2rem"
  md: "0.4rem"
  pill: "1rem"
spacing:
  xs: "0.35rem"
  sm: ".6rem"
  md: "1rem"
  lg: "2rem"
components:
  chip-status:
    backgroundColor: "{colors.status-progress-bg}"
    textColor: "{colors.status-progress-fg}"
    rounded: "{rounded.pill}"
    padding: ".05em .5em"
  hint-popup:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: ".6rem .75rem"
  layer-details:
    rounded: "{rounded.md}"
    padding: "0 .75rem .75rem"
  stand-row:
    padding: ".75rem 0"
  weg-column:
    padding: ".2rem 1rem .4rem"
---

# Design System: picam-ai Wiki (Zensical)

## Overview

**Creative North Star: "The Lab Binder"**

Das Wiki ist ein gut geführtes Laborhandbuch: das Zensical-Theme (Material-artig, modern-Variante) trägt Schrift, Navigation, Farbschemata und Raster, und bleibt verbindlich. Alles Eigene ist eine präzise Erweiterung darauf, geschrieben in Theme-Variablen (`--md-*`), damit hell, dunkel und System ohne Sonderfälle funktionieren. Struktur entsteht durch 1px-Haarlinien und Abstand, nicht durch Kästen.

Die Dichte ist die eines Nachschlagewerks im Lesemodus: kleine, ruhige Schrift (Fließtext 0.75rem, Eigenelemente 0.62 bis 0.8rem), wenig Farbe, Farbe nur als Statussprache. Tiefe liegt in Schichten (aufklappbar), nicht in der Fläche. Bewegung dient dem Verstehen (Anime.js lokal, kurz, `outExpo`) und fällt bei reduzierter Bewegung weg.

**Key Characteristics:**
- Theme-Tokens zuerst, eigene Tokens nur für Status (`--docs-*`) und Diagramme (`--wiki-chart-*`).
- Haarlinien (`--md-default-fg-color--lightest`) statt Karten als Seitenstruktur.
- Eine Statussprache aus sechs Paaren (Hintergrund/Vordergrund) in beiden Themes.
- Einheitlicher Hinweis-Pop-up, eine Tiefenebenen-Komponente, Icons als 1.8px-Linien-SVG.
- Jede interaktive Ansicht hat eine Text- oder Quellfassung ohne JavaScript.

## Colors

Zurückhaltend: Theme-Indigo für Links und Marke, Theme-Akzent für Fokus und Hover, alles Weitere sind gedämpfte Statuspaare.

### Primary
- **Zensical Indigo** (`primary`): Linkfarbe (`--md-typeset-a-color`) und Aktionstexte wie "Weiter"-Links und Zusammenfassungen.
- **Fokus-Blau** (`accent`): Fokusringe (2px), Hover von Kopfzeilenlinks, aktive Filter. Werte stammen aus dem Theme und folgen der Palette.

### Neutral
- **Papier / Nachtgrund** (`surface`, `surface-dark`): Seitenfläche; Pop-up und Diagrammflächen nutzen denselben Grund.
- **Tinte** (`ink`, `ink-light`): Text und Sekundärtext (Labels, Meta, Hinweise).
- **Haarlinie** (`hairline`): einzige Trennlinie von Statusreihe, Wegspalten, "Alle Seiten", Tiefenebenen, "Weiter"-Zeile.

### Status (Sekundär, nur für Zustand)
- **Offen, In Arbeit, Teilweise, Gelöst, Verworfen, Blockiert** (`status-*-bg/fg`): Chips, Wegsymbole, Ebenen-Symbole. Dunkle Variante unter `[data-md-color-scheme="slate"]` ist abgetönt (z. B. Gelöst `#1c4028` / `#c2ebc8`). Kontrast jeweils ≥ 4,5 : 1.
- **Diagramm** (`chart-*`): Serie, gut, Warnung, kritisch, Raster, Achse; im Dunkeln ändert sich nur Serie, Raster, Achse.

### Named Rules
**The Theme-First Rule.** Eine neue Fläche erbt Farbe aus `--md-*`; eine neue Farbe braucht eine Statusbedeutung.
**The Status-Pair Rule.** Statusfarbe erscheint immer als Hintergrund/Vordergrund-Paar, nie als nackter Farbton auf Fließtext.
**The Meaning-Not-Decoration Rule.** Farbe unterscheidet Zustand oder Rolle (Bedienen = Gelöst-Grün, Konfigurieren = In-Arbeit-Blau, Entwickeln = Teilweise-Violett), nie Dekoration.

## Typography

**Display/Body Font:** Systemschrift des Themes (`-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif`); keine eigene Schrift wird geladen.
**Label/Mono Font:** Theme-Monospace (`SFMono-Regular, Consolas, Menlo, monospace`) für Code und Diagramm-Kennungen.

**Character:** Neutral und sachlich; Gewicht (600/700) statt Größe schafft Rangfolge, negative Laufweite nur in Überschriften.

### Hierarchy
- **Headline** (700, 1.5em, 1.4, -0.025em): Seitenabschnitte (h2) aus dem Theme.
- **Title** (600, 0.8rem, 1.3): Wegtitel, Ebenen-Zusammenfassungen (0.74rem), Diagrammtitel.
- **Body** (400, 0.75rem, 1.8): Fließtext, Maximalbreite des Themes (61rem Raster).
- **Label** (600, 0.7rem, 1.4): Statuszeile, Seitenkopf, Weg-Links (0.74rem). Sekundärtext 0.62 bis 0.7rem in `ink-light`. Zahlen in Diagrammen `tabular-nums`.

### Named Rules
**The Small-Quiet Rule.** Eigene Elemente sind kleiner als der Fließtext und unterscheiden sich durch Gewicht 600 und `ink-light`, nicht durch Großbuchstaben oder Laufweite.

## Layout

Zensical-Raster (`.md-grid` 61rem) mit Seitenleisten. Die Startseite ist von oben nach unten: Titel, ein Satz Zweck, haarlinien-begrenzte Statusreihe (Flex, `gap .6rem 2rem`, Items ab 14rem), dann "Wähle deinen Weg" als drei Spalten (`repeat(3, minmax(0,1fr))`, `gap 0`), getrennt durch 1px-Haarlinien, Innenabstand 1rem, erste/letzte Spalte ohne Außenabstand. Unter 52em stapeln die Wege, Trennlinie wechselt von links nach oben. Tabellen und Diagramme brechen unter 600px um; kein horizontales Scrollen. Rhythmus: 0.35 / 0.6 / 1 / 1.3 bis 1.6 / 2rem; Abschnitte mit Haarlinie ab `margin-top 2.4rem`. Seitenkopf (Weg, Meta, Weiter-Link) sitzt in einer Flex-Zeile über dem Inhalt, `margin -.5rem 0 1.6rem`.

Roadmap-Karte weitet das Raster (bis 1920px) und blendet die rechte Leiste aus; sie ist eine Sonderseite.

## Elevation & Depth

Flach. Tiefe entsteht durch Haarlinien, zurückgenommene Tönung (3 % Vordergrund auf Hintergrund bei Tiefenebenen) und Aufklappen. Einzige Schattenstufe ist das Hinweis-Pop-up.

### Shadow Vocabulary
- **Hint-Popup** (`box-shadow: 0 .5rem 1.4rem -.6rem rgb(0 0 0 / .35)`): weicher, negativer Spread, nur am schwebenden Hinweis; erscheint mit 140ms Fade und 4px Anhebung.

### Named Rules
**The One-Shadow Rule.** Nur das schwebende Hinweis-Pop-up hat einen Schatten; alles im Textfluss hat `box-shadow: none`, auch bei `:focus-within`.

## Shapes

Zurückhaltend gerundet: 0.4rem für Pop-up, Tiefenebenen, Diagramm- und Tabellenrahmen; 0.2rem für Eingabefelder; Pillen (1em bis 1rem) für Statuschips und Filter; Kreise (8px) für Statuspunkte der Kette. Rahmen sind immer 1px Haarlinie. Fokus: 2px Akzent-Ring mit 2px Abstand. Icons sind Linien-SVG, 1.8px Strichstärke, runde Enden, `currentColor`.

## Components

### Statuschip
Pille (`1em`), `.72em`, 600, Paar aus Status-Hintergrund und -Vordergrund, `margin-left .3em`. Sechs Varianten: offen, in Arbeit, teilweise, gelöst, verworfen, blockiert. Erscheint im Fließtext, in der Statusreihe (OQ-Chip) und im Pop-up.

### Rollenwege (Wähle deinen Weg)
Drei Spalten ohne Karten, Haarlinien dazwischen. Titel (h3, 0.8rem) mit Linien-Icon in Rollenfarbe, Beschreibung in `ink-light`, Links 600 mit Hinweiszeile darunter. Darunter eine aufklappbare "Alle Seiten"-Zeile, nur Haarlinien oben und unten, Pfeil rotiert 90° in 150ms.

### Statusreihe
Haarlinie oben und unten, Label 600 in `ink-light`, darunter Wert; Kamera, Messpfad, GSVmulti (mit OQ-Chip).

### Hinweis-Pop-up (ein Bauteil)
Ein gemeinsames Element für Glossarbegriffe, Abschnittsvorschau, Codezeilen, API-Kurzerklärung. Surface-Grund, 1px Haarlinie, Radius 0.4rem, Padding .6rem .75rem, max 22rem, 0.68rem. Titel 0.72rem fett, Meta in `ink-light`. Per Tastatur erreichbar; bei reduzierter Bewegung ohne Übergang.

### Tiefenebene (details)
Aufklappbarer Block: 1px Haarlinie, Radius 0.4rem, 3 %-Tönung, Zusammenfassung 0.74rem 600 mit Linien-Icon links (Farbe je Ebene: Hintergrund = In-Arbeit-Blau, Entwickler = Teilweise-Violett, Historisch = `ink-light`) und rotierendem Pfeil rechts. Inhalt unter einer Haarlinie. Varianten Setting/Seam (Tabellen mit Rahmen 0.4rem, Zeilenüberschrift 0.8rem 600).

### Diagramm aus Tabelle (wiki-chart)
SVG aus Tabellendaten, Titel 0.74rem 600, Beschriftung 0.62 bis 0.68rem, Raster/Achse aus `chart-grid`/`chart-axis`, Balken wachsen in 420ms (`outExpo`, 60ms Staffel). Tabelle bleibt als Quelle erreichbar.

### Verlauf je Lauf (Session-Explorer)
Eine Spalte je Lauf in Startreihenfolge, Tage darunter gruppiert und durch eine gepunktete Linie getrennt; Abstände sind keine Zeitabstände. Statusanteile als gestapelte Balken (VALID `chart-good`, TRANSITION `chart-warning`, UNREADABLE `chart-critical`, STALE `ink-light`), Verarbeitung als Median-Punkt mit p95-Strich, Gesamtwerte gestrichelt. Über jedem Diagramm ein Kernsatz aus den Daten (0.68rem, `ink-light`), Legende als Schlüssel-Pillen wie auf der Fortschrittsseite. Ein Tabstopp je Diagramm, Pfeiltasten wählen den Lauf, ein 6-%-Band markiert ihn in allen Diagrammen zugleich. Softwarestände als `V1…` am ersten Lauf jedes Stands.

### Verarbeitungskette (wiki-kette)
Interaktive Kette aus `kette.json`: Stufenkästen 0.4rem, Titel 0.74rem 600, Code-Kennung mono 0.62rem, Statuspunkte 8px, Einblendung 220ms mit 70ms Staffel; kompakte Variante mit Pillen.

### Glossar und Begriffsindex
Suchfeld (Radius 0.2rem, 1px Rahmen), A-Z-Leiste und Filter als Pillen, Vorkommen pro Begriff als aufklappbare Liste, Zähler rechts in `ink-light`.

### Navigation
Zensical-Navigation unverändert (Sections, Indexes, Pfad, Top, Footer, Instant). Seitenkopf zeigt Weg und "Weiter" mit Pfeil-Icon.

## Do's and Don'ts

### Do:
- **Do** Farben, Haarlinien und Fokus aus `--md-*` beziehen; neue Zustände als Paar `--docs-*-bg/fg` in beiden Themes anlegen.
- **Do** Struktur mit 1px `--md-default-fg-color--lightest` und Abstand herstellen.
- **Do** Icons als 1.8px-Linien-SVG mit `currentColor` und runden Enden.
- **Do** Bewegung nur mit Anime.js (lokal), 140 bis 420ms, und bei `prefers-reduced-motion` abschalten.
- **Do** jede interaktive Ansicht mit Text- oder Quellfassung ohne JavaScript absichern.
- **Do** Zahlen aus Daten oder Code ziehen (`kette.json`, `fortschritt.json`, `tour-facts.json`).

### Don't:
- **Don't** Karten als Seitenstruktur verwenden; Wege, Statusreihe und Abschnitte bleiben haarlinien-begrenzt.
- **Don't** Schatten außer dem des Hinweis-Pop-ups einführen.
- **Don't** Versalien-Überschriften, Kicker oder Eyebrows über Titeln setzen.
- **Don't** farbige Seitenränder als Betonung nutzen.
- **Don't** Glyph-Icons oder Emoji als Symbole verwenden.
- **Don't** das Zensical-Grunddesign (Schrift, Navigation, Palette) ersetzen; Erweiterung, nicht Umbau.
