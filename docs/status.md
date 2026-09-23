# Status — Stand 2026-09-23

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

> **Die Arbeitsliste steht in [../TODO.md](../TODO.md).** Diese Datei sagt
> *wo wir stehen*, die TODO sagt *was zu tun ist*.
>
> **Kein Reboot-Blocker mehr.** Die Kamera lief heute erstmals erfolgreich
> gegen Hardware (siehe unten). Weiter gilt: **≤ 960×720**, kein Kill eines
> hängenden Kameraprozesses ([OQ-22](open-questions.md)).

## Wo wir stehen

Der Kamerazweig von `scripts/sync-record.py` ist heute zum ersten Mal
erfolgreich gegen echte Hardware gelaufen (960×720, `create_video_configuration`,
kein `stream on failed` im Log dieses Boots). Sechs Aufzeichnungen liegen vor,
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

Details und alle Zahlen: [VALIDATION.md](VALIDATION.md) (Einträge
2026-09-23), [lab_journal.md](lab_journal.md) (letzter Eintrag),
[open-questions.md](open-questions.md) OQ-38/OQ-40/OQ-41, Plan
[superpowers/plans/2026-09-22-auto-labeling-seriell.md](superpowers/plans/2026-09-22-auto-labeling-seriell.md).

## Was als Nächstes zählt

Siehe [../TODO.md](../TODO.md) für die vollständige, priorisierte Liste. Kurz:
M = 695 ms, die Normalisierung der führenden Null und die Behebung des Staus sind erledigt (2026-09-23) → OQ-40
(Stau-Erkennung, `SensorSequence` statt Skriptzähler, Gap-Schwelle messen) →
erst dann die eigentliche Ernte (Normierungsfaktoren abfahren für
Ziffernvielfalt).

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
