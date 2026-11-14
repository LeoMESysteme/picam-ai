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
  lebendig-ground: "#eef2fb"
  lebendig-ground-dark: "#0b1020"
  lebendig-ink: "#141a2e"
  lebendig-ink-light: "#46507a"
  lebendig-ink-dark: "#e7ebff"
  lebendig-ink-light-dark: "#aab4dc"
  lebendig-paper-dark: "#11172c"
  lebendig-link: "#2556cc"
  lebendig-accent: "#2f6df6"
  lebendig-accent-dark: "#8fb0ff"
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
  headline-lebendig:
    fontFamily: "Bricolage Grotesque, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  title-lebendig:
    fontFamily: "Bricolage Grotesque, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontWeight: 500
    letterSpacing: "-0.01em"
  body-lebendig:
    fontFamily: "Onest, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
  label-lebendig:
    fontFamily: "Onest, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
    fontWeight: 600
  code-lebendig:
    fontFamily: "Martian Mono, SFMono-Regular, Consolas, Menlo, monospace"
    fontSize: "0.8em"
    fontWeight: 400
rounded:
  sm: "0.2rem"
  md: "0.4rem"
  pill: "1rem"
  lebendig-surface: "22px"
  lebendig-narrow: "18px"
  lebendig-popup: "14px"
  lebendig-lens: "12px"
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
  lebendig-paper:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.lebendig-ink}"
    rounded: "{rounded.lebendig-surface}"
  lebendig-hint-popup:
    textColor: "{colors.lebendig-ink}"
    rounded: "{rounded.lebendig-popup}"
  lebendig-nav-lens:
    textColor: "{colors.lebendig-ink}"
    rounded: "{rounded.lebendig-lens}"
---

# Design System: picam-ai Wiki (Zensical)

## Overview

Das Wiki hat zwei Darstellungen, umschaltbar im Kopf (`assets/wiki-look.js`, Attribut `html[data-wiki-look]`): **„ruhig“** und **„lebendig“**. `docs-overrides/main.html` setzt das Attribut vor dem ersten Zeichnen; Erstbesucher bekommen „lebendig“, die Wahl liegt in `localStorage['wiki-look']`, ohne JavaScript fehlt das Attribut und es gilt „ruhig“. **Alles von hier bis einschließlich „Do's and Don'ts“ gilt für die ruhige Darstellung.** Die lebendige Darstellung steht im eigenen Hauptabschnitt [„Lebendige Darstellung“](#lebendige-darstellung) am Ende; sie wirkt ausschließlich unter `[data-wiki-look="lebendig"]` und lässt die ruhigen Regeln unberührt.

**Creative North Star: "The Lab Binder"** (ruhige Darstellung)

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

### Laufmatrix (Session-Explorer)
Der Lauf ist das zentrale Objekt. Oben eine Kopfzeile (Anzahl, Frames, Archivstand) und ein Lagebild in zwei Spalten zwischen Haarlinien: links „Letzter Lauf“ mit Statusstreifen und drei Zahlen (0.84rem 600), rechts „Zum Nachsehen“ mit Zähler im Offen-Paar, je Lauf ein Verweis (Linkoptik, springt nur zur Tabellenzeile) und je Grund eine Zeile „Wert“ fett plus „Gruppe sonst q1–q3“ in `ink-light`; unter 700px einspaltig. „auffällig“ heißt außerhalb der Tukey-Zäune der Gruppe (ab vier Läufen). Darunter drei Kennzahlen (VALID, Verarbeitung mit p95 als Zusatz, Leserate mit Kamera-Bildrate), Haarlinie oben, Wert 1rem 600. Gewichtung, Konfidenz, Tracking und Softwarestand in einer Tiefenebene (`wiki-layer--hintergrund`).
Verlauf: ein Diagramm zur Zeit, umschaltbar über Pillen (`role=tab`, gewählt = Tinte auf Grund). Eine Spalte je Lauf in Startreihenfolge, Tage darunter gruppiert und gepunktet getrennt; Abstände sind keine Zeitabstände. Statusanteile gestapelt (VALID `chart-good`, TRANSITION `chart-warning`, UNREADABLE `chart-critical`, STALE `ink-light`), je Reiter nur die in dieser Kennzahl auffälligen Läufe mit Punkt in `status-open-fg` über der Spalte (Legende „Auffällig in dieser Kennzahl“); andere Gründe nennt die Auslesezeile. Statusanteile durch eine 1px-Fuge im Grundton getrennt. Verarbeitung als Median-Punkt mit p95-Strich, beide in `chart-series` und nur durch Form unterschieden; Gesamtwerte gestrichelt (VALID gesamt in Tinte), p95 gesamt gepunktet. Leserate mit Achse um die Daten (nicht ab null) und kräftig gepunkteter Kamera-Bildrate in Tinte. Kernsatz über dem Diagramm in Tinte, 0.72rem 600. Werte zum Lauf erscheinen in einem schwebenden Tooltip über dem Diagramm (Hinweis-Optik, einziger weiterer Schatten), nie in einer Zeile, die die Seite verschiebt; die Reiterfläche hat die vorab gemessene Höhe des größten Reiters. Statusstreifen erklären Farbe, Anteil und Bedeutung über den gemeinsamen Wiki-Hinweis. Bewegung: Säulen wachsen (scaleY, 420ms `outExpo`, 30ms Staffel), Streifen laufen von links ein, Detailzeilen blenden auf (220ms); nur beim Erscheinen und bei Wechseln. SVG-Text in rem (0.6rem). Ein Tabstopp, Pfeiltasten wählen, Enter führt zur Tabellenzeile; ein 9-%-Band (höchstens 56px breit) markiert den Lauf, synchron mit der Zeilentönung (6 %). Eine einzige versteckte Live-Ansage je Tastenwechsel. `V1…` erst ab zwei Softwareständen.
Tabelle: eine Zeile je Lauf mit Startzeit (600) und Kennung (0.62rem `ink-light`), Statusstreifen (0.7rem hoch, Anteile nebeneinander, `role=img`), Zahlen rechtsbündig in `tabular-nums`, Auswahl „Ansehen“ bzw. „Als B daneben“ nur wenn sinnvoll (keine gesperrten Knöpfe). „Details und Dateien“ öffnet eine Zeile über alle Spalten mit Faktenraster und Downloads. Knöpfe tragen den Lauf im zugänglichen Namen. Filter „Nur auffällige“ in „Zeigen“. Feldrahmen in `ink-light` (≥ 3:1). Ladefehler: eine Meldung mit `role=alert` und „Seite neu laden“; die Ersatztabelle klappt auf. Unter 700px wird jede Zeile ein Block: Lauf, Streifen, drei Zahlen nebeneinander, Auswahl. Die rechte Inhaltsleiste ist auf dieser Seite ausgeblendet, damit Tabelle und Einzelansicht die Breite bekommen.

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

## Lebendige Darstellung

Gilt nur unter `html[data-wiki-look="lebendig"]`. Quelle: `assets/wiki-lebendig.css` (Rahmen, Tokens, Schriften), `assets/wiki-lebendig.js` (Atmosphäre, Linse, Seiteneintritt), lebendige Schichten am Ende von `wiki.css`, `tour.css`, `roadmap.css`, `fortschritt.css`, `sessions.css`. Inhalt, Navigation, Tabellen, Status- und Datenfarben sind dieselben wie in „ruhig“; es ändern sich Material, Schrift und Bewegung.

### Overview

**Creative North Star: "Glas über atmender Atmosphäre"**

Das Wiki liegt als Glas über einer ruhig atmenden Farbatmosphäre. Die Welt setzt die Codebase-Bühne (`assets/codebase/`); jede Textseite trägt sie leise weiter. Wer umschaltet, erkennt dasselbe Wiki: Navigation, Text und Tabellen bleiben an ihrem Platz, nur der Rahmen wird Glas und die Seite bekommt einen Eintrittsmoment.

Glas ist dem vorbehalten, was über dem Inhalt schwebt oder was man bedient: Kopf, Seitenleisten, Pop-up, Fußzeile, schwebende Bedienflächen. Die Lesefläche selbst ist fast deckendes Papier (90 %), damit Lesen nie leidet. Inhalt im Textfluss (Diagramme, Tour-Bühne, Roadmap-Karte) liegt in ruhigen Schalen ohne Unschärfe.

**Key Characteristics:**
- Fester Atmosphäre-Grund mit drei weichen Radialtönungen, getönt nach Weg der Seite.
- Glasbänder mit weißem Innenlicht oben, bläulichem Unterschatten, 1px heller Kante.
- Lesefläche als große gerundete Scheibe (22px), fast deckend.
- Eigene Schriften lokal: Bricolage Grotesque, Onest, Martian Mono.
- Ein Bewegungsmoment je Seite (Eintritt), Signatur gleitende Linse; bei reduzierter Bewegung alles aus.
- Status- und Datenfarben unverändert aus „ruhig“.

### Colors

Nebelblau und Tinte statt Theme-Indigo; Farbe trägt weiterhin nur Status und Daten. Die Tokens setzt `wiki-lebendig.css` am `<body>` (Zensical setzt seine Farben dort), hell und unter `[data-md-color-scheme="slate"]` dunkel; die Zensical-Variablen (`--md-default-*`, `--md-typeset-*`, `--md-accent-*`) werden darauf umgebogen.

- **Nebelblau / Nachtblau** (`--lb-ground`, `lebendig-ground` / `lebendig-ground-dark`): Seitengrund unter der Atmosphäre.
- **Tinte** (`--lb-ink`, `lebendig-ink` / `lebendig-ink-dark`): Text, Überschriften, aktiver Navigationseintrag.
- **Tinte hell** (`--lb-ink2`, `lebendig-ink-light` / `lebendig-ink-light-dark`): Sekundärtext, Legenden, Achsen, Fußzeilen-Meta.
- **Linie** (`--lb-line`, `rgb(60 80 150 / .16)` / `rgb(170 185 255 / .16)`): Haarlinien und Schalenränder; ersetzt `--md-default-fg-color--lightest` in den Sonderseiten.
- **Papier** (`--lb-paper`, `rgb(255 255 255 / .9)` / `rgb(17 23 44 / .9)`): Lesefläche. Zensical-Grund `--md-default-bg-color` wird `#fff` / `lebendig-paper-dark`.
- **Link / Akzent** (`lebendig-link` `#2556cc`, `lebendig-accent` `#2f6df6`; dunkel beide `lebendig-accent-dark`): Links, Fokusring, Textauswahl (`#2f6df6` auf Weiß).
- **Glas** (`--lb-glass`, `--lb-glass-edge`, `--lb-glass-light`): Verlauf `135deg` aus Weiß .5 → .2 → .38 (dunkel .09 → .03 → .06), Kante Weiß .7 (dunkel .13).
- **Linse** (`--lb-lens`, `--lb-lens-shadow`): heller Verlauf `170deg` von Weiß nach `rgb(235 242 255 / .92)`; dunkel `rgb(120 150 255 / .32 → .16)`.
- **Glanz** (`--lb-sheen`): Weiß .55, dunkel `rgb(160 185 255 / .14)`.

**Atmosphäre je Weg** (`TINTS` in `wiki-lebendig.js`, drei Radialtönungen `--a/--b/--c`; Weg aus `.wiki-pagehead[data-weg]`, Codebase-Seite = projekt, sonst start):

| Weg | hell | dunkel (gedämpft) |
|---|---|---|
| start | `#bcd7ff` `#dccbff` `#c9f2e3` | `rgb(64 110 230 / .16)` `rgb(130 90 230 / .14)` `rgb(40 170 140 / .1)` |
| bedienen | `#c9f2e3` `#d3e8ff` `#e6f6d6` | `rgb(40 170 140 / .13)` `rgb(64 110 230 / .12)` `rgb(90 170 80 / .09)` |
| konfigurieren | `#bfd8ff` `#cfe0ff` `#d9d0ff` | `rgb(64 110 230 / .17)` `rgb(80 130 240 / .11)` `rgb(120 100 230 / .11)` |
| entwickeln | `#dccbff` `#d6ccff` `#ffd9ec` | `rgb(130 90 230 / .16)` `rgb(110 90 220 / .12)` `rgb(220 90 160 / .09)` |
| projekt | `#ffe0c7` `#cfe0ff` `#e3d3ff` | `rgb(230 140 70 / .11)` `rgb(64 110 230 / .13)` `rgb(140 100 230 / .11)` |

**The Gedämpft-Dunkel Rule.** Dunkel bleibt Nachtblau, nie Neon: Atmosphäre-Alphas höchstens .17, Glas im Dunkeln nur `saturate(112%)` statt 180 %, damit die Leisten nicht königsblau werden.
**The Same-Status Rule.** Status- (`--docs-*`) und Datenfarben (`--wiki-chart-*`-Serien, `--fs-*`, Tour `tp-*`) sind in beiden Darstellungen identisch; „lebendig“ ändert nur Raster, Achsen, Spuren und Material.

### Typography

**Titel:** Bricolage Grotesque 500/700 · **Text:** Onest 400/600 · **Code:** Martian Mono 400. Alle lokal unter `docs-site/assets/fonts/` (WOFF2, latin), SIL Open Font License (`fonts/OFL.txt`), `font-display: swap`. Die `@font-face`-Regeln laden nur, wenn eine lebendige Regel sie benutzt.

**Character:** Bricolage gibt den Titeln eine eigene, leicht exzentrische Grotesk-Stimme mit enger Laufweite; Onest bleibt im Fließtext neutral und gut lesbar; Martian Mono setzt Code deutlich ab.

- **Headline** (`headline-lebendig`: h1 700, `-0.03em`, Zeilenhöhe 1.08; h2 700, `-0.02em`): Seiten- und Abschnittstitel, `text-wrap: balance`. Größen bleiben die des Themes.
- **Title** (`title-lebendig`: h3 500, `-0.01em`): Unterabschnitte; Seitentitel im Kopf und Diagrammtitel (`figcaption`, 0.8rem) in Bricolage 700.
- **Body** (`body-lebendig`: Onest 400, Theme-Größe 0.75rem): Fließtext, `text-wrap: pretty`; Links mit `text-underline-offset .18em`.
- **Label** (`label-lebendig`: Onest 600): aktiver Navigationseintrag, Kapitel- und Wertpillen.
- **Code** (`code-lebendig`: Martian Mono 400, 0.8em): `code`, `kbd`, `pre`.

**The Measure-After-Fonts Rule.** Was Text vermisst (Diagramme), zeichnet nach `document.fonts` `loadingdone` neu, weil Onest später kommt als die Systemschrift.

### Layout

Raster und Seitenleisten von Zensical bleiben. Lesefläche `.md-content` mit `margin-top 1rem` am Haupt-Container und Abstand zum Rand: ab 60em `margin-inline .6rem` (auch auf Seiten ohne Seitenleisten wie Tour und Roadmap), unter 60em `0 .4rem 1.2rem`. Glas der Navigation ab 76.25em (Abstand `margin-right .6rem`, `padding-block .5rem`), Glas des Inhaltsverzeichnisses ab 60em am inneren Block, also nur so hoch wie das Verzeichnis (`margin-left .6rem`); der Scrollbereich blendet unten auf 18px weich aus. Codebase-Seite weitet das Raster auf `min(1600px, 100% - 56px)`, Fließtext bleibt bei 42rem.

### Elevation & Depth

Geschichtet statt flach: feste Atmosphäre (z-index -1) → Glasbänder mit Unschärfe → Papier der Lesefläche → schwebendes Glas (Pop-up, Tooltips). Die One-Shadow-Rule der ruhigen Darstellung gilt hier nicht; an ihre Stelle tritt ein festes Schattenvokabular.

**Glas sitzt an:** Kopf (`blur(14px) saturate(180%)`), Navigation und Inhaltsverzeichnis (Seitenleisten, `blur(14px)`), deren Kopfzeilen (Milchglas `blur(12px)`, 72 % Grund), Fußzeile (`saturate(160%)`), Hinweis-Pop-up und schwebende Werte (`blur(16px)`), schwebende Bedienflächen der Sonderseiten (Roadmap-Navigation und Übersicht, Phasenkontext schmal). **Lesefläche:** `--lb-paper` (90 % deckend), ohne Unschärfe. **Schalen:** Tour-Bühne, Roadmap-Karte, Fortschritts-Diagramme liegen flach in der Lesefläche (Innenschatten oder getönter Grund, keine Unschärfe).

### Shadow Vocabulary
- **Glas-Innenlicht** (`--lb-glass-light`: `inset 0 1.5px 0 rgb(255 255 255 / .95), inset 1.5px 0 0 rgb(255 255 255 / .45), inset 0 -14px 26px -16px rgb(70 100 220 / .3)`; dunkel `inset 0 1px 0 rgb(255 255 255 / .16), inset 0 -14px 26px -16px rgb(90 120 255 / .22)`): jede Glas- und Papierfläche.
- **Tiefe** (`--lb-drop`: `0 34px 70px -30px rgb(40 60 150 / .42), 0 8px 20px -8px rgb(40 60 150 / .14)`; dunkel Schwarz .7/.4): Lesefläche, Glasbänder der Tour und Sessions, Roadmap-Bedienung.
- **Leiste** (`0 20px 50px -30px rgb(40 60 150 / .45)`): Navigation und Inhaltsverzeichnis, leichter als die Lesefläche.
- **Kopf** (`inset 0 -1px 0 var(--lb-line), 0 10px 30px -24px rgb(40 60 150 / .5)`).
- **Linse** (`--lb-lens-shadow`: `inset 0 1px 0 #fff, inset 0 -8px 12px -8px rgb(60 90 200 / .35), 0 8px 18px -8px rgb(40 60 150 / .5), 0 1px 3px rgb(40 60 150 / .18)`): aktiver Eintrag, gewählte Pillen und Knöpfe.
- **Schwebend** (`inset 0 1px 0 #fff, 0 18px 40px -18px rgb(40 60 150 / .55), 0 2px 6px rgb(40 60 150 / .12)`; dunkel `inset 0 1px 0 rgb(255 255 255 / .12), 0 18px 40px -18px rgb(0 0 0 / .8)`): Hinweis-Pop-up, `.fs-tooltip`, `.session-tip`.
- **Schale** (`inset 0 1px 3px rgb(40 60 150 / .1)`; dunkel `rgb(0 0 12 / .45)`): Tour-Bühne, Roadmap-Viewport, Suchfelder (`inset 0 1px 2px`).
- **Diagrammbalken** (`drop-shadow(0 2px 3px var(--wiki-chart-rest))`, Hover `0 6px 8px var(--wiki-chart-lift)`).

**The Glass-Floats Rule.** Glas mit Unschärfe nur, wo etwas über Inhalt schwebt oder bedient wird; Inhalt liegt auf Papier oder in einer Schale. Glas als Deko auf jedem Kasten ist ausgeschlossen.

### Shapes

Weich und groß gerundet, Rundung nimmt mit der Fläche ab: **22px** Flächen (Lesefläche, Seitenleisten, Roadmap-Navigation, Sessions-Diagrammwahl), **18px** schmale Lesefläche unter 60em und Schalen (Tour-Bühne, Fortschritts-Diagramme, Roadmap-Karten, Session-Einzelansicht), **14px** Pop-up, schwebende Werte, Leisten-Kopfzeilen, „Mehr dazu“- und Stand-Kästen, **12px** Linse und Eingabefelder. Pillen (`999px`) für Wert-, Legenden- und Bedienpillen, Kreise für runde Bedienknöpfe. Kanten 1px: `--lb-glass-edge` an Glas, `--lb-line` an Schalen. Icons bleiben Linien-SVG mit `currentColor` (auch die Tour-Bedienknöpfe, `tour.js` `controlIcon`, 1.8px, in beiden Darstellungen).

### Motion

Kurven: Feder `--lb-spring` `cubic-bezier(.2, 1.25, .35, 1)` (Umschalterknopf, Pillen, Kettenknoten, Pop-up-Anhebung), Auslauf `--lb-out` `cubic-bezier(.16, 1, .3, 1)` (Eintritt, Überblendungen).

- **Der eine Moment: Seiteneintritt.** Glanzstreif (`105deg`, `--lb-sheen`) läuft in 1.15s über die Lesefläche; die ersten sechs sichtbaren Blöcke tauchen gestaffelt auf (`translateY(14px)`, Deckkraft .35 → 1, 760ms, 45ms Staffel). Inhalt ist ohne Animation lesbar.
- **Signatur: gleitende Linse.** Beim Klick in der Navigation merkt sich `wiki-lebendig.js` die alte Linse; nach dem Seitenwechsel gleitet ein Geist (`.wiki-lens-geist`) in .75s (`cubic-bezier(.22, 1.12, .36, 1)`) zum neuen Eintrag.
- **Atmosphäre:** zwei feste Schichten überblenden beim Wegwechsel in 1.4s.
- **Diagramme** wachsen beim Sichtbarwerden: Balken 900ms `outExpo`, 45ms Staffel, Wertpillen ab 420ms in 360ms; beim Umschalten zeichnen sie neu und wachsen erneut, wenn sie im Blick sind.
- **Kette:** Puls wandert die Schiene in 80 % von 5.6s ab und verblasst, jede Stufe leuchtet bei Ankunft kurz auf; kompakte Kette mit Signal entlang der Pfeile (4.2s, 350ms Versatz), nur solange sichtbar.
- **Wechsel der Darstellung:** View Transition .45s.
- **Reduzierte Bewegung:** Eintritt, Linse, Puls, Signal, Überblendungen und Federn entfallen; die Tönung springt.

### Components

#### Umschalter (beide Darstellungen)
Schalter `role="switch"` im Kopf vor der Farbschema-Wahl: Spur 2.1 × 1.1rem, Pillenform, 1px Rand in `currentColor` 45 %, Knopf .8rem in `currentColor`, gleitet mit Feder .45s. Linien-SVG an beiden Enden (ruhig: drei Zeilen, lebendig: Welle); der Knopf verdeckt das aktive, sichtbar bleibt, was ein Klick bringt. Aktiv lebendig: Spur mit zwei Radialtönungen (`#bcd7ff`/`#dccbff` .55). `title` erklärt beide Zustände; Wechsel meldet `wiki:look`, andere Tabs ziehen über `storage` nach.

#### Linse
Aktiver Navigationseintrag: `--lb-lens`, Radius 12px, `--lb-lens-shadow`, Onest 600 in Tinte. Dieselbe Linse markiert die gewählte Option überall: aktuelles Tour-Kapitel, gedrückte Tour- und Roadmap-Knöpfe, aktive Fortschritts-Legende, gewählte Sessions-Diagrammwahl.

#### Glas-Pop-up
`.wiki-hint`: Verlauf Weiß .94 → .82 (dunkel `rgb(24 31 58 / .95)` → `rgb(17 23 44 / .9)`), `blur(16px) saturate(180%)`, Kante `#fff` (dunkel Weiß .14), Radius 14px, Schatten „Schwebend“; Einblendung .25s Auslauf, Anhebung .45s Feder. Dieselbe Optik tragen `.fs-tooltip` und `.session-tip`.

#### Lebendige Diagramme (`wiki-chart.js`)
Nur lebendig: Spur je Balken (`--wiki-chart-track`), Balken mit fast eckiger Grundlinie (2px) und weichem Datenende (7px), Glanz im oberen Drittel, Wert in Glaspille (Radius 9, 6px Innenabstand). Raster und Achse in Linienblau, Titel Bricolage 700. Überfahren/Fokus hebt den Balken, die übrigen treten auf .32 zurück, Pillen bleiben voll lesbar; Fokusring 2px Akzent. Achsenmarken in runden Schritten (1, 2, 2,5, 5 × 10ⁿ), kollidierende Beschriftungen entfallen (gilt in beiden Darstellungen).

#### Kette (`wiki-kette.js`)
Stufen als Glasknoten (Radius 16px, Verlauf `165deg`, Innenlicht), Hover/Fokus `scale(1.02)` mit Feder. Volle Fassung: Schiene 2px links mit Stationspunkten (10px, Statusfarbe `--docs-*-fg`, 3px Papierring) und wanderndem Puls in Akzent. Kompakt (Startseite): Glaspillen, `scale(1.05)`, Signal entlang der Pfeile.

#### Sonderseiten-Schichten
- **Tour** (`tour.css`): Bühne als Schale (18px, Innenschatten), eigene Atmosphäre-Tönung für Vollbild. Kapitelwahl und Steuerung als zwei Glasbänder (Radius 24px, Innenabstand 5px), Linse unter dem aktuellen Kapitel, runde Bedienknöpfe mit Linse beim Überfahren/Drücken, aktueller Schrittpunkt als kurze Linse (1.5rem). „Mehr dazu“ als weicher Kasten (14px) statt Randbalken; „Nochmal“ als Glaspille.
- **Roadmap** (`roadmap.css`): Karte als Schale (20px), Meilenstein- und Schrittkarten als Glasscheiben ohne Unschärfe (18px), Verbindungen 2px rund; Navigation (22px) und Übersicht (16px) als Glas mit Unschärfe, Ansichtswahl als Glasband, Suche als Feld (20px). Hover färbt Kante und Schatten in der Knotenfarbe.
- **Fortschritt** (`fortschritt.css`): jedes Diagramm in einer Schale (18px, schmal 14px), die so weit in den Rand ragt, wie sie innen Abstand hält (Zeichenbreite bleibt beim Umschalten gleich). Legendenschalter als Glaspillen, ausgeschaltet als Umriss; Stand-Hinweis als weicher Kasten mit getönter Kante je Zustand.
- **Sessions** (`sessions.css`): Knöpfe als Linsenpillen, Verweisknöpfe bleiben Text, Felder 12px; Diagrammwahl als Glasband (22px) mit Linse; Laufmatrix-Kopf als flaches Band mit runden Enden (12px); Detailzeile getönt (unten 14px); Einzelansicht im Glasrahmen (18px). Der eingebettete Records-Explorer behält seine eigene Darstellung.
- **Codebase-Seite** (`docs/uebersicht/codebase.md`, `wiki-codebase.js`): bettet nur in „lebendig“ die Bühne `assets/codebase/index.html` ein und reicht das Farbschema per `postMessage` durch; in „ruhig“ bleiben Text, Tabellen und Diagramme, die Bühne ist über „Vollbild öffnen“ erreichbar. Die Bühne (`codebase.css`, `codebase.js`, `kit.js`) ist die Ursprungswelt dieser Darstellung und hat einen eigenen Tokensatz (`--glass-*`, `--lens-*`, Bereichsfarben).

### Do's and Don'ts

#### Do:
- **Do** jede lebendige Regel unter `[data-wiki-look="lebendig"]` schreiben; ohne Attribut darf sich nichts ändern.
- **Do** Farben, Glas, Linse und Kurven aus `--lb-*` beziehen, hell und dunkel.
- **Do** Glas nur an schwebende oder bediente Flächen setzen; Inhalt auf Papier (`--lb-paper`) oder in Schalen.
- **Do** die gewählte Option mit der Linse markieren (`--lb-lens`, `--lb-lens-shadow`).
- **Do** Status- und Datenfarben aus der ruhigen Darstellung übernehmen.
- **Do** Bewegung an Sichtbarkeit binden und bei `prefers-reduced-motion` vollständig abschalten.
- **Do** Rundung nach Flächengröße wählen: 22 / 18 / 14 / 12px.
- **Do** Kästen statt Randbalken: Betonung als weicher Kasten mit 1px `--lb-line` und getöntem Grund.

#### Don't:
- **Don't** Glas als Dekoration auf jeden Kasten legen oder die Lesefläche durchscheinend machen.
- **Don't** einen zweiten seitenweiten Bewegungsmoment neben dem Seiteneintritt einführen.
- **Don't** Neon-Dunkel: keine gesättigten Leuchtflächen, Glas im Dunkeln nicht über `saturate(112%)`.
- **Don't** Navigation, Text oder Tabellen gegenüber „ruhig“ verschieben oder umbauen.
- **Don't** Schriften von einem CDN laden; nur `assets/fonts/` mit `OFL.txt`.
- **Don't** Glyph-Icons oder Unicode-Zeichen als Bediensymbole; Linien-SVG mit `currentColor`.
