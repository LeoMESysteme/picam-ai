# TODO — Stand 2026-09-23

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
`docs/status.md` ist die erste Datei. Diese hier ist die Arbeitsliste daneben.

---

## Kein Blocker mehr — die Kamera läuft

Der Kamerazweig von `scripts/sync-record.py` ist am 2026-09-23 erstmals
erfolgreich gegen echte Hardware gelaufen (960×720, `create_video_configuration`,
kein `stream on failed` im Kernel-Log). Regel bleibt trotzdem: **≤ 960×720**,
kein Kill eines hängenden Kameraprozesses ([OQ-22](docs/open-questions.md)).

---

## Wo wir stehen

* Sollwertkanal (RS232 ASCII vom GSV-2AS) steht seit 2026-09-22.
* Kamerazweig läuft seit heute; sechs Aufzeichnungen liegen vor, u. a. mit
  `--norm-schedule` (Normierungssprünge live aus der offenen Portsitzung).
* Task B (Versatz Telegramm ↔ Glas) hat erste Zahlen: δ zwischen +80 und
  +116 ms über drei Aufzeichnungen, konsistent positiv (Glas nach Telegramm).
  M-Formel liefert je Population 499–695 ms.
* Zwei neue Befunde brauchen Entscheidungen, bevor geerntet wird: die
  unterdrückte führende Null auf dem Glas (OQ-41) und ein Prozess-Stau mit
  verfälschten Zeitstempeln (OQ-40-Nachtrag).

Details: [docs/status.md](docs/status.md), alle Zahlen in
[docs/VALIDATION.md](docs/VALIDATION.md) (2026-09-23), Herleitung in
[docs/lab_journal.md](docs/lab_journal.md) (letzter Eintrag).

---

## Die Aufgaben, in Reihenfolge

### 1.–2. Erledigt 2026-09-23: M und führende Null

* **M = 695 ms**, der grösste Wert über die Populationen. Das hat der Nutzer
  entschieden, festgeschrieben im Plan unter Festlegung 3.
* **Führende Null:** Sie wird vor dem Vergleich aus dem Telegramm entfernt,
  wie vom Nutzer entschieden. Das macht `telegram_to_display_text()` in
  `scripts/gate-label.py`, im Plan steht es unter Festlegung 1. Offen aus
  [OQ-41](docs/open-questions.md) bleiben (b), die leere Zelle im Zellenraster
  des Lesers, und (c), negative Werte (ungeprüft).

### 3. OQ-40: Prozess-Stau und Lückenschwelle

Einmal standen beide Kanäle (Kamera + seriell) ~2,5 s still, danach kamen
5 Telegramme mit fast identischem `t_boot` — die Werte sind vollständig,
ihre Ankunftszeiten nicht. Drei Teilaufgaben:

* Ursache finden (SD-Schreibstau? blockierender Hauptprozess?).
* `scripts/gate-label.py` um Burst-/Mindestabstand-Erkennung ergänzen —
  reines `--max-gap-ms` fängt den gestauchten Fall nicht.
* `sync-record.py`: `frames.jsonl` soll `SensorSequence` (echter
  Sensorzähler) statt nur des Skript-Zählers `frame_sequence` mitschreiben —
  sonst zeigt ein Stau gar keine Lücke.
* Der Gap-Schwellwert selbst ist weiterhin ungemessen; braucht eine längere
  Aufzeichnung (Stunden, möglichst unter Kameralast).

→ [OQ-40](docs/open-questions.md).

### 4. Dann erst: Ernte-Skript für Ziffernvielfalt

`sync-record.py --norm-schedule` liefert den Mechanismus bereits. Beim Bauen
beachten: jeder Schreibzyklus pausiert den Strom ~1,8 s (STOP → `set norm` →
`set dpoint` → START) — das gehört in die Zeitplanung der Sitzung.

### 5. Externer Loader lehnt Export-Schema 2 ab

`picam-ai-auto-seven-segment/src/dispread/experimental/evaluation.py:50`
akzeptiert nur `schema_version` 1. Ein einzeiliger Relax auf `{1, 2}` würde
reichen. **Der Nutzer ist unentschieden (2026-09-23), deshalb bleibt es
unverändert**, weil es ein anderes Repo ist. Bis dahin ist
`test_real_export_is_accepted_by_the_actual_experiment_loader` `xfail(strict=True)`.

### 6. Kleinere offene Punkte

* **Vorzeichenstelle unverifiziert** (Firmware 1.3.07, negative Normierung
  erst ab 1.5.06) — muss bei jeder Benchmarkzahl mitgenannt werden.

---

## Was nicht vergessen werden darf

Vorab festgelegt, damit nichts nachträglich an ein Ergebnis angepasst wird
(Plan, Abschnitt „Vorab-Festlegungen"):

1. **Exakte Zeichenkettengleichheit** zwischen Label und Anzeige — keine
   Toleranz, kein Runden. (Die OQ-41-Abbildung ist eine Vorschrift, keine
   Toleranz — Festlegung bleibt bestehen.)
2. **Bilder im Schutzfenster bekommen keinen geratenen Wert.**
3. **M fällt aus der Formel**, es wird nicht ausgesucht — aber welche
   Population/Kombination gilt, ist noch offen zu entscheiden (Aufgabe 1).
4. **`independence_group` je Aufnahmesitzung**, nicht je Bild.
5. **Jede Benchmarkzahl nennt die Herkunftsmischung** (`manual` vs.
   `serial_ascii`) und die unbelegte Vorzeichenstelle.

---

## Fallstricke

* **`0x3B`-Präfix** bei GSV-Registerantworten — `scripts/gsv-registers.py`
  macht es richtig.
* **`capture_request(wait=2.0)`** ist ein Timeout in Sekunden, kein Flag.
* **`create_video_configuration`**, nicht `create_still_configuration` — mit
  `RGB888`, gesetzter `FrameRate`, `queue=False`.
* **Ein Normierungsschreibzyklus pausiert den Strom ~1,8 s** (STOP/CLEAR →
  schreiben → START) — sichtbar in `commands.jsonl` als `non_telegram`.
* **`frame_sequence` in `sync-record.py` ist ein Skriptzähler**, kein
  Sensorzähler — zeigt Staus/Lücken nicht an (siehe OQ-40).
* **Das Telegramm hat eine führende Null, das Glas nicht** — Rohübernahme
  des Telegramms als Label ist ab Wert ≥ 1 falsch (OQ-41).

---

## Landkarte — wo steht was

| Frage | Datei |
| --- | --- |
| Aktueller Stand, Blocker | `docs/status.md` |
| Plan mit Tasks A–H, Vorab-Festlegungen | `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md` |
| Alle Messzahlen | `docs/VALIDATION.md` (Einträge 2026-09-23 am Ende) |
| Aufbau, Deutung, Irrwege | `docs/lab_journal.md` (letzter Eintrag) |
| Offene Fragen | `docs/open-questions.md` — OQ-22 (Kamera, jetzt grösstenteils erledigt), OQ-38 (Zeitkopplung), OQ-40 (Lücke/Stau), OQ-41 (führende Null, neu) |
| Dot-Matrix-Leser, nicht bestandenes Gate | `docs/superpowers/plans/2026-09-22-dotmatrix-backend.md` |

### Werkzeuge

| Skript | Zweck | Stand |
| --- | --- | --- |
| `scripts/gsv-registers.py` | Registerstand als Rückstellpunkt, nur Lesebefehle | läuft, verifiziert |
| `scripts/sync-record.py` | Kamera + serieller Strom, `--norm-schedule` | **läuft gegen Hardware**, verifiziert |
| `scripts/display-offset.py` (neu) | Photometrischer Versatz Telegramm↔Glas, Vorlagen-Projektion | läuft, erste Zahlen liegen vor |
| `scripts/gate-label.py` | Offline-Gate, rein über Zeitstempel | Normalisierung der führenden Null gebaut (OQ-41), M = 695 ms festgelegt; nie auf echten Daten gelaufen |
| `scripts/migrate-samples-v1-to-v2.py` | Schemamigration | gelaufen, erledigt |
