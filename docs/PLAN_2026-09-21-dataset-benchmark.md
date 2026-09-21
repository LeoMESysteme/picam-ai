# Plan: Bridging-Skript — Datensatz-Proben gegen den 7-Segment-Leser messen

> **Stand 2026-09-21: umgesetzt (Task 1–4), erster echter Lauf gefahren.**
> `src/dispread/benchmark.py` und `scripts/dataset-benchmark.py` sind fertig
> und getestet (5 Commits im Worktree `worktree-dataset-benchmark`). Der
> erste echte Lauf gegen den vollständigen Sammelmodus-Bestand (73 lesbare
> Proben, 2 Geräte) bestätigt die Vorab-Messung: **0 von 73 Proben passen**,
> Phase B liefert dadurch in keiner der sechs durchgeführten Faltungen eine
> Übertragungszahl. Zahlen in [VALIDATION.md](VALIDATION.md) (2026-09-21),
> Deutung in [lab_journal.md](lab_journal.md) (2026-09-21), Updates an
> [OQ-23](open-questions.md), [OQ-25](open-questions.md) und
> [OQ-17](open-questions.md). Offen: Integration in `master` (noch im
> Worktree), Behebung der zwei gefundenen Lücken (fehlender `selected`-
> Vertreter für eine BK-Situation; Rastergeometrie selbst, siehe
> OQ-23-Update).

**Ziel:** Die im Sammelmodus erfassten realen Proben (Zielbox + getippter
Sollwert) erstmals messbar machen, ohne dabei eine Zahl zu erzeugen, die besser
aussieht als sie ist.

## Context

Der Datensatz-Sammelmodus liefert inzwischen 52 reale Proben (2 Geräte, 5 Situationen,
51 lesbar / 1 unlesbar). Diese Proben sind aber **nicht messbar**: sie speichern
bewusst nur eine achsparallele Zielbox und den getippten Sollwert — **kein
Segmentraster** (`ocr_box`/`layout`) und **kein Vierpunkt-Quad**. Der bestehende
`scripts/ocr-benchmark.py` braucht aber genau das (`evaluate_annotation` verlangt
`annotation["profile"]["layout"]`, `roi_quad`, `ocr_box`). Ergebnis: mit den
gesammelten Bildern lässt sich aktuell **keine einzige Zahl** über die
Erkennungsqualität gewinnen.

Ziel ist, diese Lücke zu schließen — so, dass die entstehende Zahl **ehrlich**
ist. Die naheliegende Abkürzung (Raster mit dem bekannten Sollwert fitten, dann
dasselbe Bild damit lesen) ist wertlos: `fit_layout` meldet `matched=True` nur,
wenn der Parametersatz genau diesen Text dekodiert — eine Quote darauf wäre per
Konstruktion 100 %.

Offene Fragen, die das Skript beantworten soll:
- **OQ-23**: Passt das feste relative Segment-Abtastraster überhaupt zur realen
  Schrift? Bisher an einem Bild vermutet, nie gezählt.
- Wie stark brechen **schräge** Aufnahmen ein, und wie viel bringt Entzerren?
- Wo steht der Leser heute, damit spätere Änderungen vergleichbar werden?

## Abgestimmte Entscheidungen

| Frage | Entscheidung |
| --- | --- |
| Messart | **Phase A (Passbarkeit/Diagnose) + Phase B (Übertragung)** |
| Schräge Bilder | **Beide Geometrien messen und vergleichen** |
| Eingabequelle | **Live-Probenspeicher** `var/workbench/datasets/samples/` |

## Vorab-Messung (read-only Spike, während der Planung gelaufen)

Der wichtigste Befund — er ändert den Zuschnitt des Skripts:

| Prüfung (5 markierte Vertreter, je 1 pro Situation) | Ergebnis |
| --- | --- |
| `fit_layout` mit `ocr_box=(0,0,1,1)` | **0 von 5** gefittet |
| `fit_layout` mit `fit_ocr_box`-Startrahmen | **0 von 5** gefittet |
| Grobe Rahmensuche, 132 Startrahmen × ~71 Auswertungen ≈ 9 400 Leseversuche (eine Probe) | **kein einziger Treffer** |
| Kontrast im Ausschnitt | 0,27–0,57 — **weit über** der Mindestschwelle 0,10 |
| Überstrahlung / `glare` | 0,000–0,003, **kein** Flag |
| Leserausgabe | `'????'` / `'?????'` — **jede** Ziffernzelle unlesbar |

Deutung: **kein** Belichtungs-, Kontrast- oder Reflexionsproblem, und der
Ziffernbereich liegt ungefähr dort, wo `fit_ocr_box` ihn vermutet (visuell im
Ausschnitt geprüft: die 7-Segment-Ziffern sind deutlich sichtbar). Trotzdem
landet **kein** abgetastetes Segmentmuster in der Zifferntabelle. Das ist exakt
die Vermutung aus [OQ-23](open-questions.md) — jetzt erstmals gezählt.

**Konsequenz:** Ein Skript, das heute nur korrekt/falsch/abgelehnt zählt, meldet
überall „0 %" — wahr, aber nicht handlungsfähig. Der erste Nutzen liegt in der
**Diagnose je Segment**. Die Quote kommt dazu, sobald überhaupt etwas passt.
Zusätzlich gezeigt: der Nachzieh-Bereich von `fit_layout` (Rahmen ±6 %,
Skalierung 0,9–1,1) ist für eine **von Hand gezogene** Zielbox viel zu eng — er
ist für einen bereits bestätigten `ocr_box` ausgelegt. Eine grobe Vorsuche ist
nötig, damit „passt nicht" wirklich „passt nicht" heißt.

## Phase A — Passbarkeit und Diagnose (ausdrücklich *kein* Erkennungswert)

Je lesbarer Probe: Zielbox → Ausschnitt → **grobe Rahmenvorsuche** →
`fit_layout`. Die Vorsuche variiert nur **Geometrie**, nie den Sollwert — sie
kann also keine Ziffer „passend raten".

**Die eigentliche OQ-23-Aussage ist nicht die Trefferzahl**, sondern:
1. **Streuung der gefitteten Verhältnisse** über die Proben *eines* Geräts
   (`digit_gap_ratio`, `sign_cell_ratio`, `thickness_ratio`, `inset_ratio`) plus
   die Zahl der `flat_optimum`-Fälle. `VALIDATION.md` hat die Geometrie
   bereits als unterbestimmt gemessen; instabile Verhältnisse über Proben
   derselben Anzeige beantworten OQ-23, eine Passquote nicht.
2. **Segmentdiagnose, wenn nichts passt** (der heutige Regelfall): je
   Ziffernstelle die gemessenen Segmenthelligkeiten, die Schwelle, der Abstand
   und das Sollmuster aus `DIGIT_SEGMENTS` —
   `erwartet 2 = a,b,d,e,g` vs. `gemessen a=0.71 b=0.66 c=0.12 …`. Daraus ist
   ablesbar, *welches* Segment falsch abgetastet wird. Bausteine liegen vor:
   `ReadResult.glyphs[i].segments`/`.margin`, `diagnostics{threshold,contrast}`.

Aufschlüsselung nach Gerät, Situation und **Bedingung** (`reflection` 51×,
`digits` 44×, `frontal` 28×, `angled` 24×, `distance` 10×, `dim` 8×,
`negative` 6×, `decimal` 2×). **Nicht** nach `technology` aggregieren: das
BK-5491B ist als `LED` erfasst, ist aber physisch VFD (OQ-23).

## Phase B — Übertragung (die eigentliche Erkennungszahl)

**Leave-one-group-out, je Faltung getrennt berichtet, nie gepoolt.** Für
„RND-Lab" (4 Situationen): Raster auf dem Vertreter von Situation *i* fitten,
auf die Proben der Situationen *j ≠ i* anwenden → vier Faltungen.
„BK Precision" hat **nur eine** Situation — Übertragung über Situationen ist
dort unmöglich, ausgerechnet für das Gerät, um das OQ-23 geht. Das ist eine
**Datenlücke, die gemeldet wird**, keine Zeile, die man weglässt.

Warum nicht innerhalb einer Situation: 14 der 52 Proben tragen eine
`similarity_warning`, alle gruppenintern — Bewertung dort wäre teils Bewertung
auf Beinah-Kopien. Der Grad der Ähnlichkeit je Faltung wird mit
`DatasetStore._similarity_score` **gemessen** statt in Prosa beschwichtigt.

### Was eingefroren wird — und was ausdrücklich nicht

Eingefroren wird **nur die Glyphengeometrie**: `digit_gap_ratio`,
`sign_cell_ratio`, `thickness_ratio`, `inset_ratio`.

| Größe | Quelle je Zielprobe | Begründung |
| --- | --- | --- |
| `digits`, `decimals` | aus dem `expected_text` der **Zielprobe** | wie der Bediener das Format im Betrieb bestätigt |
| `has_sign` | aus dem **Gerät**, nie aus dem Zieltext | das Vorzeichen ist eine eigene kritische Klasse und darf nicht vom Sollwert abgeleitet werden |
| `ocr_box` | je Zielprobe neu über `fit_ocr_box(crop, layout)` | siehe unten |
| Glyphenverhältnisse | eingefroren aus der Faltung | das ist die eigentlich übertragene Größe |

**Zwingend, sonst baut die Messvorrichtung selbst Fehler:** Gruppe `26692830`
(BK) mischt die Formate `(5 Stellen, 2 Nachkomma)` und `(5, 4)` — Werte wie
`012.37` stehen neben `-0.0009`/`-0.0010`, das Gerät hat mitten in der Sitzung
den Bereich gewechselt. `fit_layout` backt `digits`/`decimals` in das
zurückgegebene Layout ein, und `decimal_point_index() = digits - decimals - 1`
erzwingt die Punktposition. Ein eingefrorenes `decimals=2` auf `-0.0009`
angewandt erzeugt garantiert die Fehlerklasse `decimal` — **vom Prüfstand
fabriziert, nicht von der Optik**; das beträfe ~18 % des einzigen VFD-Geräts.
Der Bereichswechsel gehört zusätzlich als empirischer Datenpunkt an
[OQ-17](open-questions.md) gemeldet.

**Preis, der ausgesprochen werden muss:** Weil der Dezimalpunkt so mitgeliefert
wird, ist die Fehlerklasse `decimal` in dieser Messung **strukturell
unerreichbar**. „0 Dezimalfehler" darf niemand als Beleg lesen. Das gehört in
die Ausgabe des Skripts selbst, nicht nur in die Doku (OQ-17: der Punkt wird
ohnehin aus dem Profil angenommen, nicht gemessen).

**`ocr_box` je Ziel neu bestimmen, nicht einfrieren:** Die von Hand gezogenen
Zielboxen einer einzigen Situation unterscheiden sich in der Fläche um das
~5-fache. Ein normierter Rahmen aus der Faltung landet in einer anderen Probe
physisch woanders — weit außerhalb der ±6-%-Toleranz. Das wäre
Annotationsrauschen, das man anschließend fälschlich dem Segmentmodell
anlastet. `fit_ocr_box` bekommt das Layout mit (sonst ist sein Aspekt-Filter
wirkungslos); liefert es `None`, ist das ein **eigener Eimer**, nie ein stiller
Rückfall auf den eingefrorenen Rahmen.

### Ehrliches Ausfallverhalten

- Findet Phase A für eine Faltung kein Raster (heute der Regelfall), meldet
  Phase B „kein Raster gefunden, keine Übertragung möglich" — **nicht** „0 %
  korrekt". Eine nicht durchführbare Messung ist keine bestandene Messung
  (wie `check-dataset-export.py`: „ein fehlender Experimentstand ist kein Bestehen").
- **Nenner vorab festnageln** auf alle lesbaren Proben des Geräts. Ein
  fehlgeschlagener Fit macht seine Bewertungsproben `rejected`, er lässt sie
  **nie aus der Statistik verschwinden** (sonst Survivorship-Bias nach oben).
- **Kein Auswahl-Orakel:** Vertreter ist ausschließlich die mit `selected`
  markierte Probe (alle fünf Situationen haben genau eine). Ein Rückfall auf
  „die mit der besten `separation`" wäre Auswahl nach Fit-Güte und damit
  geschönt — fehlt `selected`, bricht der Lauf laut ab.
- **Ablehnungsquote gleich prominent** drucken wie die Trefferquote: null
  falsche Annahmen bei 70 % Ablehnung ist kein Erfolg.
- Die eine `unreadable`-Probe **nicht** in die Zählung falten: sie hat per
  Speicherregel keinen `expected_text`, „falsch angenommen" würde Wissen
  behaupten, das nicht vorliegt. `docs/VALIDATION.md:490` macht null falsche
  Annahmen zur maßgeblichen Zahl — eine fabrizierte würde später eine
  berechtigte Dekoderänderung blockieren. Stattdessen als benannte
  Einzelfalldiagnose ausgeben (n=1, keine Quote).
- Beide Geräte stehen auf `split: development`, keines auf `heldout`: **nichts,
  was dieses Skript druckt, darf Testergebnis heißen.** Ein leerer Split wird
  laut als Lücke gemeldet.
- Gruppen-Disjunktheit per `assert`-Funktion nach dem Vorbild von
  `assert_disjoint_devices` erzwingen, nicht nur als Regel dokumentieren.

## Geometrie: beide Wege, sauber verglichen

Je Probe zweimal auswerten:
1. **achsparallel** — Zielbox-Ecken → normiertes Quad (`rectify._order_quad`) → `rectify`
2. **entzerrt** — `fit_quad_in_region(image, normierte_bbox)` → gedrehtes Rechteck → `rectify`

Der Vergleich wird **nur über Proben gebildet, bei denen beide Arme ein Quad
geliefert haben**, plus eine getrennte Zahl der `None`-Fälle. Ein stiller
Rückfall von Arm 2 auf Arm 1 würde eine Mischung erzeugen und den Vergleich
uninterpretierbar machen. Ehrliche Grenze: `fit_quad_in_region` nutzt
`cv2.minAreaRect`, fängt also **Drehung** ab, echte Keystone-Verzerrung nur
teilweise.

## Dateien

**`src/dispread/benchmark.py`** (erweitern — die Logik gehört hierher, `evaluate_clip`/
`evaluate_annotation` liegen bereits hier):
- `load_dataset_samples(root)` — liest `samples/<uuid>/sample.json`, überspringt
  `synthetic` (wie der Exportvertrag), meldet Übersprungenes einzeln.
- `sample_quad(image, bbox, *, deskew)` — Pixel-`bbox` → **normiertes** Quad
  (`read_frame` erwartet normiert); mit `deskew=True` erst `fit_quad_in_region`.
- `search_ocr_box(crop, expected_text, *, reader)` — grobe Rahmenvorsuche über
  `x/y/Breite/Höhe` plus `fit_ocr_box`-Vorschlag, jeder Kandidat an `fit_layout`,
  bester Treffer nach `separation`.
- `fit_dataset_sample(...)` → `SampleFit` (`matched`, `layout`, `ocr_box`,
  `separation`, `runner_up`, `flat_optimum`, `geometry`, `reason`).
- `target_layout(device, sample, frozen_ratios)` — **der eine Engpass**, der das
  Ziel-Layout aus genau (Geräte-`has_sign`, Zielformat, eingefrorene
  Verhältnisse) baut und aus nichts sonst. Strukturell dieselbe Absicherung wie
  bei `ValueReader.read`.
- `evaluate_dataset_sample(...)` → bestehendes `Outcome`, intern über `read_frame` + `_tally`.
- `segment_report(crop, layout, ocr_box, expected_text, *, reader)` — Diagnose je
  Segment gegen `DIGIT_SEGMENTS`.
- `aggregate(outcomes)` — Summierung aus `evaluate_set` herausgezogen, damit
  beide Pfade dieselbe Aggregation benutzen statt zwei Kopien.
- `assert_disjoint_groups(...)` — analog `assert_disjoint_devices`.

**`scripts/dataset-benchmark.py`** (neu, dünne CLI nach Hausstil von `ocr-benchmark.py`):
- `--samples PATH` (Default `var/workbench/datasets`), `--split development|heldout|all`,
  `--deskew both|off|on`, `--device ID`, `--diagnose N`.
- Phase-A- und Phase-B-Bericht getrennt; Phase A ausdrücklich als „Passbarkeit
  (keine Erkennungsquote)" beschriftet. Ausgabeformat über das vorhandene
  `_print_report`-Muster, damit der Mensch ein Format sieht.
- Druckt den Hinweis mit, dass `decimal` in dieser Messanordnung nicht messbar ist.
- `main() -> int`, Exit 0/1, Fehler nach stderr mit `FEHLER: `-Präfix.
- **Schreibt nichts in `docs/`**.

**`tests/test_dataset_benchmark.py`** (neu) — Stil von `tests/test_benchmark.py`:
synthetisch und deterministisch über `render_display`
(`src/dispread/frames/synthetic_source.py`), kein Realbild nötig:
- gefittete Verhältnisse übertragen sich auf eine synthetische Probe einer
  **anderen** Situation mit anderem Wert → `correct`
- **Formatwechsel-Test**: Zielprobe mit anderer Nachkommastellenzahl darf **keine**
  `decimal`-Fehlklasse erzeugen (die reale BK-Falle)
- ausgefallenes Segment (`dropout_segments`) → `rejected`, nicht `wrong`
- fehlgeschlagener Fit → Bewertungsproben erscheinen als `rejected`, verschwinden
  nicht aus dem Nenner
- fehlendes `selected` → lauter Abbruch, keine Ersatzwahl
- `synthetic: true` wird übersprungen; leerer Split meldet die Lücke
- CLI als Subprozess (Muster aus `tests/test_dataset_export.py`)

## Wiederverwendung (nichts davon neu bauen)

| Vorhanden | Rolle |
| --- | --- |
| `benchmark.read_frame` | liest *genau* wie der Betrieb (`rectify` + `crop_box` + `read`); erwartet `roi_quad` **normiert** |
| `benchmark.normalise` / `classify` / `_tally` / `_reject_reasons` / `Outcome` | Dreiteilung + Fehlerklassen, bereits getestet |
| `ocr-benchmark.py::_print_report` | ein Ausgabeformat für den Menschen |
| `ocr.autofit.fit_layout`, `parse_expected` | Rastersuche aus dem Sollwert |
| `workbench.vision.fit_quad_in_region`, `fit_ocr_box` | Quad bzw. `ocr_box` — beide **ohne** Sollwert, also ohne Leck |
| `rectify.rectify`, `rectify._order_quad`, `controller.crop_box`, `CROP_SIZE` | identische Bildvorbereitung wie im Betrieb |
| `workbench.datasets.DatasetStore.list_devices`, `_similarity_score` | `split`/`has_sign` je Gerät; Ähnlichkeit je Faltung messen |
| `frames.synthetic_source.render_display` | Testfixtures |

Nicht über `ReleaseGate` führen: die Leserebene ist die konservative Obergrenze.

## Verifikation

```bash
./.venv/bin/pytest -q
./.venv/bin/ruff check src tests examples scripts
./.venv/bin/python scripts/dataset-benchmark.py --samples var/workbench/datasets --split development
./.venv/bin/python scripts/ocr-benchmark.py --annotations var/workbench/annotations   # Gegenprobe: unverändert
```

**Synthetische Kontrolle als Pflichtprüfung:** derselbe Lauf gegen eine
`render_display`-Probe **muss** `matched=True` und eine saubere Übertragung
liefern. Schlägt sie fehl, liegt der Fehler im Skript, nicht in den Realbildern —
ohne diese Kontrolle ist „passt nicht" nicht von „kaputt" zu unterscheiden.

**Erwartungsmanagement:** Der erste echte Lauf wird sehr wahrscheinlich eine
Passbarkeit nahe null plus Segmentdiagnose liefern, keine schöne Quote. Das ist
der Zweck. Ein Lauf, der plötzlich hohe Quoten meldet, ist zuerst auf ein Leck zu
prüfen (Sollwert im Bewertungspfad), nicht zu feiern.

## Doku-Pflicht (AGENTS.md)

- `CHANGELOG.md` im selben Commit (Änderung unter `src/` und `scripts/`).
- `docs/status.md` vor dem letzten Commit neu schreiben.
- Ergebniszahlen **nicht** automatisch nach `VALIDATION.md` — das entscheidet
  ein Mensch nach Sichtung; das Skript schreibt nirgends in `docs/`.
- Nach dem ersten echten Lauf: Messung protokollieren (`VALIDATION.md` =
  Zahlen, `docs/lab_journal.md` = Aufbau/Deutung), **Update an OQ-23** (erstmals
  gezählte Antwort statt Einzelbild-Vermutung) und **an OQ-17** (der beobachtete
  Bereichswechsel des BK-5491B mitten in einer Situation ist genau der dort
  offene Fall „Geräte, die Punkt/Bereich während eines Laufs wechseln").
- Die Spike-Zahlen oben sind vorläufig — durch den Lauf des fertigen Skripts
  ersetzen, nicht aus diesem Plan abschreiben.
