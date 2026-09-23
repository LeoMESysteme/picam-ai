# Dot-Matrix-Leser für Zeichen-LCDs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Punktraster-Zeichen-LCD des GSV-Sensors tatsächlich *lesen* —
also einen Wert liefern, nicht nur sicher ablehnen. Das bestehende
`tesseract_cli`-Backend erreicht auf den 11 bestätigten GSV-Proben 0/11
Lesungen; dieser Plan ersetzt den generischen OCR-Ansatz für diese
Displayklasse durch einen Zeichenzellen-Matcher nach dem Muster von
`sevenseg.py`.

**Spec:** Bewusst kein separates Design-Dokument — die Begründung steht in
diesem Header, der Messstand in [Ausgangsmessungen](#ausgangsmessungen).
Wird der Plan größer als hier geschnitten, gehört eine Spec unter
`docs/superpowers/specs/` nachgezogen.

---

## Warum dieser Ansatz (Entscheidungsgrundlage)

Zwei Wege standen zur Wahl:

**A — eigenes Tesseract-Traineddata** für die Punktraster-Schrift trainieren
(via `tesstrain`, analog `letsgodigital`).

**B — eigener Dot-Matrix-Matcher**: Zeichenzellen-Raster aus dem bestätigten
Profil, Bitmuster pro Zelle gegen eine Zeichentabelle matchen — dasselbe
Verfahren, das `sevenseg.py` für 7-Segment-Anzeigen bereits erfolgreich
anwendet.

Gewählt: **B**. Gründe, in der Reihenfolge ihres Gewichts:

1. **Erklärbare Evidenz statt unkalibrierter Konfidenz.** `sevenseg` liefert
   pro Stelle einen Margin zur gepoolten Schwelle; die Freigabelogik aus
   Konzept.md §7 ist darauf gebaut. Tesseracts Wortkonfidenz ist ausdrücklich
   keine Fehlerwahrscheinlichkeit — das steht bereits als bekannte Grenze im
   Docstring von `src/dispread/ocr/tesseract_cli.py`.
2. **Sauberes Ablehnungsverhalten bei unbekannten Zeichen.** Kein
   Tabelleneintrag → `"?"`. Ein trainiertes OCR-Modell rät bei einer
   Trainingslücke stattdessen das ähnlichste bekannte Zeichen — eine
   Falschlesung statt einer Ablehnung, also die nach Konzept.md §7 *falsche*
   Fehlerrichtung.
3. **Geringerer Infrastrukturaufwand.** B braucht ein Referenzmuster pro
   Zeichen; A braucht eine komplette Trainings-Toolchain (`tesstrain`-Build,
   Korpusgenerierung, Trainingslauf, Validierung) auf dem Pi.
4. **Strukturelle Trennung von Zahl und Einheit.** Die Zellgeometrie kennt
   die Grenze zwischen Wert- und Einheitzellen. Bei `tesseract_cli` ist diese
   Trennung heute nur ein Nebeneffekt der Ziffernzahlprüfung (dort als
   bekannte Grenze dokumentiert).

**Was gegen B spricht und im Plan adressiert werden muss:** Der Ansatz
generalisiert nicht von selbst auf unbekannte Displaytypen oder Schriftarten.
Das ist im Projekt die akzeptierte Richtung (bestätigtes Profil statt Raten),
aber es heißt: jeder neue Zeichensatz braucht eine Tabellenerweiterung.
Siehe [Task 3](#task-3-zeichentabelle-aus-bestatigten-proben-aufbauen).

### Ausgangsmessungen

Gemessen am 2026-09-22 auf den 11 bestätigten GSV-Proben (Gerät
`87564e345aa047338f954c045bc9df02`) im Datensatz unter
`var/workbench/datasets/samples/`. Alle Zahlen hier sind **Messwerte dieses
Spikes**, keine Schätzungen:

| Befund | Messung |
|---|---|
| `tesseract_cli` auf dem rohen ROI-Ausschnitt | Tesseract findet **überhaupt keine Wörter** (nur TSV-Ebene 1, `conf=-1`). Die reale Ablehnungsursache ist damit `kein_text_erkannt`, **nicht** `ziffernzahl_stimmt_nicht` — der im Docstring beschriebene Einheit-klebt-an-Zahl-Effekt tritt in der Praxis gar nicht erst ein, weil vorher nichts erkannt wird. |
| Ursache dafür | Der ROI-Ausschnitt ist achsparallel um ein **gekipptes** Display gelegt und enthält deshalb Gehäuseecken/Schrauben. Die globale Otsu-Schwelle kippt daran und schwärzt halbe Bildbereiche. |
| Sättigungsmaske (`HSV-S > 60`) → `minAreaRect` → `warpPerspective` | Liefert auf dem GSV-Gerät einen sauberen, entkippten Ausschnitt. Der größte gesättigte Bereich deckt im Median **96 %** des ROI ab (min 0,54 / max 0,97, n=11). |
| Tesseract auf dem **so entzerrten** Ausschnitt | Liest `41.5000` statt `+1.05000`, Konfidenz **5,2** von 100. Mit *und* ohne Zeichen-Whitelist identisch (beide Varianten geprüft — die Whitelist ist nicht die Ursache). `--oem 0` liefert gar nichts. |
| Zeichenraster auf dem entzerrten Ausschnitt | Die Zeichen sitzen auf einem regelmäßigen Monospace-Raster. Auf der saubersten Probe: Tintenblock-Mitten bei 6,5 / 39 / 70,5 / 101,5 / 138,5 / 172 / 205,5 / 239,5 / 273,5 px → Teilung ≈ 33,5 px bei 600 px Warp-Breite. |
| **Displaytyp (vom Nutzer, von der Platine abgelesen)** | **Displaytech 161A** → 16 Zeichen × 1 Zeile. Die Zellenzahl ist damit **bekannt**, keine Schätzgröße mehr. |
| Gleichmäßiges 16-Zellen-Raster, Kleinste-Quadrate-Fit gegen `+1.05000` (saubere Probe) | Linke Kante 20,1 px, Teilung 33,71 px, **maximale Abweichung 2,93 px bei 33,7 px Zellbreite** (< 9 % einer Zelle). Die zwei größten Abweichungen sind exakt `+` (+2,0) und `.` (−2,9) — also die Glyphen, deren Tinte nicht zellzentriert sitzt. Die Ziffern liegen innerhalb ±0,5 px. |
| Rasterverankerung über alle 11 Proben (2-Parameter-Fit, 16 Zellen fix) | **Nicht stabil.** Linker Rand 4,2–18,3 % der Quad-Breite, 16-Zellen-Spanne 74,5–94,5 %. Sichtbar zwei Cluster, die mit der Aufnahmeposition korrelieren (die drei `1.05000`-Proben liegen zusammen bei ~5 % / ~92 %). |
| **Beschriftungsqualität des Datensatzes** | **2 der 11 Beschriftungen sind falsch** (`0.904801` und `0.9801`; beide Anzeigen zeigen `+0.94801`). Aufgefallen durch Formatabgleich: 9 von 11 haben 6 Ziffern / 5 Nachkommastellen, das Anzeigeformat ist fest. Siehe [Task 0](#task-0-zwei-fehlerhafte-beschriftungen-im-datensatz-korrigieren). |

**Schlussfolgerung A:** Tesseract ist auf dieser Schrift nicht blind, aber
weit unter brauchbar — es produziert eine Zeichenkette ungefähr richtiger
*Form* mit falschem *Inhalt* bei Konfidenz 5,2. Preprocessing ist als Ursache
ausgeschlossen (auf dem sauber entzerrten Bild bleibt das Ergebnis gleich).

**Schlussfolgerung B:** Die Hypothese zerfällt in zwei Teilfragen, die
unterschiedlich gut beantwortet sind:

1. **Sitzen die Zeichen auf einem gleichmäßigen Raster? — Ja, gut gestützt.**
   Der 16-Zellen-Fit trifft die Ziffern auf ±0,5 px genau. Die anfangs
   gemessene „Unregelmäßigkeit" (Streuung bis 8,1 px über Tintenblockmitten)
   war ein **Artefakt der Messmethode**: Tintenblock-Schwerpunkte sind durch
   die Glyphenform verzerrt (das `.` sitzt links in seiner Zelle) und
   verschmelzen bei Nachbarzeichen. Das ist keine Rasterunregelmäßigkeit.
2. **Lässt sich das Raster zuverlässig *verankern*? — Noch nicht.** Der
   Sättigungs-Quad ist als Bezugsrahmen nicht stabil genug (linker Rand
   4,2–18,3 %, Spanne 74,5–94,5 % über die 11 Proben). Ein Raster pro Bild zu
   fitten bleibt deshalb nötig.

Deshalb bleibt [Task 2](#task-2-gate-rasterverankerung-gegen-alle-11-proben-prufen)
ein **Abbruchtor** — aber die Frage hat sich verschoben: nicht mehr „gibt es
ein Raster", sondern „lässt es sich pro Bild richtig anlegen".

**Offen, nicht gemessen:** Viele 16×1-Module sind intern als 8+8 adressiert,
und manche haben deshalb eine **breitere Lücke in der Zeilenmitte**. Der
saubere Fit oben deckt nur die Zeichen 1–8 (`+1.05000`) ab — genau bis zur
möglichen Bruchstelle. Ob die Zellen 9–16 (Leerzeichen + `mV/V`) auf demselben
gleichmäßigen Raster liegen, ist **ungeprüft**. Für den Messwert ist das
zunächst unkritisch (der Wert liegt in Zelle 1–8), für ein späteres Lesen der
Einheit nicht.

---

## Architecture

Der Leser implementiert dieselbe `ValueReader`-Schnittstelle
(`read(crop, layout) -> ReadResult`, `src/dispread/ocr/__init__.py`) wie
`sevenseg` und `tesseract_cli` — **keine Schnittstellenänderung**.

```
Controller._read()
  └─ self._reader_for(config["backend"]).read(reader_crop, layout)
       ├─ backend="sevenseg"      -> SevenSegmentReader  (unverändert)
       ├─ backend="tesseract_cli" -> TesseractReader     (unverändert, bleibt)
       └─ backend="dotmatrix"     -> DotMatrixReader     (neu)

src/dispread/rectify.py (erweitert)
  └─ lcd_quad_in_region()   Sättigungsmaske -> minAreaRect
                            nur für hinterleuchtete LCDs, opt-in
```

Neue Bausteine, jeder mit einer Aufgabe:

| Baustein | Aufgabe | Datei |
|---|---|---|
| `lcd_quad_in_region()` | Aus einem ROI das LCD-Glas als Quad finden (Sättigung) | `src/dispread/rectify.py` |
| `fit_character_grid()` | Auf einem entzerrten Ausschnitt linke Kante + Teilung bestimmen, bei fester Zellenzahl aus dem Profil (GSV: 16) | `src/dispread/ocr/dotmatrix.py` |
| `GLYPH_TEMPLATES` | Zeichen → erwartetes Punktmuster | `src/dispread/ocr/dotmatrix.py` |
| `DotMatrixReader` | Zellen abtasten, Muster nachschlagen, Ablehnung statt Raten | `src/dispread/ocr/dotmatrix.py` |

**Tech Stack:** Python 3, OpenCV (`cv2`), NumPy. **Keine neue Abhängigkeit** —
insbesondere kein `tesstrain`, kein ML-Framework.

---

## Global Constraints

- **Abnahmekriterium, numerisch:** Auf dem `development`-Split der 11
  bestätigten GSV-Proben gilt am Ende von Task 6: **≥ 9 von 11 exakt korrekte
  Lesungen bei 0 falschen Werten** — **nachdem Task 0 die zwei fehlerhaften
  Beschriftungen korrigiert hat.** Gemessen mit dem *bestehenden* Harness
  (`src/dispread/benchmark.py`, `classify()` / `evaluate_set()`), **kein neues
  Messwerkzeug bauen**. Wird die Zahl nicht erreicht, ist der Plan nicht
  fertig — „nie falsch, aber nie richtig" ist ausdrücklich **kein** Erfolg.
  Das ist genau der Zustand, in dem `tesseract_cli` heute steht.
- **Ohne Task 0 ist das Kriterium nicht messbar.** Zwei der 11 Beschriftungen
  sind nachweislich falsch (siehe Task 0); gegen sie kann kein Leser gewinnen.
  Ein Tor, das an fehlerhaften Beschriftungen scheitert, sagt nichts über den
  Leser aus — das ist der teuerste Weg, einen Implementierungslauf zu verbrennen.
- **Vorzeichen ist kein Vergleichsproblem.** `benchmark.normalise()` entfernt
  ein führendes `+`. Ein Leser, der korrekt `+0.94801` liefert, vergleicht
  sauber gegen die Beschriftung `0.94801`. Ein **Minus** bleibt erhalten und
  wird von `classify()` als eigene Fehlerklasse `"sign"` geführt.
- **Anzeigeformat des GSV-Sensors, aus den Proben belegt:** durchgehend
  `+X.XXXXX mV/V` — 6 Ziffern, 5 Nachkommastellen, Vorzeichen immer sichtbar,
  13 von 16 Zellen belegt. Ein Festformat-Profil (`digits=6`, `decimals=5`) ist
  damit tragfähig; nach Task 0 passen **alle 11** Proben dazu.
- **Unlesbares wird abgelehnt, nie geraten** (Konzept.md §7, nicht
  verhandelbar). Jeder Ablehnungspfad gibt `value=None` zurück, nie eine
  bestmögliche Schätzung.
- **Kein Erfinden von Protokollen oder Zeichen.** Ein Muster, das in keiner
  Tabelle steht, wird abgelehnt und nicht auf das nächstliegende Zeichen
  gerundet — dieselbe Regel, die `sevenseg._decode_cell()` bereits umsetzt.
- **`ValueReader` bleibt unverändert.** Alle drei Backends teilen sich
  `read(crop, layout) -> ReadResult`.
- **`unit_text` kommt weiter aus dem bestätigten Profil**, nicht aus Pixeln
  (OQ-17) — auch wenn dieser Leser die Einheitzeichen prinzipiell lesen
  *könnte*. Eine gelesene Einheit dürfte einen Wert nie überstimmen; will man
  sie später als Plausibilitätsprüfung nutzen, ist das eine eigene
  Entscheidung mit eigener OQ.
- **Der bestehende `tesseract_cli`-Leser bleibt erhalten.** Er wird nicht
  gelöscht und nicht als gescheitert markiert — er bleibt der Pfad für
  Zeichen-LCDs, für die keine Zeichentabelle existiert.
- **Schwellen ehrlich kennzeichnen.** Jede neu eingeführte Konstante
  (Sättigungsschwelle, Mindest-Matchabstand, Mindestkontrast) ist ein
  *unvalidierter Vorabdefault*, bis eine Messung dagegen steht — so
  dokumentiert wie `sevenseg._MIN_CONTRAST` und
  `tesseract_cli._MIN_WORD_CONFIDENCE` es bereits sind. Keine Behauptung
  empirischer Validierung ohne Messung.
- **Doku-Pflicht (AGENTS.md):** Jeder Commit, der `src/`, `scripts/` oder
  `examples/` berührt, braucht im **selben Commit** einen `CHANGELOG.md`-Eintrag.
- **Kein Zugriff auf die laufende Produktions-Workbench.** Auf diesem Pi läuft
  ein produktiver `dispread`-Prozess. Vor irgendeiner Aktion, die ihn berühren
  könnte (Neustart, Portbelegung, Gerätedateien), erst prüfen und beim Nutzer
  rückfragen.

---

## Task 0: Zwei fehlerhafte Beschriftungen im Datensatz korrigieren

**Muss vor allem anderen passieren** — ohne diesen Task ist das
Abnahmekriterium aus den Global Constraints nicht messbar.

Beim Prüfen der Beschriftungen gegen die entzerrten Bilder (2026-09-22) sind
zwei Tippfehler aufgefallen. Beide Anzeigen zeigen nachweislich `+0.94801 mV/V`:

| Probe | `expected_text` heute | Anzeige zeigt tatsächlich | Fehler |
|---|---|---|---|
| `663591e6…` | `0.904801` | `0.94801` | eine `0` zu viel eingefügt |
| `e96bd68c…` | `0.9801` | `0.94801` | die `4` fehlt |

Auffindbar waren sie, weil 9 der 11 Proben exakt 6 Ziffern / 5 Nachkommastellen
haben und genau diese zwei abweichen — das Anzeigeformat ist fest.

**Files:**
- Modify: `var/workbench/datasets/samples/663591e6…/sample.json`
- Modify: `var/workbench/datasets/samples/e96bd68c…/sample.json`
- Modify: `docs/lab_journal.md`
- Modify: `CHANGELOG.md`

**Status: erledigt am 2026-09-22.**

**Steps:**
- [x] **Erst mit dem Nutzer bestätigen.** Das sind seine real aufgenommenen
      Messdaten. Die Bilder oben sind eindeutig, aber Messdaten werden nicht
      ohne Rückfrage umgeschrieben.
- [x] Korrektur über den vorgesehenen Pfad vornehmen — **existierte nicht und
      musste gebaut werden**: `save_sample` lehnt ein abweichendes Label für
      denselben `capture_token` bewusst ab (`datasets.py:401-415`). Neu:
      `DatasetStore.relabel_sample` nach dem Muster von `select_sample`
      (Revisionsprüfung, `metadata_revision` hochzählen, atomar schreiben),
      plus Controller-Op `dataset.relabel` und 10 Tests.
- [x] Prüfen, ob `sha256` und die übrigen Bildfelder unberührt bleiben —
      bestätigt, gegen Sicherungskopien geprüft.
- [x] Befund im `docs/lab_journal.md` festhalten (Eintrag 2026-09-22),
      inklusive der Prüfregel für künftige Sammelläufe.
- [x] **Prüfen, ob dieselbe Formatprüfung auf die anderen beiden Geräte
      anwendbar ist** — geprüft: `91853b73…` (41 Proben) völlig einheitlich,
      `4237c46d…` (36 Proben) sieben Ausreißer, davon vier als
      Nahe-Null-Cluster plausibel legitim. **Nichts geändert**; beide Geräte
      sind LED-/VFD-Laborvertreter und für den Produktionspfad nicht maßgeblich
      (Nutzerentscheidung 2026-09-22).
- [x] **Neu gegenüber der ursprünglichen Planung:** `label_history` hält den
      vorherigen Wert samt Begründung in der Probe fest. Grund: `var/` ist
      gitignored, es gäbe sonst keine Spur, dass Grundwahrheit verändert wurde.

---

## Task 1: LCD-Quad im ROI finden (`lcd_quad_in_region`)

Der Leser bekommt laut Schnittstelle einen *bereits entzerrten* Ausschnitt.
Heute findet `fit_quad_in_region` auf dem realen Datensatz **0 von 73** Quads
(gemessen, siehe `docs/VALIDATION.md` 2026-09-21, OQ-25). Ohne diesen Task
lässt sich der neue Leser gegen den Datensatz gar nicht erst ausführen.

**Files:**
- Modify: `src/dispread/workbench/vision.py` (neue Funktion `lcd_quad_in_region`)
- Create: `tests/test_lcd_quad.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/open-questions.md` (neu: **OQ-36**, siehe unten)

**Korrekturen gegenüber der ersten Planfassung (2026-09-22):** Die Funktion
gehört nach `workbench/vision.py` neben ihr Geschwisterteil
`fit_quad_in_region` (`vision.py:87`) — `rectify.py` entzerrt ein *bekanntes*
Quad, es findet keines. Und die nächste freie Fragenummer ist **OQ-36**, nicht
OQ-30 (das ist längst vergeben; der Katalog steht bei 35).

**Status: erledigt am 2026-09-22.**

**Steps:**
- [x] `lcd_quad_in_region(frame, region, *, saturation_threshold=60)` schreiben:
      HSV-Sättigungsmaske → `MORPH_CLOSE` → größte Kontur → `minAreaRect` →
      vier Ecken in der Reihenfolge `tl, tr, br, bl`.
- [x] Rückgabe `None`, wenn keine Kontur gefunden wird **oder** der größte
      gesättigte Bereich unter einem Mindestflächenanteil des ROI liegt
      (Vorabdefault; der gemessene Bereich auf GSV war 0,54–0,97).
- [x] Tests gegen synthetische Bilder (gekipptes helles Rechteck auf dunklem
      Grund) — muss ohne Kamera und ohne Datensatz laufen.
- [x] Ein Test, der die Rückgabe `None` für einen ungesättigten (grauen)
      Ausschnitt festhält — die Funktion darf auf nicht-hinterleuchteten
      Anzeigen nicht raten.
- [x] **OQ-36 anlegen:** „Sättigungsbasierte LCD-Quad-Findung nur an einem
      Gerät gemessen". Inhalt: auf GSV (n=11) Median-Flächenanteil 0,96; auf
      den beiden anderen Datensatzgeräten nur 0,58 bzw. 0,69 — das sind
      LED-/VFD-Laborvertreter, laut Zielhardware **nicht** repräsentativ
      (Produktionsanzeigen sind durchgehend LCD). Offen: ob die Schwelle 60
      über mehrere echte LCD-Geräte trägt.
- [x] Im Docstring festhalten: Diese Funktion ist **kein Ersatz** für
      `fit_quad_in_region`, sondern ein Sonderpfad für hinterleuchtete,
      farbige LCDs. Sie ersetzt keine Bedienerbestätigung.
- [x] **Aufgabenzuschnitt nicht überdehnen:** Task 2 misst, dass dieser Quad
      als *Rasteranker* zu ungenau ist (linke Kante 4,2–18,3 %). Seine Aufgabe
      ist damit nur „entkippter, gehäusefreier Ausschnitt" — die Rasterlage
      kommt aus dem Fit, nicht aus der Glaskante. Nicht in die Feinabstimmung
      der Sättigungsschwelle investieren; sie muss den Ausschnitt liefern,
      nicht ihn auf ein Pixel genau treffen.

---

## Task 2 (GATE): Rasterverankerung gegen alle 11 Proben prüfen

> **Ergebnis 2026-09-22: Gate NICHT bestanden.** Bestes Verfahren
> (Tintenausdehnung als Anker) erreicht **67,9 %** Median über die sechs
> vorab festgelegten Parameterkombinationen; die Abbruchgrenze lag bei 70 %.
> Drei Verankerungsverfahren gemessen, Zahlen in
> [VALIDATION.md](../../VALIDATION.md) 2026-09-22 und
> [lab_journal.md](../../lab_journal.md).
>
> **Ausdrücklich nicht belegt: dass der Ansatz scheitert.** In drei Anläufen
> war jeder Rückschlag ein Werkzeugfehler, nicht ein Befund über das
> Verfahren. Belegt ist nur: die Verankerung ist in drei Anläufen nicht
> zuverlässig gelungen.
>
> **Ursachenhinweis:** Der Sättigungs-Quad erfasst je nach Aufnahmesituation
> unterschiedlich viel physischen Ausschnitt (16 Zellen belegen 0,94 der
> Crop-Breite bei den drei Proben aus einer Aufnahmeposition, 0,73–0,78 bei
> den übrigen acht). Der nächste sinnvolle Schritt ist deshalb eine stabilere
> Bezugsgrösse für den Ausschnitt, kein viertes Verankerungsverfahren.
>
> Task 3 und folgende bleiben damit **gesperrt**, bis das entschieden ist.

**Dieser Task ist ein Abbruchtor.** Dass ein gleichmäßiges Raster existiert,
ist gemessen (±0,5 px auf den Ziffern). Offen ist die *Verankerung*: Der
Sättigungs-Quad taugt als Bezugsrahmen nicht (linker Rand 4,2–18,3 %, Spanne
74,5–94,5 % über die Proben), das Raster muss also pro Bild gefittet werden —
und ob das zuverlässig gelingt, entscheidet über den ganzen Ansatz.

**Die Zellenzahl ist keine freie Variable mehr:** Displaytech 161A = 16 Zellen.
Der Fit hat damit nur noch zwei Freiheitsgrade (linke Kante, Teilung) statt
einer offenen Rastersuche.

**Files:**
- Create: `scripts/dotmatrix-grid-probe.py` (Diagnosewerkzeug, kein Produktivpfad)
- Modify: `CHANGELOG.md`

**Steps:**
- [ ] Für jede der 11 GSV-Proben: ROI → `lcd_quad_in_region` (Task 1) →
      `warpPerspective` → Binarisierung → Spaltenprofil.
- [ ] Linke Kante und Teilung **pro Bild** fitten, bei **fest 16 Zellen**.
      Nicht über Tintenblockmitten — die sind durch die Glyphenform verzerrt
      (gemessen: `.` liegt 2,9 px links, `+` 2,0 px rechts der Zellmitte).
- [ ] **Nicht-zirkuläre Prüfung — Zeichenkonsistenz über Proben hinweg.**

      *Verworfen (2026-09-22):* die zunächst geplante Belegt/Leer-Prüfung der
      16 Zellen gegen `expected_text`. Sie diskriminiert nicht — alle 11
      Proben haben dasselbe Festformat (6 Ziffern / 5 Nachkommastellen), also
      auch dasselbe Muster „8 belegt, Lücke, 4 belegt, 3 leer". Das erfüllt
      jedes halbwegs richtig liegende Raster. Ebenso untauglich ist ein Score
      „Tinte in der Mitte, wenig am Rand": den maximiert auch ein falsches
      Raster.

      *Stattdessen:* Zellen extrahieren, jede auf ein 5×7-Punktmuster
      herunterrechnen, und messen, ob Zellen **mit demselben erwarteten
      Zeichen** über alle 11 Proben hinweg gleich aussehen:
      * mittlerer Hamming-Abstand innerhalb einer Zeichenklasse
        (within-class),
      * gegen den mittleren Abstand zwischen verschiedenen Klassen
        (between-class),
      * und pro Zelle: liegt sie ihrer *eigenen* Klasse am nächsten?

      Sitzt das Raster auf jedem Bild richtig, müssen sich gleiche Zeichen
      ähneln und verschiedene unterscheiden. Driftet es zwischen Bildern,
      explodiert der within-class-Abstand und das Verhältnis fällt gegen 1.
      Das ist nicht zirkulär und liefert nebenbei genau die Vorlagen, die
      [Task 3](#task-3-zeichentabelle-aus-bestatigten-proben-aufbauen) braucht.
- [ ] **Mittenlücke prüfen** (bisher ungemessen): Liegen die Zellen 9–16 auf
      demselben gleichmäßigen Raster wie 1–8, oder hat das Modul die bei
      8+8-adressierten 16×1-Displays verbreitete breitere Lücke in der
      Zeilenmitte? Falls ja, braucht das Raster einen zusätzlichen
      Mittenversatz — und der Wertbereich (Zelle 1–8) bleibt davon unberührt.
- [ ] **Abbruchbedingung, vorab festgelegt** (angepasst an das neue Maß,
      2026-09-22): Maßgeblich ist der Anteil der Zellen, die ihrer eigenen
      Zeichenklasse am nächsten liegen — das ist die direkteste Entsprechung
      dazu, ob ein Tabellennachschlag später treffen würde.
      * **≥ 90 %** → tragfähig, weiter mit Task 3.
      * **70–90 %** → nicht sauber; erst die Verankerungs-Alternative unten
        (Tintenprofil statt Glaskante) messen, bevor entschieden wird.
      * **< 70 %** → **stoppen.** Befund nach `docs/VALIDATION.md` und
        `docs/lab_journal.md`, Entscheidung A/B mit dem Nutzer neu aufmachen —
        nicht „irgendwie weiterbauen".

      Die Schwellen sind vorab gesetzt, damit sie nicht nachträglich an das
      Ergebnis angepasst werden.

### Vorab-Festlegung für den entscheidenden Lauf (2026-09-22, vor der Messung)

Der erste Messversuch lieferte nacheinander 19,3 % → 37,5 % → 65–74 %, und
**jede** Steigerung kam von einem behobenen Werkzeugfehler, nicht von einer
Änderung am Ansatz (entarteter Rasterfit; globale Otsu-Schwelle gegen einen
Helligkeitsverlauf; eine 5×7-Reduktion, die tintenarme Glyphen wie `.` zum
Nullvektor macht). Die 73,9 % waren zudem der **beste von sechs** nachträglich
durchprobierten Parametersätzen — also kein zulässiges Ergebnis.

Damit der nächste Lauf zählt, steht die Verarbeitungskette hier **vor** der
Messung fest:

| Stufe | Festlegung |
|---|---|
| Entzerrung | `lcd_quad_in_region` → `warpPerspective` auf 640×128 |
| Beschnitt | vertikal 12 %–88 %, horizontal je 14 px |
| Binarisierung | `adaptiveThreshold`, Gauss, Blockgröße 51, C = 15 |
| **Teilung** | **Autokorrelation** des mittelwertbefreiten Tinten-Spaltenprofils, erste Grundperiode im Bereich 25–55 px. Unüberwacht — immun gegen die Score-Entartung, an der der erste Versuch scheiterte |
| Phase | bei *fester* Teilung: Versatz maximiert (Tinte in 16 Zellmitten − Tinte an 17 Zellgrenzen). Nur ein Freiheitsgrad, keine Entartung mehr |
| Zellraster | Parametergitter 5×7 und 8×10 × Schwellen 0,15 / 0,25 / 0,35 |
| Klassen | `space` und `empty` zu **`blank`** zusammengefasst — beide sind leer und prinzipiell ununterscheidbar |

**Entscheidungsgröße ist der MEDIAN über alle sechs Parameterkombinationen**,
nicht der beste Wert. Grund: Die Reduktionsparameter sind aus dem ersten Sweep
bereits bekannt; sie jetzt als „vorab gewählt" auszugeben wäre unredlich. Der
Median ist gegen genau dieses Rosinenpicken robust. Alle sechs Einzelwerte
werden mitberichtet.
- [ ] Falls die Verankerung über den Sättigungs-Quad scheitert: als Alternative
      prüfen, ob sich das Raster direkt am Tintenprofil verankern lässt (erste
      und letzte belegte Zelle als Anker) statt an der Glaskante.
- [ ] Ergebnis (Teilung, Versatz, Zellenzahl je Probe) als Tabelle in
      `docs/VALIDATION.md` festhalten, mit Datum.
- [ ] **Berührt OQ-27/OQ-28:** Die Spike-Messung zeigt, dass die Teilung *pro
      Bild* bestimmt werden muss. Rasterfeinschliff je Bild ist laut OQ-27
      bewusst nicht gebaut worden. Ist das hier nötig, muss OQ-27 aktualisiert
      werden — mit der Begründung, warum es für diesen Leser doch nötig ist.

---

## Task 3: Zeichentabelle aus bestätigten Proben aufbauen

**Files:**
- Create: `src/dispread/ocr/dotmatrix.py` (nur `GLYPH_TEMPLATES` + Aufbaulogik)
- Create: `tests/test_dotmatrix_templates.py`
- Modify: `CHANGELOG.md`

**Steps:**
- [ ] Zeichentabelle **primär aus den 11 bestätigten Proben** ableiten:
      `expected_text` liefert die Beschriftung, das Raster aus Task 2 die
      Zellgrenzen — die Zuordnung Zeichen→Muster fällt damit ohne manuelles
      Labeln an.
- [ ] Muster als grobes Punktraster je Zelle speichern (z. B. 5×7 oder 5×8
      abgetastete Felder), nicht als Rohbild — das Muster muss gegen
      Beleuchtung und Maßstab robust sein.
- [ ] **Die ROM-Zeichentabelle bleibt der *sekundäre*, nicht der primäre Weg**
      — auch jetzt, wo der Modultyp bekannt ist (**Displaytech 161A**, vom
      Nutzer von der Platine abgelesen, 16 × 1 Zeichen). Der Modultyp legt die
      Geometrie fest, **nicht** automatisch den Zeichensatz: Der
      Controller-Baustein (HD44780-kompatibel, z. B. ST7066U oder KS0066U) ist
      noch nicht verifiziert, und diese Bausteine kommen in Varianten mit
      **unterschiedlichen ROM-Zeichensätzen** (A00/A02 bzw. `-0A`/`-0B`/`-0E`).
      Ein falsch gewählter Zeichensatz fällt bei Ziffern nicht auf, sondern
      erst bei Sonderzeichen — also genau im Umprogrammierungsfall, für den die
      ROM-Tabelle gedacht wäre.
- [ ] Konkreter Folgeschritt statt Annahme: Datenblatt zum **Displaytech 161A**
      beschaffen und die ROM-Variante daraus belegen. Erst danach ist die
      Tabelle als Ergänzung für ungesehene Zeichen (`°`, `Ω`, `µ`) brauchbar.
      Eigener Schritt mit eigener OQ, **nicht** Teil dieses Plans.
- [ ] Beobachteten Zeichensatz dokumentieren: Aus den 11 `expected_text`-Werten
      kommen nur Ziffern, `.` und implizit das Vorzeichen vor. Die
      Einheitzeichen (`m`, `V`, `/`) stehen im Bild, aber nicht in
      `expected_text`. Festhalten, welche Zeichen damit belegt sind und welche
      Lücken bleiben.
- [ ] Test: Jedes Muster in der Tabelle ist von jedem anderen um einen
      Mindestabstand verschieden (sonst sind zwei Zeichen strukturell nicht
      unterscheidbar und das gehört gewusst, bevor es im Feld auffällt).

---

## Task 4: `DotMatrixReader` — Leser mit Pro-Zeichen-Evidenz

**Files:**
- Modify: `src/dispread/ocr/dotmatrix.py` (`DotMatrixReader`)
- Create: `tests/test_dotmatrix_reader.py`
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md` (Architekturtabelle: neues Backend eintragen)

**Steps:**
- [ ] `read(crop, layout) -> ReadResult` implementieren, Ablauf analog
      `sevenseg.read()`:
      Polarität normieren → Raster fitten (Task 2) → je Zelle Punktmuster
      abtasten → **gepoolte** Schwelle über alle Zellen (nicht pro Zelle —
      die Begründung steht ausführlich in `sevenseg.segment_threshold()` und
      gilt hier genauso) → Tabellennachschlag → `GlyphEvidence`.
- [ ] Kein Tabellentreffer oder zu geringer Abstand zum zweitbesten Kandidaten
      → `GlyphEvidence(text="?", confidence=0.0)` plus `ambiguous_with`, wie
      `sevenseg._decode_cell()` es macht. **Nicht** auf das nächstliegende
      Zeichen runden.
- [ ] Vorzeichen getrennt führen: `sign_region_readable` muss von
      `sign_detected` unterscheidbar bleiben — ein unlesbarer Vorzeichenbereich
      führt zur Ablehnung, **nicht** zu „positiv" (Konzept.md §7).
- [ ] Überstrahlung auf den **rohen** Grauwerten messen, vor jeder
      Polaritätsumkehr — sonst verschluckt die Umkehr eine echte Reflexion.
      Denselben Fehler vermeidet `sevenseg` bereits bewusst (dortiger
      Kommentar zu `raw_gray`).
- [ ] `declares_confidence_calibrated` → `False`. Es gibt keine Kalibriermessung
      gegen echte Fehlerraten.
- [ ] Tests: synthetisch gerenderte Punktraster-Zeichen (bekannte Wahrheit),
      plus explizite Tests für die Ablehnungspfade. Laufen ohne Hardware.

---

## Task 5: Profilschema, `Controller`, Workbench-UI

**Files:**
- Modify: `src/dispread/workbench/controller.py` (`_reader_for`)
- Modify: Profilschema (Schema-Version hochziehen, Migration für Altprofile)
- Modify: `src/dispread/workbench/static/` (Backend-Auswahl um `dotmatrix`)
- Modify: `tests/test_workbench.py`
- Modify: `CHANGELOG.md`

**Steps:**
- [ ] `backend="dotmatrix"` im Profilschema zulassen, Schema-Version erhöhen,
      Altprofile migrieren (Default bleibt `sevenseg` — bestehende Geräte
      dürfen sich nicht stillschweigend ändern).
- [ ] **Zeichenzellenzahl ins Profil aufnehmen** (GSV/Displaytech 161A: 16).
      Sie ist eine Eigenschaft des verbauten Moduls, kein Messergebnis, und
      gehört deshalb zum bestätigten Profil — nicht in eine Konstante im
      Lesercode. Ein anderes Modul (162A = 16 × 2, 202A = 20 × 2) braucht nur
      einen anderen Profilwert, keinen Codeeingriff.
- [ ] `Controller._reader_for()` um den neuen Leser erweitern.
- [ ] Backend-Auswahl in der UI ergänzen.
- [ ] `controller.py` ist laut Repowise die Datei mit der schlechtesten
      Code-Health (2,0/10) und 3 Bugfixes in kurzer Zeit — hier **minimal
      invasiv** arbeiten, keine Aufräumaktion nebenbei.

---

## Task 6: Abnahme gegen den Datensatz

**Files:**
- Modify: `docs/VALIDATION.md`
- Modify: `docs/lab_journal.md`
- Modify: `docs/status.md`
- Modify: `docs/ROADMAP.md` (falls P0-Stand sich ändert)
- Modify: `CHANGELOG.md`

**Steps:**
- [ ] `scripts/dataset-benchmark.py` mit `backend=dotmatrix` gegen den
      `development`-Split laufen lassen. **Kein neues Messwerkzeug bauen.**
- [ ] Gegen das Abnahmekriterium prüfen: **≥ 9/11 exakt korrekt, 0 falsche
      Werte**, gegen die in Task 0 korrigierten Beschriftungen. Nicht erreicht
      → der Plan ist nicht fertig; Befund schreiben und mit dem Nutzer
      entscheiden, nicht stillschweigend abschließen.
- [ ] Vorher sicherstellen, dass Task 0 wirklich gelaufen ist. Läuft der
      Benchmark gegen die unkorrigierten Beschriftungen, ist die Obergrenze
      9/11 und das Kriterium unerreichbar — der Lauf wäre wertlos.
- [ ] Ergebnis mit Datum in `docs/VALIDATION.md` und `docs/lab_journal.md`.
- [ ] `docs/status.md` überschreiben (nicht anhängen) — inklusive einer
      ehrlichen Aussage dazu, wie `tesseract_cli` jetzt dasteht.
- [ ] Den `test`-Split **nicht** anfassen, solange am Verfahren noch
      geschraubt wird — sonst ist er als unabhängige Abnahme verbrannt.

---

## Ausdrücklich nicht in diesem Plan

- **Serielles Live-Labeling** (Sensor per Schnittstelle an den Pi, Werte gegen
  den Kamera-Feed labeln). Sinnvoll und unabhängig vom Backend wertvoll, aber
  eigener Plan: es berührt Hardware-Verkabelung (**OQ-09: Pi-GPIO-Pegel dürfen
  nicht direkt an RS-232**, Pegelwandler nötig) und die laufende
  Produktions-Workbench auf diesem Pi.
- **HD44780-ROM-Zeichensatz vollständig einpflegen** — Folgeschritt, siehe
  Task 3, braucht zuerst eine Verifikation des Controller-Typs.
- **`tesseract_cli` entfernen oder ersetzen.** Es bleibt.
- **Aufräumen in `controller.py`/`datasets.py`**, so verlockend die
  Health-Werte auch sind. Nicht Teil dieses Ziels.
