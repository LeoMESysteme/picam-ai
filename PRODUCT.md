# Product

<!-- impeccable:product-schema 1 -->

Geltungsbereich: das **Zensical-Wiki** (`docs-site/`, gebaut nach `site/`,
veröffentlicht unter https://picam-docs.pages.dev/) samt Projekt-Tour,
Roadmap-Karte und Fortschrittsseite. Die Bedieneroberfläche der Werkbank
(`dispread serve`, `/live`) bekommt später eine eigene PRODUCT.md unter
`src/dispread/workbench/`, sobald ihre Technik steht; bis dahin gilt diese
Datei nicht für sie.

## Platform

web

## Users

Das Wiki dient drei Lesergruppen, die in dieser Reihenfolge an Tiefe gewinnen:

1. **Neue Nutzer und Bediener im Kalibrierlabor.** Sie wollen das System
   einrichten und bedienen: Kamera und Anzeige in Betrieb nehmen, einen
   Messlauf fahren, Ergebnisse einordnen. Sie brauchen einen freundlichen
   Einstieg und sollen nicht von Codebeispielen, Funktionsnamen oder
   Entwicklungsdetails überflutet werden oder sich im Wiki verlieren.
2. **Fortgeschrittene Bediener.** Sie stellen speziellere Einstellungen und
   Konfigurationen ein und wollen verstehen, was im Hintergrund abläuft,
   wofür eine Konfiguration da ist und ob sie überhaupt etwas daran ändern
   sollten.
3. **Entwickler und Programmierer.** Der Projektautor selbst und künftig
   andere Entwickler, die Änderungen vornehmen. Sie brauchen genaue
   Erklärungen zu Pipelines, Bibliotheken und Schnittstellen und dazu, wo und
   wie sie anbinden oder weiterbauen können und dürfen (Beispiel: Unterstützung
   für ein anderes Protokoll oder einen neueren GSVmulti einbauen). Hier sind
   Codebeispiele wichtig.

Dazu kommen Kollegen und Vorgesetzte, die sich über Tour, Roadmap und Status
einen Überblick über Stand und Grenzen verschaffen.

## Product Purpose

picam-ai (Paket `dispread`) liest auf einem Raspberry Pi 5 mit einer Logitech
StreamCam die Anzeigen wechselnder Messverstärker optisch aus und überträgt
die Werte zeitgestempelt über eine serielle Schnittstelle an GSVmulti; Einsatz
im Kalibrierlabor, Prüfling und Referenz müssen zeitlich zuordenbar sein.

Das Wiki ist mit dem wachsenden Code nicht mehr nur Installationsanleitung,
sondern Begleiter über den ganzen Lebenszyklus: Einrichten, Bedienen,
Konfigurieren und Weiterentwickeln. Erfolg heißt: Ein neuer Nutzer findet
ohne Umwege den für ihn relevanten Weg, ein Bediener versteht die Wirkung
einer Einstellung, bevor er sie ändert, und ein Entwickler findet die
Anbindungsstelle samt Vertrag, ohne den Quelltext durchsuchen zu müssen.

## Positioning

Eine klassische CV-/OCR-Kette mit Regelprüfung, bedienergeführt. Große
Sprachmodelle oder generative KI sind im laufenden Messpfad ausdrücklich
nicht vorgesehen. Unlesbares wird abgelehnt statt geraten, veraltete Werte
werden nie unmarkiert weitergeführt, und Konfidenz ist keine
Fehlerwahrscheinlichkeit. Das Wiki benennt die belegten Grenzen offen statt
sie zu glätten.

## Operating Context

- Sprache durchgehend Deutsch; Zensical-Theme mit hellem, dunklem und
  System-Farbschema, Sofortnavigation (`navigation.instant`).
- Quellen sind die Markdown-Dateien des Repos: `docs/` als Baum plus die in
  `scripts/docs-site.sh` gelisteten Wurzeldateien; `docs-site/api/` ist
  eigens gepflegt. Gebaut wird immer über `./scripts/docs-site.sh`.
- Gliederung heute: Start, Projekt-Tour, Projekt, Lernpfad „Selbst
  programmieren", Vertiefung, Betrieb und Hardware, Messungen,
  Entscheidungen (OQs), API-Referenz, Für Agents.
- Vorhandene Interaktionen: Glossar- und Abschnittsvorschau beim Überfahren,
  erläuterte Codezeilen, API-Kurzerklärungen, OQ-Filter und -Suche,
  Roadmap als Karte mit innerer Ebene, Fortschrittsdiagramme aus Daten,
  Projekt-Tour als Anime.js-Bühne mit Werten aus `scripts/tour-facts.py`.
- Browsertests in `tests/docs-site.spec.ts`
  (`npx playwright test -c playwright.docs.config.ts`) sichern Verhalten,
  Kontrast, Fallbacks und Aufräumen bei Sofortnavigation.

## Capabilities and Constraints

- Das aktuelle Grunddesign des Zensical-Wikis bleibt erhalten. Es soll
  moderner und professioneller wirken, gewünscht sind mehr Informationen beim
  Überfahren (Pop-ups), mehr Animationen, Grafiken und dynamische Diagramme.
- Inhalte ohne JavaScript bleiben lesbar; interaktive Ansichten haben eine
  Quell- oder Textfassung, reduzierte Bewegung wird respektiert.
- Anime.js 4.5.0 liegt lokal unter `docs-site/assets/vendor/`; kein CDN.
- Zahlen in Szenen und Diagrammen stammen aus Code oder Datendateien, nicht
  aus Fließtext.
- Offen: die echte GSVmulti-Telegrammspezifikation (OQ-07); die reale Prüfung
  ist auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V begrenzt.

## Brand Commitments

Das bestehende Zensical-Grunddesign (Schrift, Theme, Navigation,
Statusfarben) ist verbindlich; Verbesserungen bauen darauf auf, statt es zu
ersetzen.

## Evidence on Hand

- Messzahlen: `docs/VALIDATION.md`, Deutung im `docs/lab_journal.md`,
  Zeitverhalten in `docs/TIMING.md`.
- Ernte- und Trainingsfortschritt: Datendateien der Fortschrittsseite
  (`docs-site/assets/data/`).
- Stand und Grenzen: `docs/status.md`, `docs/ROADMAP.md`,
  `docs/open-questions.md`, `docs/project_history.md`.
- Nicht vorhanden und nicht zu erfinden: Kundenstimmen, Abnahmen weiterer
  Gerätetypen, eine GSVmulti-Spezifikation, Zertifizierungen.

## Product Principles

1. **Der Weg folgt der Rolle.** Einsteiger sehen zuerst Einrichten und
   Bedienen; Konfigurationstiefe und Entwicklerdetails sind erreichbar, aber
   nicht im Weg.
2. **Erklären, bevor man ändern lässt.** Jede Einstellung sagt, wozu sie da
   ist, was im Hintergrund passiert und ob man sie überhaupt anfassen sollte.
3. **Anbindungsstellen sind dokumentierte Verträge.** Wer weiterbaut, findet
   Trennstellen, Schnittstellen und Grenzen dessen, was er ändern darf, mit
   Codebeispielen.
4. **Belegt statt behauptet.** Zahlen kommen aus Daten und Code, Grenzen
   stehen offen da, Unbekanntes bleibt als OQ sichtbar.
5. **Lebendig, aber nie auf Kosten des Lesens.** Interaktion und Bewegung
   machen Zusammenhänge sichtbar; der Text bleibt ohne sie vollständig.

## Accessibility & Inclusion

Bestehende, durch Tests gesicherte Praxis: ausreichender Textkontrast
(≥ 4,5 : 1) in beiden Themes, Tastaturbedienung der interaktiven Ansichten,
reduzierte Bewegung, schmale Ansichten ohne horizontales Scrollen und
Nutzung ohne JavaScript.
