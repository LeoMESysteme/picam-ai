# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

> **Die Arbeitsliste steht in [../TODO.md](../TODO.md).** Diese Datei sagt
> *wo wir stehen*, die TODO sagt *was zu tun ist*.
>
> **Kein Blocker.** Nach dem Neustart (Boot `18ba46e9…`) liefen zwei
> Streamstarts fehlerfrei. OQ-22 bleibt offen: Heute Vormittag blockierte die
> Brücke schon beim 8. Start eines Boots — **Starts sparen**, Kamera nicht
> verstellen.

**Ernte 1 ist durch (Task 7, 2026-09-24):** 2835 Bilder, 837 gelabelt,
**81 Proben importiert** (Datensatz 88 → 169, 31 Zeichenketten, 100 %
`serial_ascii`, Vorzeichen ungeprüft, Gap-Schwellen vorläufig). Stichprobe
von 12 Bildern: alle Labels stimmen. Details: VALIDATION.md, „Ernte 1".
Task 6 (Schwelle 2,6 px) ist ebenfalls erledigt.

## Wo wir stehen

Der Kamerazweig von `scripts/sync-record.py` ist heute zum ersten Mal
erfolgreich gegen echte Hardware gelaufen (960×720, `create_video_configuration`,
im damaligen Boot ohne `stream on failed`). Sechs Aufzeichnungen liegen vor,
darunter Läufe mit `--norm-schedule` (Normierungssprünge aus der offenen
Portsitzung heraus, mit Verify/Restore).

**Task B (Versatz Telegramm ↔ Glas) hat erste Zahlen**, gemessen mit dem neuen
`scripts/display-offset.py` (Vorlagen-Projektion statt Bild-zu-Bild-Differenz —
letztere hatte fälschlich „kein Signal" gemeldet, siehe
[lab_journal.md](lab_journal.md)):

| Population | δ | M (Formel) |
| --- | --- | --- |
| `smoke15` (Ruhe, small) | +97 ms | 499 ms |
| `offset-stim` (Stimulator, large) | +80 ms | 532 ms |
| `offset-stim` (Stimulator, small) | +116 ms | 695 ms |
| `offset-norm` (Ruhewechsel, small) | +94 ms | 664 ms |

δ ist über drei Aufzeichnungen konsistent positiv (Glas wechselt nach dem
Telegramm) und `large`/`small` stimmen im Stimulatorlauf auf 36 ms überein —
das Verfahren ist damit selbst geprüft. **M = 695 ms**, festgelegt vom Nutzer
am 2026-09-23 vor jeder Ernte: der grösste Wert der Formel über die
Populationen (499–695 ms). Er steht im Plan unter Festlegung 3.

**Zwei neue Befunde aus der optischen Gegenprobe, beide mit Konsequenz:**

* **OQ-41 (neu):** Das Glas unterdrückt die führende Null, das Telegramm
  nicht (`+01.8290` vs. `+ 1.8290`). Über alle 15 geprüften Normierungsfaktoren
  konsistent. **Umgesetzt:** `gate-label.py` entfernt die Null vor dem
  Vergleich (Plan, Festlegung 1).
* **OQ-40:** Der Stau (beide Kanäle ≈ 2,5 s still) kam vom Zurückschreiben auf
  die SD-Karte, das die Dateischreibvorgänge blockierte. Behoben durch
  getrennte Schreibthreads, unter Last geprüft. Offen sind nur noch die
  Gap-Schwellen.

**Sonst erledigt heute:** `--norm-schedule` (Schreiben aus der offenen
Portsitzung, mit Vorprüfung gegen den Rückstellpunkt und bestätigter
Rückstellung danach — jeder Schreibzyklus hält den Strom ~1,8 s an);
`SIGTERM` nimmt jetzt denselben Abbruchpfad wie `SIGINT`;
`camera-commissioning.sh` prüft jetzt echten Bilddurchlauf statt nur
Enumeration (OQ-22 Punkt d erledigt); Export trägt `label_origin` jetzt mit
(`EXPORT_SCHEMA_VERSION` 2) — der externe Loader in
`picam-ai-auto-seven-segment` lehnt Schema 2 noch ab
(`evaluation.py:50`, Test `xfail(strict=True)`).

**Codex-Arbeitsweise:** Der verbliebene lokale CodeGraph-MCP-Eintrag wurde
entfernt. Das doppelte Repowise-Plugin ist in Codex deaktiviert; der gezielt
nutzbare Repowise-MCP-Server und der lokale Distill-Hook bleiben eingerichtet.
`AGENTS.md` beschreibt nun die aufgabenbezogene Doku-Lektüre und den Umgang
mit gekürzten Ausgaben.

Details und alle Zahlen: [VALIDATION.md](VALIDATION.md) (Einträge
2026-09-23), [lab_journal.md](lab_journal.md) (letzter Eintrag),
[open-questions.md](open-questions.md) OQ-38/OQ-40/OQ-41, Plan
[superpowers/plans/2026-09-22-auto-labeling-seriell.md](superpowers/plans/2026-09-22-auto-labeling-seriell.md).

## Was als Nächstes zählt

Siehe [../TODO.md](../TODO.md) für die vollständige, priorisierte Liste. Kurz:
Zuerst den RP2040-Zustand klären. Ein weiterer Warmreboot allein hat keinen
funktionierenden Stream geliefert. Falls der Nutzer einen vollständigen
Stromzyklus des Pi durchführt und die Kamera danach ein Bild liefert, Fokus,
ScalerCrop und Winkelprobe in möglichst einer langen Sitzung erledigen.
Erst danach Task 6 abschliessen
(Raster-Overlay und native Auflösungsschwelle); dann Task 7, die eigentliche
Ernte. OQ-40 blockiert sie laut Ernte-Phase-1-Plan nicht: 300/800 ms bleiben
vorläufig und werden im Artefakt markiert.

## Unverändert aus vorherigen Sitzungen

* **Dot-Matrix-Leser (`tesseract_cli`)** steht weiter an seinem Gate: 0/11
  echte GSV-Proben liefern einen Wert, nie ein falscher — reiner
  Genauigkeits-Folgeaufwand, kein Bug. Wird erst nach einem grösseren
  Datensatz wieder angefasst.
* **Zielhardware ist LCD**, nicht LED/VFD (Nutzerbestätigung, OQ-04) — der
  bisherige 73-Proben-Realdatensatz (`RND-Lab`, `BK Precision`) ist LED/VFD,
  nicht repräsentativ für den Zielbetrieb.
* **Sammelmodus** funktioniert (Geräte/Situationen/Export), Vertreterauswahl
  Phase 2 (Galerie zum nachträglichen Markieren) weiterhin nicht begonnen.
* Vorzeichenstelle des GSV-2AS bleibt unbelegt (Firmware 1.3.07, negative
  Normierung erst ab 1.5.06) — an jeder Benchmarkzahl zu nennen.
