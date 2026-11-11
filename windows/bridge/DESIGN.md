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
  mica: "#eeeeee"
  mica-recessed: "#e6e6e6"
  card: "#ffffff"
  stroke: "#e0e0e0"
  ok-icon: "#107c10"
  warn-icon: "#c27c00"
  err-icon: "#d13438"
  select: "#f0f6fc"
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
  section:
    fontFamily: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: "20px"
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

Stand: Qt-Umsetzung unter `windows/bridge/src/dispread_bridge_app/ui` nach UX2
(Spec `docs/superpowers/specs/2026-11-11-windows-bruecke-ux2.md`, Runden UI-1 und
UI-2). Ursprung ist der freigegebene HTML-Mock
(`docs/superpowers/specs/2026-11-06-windows-bruecke-mock/mock.html`); wo der Bau
abweicht, gilt der Bau. Die Abschnitte „UX2-Bausteine“ und „Bewegung“ unten
beschreiben, was gegenüber dem Mock neu ist.

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
- Sechs Prüfpunkte als 3 × 2-Raster (bewusste Abweichung von der Einzeile des Direction Contracts, siehe Kacheln).
- Ereignisjournal mit Tabellenziffern und Störungsdauer als Signatur.
- Feste DUT-Sperrzeile in jedem Zustand.

## Colors

Neutral-graue Fluent-Flächen mit einem einzigen Akzent; Farbe trägt sonst nur
Statusstufen, und Grün ist knapp gehalten. Alle Werte stehen in der Frontmatter;
Dunkelvarianten tragen das Suffix `-dark`.

### Primary
- **Systemakzent** (`primary` #005fb8 hell, `primary-dark` #60cdff dunkel): Primäraktion der InfoBar und des Schritts, Auswahl (aktives Segment als 2-px-Unterstrich, geöffnete Kachel und gewählte Karte als Rand), Fokus bei Eingabefeldern (2-px-Unterstrich), Fortschrittsbalken. Die Mock-Werte sind Platzhalter; zur Laufzeit ersetzt `QPalette.Highlight` sie, mit `on-primary` als Textfarbe.

### Neutral
- **Mica** (`mica` #f3f3f3 / `mica-dark` #202020): Fensterfläche.
- **Mica vertieft** (`mica-recessed` #ededed / #1b1b1b): Fußleiste, Segmentgrund, Dialogfuß.
- **Karte** (`card` #fbfbfb / #2b2b2b): Karten, Journal, Kacheln, Werkzeugfenster-Inhalt.
- **Kartenrand** (`stroke` #e5e5e5 / #3a3a3a): 1-px-Rand und Trennlinien.
- **Bedienrand** (`stroke-strong` #8a8a8a / #9a9a9a): Radio, Checkbox, Ablagefläche; Kontrast ≥ 3 : 1.
- **Schaltfläche** (`control`, `-hover`, `-press`, `control-stroke`): Standardschaltflächen.
- **Text** (`text` #1a1a1a / #ffffff), **Text sekundär** (`text-secondary` #5d5d5d / #cfcfcf, hell ≈ 6,0 : 1, dunkel ≈ 11 : 1), **Text deaktiviert** (`text-disabled`).

### Status
Statussymbole (Grafik, ≥ 3:1) tragen in Hell eigene Tokens `ok-icon`, `warn-icon`, `err-icon`; Statuswörter bleiben in den dunkleren Textfarben `ok`/`warn`/`err` (≥ 4,5:1). In Dunkel sind beide gleich. Ebenen im Hellen: Karte `#ffffff` auf Grund `#eeeeee`, Wertfelder und vertiefter Grund bleiben sichtbar grau. Ausgewählte Karten (Moduswahl, Auswahlboxen, geöffnete Kachel) tragen einen zarten Akzentton (`select`, ≈ 6 % Akzent auf Weiß) plus Akzentrand. Der Kopfbereich steht direkt auf dem Grund, Inhalte liegen auf Karten. Darstellung: Automatisch/Hell/Dunkel in den Einstellungen (erster Abschnitt). Kontrollkästchen und Bildlaufleisten sind vollständig aus den Tokens gestylt.
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
- **Titel** (600, 20/28 px, Qt 15 pt): Pi-Anzeigename im Kopf, Titel im Fensterinhalt. Der Weg steht nicht mehr als Text im Kopf, sondern im Moduswahl-Knopf rechts.
- **Abschnitt** (600, 15/20 px, Qt 11 pt): Überschriften in Werkzeugfenstern (Einstellungen, Moduswahl, Detailfenster). Keine Kicker darüber.
- **Text** (400, 14/20 px, Qt 10,5 pt): Fließtext, Journaltitel, Schaltflächen.
- **Text stark** (600, 14/20): Zustandssatz, InfoBar-Titel, Kartenüberschrift.
- **Beschriftung** (400, 12/16, Qt 9 pt): Kachel-Name, Feldnamen, Zweitzeile, Journalzeit, Version.
- **Beschriftung stark** (600, 12/16): Kachel-Statuswort, Störungsdauer, Prüfmeldung.
- **Daten** (Mono, 12/18): Fingerabdruck, Pi-ID, Endpunkt, Dateinamen; Fingerabdruck in Kleinbuchstaben-Hex, Vierergruppen, 4 Gruppen je Zeile, nie gekürzt.

### Named Rules
**The Tabular Rule.** Zeiten, Dauern, Zähler und Zeilenzahlen nutzen Tabellenziffern (`tnum`), damit die Zeitspalte des Journals bündig läuft.

## Layout

Ein einspaltiges Kompaktfenster, 4-px-Raster (4 / 8 / 12 / 16 / 20). Außenrand 16, Karteninnenrand 12 bis 14, Abstand zwischen Karten 12, Kachel-Lücke 6/8, Journalzeile 6 oben und unten, 12 seitlich. Betrieb von oben nach unten: Kopf (Pi-Name, rechts Moduswahl-Knopf, Pi-Wechsel, Schloss), Herzschlag + Zustandssatz, feste DUT-Sperrzeile, InfoBar, Kachel-Raster, Segmented „Alle | Störungen“ mit Eintragszahl, Journal (scrollt, flexibel), Symbolleiste. Die Einrichtung ersetzt im selben Fenster den Inhalt durch einen Schrittkopf (Brückenwege 5 Schritte, „UART direkt“ 4 Schritte: Adapter · Verdrahtung · Session · Fertig) unter derselben Kopfzeile; rechts neben dem Leitsatz steht „Einrichtung verlassen“ (`dismiss`), wenn der Controller es erlaubt. Der Inhalt scrollt, der Fuß bleibt.

Bei 380 × 560 schrumpft nur das Journal (Mindesthöhe 150); Kopf und Kacheln bleiben, reicht die Höhe nicht, scrollt der Kopfbereich. Skalierung 100 bis 200 % ohne Abschneiden, lange Namen brechen um, der volle Name steht im Tooltip; keine festen Pixelhöhen für Text. Tab-Reihenfolge Betrieb: Moduswahl, Pi-Wechsel, Schloss, InfoBar-Knöpfe, sechs Kacheln, Segmented, Journal, Symbolleiste.

## Elevation & Depth

Tonale Schichtung, flach im Ruhezustand: Mica, darauf Karten mit 1-px-Rand, Symbolleiste vertieft. Schatten haben nur schwebende Ebenen: Werkzeugfenster (nativ) und Dialog (`0 8px 16px rgba(0,0,0,.14), 0 0 2px rgba(0,0,0,.2)` hell, 50 % Schwarz dunkel). Das Fenster selbst nutzt den Systemschatten, in der Qt-Umsetzung den nativen Rahmen. Hinter dem Dialog liegt ein Scrim (30 % hell, 50 % dunkel). Keine Verläufe.

### Named Rules
**The Flat-Until-Floating Rule.** Karten, Kacheln und InfoBars tragen Rand statt Schatten. Werkzeugfenster haben den nativen Windows-Rahmen und dessen Schatten, keinen eigenen.

## Shapes

Zwei Radien: 4 px für Schaltfläche, Kachel, InfoBar, Eingabefeld, Segmente und Abzeichen; 8 px für Karte, Journal, Dialog, Fenster. Kreise nur für Radio und Schrittpunkte. Ränder sind 1 px; Fokus ist ein doppelter Rahmen (2 px `focus-outer`, innen 1 px `focus-inner`, hell schwarz/weiß, dunkel weiß/schwarz), innerhalb der Widgetfläche gezeichnet, damit Scrollbereiche nichts abschneiden. Eingabefelder zeigen stattdessen einen 2-px-Akzent-Unterstrich. Hochkontrast übernimmt die Systempalette ohne feste Hex-Werte, die Karten behalten ihren 1-px-Rand in `WindowText`. Bewegung: siehe Abschnitt „Bewegung“.

## Components

### Buttons
- **Shape:** 4 px, 32 px hoch, Polster 4 / 12, Symbol 16 px optional.
- **Standard:** `control` mit Rand `control-stroke`; Hover `control-hover`, gedrückt `control-press` mit sekundärem Text; deaktiviert auf `mica-recessed` mit `text-disabled`.
- **Akzent:** `primary` mit `on-primary`, Semibold; genau einer je InfoBar oder Schritt, rechts.

### Infobar
- Eine nächste Aktion, höchstens zwei Knöpfe, Primäraktion rechts; Titel Text stark, Symbol links in 20-px-Spalte. Töne `warn`, `err`, `ok`, `info`. Kein weiteres Pop-up bei Wiederholung; Zustand aktualisieren, „Erneut versuchen“/„Abbrechen“ anbieten. Eine erzeugte Sessiondatei (E4ok) ist `info`, nicht `ok`.

### Prüfpunkt-Kacheln (bisher Chips)
- **Raster:** 3 × 2, bewusste Abweichung vom Direction Contract (eine Zeile): sechs Kacheln mit Statuswort und Unterzeile passen bei 440 px nicht in eine Zeile, ohne Wörter zu kürzen. Reihenfolge: Komponenten, UART, Pi / Ausgabe, Weitergabe, GSVmulti. Kacheln einer Reihe sind gleich hoch.
- **Aufbau:** erste Zeile Komponenten-Symbol (16 px, `text2`) + Name (Beschriftung, sekundär) + rechts Info-Symbol (Tooltip aus `CHIP_HELP`: was der Prüfpunkt bedeutet und was nicht). Passt ein Name dort nicht (echter Platzmangel, z. B. 380 px), stehen die Namen aller sechs Kacheln in eigener Zeile. Darunter Statussymbol + Statuswort (Beschriftung stark), optionale Zweitzeile; lange Wörter bekommen nur bei Platzmangel weiche Trennstellen.
- **Zustand:** Hover `control-hover`; geöffnet = 1-px-Akzentrand, solange das Detailfenster offen ist. Echter Zustandswechsel: 200-ms-Farbübergang aus dem Ton der neuen Stufe zurück zur Kartenfläche, nie beim bloßen Neuzeichnen.

### Wahrheitsregeln der Aussagen (tragend)
- **Weitergabe ist nicht Empfang.** „Weitergabe bestätigt“ und „vom Port angenommen“ heißen ausschließlich, dass der COM-Treiber geschrieben hat; sie erscheinen nur in der Demo (als „Demo-Werte“ gekennzeichnet) und im künftigen, nicht erreichbaren Zustand B1x. Im Normalzustand unter DUT-Sperre steht die Kachel neutral: „Keine Weitergabe“ / „DUT-Ausgabe gesperrt“.
- **GSVmulti-Kachel:** Nach Bedienerbestätigung nur `info` mit „Übernahme bestätigt“ und Zweitzeile „Empfang nicht nachgewiesen“. „Empfang belegt“ in Grün erscheint erst nach dem Empfangstest mit Vergleich gegen die Originaltestdatei, mit Zweitzeile wie „Test 14:02 (Demo), 600/600“, und gilt nur für genau diese Konfiguration. Weichen Werte ab (598/600), bleibt es kein Beleg.
- **Ausgabe-Kachel:** `warn` „DUT gesperrt“, solange der Pi die Sperre meldet; geht der Pi verloren, bleibt der zuletzt gemeldete Stand stehen, die Kachel meldet „Unbekannt“.
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

### UX2-Bausteine
- **Symbolknopf** (`IconButton`): 32 × 32, flach, Hover `control-hover`, Fluent-Symbol 20 px (16 px in Feldern). Tooltip und Screenreader-Name sind Pflicht. Symbole kommen ausschließlich aus Fluent UI System Icons (eingebettete SVGs, gefärbt aus den Tokens); keine Unicode-Zeichen oder Emoji.
- **Symbolleiste** statt Fußleiste: links Einstellungen (`settings`), Protokolle exportieren (`document_arrow_down`), Info (`info`); rechts Version (Beschriftung) und Beenden (`power`). Grund `mica-recessed`, Rand oben `stroke`.
- **Moduswahl-Knopf** im Kopf: Symbol des Wegs, Kurzname („Netzwerk“, „UART · Brücke“, „UART direkt“), Chevron; öffnet das Moduswahl-Fenster.
- **Werkzeugfenster** (`ToolWindow`) statt Flyout: nicht modal, nativer Rahmen, Besitzer = Hauptfenster, Esc schließt, Position je Art für die Laufzeit gemerkt, höchstens eine Instanz je Art, Inhalt scrollt, Mindestbreite 360. Arten: Kachel-Details, Schloss, gekoppelte Pi, Info, Protokolle exportieren, Moduswahl, Einstellungen. Fenster-Fuß `mica-recessed`; nach erfolgreichem Speichern wandert der Akzent auf „Schließen“.
- **Moduswahl:** drei Karten untereinander (Radio-Semantik, Pfeiltasten), je Symbol, Name, ein Satz Erklärung (Raten aus dem Kontext), Statuszeile mit Symbol + Wort. Gewählte Karte 1-px-Akzentrand; aktiver Weg trägt das Abzeichen „Aktiv“ (Rand + Text, nie grün). Nicht wählbare Karten: Name sekundär, Schloss + Grund in lesbarem Kontrast. Fuß „Abbrechen“ / „Wechseln“ (Akzent).
- **Einstellungen (Runde 3):** Abschnitte Allgemein (Autostart, Darstellung System/Hell/Dunkel als Segmented, lokal per QSettings, wirkt sofort) · Pi · Ports · GSVmulti-Session · Protokolle · Über; kein Abschnitt „Weg“ (der Weg wird nur über den Knopf im Kopf gewählt, „Einrichtung erneut durchlaufen“ steht in der Moduswahl). Während einer Übertragung steht oben das Abzeichen „schreibgeschützt“ mit ⓘ; Werte bleiben als Wertfeld kopierbar. Endpunkt: schreibgeschütztes Wertfeld mit Stift-Symbolknopf, beim Bearbeiten wird er zum Haken „Bestätigen und speichern“ (gesperrt bei falschem Format), kein Textknopf. Portpaar prüft wie in der Einrichtung (gleicher Port, Nicht-Paar: err/warn, kein stilles Übernehmen). Übernehmen baut das Fenster nicht neu auf; die Bildlaufposition bleibt. Comboboxen reagieren nur mit Fokus auf das Mausrad.
- **Wertfeld (`ValueField`, R3-1):** Jeder veränderliche Wert (Port, Pfad, Baudrate, Frequenz, Pi-ID, Endpunkt, Fingerabdruck, Version, Zähler) steht in einem grauen Feld: Grund `field` (hell `mica-recessed`, dunkel `control`), Radius 4, Polster 3/8, Cascadia Mono 9 pt. Bezeichner darüber in `text2`. Kopieren per Klick auf das Feld, Enter/Leertaste oder das Kopiersymbol (nur bei Hover/Fokus sichtbar); danach 1,2 s `checkmark`. Sätze enthalten keine Werte. Leere Werte stehen in `text2` ohne Kopiersymbol.
- **ValidatedField (R3-4):** Zustand über Form: Rand des Feldes in `ok`/`warn`/`err` (1 px rundum, 2 px unten), darunter eine einzeilige Meldung mit Statussymbol **davor** (Wort + Symbol, nicht nur Farbe); Erklärung und Abhilfe im ⓘ hinter der Meldung. Der Ring wird durch das Ergebnissymbol erst nach seiner Mindestdauer ersetzt. Leer = kein Status; Tippen → 500 ms Ruhe → ProgressRing 16 px; Auswahl prüft sofort. `ok` (Häkchen in `ok`) nur nach bestandener echter Prüfung des angezeigten Werts; jede Änderung verwirft ältere Ergebnisse. Meldung zusätzlich als `accessibleDescription`. In den Einstellungen übernimmt eine bestandene Auswahlprüfung sofort, Text (Endpunkt) über „Übernehmen“; bestätigt wird mit „Gespeichert“.
- **Gespeichert:** Häkchen in `ok` + Beschriftung, blendet nach 2 s aus (Einrichtung unter dem Schrittkopf, Einstellungen am Feld).
- **Herzschlag:** 8-px-Punkt vor dem Zustandssatz, das einzige Zeichen davor (kein zweites Statussymbol). Er trägt den Zustand der Pi-Verbindung: `ok` (grün) nur bei authentifiziert verbundenem Pi ohne Störung, `warn` bei Achtung, `err` bei Fehler, hohl in `stroke-strong` ohne Verbindung. Tooltip „Kontakt zum Pi – sagt nichts über Weitergabe oder Empfang“; Puls je neuem `activity_seq`. Bei Aufbau und Backoff steht stattdessen ein ProgressRing. Proven-Green bleibt: grün nur bei belegter, authentifizierter Verbindung.
- **Session (R3-3):** Eine Ergebniszeile: neutrales Häkchen (erzeugt ist nicht abgenommen, nie grün), Pfad im Wertfeld, Symbolknöpfe „Ordner öffnen“ und „Neu erzeugen“. Darunter Abzeichen „nicht abgenommen“ und (Einkanal-Vorlage auf Brückenwegen) „Einkanal“, beide mit ⓘ; der F3-Wortlaut steht unverändert im ⓘ von „Einkanal“, auch im Detailfenster der GSVmulti-Kachel. Checkliste „In GSVmulti einstellen“: je Punkt Kontrollkästchen, kurzer Text, ⓘ. „Record Hidden Channels einschalten“ trägt das Abzeichen „Pflicht“ (nur bei ausgeblendeten Kanälen) und hält „Weiter“ zurück; „Autoscale Y für Kanal … aus“ ist Empfehlung; „Session in GSVmulti öffnen“ bestätigt die Einrichtung. Haken sind Bedienerangaben, kein Beleg.
- **Abzeichen (`Badge`, R3-2):** wiederkehrende Einschränkung als Umriss `stroke-strong`, 9 pt, Radius 4, nie grün, mit ⓘ für die Erklärung: „nicht abgenommen“, „Demo“, „Testfreigabe“, „kein Empfangsnachweis“ („Weitergabe ist nicht Empfang“ im ⓘ), „Einkanal“, „schreibgeschützt“, „Pflicht“. Im Betrieb stehen sie unter der Sperrzeile.
- **Textbudget (R3-2):** Karte, Infobar, Kachel höchstens ein kurzer Satz (≈ 70 Zeichen); Kachel-Zweitzeile höchstens drei Wörter oder ein Wert. Erklärungen stehen im ⓘ (Tooltip als Box, höchstens 320 px, 300 ms) oder im Detailfenster. Im Normalbetrieb (Lauf läuft, Ausgabe gesperrt) steht keine Infobar, die die Sperrzeile wiederholt; die Erklärung der Sperre steht im ⓘ der Sperrzeile.
- **Strecke „UART direkt“ (B-19):** Statt Kacheln ein Bild: USB-Adapter (steckt/fehlt) → Wertfeld mit dem Port → GSVmulti „liest direkt“.
- **Auswahlbox:** Bei Radio-Auswahlen (Adapterliste, Netzwerk/UART, Moduswahl) ist die ganze Box klickbar; Pfeiltasten wechseln die Moduskarten; Enter löst fokussierte Knöpfe, Symbolknöpfe und Kacheln aus, auch in Werkzeugfenstern.

### Bewegung
Nur wo sie Zustand erklärt, 150–250 ms, ease-out, Ausgang schneller als Eingang. Zentraler Schalter `theme.motion_enabled()` (Windows: „Animationseffekte“; `DISPREAD_UI_MOTION=0` für Tests). Aus = Endzustand sofort, Bedeutung bleibt.

| Ort | Bewegung |
| --- | --- |
| Herzschlag | Puls 250 ms je Pi-Kontakt |
| Verbindungsaufbau, Backoff, Prüfungen, Suche | ProgressRing (unbestimmt), Mindestanzeigedauer 400 ms |
| Export, Session ohne eigenen Platz | 2-px-Ladebalken unter dem Kopf |
| Kopieren, Prüfung ok, Gespeichert | Symbol mit 150 ms Skalierung; „Gespeichert“ blendet in 150 ms aus |
| Fenster öffnen | Systemanimation |

Runde 3: Kachel-Farbblitz, Überblendung Betrieb ↔ Einrichtung und Schrittübergang sind entfernt (sie flackerten); die Einrichtung baut bei einem Datenwechsel zwar Widgets neu auf, behält aber Eingabetext, Haken, Auswahl, Fokus und Bildlaufposition. Keine Dauerschleifen außer Ring/Ladebalken während echter Arbeit; versteckte Fenster stoppen ihre Animationen.

### Dialog und Tray
- Modal sind nur Bestätigungen, die die Übertragung beenden (Beenden, Trennen): max. 360 px, Radius 8, Fuß `mica-recessed`; Standard- und Esc-Taste ist die ungefährliche Wahl („Weiter übertragen“). Alles andere sind nicht modale Werkzeugfenster. Tray-Symbol in drei Varianten (normal, Achtung, Fehler als 10-px-Badge), Tooltip = Zustandssatz; der einmalige Hinweis erscheint nur beim ersten Minimieren.

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
