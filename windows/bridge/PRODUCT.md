# Product

<!-- impeccable:product-schema 1 -->

Geltungsbereich: die Windows-Anwendung der GSVmulti-Brücke (`windows/bridge/`,
Qt/PySide6, Setup-EXE). Werkbank `/live` und Wiki haben eigene PRODUCT.md.
Autoritativ für Funktion, Zustände und Grenzen ist die freigegebene Spec
`docs/superpowers/specs/2026-11-06-windows-bruecke-design.md`; für Aussehen
und Verhalten der Mock `docs/superpowers/specs/2026-11-06-windows-bruecke-mock/`.

## Platform

desktop (Windows 11 x64, Qt Widgets/PySide6; der Mock ist HTML)

## Users

1. **Laborbediener am GSVmulti-PC**, ohne IT-Wissen. Er installiert die App
   selbst (Nutzerentscheidung 06.11.2026), koppelt einen Pi, wählt UART oder
   Netzwerk, öffnet die erzeugte Session in GSVmulti und lässt das Fenster
   kompakt neben GSVmulti offen. Administratorrechte fragt die App nur, wenn
   Windows sie verlangt; fehlen sie, nennt sie „IT-Freigabe erforderlich“.
2. **Der Entwickler**, der Diagnose und Versionen braucht – eine Ebene tiefer
   („Details“, „Diagnose exportieren“).

## Product Purpose

Pi und GSVmulti ohne Python, COM-Zuordnung oder Konfigurationsdateien
verbinden. Erfolg heißt: ein Bediener kommt ohne Terminal von der Installation
bis zum Empfangstest, sieht danach jederzeit, welcher Teil der Strecke steht,
und erfährt bei jeder Störung die nächste sinnvolle Aktion.

## Positioning

Ein Verbindungswerkzeug, kein Messprogramm: Die App startet keine Messung,
bestätigt keinen Bildvorschlag und gibt keine Messwerte frei. Verbindung,
COM-Weitergabe und GSVmulti-Empfang sind drei verschiedene Aussagen.

## Operating Context

* Büro-/Labor-PC mit Windows 11, Maus und Tastatur, DPI 100–200 %.
* Fenster kompakt (Standard 440 × 720, min. 380 × 560) neben GSVmulti; Tray
  hält die Brücke beim Minimieren aktiv. Zweiter Start aktiviert das Fenster.
* Hell und dunkel folgen dem Windows-Farbschema; Akzent = Systemakzent.
* Deutsch, Tastaturbedienung, lange Gerätenamen gehören zur Abnahme.

## Capabilities and Constraints

* Qt Widgets mit Fluent-naher Gestaltung über Palette/QSS; keine Web-View.
* Widgets blockieren nie: Port- und Netzoperationen laufen im Kern.
* Keine wiederholten Timeout-Pop-ups; Zustand aktualisieren, Wiederholen/Abbrechen anbieten.
* Laufende Konfiguration ist schreibgeschützt; kein unbemerkter Wechsel
  UART↔Netzwerk oder auf einen anderen Pi.

## Brand Commitments

* Windows 11 nativ (Nutzerentscheidung 06.11.2026): Segoe UI Variable,
  Mica-Grund, Karten mit 1-px-Rand, Systemakzent. Keine dunkle Werkbank-HMI-Optik.
* Keine ME-Systeme-Markenvorgaben vorhanden – nichts erfinden.

## Evidence on Hand

* Spec §10 (Statuswörter je Prüfpunkt), §11 (Session), Plan W1–W4.
* Keine echten Screenshots von GSVmulti in der Doku; Beispielwerte im Mock sind synthetisch.

## Product Principles

1. **Nie pauschal grün.** Sechs Prüfpunkte getrennt: Komponenten, physischer
   UART, Pi, Ausgabe, Windows-Weitergabe, GSVmulti.
2. **Eine nächste Aktion.** Die Infoleiste nennt genau eine, mit höchstens zwei Knöpfen.
3. **Belegt statt behauptet.** „Empfang belegt“ nur nach Empfangstest gegen die
   Originaldatei; „Weitergabe bestätigt“ heißt nur COM-Treiber.
4. **Gesperrt bleibt sichtbar.** Solange die DUT-Ausgabe gesperrt ist, steht es da.

## Accessibility & Inclusion

Tastatur (Tab/Enter/Esc), sichtbarer Fokus, Zustand nie nur über Farbe
(Symbol + Wort), Kontrast ≥ 4,5 : 1 in hell und dunkel, Skalierung bis 200 %.
