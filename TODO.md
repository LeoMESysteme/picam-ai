# TODO — Stand 2026-09-24

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
`docs/status.md` ist die erste Datei. Diese hier ist die Arbeitsliste daneben.

---

## Kein Blocker — aber Streamstarts sparen (OQ-22)

Am 2026-09-24 blockierte die Brücke beim 8. Start eines Boots; nach Neustart
liefen zwei Starts fehlerfrei. Jede Sitzung so planen, dass sie mit wenigen
Starts auskommt: Kamera nicht verstellen, ScalerCrop aus **einem** Vollbild,
Ernte direkt anschliessen.

---

## Wo wir stehen

* Sollwertkanal (RS232 ASCII vom GSV-2AS) steht seit 2026-09-22.
* Kamerazweig läuft seit heute; sechs Aufzeichnungen liegen vor, u. a. mit
  `--norm-schedule` (Normierungssprünge live aus der offenen Portsitzung).
* Task B (Versatz Telegramm ↔ Glas) hat erste Zahlen: δ zwischen +80 und
  +116 ms über drei Aufzeichnungen, konsistent positiv (Glas nach Telegramm).
  M-Formel liefert je Population 499–695 ms.
* Führende Null (OQ-41) und SD-Schreibstau (OQ-40) sind behandelt; die
  endgültigen Gap-Schwellen bleiben offen, blockieren die erste Ernte aber
  nicht.

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

### 3. Erledigt 2026-09-24: Task 6, Fokus, ScalerCrop, Schwelle

* Fokus nachgestellt, ScalerCrop 1920×1440 um die Anzeige → `native_scale = 1,0`.
* Gemessen: frontal 3,36, „30°" (≈ 20°) 3,34, „45°" (≈ 23°) 2,68 native px
  je Punktspalte. **`resolution_threshold_px = 2,6`**, vom Nutzer festgelegt
  (Plan, Entscheidung 7).
* Profile und Bilder: `var/diagnostics/task6-{frontal,30deg,45deg}-setup/`.
  Der Ausschnitt gilt nur für die jeweilige Kameralage; nach jedem
  Verstellen neu bestimmen (10-s-Vollbild, dann Ausschnitt).

### 4. Erledigt 2026-09-24: Task 7, Ernte 1

81 Proben importiert (VALIDATION.md, „Ernte 1"). Profil und Lauf:
`var/diagnostics/ernte1-profile/`, `var/diagnostics/ernte1-run/`; Sicherung
des Datensatzes davor: `var/backup-datasets-vor-ernte1-20260924T1159/`.

**Nächste Schritte:**
* Weitere Ernten mit anderen `--seed`, um die Ziffernlücken je Zelle zu
  schliessen (OQ-39-Nachtrag). Solange die Kamera nicht bewegt wird, gilt
  `ernte1-profile/profile.json` weiter — dann ist jede Ernte **ein** Start.
* Prüfen, warum nur ≈ 28 statt ≈ 39 Bilder je Schritt gelabelt werden
  (`telegrammluecke` 1497): nur die Schreibpause oder auch zu knappe 800 ms?
* Phase 2: Zellen-Klassifikator (Plan, Entscheidung 1).

### 5. OQ-40: Gap-Schwellen nachmessen (kein Ernte-Blocker)

**Erledigt 2026-09-23:**
* Ursache gemessen: Beim Zurückschreiben auf die SD-Karte blockieren die
  Dateischreibvorgänge.
* `sync-record.py` schreibt jetzt in eigenen Threads.
* `sensor_sequence` wird je Bild mitgeschrieben, verlorene Bilder sind
  gezählt.
* `gate-label.py` lehnt Stösse über `--min-gap-ms` ab.

Zahlen: `docs/VALIDATION.md`, Eintrag „Stillstand beim Aufzeichnen".

**Offen:** Endgültige Werte für `--min-gap-ms` und `--max-gap-ms`. Laut
Ernte-Phase-1-Plan wird die Stundenaufzeichnung bewusst nicht vorgezogen:
die erste Ernte benutzt 300/800 ms und markiert
`gap_thresholds_provisional: true`. Die Stundenmessung folgt separat.

→ [OQ-40](docs/open-questions.md).

### 6. Externer Loader lehnt Export-Schema 2 ab

`picam-ai-auto-seven-segment/src/dispread/experimental/evaluation.py:50`
akzeptiert nur `schema_version` 1. Ein einzeiliger Relax auf `{1, 2}` würde
reichen. **Der Nutzer ist unentschieden (2026-09-23), deshalb bleibt es
unverändert**, weil es ein anderes Repo ist. Bis dahin ist
`test_real_export_is_accepted_by_the_actual_experiment_loader` `xfail(strict=True)`.

### 7. Kleinere offene Punkte

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
3. **M fällt aus der Formel**, es wird nicht ausgesucht. Die vorab
   entschiedene konservative Kombination ergibt **695 ms**.
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
* **`frame_sequence` in `sync-record.py` ist ein Skriptzähler**; für
  Sensorlücken das zusätzlich aufgezeichnete `sensor_sequence` verwenden
  (siehe OQ-40).
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
| Offene Fragen | `docs/open-questions.md` — OQ-22 (Kamerabrücke, seit 2026-09-24 wieder funktionsfähig), OQ-38 (Zeitkopplung), OQ-40 (Gap-Schwellen), OQ-41 (führende Null) |
| Dot-Matrix-Leser, nicht bestandenes Gate | `docs/superpowers/plans/2026-09-22-dotmatrix-backend.md` |

### Werkzeuge

| Skript | Zweck | Stand |
| --- | --- | --- |
| `scripts/gsv-registers.py` | Registerstand als Rückstellpunkt, nur Lesebefehle | läuft, verifiziert |
| `scripts/sync-record.py` | Kamera + serieller Strom, `--norm-schedule` | **läuft gegen Hardware**, verifiziert |
| `scripts/display-offset.py` (neu) | Photometrischer Versatz Telegramm↔Glas, Vorlagen-Projektion | läuft, erste Zahlen liegen vor |
| `scripts/gate-label.py` | Offline-Gate, rein über Zeitstempel | Normalisierung der führenden Null gebaut (OQ-41), M = 695 ms festgelegt; nie auf echten Daten gelaufen |
| `scripts/migrate-samples-v1-to-v2.py` | Schemamigration | gelaufen, erledigt |
