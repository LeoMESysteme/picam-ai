# Status — Stand 2026-09-18

Wird überschrieben, nicht angehängt. Historie und Messaufbau in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).

## Isolierter Experiment-Branch

Branch `codex/automatic-seven-segment`, eigener Worktree
`/home/me-systeme/picam-ai-auto-seven-segment`, Basis `e0c263f` von
`ocr-selbstkalibrierung`. Der ursprüngliche Checkout wurde nicht bearbeitet;
parallel entstandene Änderungen/Commits dort sind nicht Teil dieses Experiments.
Kein Merge, Push, Deployment, Kameraeingriff oder Cloud-Upload.

## Ergebnis

[Vergleichsbericht](automatic-seven-segment-report.md): reproduzierbarer
Offline-Vergleich von Produktionsbaseline, Tesseract `ssd_int`/`ssd`/`7seg`
und PP-OCRv5 mobile ONNX. Spezialisierter TFLite-Kandidat begründet ausgeschlossen.
Eigenes Scoring schützt Dezimalposition, Vorzeichen, physische Gerätesplits,
Bildhashes und Unabhängigkeit. Produktionsbenchmark-Reviewfixes bleiben getrennt.

Elf echte Bilder, davon vier unabhängige Testgeräte/Bilder (zwei lesbar).
Ziel 30 unabhängige Testbilder verfehlt, keine beleuchteten LED-/Vorzeichen-/
Bewegungstests im reservierten Testteil. RND nur Entwicklung; Geräteidentität
unbestätigt. Herkünfte/Lizenzen und Rohbilder versioniert, Gewichte per
gepinntem Download mit SHA-256 reproduzierbar.

Tesseract-Entwicklungswahl: `7seg`. Im Vollbildtest: Baseline und Tesseract
jeweils vier Zielanzeigen verfehlt; PP eine Zielregion gefunden, abgelehnt,
drei verfehlt. Keine akzeptierte richtige oder falsche Testlesung. Im bekannten
Ausschnitt alle Testwerte abgelehnt. Keine bestätigte Segmenttopologie.
**Kein qualifizierter Kandidat, deshalb keine UI-Demonstration.**

Empfehlung: synthetisches Training für die konkreten Lokalisierungs-/
Segmentgeometrie-/Dezimalprobleme in einer gesonderten Phase untersuchen und
unabhängige reale Prüfdatengrundlage erweitern. Kein Training vorgenommen.
Task 11 bleibt gesperrt; keine universelle Erkennungs- oder Produktionsreife.

## Artefakte und Wiederholung

- `experiments/automatic_seven_segment/{manifest,candidates,config}.json`.
- `experiments/automatic_seven_segment/results/`: Freeze, Einzel-/Summenergebnisse,
  Erfolgs-/Fehleroverlays mit Quellen-/Lizenzangaben, Replay-Verifikation.
- [Messzahlen](VALIDATION.md), [Aufbau/Deutung](lab_journal.md),
  [Abhängigkeiten](dependencies.md), [Datenbericht](automatic-seven-segment-data.md).
- Vollständiger Befehl und Interpretation im Vergleichsbericht.

Neues optionales ORT-Extra nur in eigener venv mit Systempaketen; keine
PyPI-Kopien von NumPy/OpenCV und keine Trainingsframeworks. Lokale RND-Bilder
haben keine öffentliche Weitergabelizenz; dieser Branch wurde nicht publiziert.

## Frisch verifiziert

```text
./.venv/bin/pytest -q                                     236 passed in 9.87s
./.venv/bin/ruff check src tests examples scripts          All checks passed! (0.16.6)
node --check src/dispread/workbench/static/workbench.js   Exit 0
git diff --check                                         Exit 0
```

Zwei nichtversionierte Originalannotationsverzeichnisse für Bestandsprüfungen
wurden aus dem Originalcheckout nach Worktree-`var/` kopiert; ohne sie werden
zwei Bestandstests ausgelassen. Experimentdaten bleiben davon unabhängig.
`--frozen`-Wiederholung: 94 Auswertungen identisch einschließlich Vorhersagen,
Zielzuordnung und Geometrie, Dauern ausgenommen. Keine neuen Samples.

## Offene Punkte

OQ-33: unabhängige Daten-/Bedingungsabdeckung und belegte Segmentgeometrie.
OQ-34: Produktions-Ecksortierung degeneriert bei bestimmten ~45°-Quads;
Experiment umgeht dies mit getesteter direkter Originalpixelentzerrung,
Produktionswirkung separat prüfen. Bestehende Reviewfragen OQ-26–OQ-32 und
Claudes Änderungen werden durch diese Arbeit weder erledigt noch ersetzt.
