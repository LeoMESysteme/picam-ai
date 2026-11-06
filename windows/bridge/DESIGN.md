---
name: GSVmulti-Brücke (Windows-App)
description: Windows-11-nativ gestaltetes Kompaktfenster, das Zustand und Ereignisjournal der Pi-zu-GSVmulti-Strecke zeigt und Verbindung, COM-Weitergabe und Empfang strikt trennt.
colors:
  primary: "#005fb8"
  primary-hover: "#196ebd"
  primary-press: "#3a82c5"
  on-primary: "#ffffff"
  primary-dark: "#60cdff"
  primary-dark-hover: "#52b7e6"
  primary-dark-press: "#44a0cc"
  on-primary-dark: "#000000"
  mica: "#f3f3f3"
  mica-recessed: "#ededed"
  card: "#fbfbfb"
  stroke: "#e5e5e5"
  stroke-strong: "#8a8a8a"
  control: "#fdfdfd"
  control-hover: "#f6f6f6"
  control-press: "#efefef"
  control-stroke: "#d1d1d1"
  text: "#1a1a1a"
  text-secondary: "#5d5d5d"
  text-disabled: "#9a9a9a"
  ok: "#0f7b0f"
  warn: "#9d5d00"
  err: "#c42b1c"
  info: "#5d5d5d"
  bar-ok: "#dff6dd"
  bar-warn: "#fff4ce"
  bar-err: "#fde7e9"
  bar-info: "#f9f9f9"
  mica-dark: "#202020"
  mica-recessed-dark: "#1b1b1b"
  card-dark: "#2b2b2b"
  stroke-dark: "#3a3a3a"
  stroke-strong-dark: "#9a9a9a"
  control-dark: "#323232"
  control-hover-dark: "#3a3a3a"
  control-press-dark: "#292929"
  control-stroke-dark: "#464646"
  text-dark: "#ffffff"
  text-secondary-dark: "#cfcfcf"
  text-disabled-dark: "#7a7a7a"
  ok-dark: "#6ccb5f"
  warn-dark: "#fce100"
  err-dark: "#ff99a4"
  info-dark: "#cfcfcf"
  bar-ok-dark: "#393d1b"
  bar-warn-dark: "#433519"
  bar-err-dark: "#442726"
  bar-info-dark: "#2f2f2f"
typography:
  subtitle:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: "28px"
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
    fontFeature: "tnum"
  body-strong:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: "20px"
  caption:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
    fontFeature: "tnum"
  caption-strong:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: "16px"
  data:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "18px"
rounded:
  sm: "4px"
  md: "8px"
  round: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button:
    backgroundColor: "{colors.control}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "4px 12px"
    height: "32px"
  button-hover:
    backgroundColor: "{colors.control-hover}"
  button-pressed:
    backgroundColor: "{colors.control-press}"
    textColor: "{colors.text-secondary}"
  button-accent:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    padding: "4px 12px"
    height: "32px"
  button-accent-hover:
    backgroundColor: "{colors.primary-hover}"
  button-accent-pressed:
    backgroundColor: "{colors.primary-press}"
  checkpoint-chip:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "4px 10px 6px"
  checkpoint-chip-hover:
    backgroundColor: "{colors.control-hover}"
  infobar-warn:
    backgroundColor: "{colors.bar-warn}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "12px"
  infobar-info:
    backgroundColor: "{colors.bar-info}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "12px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  journal:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  journal-row:
    padding: "6px 12px"
  segmented:
    backgroundColor: "{colors.mica-recessed}"
    rounded: "{rounded.sm}"
    padding: "2px"
  footer:
    backgroundColor: "{colors.mica-recessed}"
    padding: "10px 16px"
  text-field:
    backgroundColor: "{colors.control}"
    rounded: "{rounded.sm}"
    height: "32px"
    padding: "0 10px"
---

# Design System: GSVmulti-Brücke (Windows-App)

Stand der Ablage: Das ausgelieferte Artefakt ist der freigegebene HTML-Mock
(`docs/superpowers/specs/2026-11-06-windows-bruecke-mock/mock.html`) samt
Qt-Umsetzungsnotiz im README; Quelle der Werte sind dessen Custom Properties und
Selektoren, belegt durch die Bilder `bx1-*.png`. Unter
`windows/bridge/src/dispread_bridge_app/ui` liegt zum Zeitpunkt dieser Ablage
kein Qt-Code. Weicht die spätere Qt-Umsetzung ab, gilt der Bau und dieses
Dokument wird nachgezogen.

## Overview

**Creative North Star: "Das Fahrtenbuch am Rand"**

Ein schmales Fenster, das neben GSVmulti stehen bleibt und zweierlei sagt: oben
in einem Satz, was jetzt gilt, darunter als Journal, was passiert ist, während
niemand hinsah. Die Gestaltung ist Windows 11 Fluent nativ: Mica-Grund,
Karten mit 1-px-Rand, Segoe UI Variable, Systemakzent. Sie tritt hinter die
Aussage zurück; sie soll aussehen wie ein Teil von Windows, nicht wie ein
Messgerät.

Dichte: kompakt (Standard 440 × 720, Minimum 380 × 560), 4-px-Raster, wenig
Ebenen. Vertrauen kommt aus Wahrheitsregeln, nicht aus Dekoration: Die App ist
ein Verbindungswerkzeug, keine Messfreigabe, und trennt deshalb sechs
Prüfpunkte, statt eine große Ampel zu zeigen. Bestätigte Ablehnung: keine
dunkle Werkbank-HMI-Optik und keine Ampel-plus-Verbinden-Knopf-Kategorie.

**Key Characteristics:**
- Hell und dunkel folgen dem Windows-Farbschema; Akzent ist der Systemakzent.
- Zustand immer als Symbol plus Wort, nie nur Farbe.
- Sechs Prüfpunkte als 3 × 2-Raster (bewusste Abweichung von der Einzeile des Direction Contracts, siehe Chips).
- Ereignisjournal mit Tabellenziffern und Störungsdauer als Signatur.
- Feste DUT-Sperrzeile in jedem Zustand.

## Colors

Neutral-graue Fluent-Flächen mit einem einzigen Akzent; Farbe trägt sonst nur
Statusstufen, und Grün ist knapp gehalten. Alle Werte stehen in der Frontmatter;
Dunkelvarianten tragen das Suffix `-dark`.

### Primary
- **Systemakzent** (`primary` #005fb8 hell, `primary-dark` #60cdff dunkel): Primäraktion der InfoBar und des Schritts, Auswahl (aktives Segment als 2-px-Unterstrich, geöffneter Chip als Rand), Fokus bei Eingabefeldern (2-px-Unterstrich), Fortschrittsbalken. Die Mock-Werte sind Platzhalter; zur Laufzeit ersetzt `QPalette.Highlight` sie, mit `on-primary` als Textfarbe.

### Neutral
- **Mica** (`mica` #f3f3f3 / `mica-dark` #202020): Fensterfläche.
- **Mica vertieft** (`mica-recessed` #ededed / #1b1b1b): Fußleiste, Segmentgrund, Dialogfuß.
- **Karte** (`card` #fbfbfb / #2b2b2b): Karten, Journal, Chips, Flyouts.
- **Kartenrand** (`stroke` #e5e5e5 / #3a3a3a): 1-px-Rand und Trennlinien.
- **Bedienrand** (`stroke-strong` #8a8a8a / #9a9a9a): Radio, Checkbox, Ablagefläche; Kontrast ≥ 3 : 1.
- **Schaltfläche** (`control`, `-hover`, `-press`, `control-stroke`): Standardschaltflächen.
- **Text** (`text` #1a1a1a / #ffffff), **Text sekundär** (`text-secondary` #5d5d5d / #cfcfcf, hell ≈ 6,0 : 1, dunkel ≈ 11 : 1), **Text deaktiviert** (`text-disabled`).

### Status
- **Erfolg** (`ok` #0f7b0f / #6ccb5f), **Achtung** (`warn` #9d5d00 / #fce100), **Fehler** (`err` #c42b1c / #ff99a4), **Info/neutral** (`info` #5d5d5d / #cfcfcf, ausdrücklich kein Akzent).
- InfoBar-Töne `bar-ok`, `bar-warn`, `bar-err`, `bar-info` (letzter mit Rand `stroke`, die anderen randlos).

### Named Rules
**The Proven-Green Rule.** Grün (`ok`, `bar-ok`) steht nur für einen belegten Zustand: Komponenten installiert, Pi verbunden, Identität geprüft, Weitergabe vom COM-Treiber angenommen (nur Demo und das künftige B1x), Empfang belegt nach Testdateivergleich. Ein gesperrter, unbestätigter oder nur behaupteter Zustand wird nie grün; „Ausgabe“ bleibt Achtung, solange die DUT-Sperre gilt.

**The One Accent Rule.** Der Akzent markiert Primäraktion, Auswahl und Fokus und nie einen Zustand. Zustandsfarben tragen Status, der Akzent trägt Handlung.

**The Word-Beside-Color Rule.** Jede Statusfarbe steht mit Symbol und sichtbarem Wort; das Symbol bekommt zusätzlich einen Screenreader-Namen („Erfolg:“, „Achtung:“).

## Typography

**Font:** Segoe UI Variable Text (Rückfall Segoe UI, dann Systemschrift). **Daten:** Cascadia Mono / Consolas.

**Character:** Die Systemschrift von Windows, in wenigen Stufen. Kein Display-Schnitt in Bedienelementen; Zahlen stehen in Tabellenziffern.

### Hierarchy
- **Untertitel** (600, 20/28 px, Qt 15 pt): Pi-Anzeigename im Kopf, Dialogtitel. Der Weg („· Netzwerk (LAN)“) folgt im Kopf in Text 14/20, sekundär.
- **Text** (400, 14/20 px, Qt 10,5 pt): Fließtext, Journaltitel, Schaltflächen.
- **Text stark** (600, 14/20): Zustandssatz, InfoBar-Titel, Kartenüberschrift.
- **Beschriftung** (400, 12/16, Qt 9 pt): Chip-Name, Zweitzeile, Journalzeit, Version.
- **Beschriftung stark** (600, 12/16): Chip-Statuswort, Störungsdauer.
- **Daten** (Mono, 12/18): Fingerabdruck, Pi-ID, Endpunkt, Dateinamen; Fingerabdruck in Kleinbuchstaben-Hex, Vierergruppen, 4 Gruppen je Zeile, nie gekürzt.

### Named Rules
**The Tabular Rule.** Zeiten, Dauern, Zähler und Zeilenzahlen nutzen Tabellenziffern (`tnum`), damit die Zeitspalte des Journals bündig läuft.

## Layout

Ein einspaltiges Kompaktfenster, 4-px-Raster (4 / 8 / 12 / 16 / 20). Außenrand 16, Karteninnenrand 12 bis 14, Abstand zwischen Karten 12, Chip-Lücke 8, Journalzeile 6 oben und unten, 12 seitlich. Betrieb von oben nach unten: Kopf (Name · Weg, Pi-Wechsel-Symbol rechts), Zustandssatz, feste DUT-Sperrzeile, InfoBar, Chip-Raster, Segmented „Alle | Störungen“ mit Eintragszahl, Journal (scrollt, flexibel), Fuß mit „Diagnose exportieren“, „Details“ und Version. Die Einrichtung ersetzt im selben Fenster den Inhalt durch einen Schrittkopf 1 bis 5 unter derselben Kopfzeile; der Inhalt scrollt, der Fuß bleibt.

Bei 380 × 560 schrumpft nur das Journal (Mindesthöhe 150); Kopf und Chips bleiben. Skalierung 100 bis 200 % ohne Abschneiden, lange Namen brechen um, der volle Name steht im Tooltip; keine festen Pixelhöhen für Text. Tab-Reihenfolge Betrieb: Pi-Wechsel, sechs Chips, Segmented, Journal, „Diagnose exportieren“, „Details“.

## Elevation & Depth

Tonale Schichtung, flach im Ruhezustand: Mica, darauf Karten mit 1-px-Rand, Fußleiste vertieft. Schatten haben nur schwebende Ebenen: Flyout und Dialog (`0 8px 16px rgba(0,0,0,.14), 0 0 2px rgba(0,0,0,.2)` hell, 50 % Schwarz dunkel). Das Fenster selbst nutzt den Systemschatten, in der Qt-Umsetzung den nativen Rahmen. Hinter dem Dialog liegt ein Scrim (30 % hell, 50 % dunkel). Keine Verläufe.

### Named Rules
**The Flat-Until-Floating Rule.** Karten, Chips und InfoBars tragen Rand statt Schatten; Schatten gibt es nur für Flyout und Dialog.

## Shapes

Zwei Radien: 4 px für Schaltfläche, Chip, InfoBar, Eingabefeld, Segmente und Abzeichen; 8 px für Karte, Journal, Flyout, Dialog, Fenster. Kreise nur für Radio und Schrittpunkte. Ränder sind 1 px; Fokus ist ein doppelter Rahmen (2 px `focus-outer`, innen 1 px `focus-inner`, hell schwarz/weiß, dunkel weiß/schwarz), innerhalb der Widgetfläche gezeichnet, damit Scrollbereiche nichts abschneiden. Eingabefelder zeigen stattdessen einen 2-px-Akzent-Unterstrich. Hochkontrast übernimmt die Systempalette ohne feste Hex-Werte, die Karten behalten ihren 1-px-Rand in `WindowText`. Bewegung: nur 150 ms für Hover und Zustandswechsel, bei „Animationseffekte aus“ ohne Übergang.

## Components

### Buttons
- **Shape:** 4 px, 32 px hoch, Polster 4 / 12, Symbol 16 px optional.
- **Standard:** `control` mit Rand `control-stroke`; Hover `control-hover`, gedrückt `control-press` mit sekundärem Text; deaktiviert auf `mica-recessed` mit `text-disabled`.
- **Akzent:** `primary` mit `on-primary`, Semibold; genau einer je InfoBar oder Schritt, rechts.

### Infobar
- Eine nächste Aktion, höchstens zwei Knöpfe, Primäraktion rechts; Titel Text stark, Symbol links in 20-px-Spalte. Töne `warn`, `err`, `ok`, `info`. Kein weiteres Pop-up bei Wiederholung; Zustand aktualisieren, „Erneut versuchen“/„Abbrechen“ anbieten. Eine erzeugte Sessiondatei (E4ok) ist `info`, nicht `ok`.

### Prüfpunkt-Chips
- **Raster:** 3 × 2, bewusste Abweichung vom Direction Contract (eine Zeile): sechs Chips mit Statuswort und Unterzeile passen bei 440 px nicht in eine Zeile, ohne Wörter zu kürzen. Reihenfolge: Komponenten, UART, Pi / Ausgabe, Weitergabe, GSVmulti. Chips einer Reihe sind gleich hoch.
- **Aufbau:** Name (Beschriftung, sekundär), Symbol + Statuswort (Beschriftung stark), optionale Zweitzeile. Nicht benutzte Prüfpunkte tragen ein Strich-Symbol und Wort ohne Fettung („nicht benutzt“).
- **Zustand:** Hover `control-hover`; geöffnet = 1-px-Akzentrand und Detail-Flyout (Karte, Radius 8), schließt bei Esc und Klick außerhalb, Fokus kehrt zum Chip zurück.

### Wahrheitsregeln der Aussagen (tragend)
- **Weitergabe ist nicht Empfang.** „Weitergabe bestätigt“ und „vom Port angenommen“ heißen ausschließlich, dass der COM-Treiber geschrieben hat; sie erscheinen nur in der Demo (als „Demo-Werte“ gekennzeichnet) und im künftigen, nicht erreichbaren Zustand B1x. Im Normalzustand unter DUT-Sperre steht der Chip neutral: „Keine Weitergabe“ / „DUT-Ausgabe gesperrt“.
- **GSVmulti-Chip:** Nach Bedienerbestätigung nur `info` mit „Übernahme bestätigt“ und Zweitzeile „Empfang nicht nachgewiesen“. „Empfang belegt“ in Grün erscheint erst nach dem Empfangstest mit Vergleich gegen die Originaltestdatei, mit Zweitzeile wie „Test 14:02 (Demo), 600/600“, und gilt nur für genau diese Konfiguration. Weichen Werte ab (598/600), bleibt es kein Beleg.
- **Ausgabe-Chip:** `warn` „DUT gesperrt“, solange der Pi die Sperre meldet; geht der Pi verloren, bleibt der zuletzt gemeldete Stand stehen, der Chip meldet „Unbekannt“.
- **Zustandssatz** wiederholt die Sperre nicht und nennt keine Messfreigabe; die Brücke gibt keine Messwerte frei.

### DUT-Sperrzeile
- Feste Zeile unter dem Zustandssatz in jedem Fenster-Zustand, Einrichtung eingeschlossen: Achtungs-Symbol (`warn`), Beschriftung 12/16, Text „DUT-Ausgabe gesperrt – die Brücke gibt keine Messwerte frei“. Sie verschwindet nur im künftigen B1x, wo „Ausgabe freigegeben am …“ sie ersetzt. Sie ist nicht schließbar und nicht an eine Farbe allein gebunden.
- Das Schloss rechts im Kopf bedeutet „Pi-Wechsel gesperrt“, nicht DUT-Sperre; es bleibt fokussierbar und nennt den Grund.

### Segmented
- „Alle | Störungen“, 28 px hoch, Grund `mica-recessed`; aktives Segment `card` mit Rand und 2-px-Akzent-Unterstrich, Pfeiltasten wechseln. Rechts die Eintragszahl in Beschriftung.

### Ereignisjournal (Signatur)
- **Aufbau:** Karte Radius 8, Gruppenköpfe „Heute“ / „Gestern“ (Beschriftung stark, sticky). Zeile: Zeit (58 px, Tabellenziffern, sekundär) · Symbol 16 px · Titel mit Zweitzeile · Dauer rechts.
- **Störungen:** Titel nennt die Störung, die Dauer steht rechts in Beschriftung stark („4 s“), die Zweitzeile den Ausgang („wieder verbunden · …“ bzw. „läuft noch · …“), ohne Doppelung.
- **Zeilentrenner** 1 px `stroke`; Journal gehört zum gewählten Pi; leer: zentrierter sekundärer Text. Bereich ist fokussierbar und scrollt mit Pfeiltasten.

### Schrittkopf, Karten, Felder
- Fünf Schritte (erledigt: gefüllt `text`; aktuell: `primary`; offen: Rand `stroke-strong`), Punkt 24 px. Karten Radius 8, Rand `stroke`, Polster 12/14. Eingabefeld 32 px, Unterstrich-Fokus. Radio und Kontrollkästchen 20 px, Auswahl im Akzent. Ablagefläche gestrichelter `stroke-strong`-Rand, bei Zug durchgezogen im Akzent. Fortschritt 4 px hoch, Text in separater Zeile. Abzeichen („Unbestätigt“, „Synthetisch“): 12/16, Rand, Radius 4.

### Dialog und Tray
- ContentDialog über Scrim, max. 360 px, Radius 8, Fuß `mica-recessed`; Standard- und Esc-Taste ist die ungefährliche Wahl („Weiter übertragen“). Tray-Symbol in drei Varianten (normal, Achtung, Fehler als 10-px-Badge), Tooltip = Zustandssatz; der einmalige Hinweis erscheint nur beim ersten Minimieren.

## Do's and Don'ts

### Do:
- **Do** Statusfarbe immer mit Symbol und Wort zeigen; Kontrast Text ≥ 4,5 : 1 in hell und dunkel.
- **Do** Grün nur für belegte Zustände; „Empfang belegt“ nur nach Testdateivergleich, „Weitergabe“ nur als COM-Treiber-Aussage.
- **Do** die DUT-Sperrzeile in jedem Zustand zeigen, solange der Pi sie meldet.
- **Do** pro InfoBar genau eine nächste Aktion, Primäraktion rechts.
- **Do** Systemakzent und Windows-Farbschema übernehmen; Hochkontrast aus der Systempalette.
- **Do** Zeiten und Dauern in Tabellenziffern setzen.

### Don't:
- **Don't** pauschal grün anzeigen oder „Verbunden“ als „Freigegeben“ lesen lassen; die App erteilt keine Messfreigabe.
- **Don't** die Sperre im Zustandssatz doppeln oder hinter einen Klick legen.
- **Don't** einen erzeugten oder bestätigten Zwischenschritt (E4ok, GSVmulti nach Bedienerbestätigung) grün tönen.
- **Don't** wiederholte Timeout-Pop-ups, Verläufe oder Schatten auf Karten.
- **Don't** den Akzent als Statusfarbe benutzen oder Markenfarben erfinden (keine ME-Systeme-Vorgaben vorhanden).
- **Don't** den Mock-Rahmen (dunkles Steuerpanel, Mono-Großschrift-Kopfzeilen, Fußzeile „Mock – synthetische Daten“, Desktop-Vorschau) in die App übernehmen; er gehört nicht zum System.
