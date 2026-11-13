# Offline-Korpus: Baseline und A1

Inventar `manifest.jsonl`: 74 `var/live`-Standbilder, darunter die 65 des
Handoffs; 16 OQ-69-Pfade auf dem Entwicklungsmedium sind jeweils bild- und
textdateigleiche Duplikate. Das Manifest bindet Bild und `cell-text.json` per
SHA-256. Die Ergebnisse und Labels sind in `results.jsonl` plus
`baseline-shard-*.jsonl` (Baseline) und `a1-shard-*.jsonl` (A1) gespeichert.
`baseline-report.md` dokumentiert den Vorlauf. Die eingefrorenen jeweiligen
Implementierungen sind `dotlattice-baseline.py` und `dotlattice-a1.py`;
übriger Code entspricht Ausgangsstand `fab15a93f0f2300fb8a4d8ca7c9a0e605e3236f5`.
Die Ausgangsquellhashes der benutzten Setupmodule stehen im Baselinebericht.

Jeder Variantenlauf braucht eine eigene Paketkopie und einen eindeutigen
Variantenamen. Der Evaluator verlangt den erwarteten SHA-256 und bricht **vor
dem ersten Bild** ab, wenn tatsächlich eine andere `dotlattice.py` geladen
wird. Der ursprüngliche A1-Erstlauf wurde verworfen, weil der Skriptordner
mit einer alten Paketkopie den `PYTHONPATH` überdeckte. Den hier gespeicherten
Evaluator verwenden; sein Ordner enthält kein importierbares `dispread`.

Beispiel A1 aus dem Repo, ohne Schreibzugriff auf Eingabedaten (jeder Shard
muss mit derselben Shardzahl laufen; alle drei parallel starten, weil
Duplikate auf den Erstpfad warten):

```bash
mkdir -p /tmp/raster-a1-repro
cp -a src/dispread /tmp/raster-a1-repro/
cp docs/quellen/raster-recherche-2026-11-13/korpus/dotlattice-a1.py /tmp/raster-a1-repro/dispread/dotlattice.py
for shard in 0 1 2; do
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  RASTER_CODE_SHA256=e302dc3b89ed406a8dba8ddd51f77068a86b38c7946c7c63d73b8c3facbe2645 \
  RASTER_VARIANT=a1_repro RASTER_SHARD=$shard RASTER_SHARDS=3 \
  DISPREAD_DEV_DATA=/mnt/ssd/picam-dev PYTHONPATH=/tmp/raster-a1-repro \
  ./.venv/bin/python docs/quellen/raster-recherche-2026-11-13/korpus/evaluate.py &
done
wait
```

Keine vorhandenen Variantendateien mit anderen Quelldateien wiederverwenden.
Vor jeder Wiederaufnahme und vor der Shardaufteilung gleicht der Evaluator
die vollständige entdeckte Pfadmenge mit dem Manifest ab und prüft Bild-
und Textdateihash jedes Pfads, auch bereits ausgewerteter Pfade. Fehlende,
zusätzliche oder veränderte Eingaben brechen ab. Bereits gespeicherte Zeilen
aller Shards des Variantennamens brauchen den passenden Quellhash und
Bildhash; historische Zeilen ohne Quellhash sind nicht für Resume zulässig.
Für einen Baseline-Neulauf daher einen frischen Variantennamen verwenden.
Bei Vergleich
sind identische Pfade, Bildhashes und Labels verpflichtend:

```bash
./.venv/bin/python docs/quellen/raster-recherche-2026-11-13/korpus/compare.py \
 'docs/quellen/raster-recherche-2026-11-13/korpus/results.jsonl,docs/quellen/raster-recherche-2026-11-13/korpus/baseline-shard-*.jsonl' \
 'docs/quellen/raster-recherche-2026-11-13/korpus/a1-shard-*.jsonl'
```

Neue Fits werden mit `check_truth.py ERGEBNIS.jsonl PFADFRAGMENT` separat
gegen passende vollständige serielle Texte geprüft; `overlay.py` zeichnet
das entzerrte Bild und die Zell- und Punktpositionen. Die Offsetprüfung und
der Leser sind keine alleinigen Beweise für die Lage. Warnungen bleiben
Warnungen; die unter `truth-*.jsonl` und `overlays/` gespeicherten Befunde
wurden zusätzlich einzeln visuell geprüft. Belege für unterschiedliche
Aufstellungen oder Maskentexte mit `?` dürfen nicht als unabhängig
bestätigte Sollgeometrie ausgegeben werden.

## B1 und A1+B1 (2026-11-13)

| Bestand | Baseline | B1 | A1 | A1+B1 |
| --- | ---: | ---: | ---: | ---: |
| 65 Handoff-Standbilder | 58 | 59 | 61 | 63 |
| 74 verschiedene Standbilder | 64 | 66 | 69 | 72 |
| 90 Pfade mit 16 Duplikaten | 80 | 82 | 85 | 88 |

B1: siebenmal `keine_startlage`, einmal `startlage_mehrdeutig` auf 90
Pfaden. A1+B1: je einmal `keine_startlage` und `startlage_mehrdeutig`.
Beide Varianten erhalten alle Baselinefits; maximaler Eckabstand B1 0 px,
A1+B1 0,52243 px. Die Gegenproben 20261026T082712Z und 083418Z haben
jeweils 0 px Abstand. Gegen A1 behalten sämtliche Fits in A1+B1 ihre Quads
exakt (0 px), darunter alle fünf neuen A1-Fits; ihre damals ermittelten
Offsetwarnungen bestehen weiter. `b1-comparison.jsonl`,
`a1b1-comparison.jsonl` und `a1-to-a1b1-comparison.jsonl` enthalten den
paarweisen Vergleich aller 90 Pfade.

B1 gewinnt `115232Z/still-versuch-1` und `142321Z/still-versuch-1`; beide
Quads sind im kombinierten Lauf identisch (0 px). Ihr zugeordneter serieller
Text stimmt mit der visuellen Zell-/Punktzuordnung überein, Offset- und
Readerprüfung sind `OK`. A1+B1 gewinnt zusätzlich `130253Z/still.png` mit
passender sichtbarer Zuordnung und Reader `OK`, jedoch Offset **`WARNUNG`**
bei maximal 0,18066 Spalten. Die fünf schon von A1 gewonnenen Fits und ihre
Warnungen bleiben bestehen; Warnung ist keine uneingeschränkte Validierung.
Die Belege ordnen sich wie folgt zu:

- [`truth-a1b1-115232-v1.jsonl`](truth-a1b1-115232-v1.jsonl) → [`live-20261113T115232Z-still-versuch-1.png`](overlays/live-20261113T115232Z-still-versuch-1.jpg)
- [`truth-a1b1-142321-v1.jsonl`](truth-a1b1-142321-v1.jsonl) → [`live-20261113T142321Z-still-versuch-1.png`](overlays/live-20261113T142321Z-still-versuch-1.jpg)
- [`truth-a1b1-130253-still.jsonl`](truth-a1b1-130253-still.jsonl) → [`live-20261113T130253Z-still.png`](overlays/live-20261113T130253Z-still.jpg)

Die Codekopien `dotlattice-b1.py` (SHA-256
`187461559dcccae6983b3a15361918c41361bc04f0bb38a8f8bdce33cb9e4202`)
und `dotlattice-a1b1.py` (SHA-256
`e2fe141232cf6300e4303f5035354aa8c7ee1d7a711966c3b084d7cceee545ec`)
wurden in getrennten Paketkopien geladen; die Evaluatorzeilen weisen den
jeweiligen Hash aus. Für jede Variante existieren drei `*-shard-*.jsonl` mit
insgesamt 90 Zeilen. Pfade, Bildhashes, ausgewählte Labels, Quellhashes und
Manifestbestand wurden geprüft, alle Shardlogs enden ohne Fehlerzeile. Die
sechs Prozesse wurden zur Entlastung der Gesamtsuite pausiert und fortgesetzt.
Der Sammel-Warteprozess meldete nach der Pause Exit 143; ein Exit-0-Nachweis
liegt dafür nicht vor. Vollständige Zeilen, erfolgreiche Vergleiche und
Logenden sind separate Evidenz. Laufzeit unter Parallelbelastung nicht als
Messwert verwenden. Keine Hardware oder Eingabedaten verändert.

**Overlays:** Im Repository liegen die Overlays als JPEG (Qualität 90, verkleinert von zusammen 21 MB auf 2,4 MB). Die PNG-Originale mit `SHA256SUMS` liegen auf dem Entwicklungs-Pi unter `/mnt/ssd/picam-dev/belege/raster-overlays-2026-11-13/`.
