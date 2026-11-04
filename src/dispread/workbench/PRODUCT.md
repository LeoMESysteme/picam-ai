# Product

<!-- impeccable:product-schema 1 -->

Geltungsbereich: die Werkbank-Seite `/live` von `dispread serve`
(`src/dispread/workbench/static/live/`). Die alte Seite `/` (Controller,
Datensätze, Terminals) und das Wiki (`PRODUCT.md` im Projektwurzel-
verzeichnis) gehören nicht dazu. Autoritativ für Daten, Wahrheitsregeln und
Schnittstellen ist die Spec
`docs/superpowers/specs/2026-11-04-werkbank-redesign-design.md`, für Aussehen
und Verhalten der freigegebene Mock daneben.

## Platform

web

## Users

1. **Laborbediener im Kalibrierlabor**, ohne CV-Wissen. Er steht im hell
   beleuchteten Labor am Aufbau (GSV-2AS, StreamCam auf Stativ, Raspberry
   Pi 5) und schaut auf einen Desktop-Monitor daneben, oft im Wechsel mit
   GSVmulti. Er richtet ein, prüft und bestätigt mit seinem Namen und startet
   dann einen Lauf, der Stunden dauern kann. Danach schaut er nur noch
   gelegentlich hin und muss jeden Störzustand auf einen Blick erkennen.
2. **Der Entwickler**, auf derselben Seite, auch über Tailscale. Er will
   Gründe, Kennzahlen und Rohbilder sehen; Diagnosen bleiben einen Klick
   tiefer erreichbar statt in der Hauptansicht.

## Product Purpose

Die Seite führt durch Einrichtung → Prüfen und Bestätigen → Lauf → Stopp und
zeigt dabei das Kamerabild als größtes Element mit einem deckungsgleichen
HUD. Erfolg heißt: Bediener kommen ohne Einweisung durch den Entwickler
zurecht, sehen jeden Einrichtungsschritt live mit Teilfortschritt, erkennen
Wechsel, Unlesbar, Nachführung verloren, Korrektur, Streamstillstand und
Verbindungsverlust ohne zu lesen, und keine Wahrheitsregel der alten Seite
wird schwächer.

## Positioning

Ein bedienergeführtes Machine-Vision-Werkzeug mit klassischer Regelprüfung,
keine KI-Oberfläche. Die Seite zeigt nur, was der Server entschieden hat:
Unlesbares wird abgelehnt statt geraten, Veraltetes ist nie Freigegeben, und
Konfidenz ist keine Fehlerwahrscheinlichkeit.

## Operating Context

* Desktop-Monitor im Labor, Maus und Tastatur. Zielbreite 1440 px, trägt von
  1280×800 bis 1920×1080. Keine Handy- oder Tablet-Bedienung.
* Helles Raumlicht; die Seite ist trotzdem nur dunkel, weil der Viewer ein
  Grafikfenster ist und eine helle Hülle das Kamerabild überstrahlen würde.
* Server: aiohttp über HTTPS mit Anmeldung und CSRF. `/live/status` alle
  500 ms, Bild und HUD aus `/live/preview.mjpg` (bis 15 fps, unter Last 5 fps;
  der Messpfad hat immer Vorrang).
* Ein Lauf dauert Stunden; die Seite muss nach einem Neuladen den Zustand
  wiederherstellen (`run.recent`, `run.counts`).

## Capabilities and Constraints

* Ohne Build: native ES-Module, Canvas 2D und SVG, keine JS-Bibliothek, kein
  CDN. Schriften Noto Sans und Noto Sans Mono (OFL) lokal unter
  `static/vendor/fonts/`.
* CSP bleibt `connect-src 'self'; img-src 'self' blob:`; keine Inline-Skripte.
* Die gesamte UI-Sprache ist Deutsch. Produkttexte aus `static/live.js`,
  `workbench/fields.py` und `tracking_advice.py` werden wörtlich übernommen.
* Statuswörter: Freigegeben VALID, Wechselt TRANSITION, Unlesbar UNREADABLE,
  Veraltet STALE.
* Offen (Spec): vorläufiger Live-Abgleich gegen die Referenz (OP-1); bis zur
  Entscheidung steht „Abgleich nach Laufende“.

## Brand Commitments

* Kategorie-Standard Machine-Vision-HMI auf dem Niveau von Cognex In-Sight
  und MVTec MERLIC (Richtung D, gewählt am 2026-10-31; Maßstab auch
  VisionPro und HALCON). Kein generischer Dark-Panel-Look.
* Die Tokens der Spec „Visuelle Welt“ gelten wörtlich: nur dunkel, Docks mit
  schmalen Titelleisten und 1-px-Linien, Radien höchstens 2 px, Schatten nur
  an Pop-ups, Menüs und Dialogen, Zustand als kleines Quadrat plus Wort.
* Teal (`--teal`) bedeutet nur „Korrektur läuft“, Magenta (`--mag`) nur
  Rahmenbereiche. Statusfarben tragen nur Bedeutung.

## Evidence on Hand

* Freigegebener Mock: `docs/superpowers/specs/2026-11-04-werkbank-redesign-mock/`
  (`mock.src.html`, Sprungmarken im README). Er ist eine Simulation, keine
  Messwerte.
* Echtes Standbild `img/still.jpg` aus `live-20261030T133635Z`; Fake-Szenen
  unter `tests/fixtures/live/scene-*.json` mit synthetischen Zeiten.
* Es gibt keine CPU-Kennzahl im Status; die Seite zeigt keine erfundenen
  Zahlen.

## Product Principles

1. **Wahrheitsregeln vor Gestaltung** (Spec „Wahrheitsregeln“): Ein Wert
   älter als 0,5 s oder ohne gültige Antwort seit 1,5 s ist Veraltet. Im
   Testlauf wird nichts freigegeben. Die Wertspur zeigt nur freigegebene
   Werte und glättet nie. Konfidenz heißt „Spur“ oder „Treffer“, nie
   „Wahrscheinlichkeit“. Bestätigen und Lauf starten nur über HTTPS mit CSRF;
   der Übungslauf sendet nie. Serverrückmeldungen (409/400) erscheinen
   wörtlich.
2. **Zeigen, wo das Problem ist**, nicht nur dass es eins gibt. Es läuft
   immer nur der Effekt mit dem höchsten Vorrang.
3. **Das Bild zuerst.** Der Viewer ist das größte Element; Diagnosen liegen
   einen Klick tiefer.
4. **Nichts erfinden.** Jede Zahl in einem Popover oder einer Zeile kommt aus
   dem Status oder dem X-Hud.

## Accessibility & Inclusion

* Bedienbar mit Tastatur: sichtbarer Fokus, Dialoge mit Fokusfalle, Esc
  schließt als „Weiter beobachten“, nie als Stopp.
* `prefers-reduced-motion` ersetzt Bewegung durch statische Markierung.
* Zustände nie nur über Farbe: Quadrat plus Wort.
