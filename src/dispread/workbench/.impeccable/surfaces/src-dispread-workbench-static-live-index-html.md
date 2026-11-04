---
version: 1
slug: "src-dispread-workbench-static-live-index-html"
primary_target: "src/dispread/workbench/static/live/index.html"
related_targets: []
---

## Direction contract

THESIS: Die Werkbank ist ein Grafikfenster mit Werkzeugdocks, kein Dashboard. Das Kamerabild mit deckungsgleichem HUD ist das größte Element; jede Störung zeigt, *wo* sie ist. Verweigert wird der generische Dark-Panel-Look mit Karten, Pillen und Glüh-Akzenten.

OWN-WORLD: Kategorie-Standard Machine-Vision-HMI (Cognex In-Sight/VisionPro, MVTec MERLIC/HALCON), nur dunkel. Warme Grautöne `--bg0…--line2` der Spec, Docks mit 26-px-Titelleisten und 1-px-Linien, Radien ≤ 2 px, Schatten nur an Pop-up, Menü, Dialog. Zustand = Quadrat + Wort. Blau nur Auswahl/Primäraktion, Teal nur Korrektur, Magenta nur Rahmenbereiche. Noto Sans 13 px, Noto Sans Mono nur für Werte, tabular.

STORY: Der Laborbediener richtet ein, sieht jeden Schritt live, prüft, bestätigt mit Namen, startet einen stundenlangen Lauf und erkennt danach jeden Störzustand aus dem Augenwinkel. Der Entwickler findet Gründe und Kennzahlen einen Klick tiefer.

FIRST VIEWPORT: 1440×900. Titelleiste 40 px (Marke · Einrichtung › Lauf · Gerät, rechts die Kontextaktion als Primärknopf). Links 248 px Ablauf-Dock mit Schrittliste und Fakten-Fuß, Mitte Viewer-Werkzeugleiste, Grafikfenster und 118-px-Zeitleiste, rechts 368 px Ergebnis (nur Lauf) über Inspektor-Tabs, unten 24-px-Statusleiste.

FORM: Code-led, Mock `docs/superpowers/specs/2026-11-04-werkbank-redesign-mock/` als freigegebene Komposition (Richtung D, Position 1). seed:862d6e2d6a71d087

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
