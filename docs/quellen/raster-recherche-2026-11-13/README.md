# Rasterbestimmung `live-20261113T130253Z`: warum `keine_startlage` — Recherche

Stand 2026-11-13. Nur Analyse; am Repo nichts geändert. Versuche liefen auf einer Kopie von `src/` im
Scratchpad (`srcp/`), Skripte `r1.py` … `r7.py`, Ergebnislisten `reg_orig.jsonl`, `reg_fix.jsonl`, Bild `raster_new.png`.

## 1. Befund: zwei unabhängige Fehler, beide im Verfahren, nicht im Bild

Das richtige Raster liegt im neuen Bild praktisch dort, wo es in `121656Z` lag:
`[[731.7,364.4],[1400.5,374.9],[1405.4,454.1],[733.2,453.1]]`. `refine` aus dem alten Quad ohne Leerzellenregel
liefert genau dort einen Fit (156 Punkte, RMS 0,115 / 0,097). Mit Leerzellenregel: `leerzelle_belegt`.

### Fehler A — die Leerzellenregel verwirft das richtige Raster (alle drei Standbilder)

- Unter dem richtigen Raster gelten genau zwei Kandidaten als „in Leerzelle 8“: Quellpixel (1129, 410) und (1130, 438),
  Rasterspalte **5,46–5,49**, relative Tiefe 0,86 und 1,09–1,12.
- Das sind keine Zeichen in Zelle 8, sondern Randminima am linken Stamm des „m“ in Zelle 9 (`raster_new.png`).
  Die Zellgrenze liegt bei Spalte 5,5; die Kandidaten liegen 0,01–0,04 Spalten (unter 0,3 px) davor.
- Ursache im Code: `_evaluate_fit` zählt alles mit `local_x < _PITCH` zur Zelle (`dotlattice.py:407-413`), also
  auch die ganze Lückenspalte bis an den Nachbarpunkt. Gesucht wird mit `_source_candidates` und fester Glättung
  0,7 px (`dotlattice.py:292-295`). Dass scharfe Punkte so mehrere Minima am Rand liefern, steht schon im Modul
  (`dotlattice.py:29-31`). Zwei Kandidaten, beide punkttief → über beiden Grenzen (`_MAX_EMPTY_CELL_ARTIFACTS = 1`, Tiefe 0,4).
- Nicht vom Anzeigewert abhängig: „m“ steht immer in Zelle 9. Abhängig von Schärfe und Subpixellage.
  Das neue Bild ist schärfer (805 Quellkandidaten gegen 626 in `113119Z`).
- Der Fehler tritt heute schon den ganzen Tag auf: derselbe Befund in `121656Z/still-versuch-1.png`
  (Spalte 5,46 / 5,49); auch `115232Z/still-versuch-1.png` scheitert und wird mit Randabstand gefunden.
  Dort half jeweils der zweite Versuch. Von den 12 Standbildern der heutigen Einrichtungen scheitern 5.

### Fehler B — falsche Unterkanten-Neigung bei der Startsuche (nur `still.png`)

- `_auto_fit` nimmt als Unterkante die längste Hough-Linie in den unteren 45 % der Hinweisbox (`dotlattice.py:562-563`).
  Die Box endet bei y = 476, die Glasunterkante liegt darunter. In allen Vergleichsbildern gibt es dort keine
  Linie, dann gilt `bottom = top` (0,0215).
- In `130253Z/still.png` entsteht genau eine Linie: (746, 427) → (1067, 442), 321 px, Neigung **0,0467**. Sie läuft
  schräg durch die Ziffernpunkte, ist also Zeichentextur. Richtige Unterkante: 0,0015.
- Folge: Die rechte untere Ecke aller 4374 Startlagen liegt rund 25–40 px zu tief. Kleinster Abstand einer
  Startlage zum richtigen Quad 12,7–15,6 px, der 32 verfeinerten 20–29 px. In `121656Z` (Durchgang 0,15):
  231 Startlagen innerhalb 10 px, beste auf Rang 1, Fit nach 8 Versuchen.
- Der Plus-Anker ist nicht schuld: (750,7; 406,3) bzw. (751,8; 406,4), richtig wäre etwa (749,5; 409).
  Die Plus-Prüfung nach OQ-69 verwirft nichts Richtiges. Die waagrechte Periode wird zwar zu groß geschätzt
  (8,2 statt 6,97 px), das ist in `121656Z` aber genauso und stört nicht.

Gegenprobe auf der Kopie (Unterkante = Oberkante erzwungen, Randabstand an der Zellgrenze):

| Variante | `still.png` | `versuch-1` | `versuch-2` |
|---|---|---|---|
| Original | keine_startlage | keine_startlage | keine_startlage |
| nur Randabstand (0,5 Spalten) | keine_startlage | Fit 150 | Fit 148 |
| nur Unterkante = Oberkante | keine_startlage | — | — |
| beides (Randabstand 0,25 oder 0,5) | **Fit 155** | **Fit 150** | **Fit 148** |

Alle Fits liegen innerhalb 0,5 px am richtigen Quad.

## 2. Bewertung: Fehler im Verfahren, kein berechtigter Abbruch

Das Bild ist lesbar und das richtige Raster erfüllt alle anderen Prüfungen. Beide Fehler wirken zur sicheren
Seite (Ablehnung, kein falscher Fit). Der Trace des Team-Leads passt dazu: Die vielen `leerzelle_belegt` und
`plus_nicht_gefunden` stammen von falsch liegenden Startlagen (Fehler B) und sind dort berechtigt.

## 3. Lösungen

| Lösung | Wirkung | Risiko „nie falscher Fit“ | Stand der Belege |
|---|---|---|---|
| **A1: Randabstand an der Zellgrenze** — Kandidaten in der Lückenspalte nahe am Nachbarpunkt (z. B. `local_x ≥ _PITCH − 0,25·_PH`) nicht der Leerzelle zurechnen | behebt Fehler A | Gering: Ein um eine Zelle verschobenes Raster legt Glyphenpunkte in Spalten 0–4, die weiter zählen. Der Test „Kandidat in Spalte 5 wird abgelehnt“ (`tests/test_dotlattice.py:126`) bleibt mit 0,25 ohne Berührung | 24 gezielte Tests (Leerzellen, Einrichtung 11.11.) grün mit 0,5. Alle 65 Standbilder unter `var/live`: 5 neue Fits, alle an plausibler Lage; kein bisheriger Fit wandert um mehr als 1 px |
| **A2: Leerzellenprüfung mit punktgroßer Glättung** (wie `_lattice_candidates`) | behebt die Ursache (Mehrfachminima) | Mittel: ändert auch, was als Artefakt gilt; Schwellen aus OQ-69 neu zu belegen | nicht geprüft |
| **B1: Unterkante nur übernehmen, wenn plausibel** (Linie nicht durch das Zeichenband; sonst wie heute `bottom = top`), oder beide Annahmen als Startlagen durchsuchen | behebt Fehler B | Sehr gering: betrifft nur die Startsuche, alle Abnahmeprüfungen bleiben. Mehr Startlagen können aber öfter `startlage_mehrdeutig` auslösen | Pauschal `bottom = top` ist **keine** Lösung: `live-20261026T082712Z` und `…083418Z` verlieren damit ihren Fit |

Empfehlung: A1 und B1, beide klein (zusammen etwa ein Tag mit Tests). Vor der Änderung noch nötig: volle Suite
mit `DISPREAD_DEV_DATA`, die Fehlraster aus OQ-69 (`test_dotlattice_setup_2026_11_11.py`) gezielt mit A1 allein,
und die 65 Standbilder je Änderung getrennt (bisher zusammen gelaufen). Neue Regressionsbilder: die drei aus
`130253Z` sowie die beiden `versuch-1` aus `115232Z` und `121656Z`.

## 4. Sofort am Aufbau

- **Anderer Anzeigewert hilft nicht** (das „m“ bleibt), **explizite Hinweisbox hilft nicht gegen Fehler A**.
- Was heute geholfen hat: Einrichtung wiederholen. Jedes Standbild hat eine neue Chance; drei Versuche je
  Einrichtung reichten zweimal, einmal nicht.
- Gegen Fehler B allein könnte eine Hinweisbox helfen, deren untere Hälfte keine lange schräge Linie durch die
  Ziffern zulässt; das ist nicht erprobt und behebt A nicht.
- Ein verlässlicher Ausweg ohne Codeänderung ist nicht belegt.
