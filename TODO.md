# TODO — Stand 2026-09-30

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
`docs/status.md` ist die erste Datei. Diese hier ist die Arbeitsliste daneben.

---

## Jetzt: Ablehnungen von Abnahme 2 verstehen, dann nächste Entwicklungsrunde

Abnahme 2 ist am 2026-09-30 **nicht bestanden**: 0 falsch, aber 85,8 %
abgelehnt (`ab3` 75 %, `ab4` 100 %, alle `zelle_unbekannt`). Die Details
stehen in VALIDATION.md 2026-09-30. `ab3`/`ab4` werden nicht nachgebessert,
sie gehen ins Training.

1. Die Ablehnungen analysieren: Abstand je Zelle und Zeichen zu den Vorlagen
   gegen `d_max`, getrennt nach `ab3`/`ab4`, und die Ursache benennen
   (Zeichengröße, Perspektive, Normierung?). Das ist eine reine Auswertung,
   ohne Änderung an den Gruppen.
2. Aus dem Befund die nächste Entwicklungsrunde ableiten. Das
   Erfolgskriterium wird vorab in der Spec festgelegt, dann `loo` mit
   `ab3`/`ab4` als Trainingsgruppen.
3. Für Abnahme 3 sind zwei **neue** Aufstellungen nötig, möglichst eine davon
   mit anderem Licht.
4. Die Einzelbilder von `ab4-run` (1,6 GB) erst nach Rückfrage löschen.

---

## Erledigt 2026-09-30: Abnahme 2 abgeschlossen (`ab4` geerntet, einmal ausgewertet)

Stand 2026-09-29 abends: Stufe 2 ist mit `bg_closing_v1` eingefroren
(Vorlagen `var/dotmatrix/templates-stufe2b-2026-09-29.json`, sha256
`fc3b44bdc880372a600168218560a3926fa307fe533b2592f7c4c244a89aa75e`).
`ab3` (frontal, nah) ist geerntet und importiert und steht in der
Profilzuordnung. **`ab4` fehlt.**

1. **`ab4` aufbauen:** Kamera schräg von rechts (30–40° seitlich, leicht von
   oben), anderes Licht als `ab3` (z. B. Lampe seitlich oder Decke aus). Nichts
   Helles hinter der Kamera, Anzeige mittig, grüner Rand neben dem Text frei,
   normal scharf.
2. **Einrichten wie `ab3`**, Ablauf in VALIDATION.md:
   * `harvest-setup.py focus` erst ohne, dann mit `--hint-box`,
   * Standbild 3 s PNG (`sync-record.py … --duration 3`),
   * Punktraster mit 4 Stützpunkten: `python var/diagnostics/latfit.py
     FRAME OUT.json x,y:spalte,zeile …` (Punktmitten, Spalte 0–95 über alle
     Zellen, Zeile 0–6). Wird mit dem Einrichtungsassistenten überflüssig.
     **Danach prüfen:** Leerzellen 8/13–15 ohne zugeordnete Punkte. Ein
     kleiner Restfehler allein beweist nichts (Befund `sc6`).
   * `propose --grid 0,25,17.78,160`,
   * Leerzellen 8/13–15 leer? Rand frei? Stabilität?
   * **Keinen Lesertest** (Abnahme-Aufstellung).
   * Bestätigen mit `--confirmed-by "Leonhard Hentschke"`.
3. **Ernten:** `touch var/RECORDING_IN_PROGRESS`, dann
   `harvest.py --profile var/diagnostics/ab4-profile --out-dir var/diagnostics/ab4-run --n-steps 30 --hold-s 6 --seed 2026093001`,
   danach `rm var/RECORDING_IN_PROGRESS`. Vorher `grep MemAvailable
   /proc/meminfo` (≥ 3,6 GB).
4. **Sichern und importieren:** tar nach `var-backups`, dann
   `import-harvest.py --harvest var/diagnostics/ab4-run --profile var/diagnostics/ab4-profile --dataset-root var/workbench/datasets`,
   `ab4` mit sha256 in `var/diagnostics/dotmatrix-profile-map.json`
   eintragen (Vorstand sichern als `.vN.json`).
5. **Einmal auswerten:**
   `dotmatrix-eval.py abnahme --dataset-root var/workbench/datasets --profile-map var/diagnostics/dotmatrix-profile-map.json --templates var/dotmatrix/templates-stufe2b-2026-09-29.json --templates-sha256 fc3b44bdc880372a600168218560a3926fa307fe533b2592f7c4c244a89aa75e --groups ab3,ab4 --out var/dotmatrix/abnahme-stufe2b-<datum>.json`.
   Bestanden bei 0 falsch und ≤ 20 % abgelehnt. **Keine Nachbesserung an
   `ab3`/`ab4`**, bei Nichtbestehen gehen sie ins Training.
6. Einzelbilder von `ab3-run` (und `ab4-run`) erst nach Rückfrage löschen.
7. Nach Import und Abnahme die Fortschrittsseite aktualisieren:
   `./.venv/bin/python scripts/docs-progress-data.py`, dann
   `docs-site/assets/data/fortschritt.json` mitcommitten
   ([FORTSCHRITT.md](docs/FORTSCHRITT.md)).

Parallel: Codex setzt „Nacharbeit 1“ im
[Plan Einrichtungsassistent](docs/superpowers/plans/2026-09-29-einrichtungsassistent.md)
um. Danach reviewt Claude und merged.

---

## Verlauf 2026-09-28/29 (erledigt, zum Nachlesen)


Stand: Kamerawechsel fertig und nach `master` gemergt. Aufstellung `sc3`
(Kamera fest auf dem Tisch) ist geerntet und importiert: 46 Proben, ROM-
Gegenprobe je Zeichen 0 Abweichungen. Dot-Matrix 942 Proben in 9
Gruppen (`sc6` 219 mit `sc6b`, `ernte1` 152, `sc5` 114, `ab1` 99, `ab2` 83, `sc4` 79, `auf2` 76, `auf3` 73, `sc3` 47 mit Profil `sc3b`). Die Aufnahmen `sc1`/`sc2`
waren durch Kamerabewegung verschoben und sind verworfen (VALIDATION.md
2026-09-28/29).

1. ~~Kalibrieraufnahme C~~ erledigt am 2026-09-29. Die neue
   `var/calibration/timing-streamcam.json` hat M = 325,9 ms und einen
   Anzeigeversatz von 89,6 ms, aus `sc3-cal-a/b/c` (VALIDATION.md
   2026-09-28/29). Die alte Datei (M = 1225,8 ms) liegt daneben als
   `.v-sc1-20260928.json`.
2. Optional `gate-label` für `sc3-run` mit dem neuen M neu laufen lassen und
   neu importieren. Das bringt mehr Ausbeute. Die jetzigen Labels (mit altem,
   größerem M) bleiben gültig.
3. ~~Zweite feste Aufstellung~~ `sc4` erledigt am 2026-09-29 (79 Proben, 0
   Abweichungen vom ROM). ~~OQ-42~~ ist entschieden (`--train-eligibility
   rom_per_group`), `loo` ist gelaufen. Ergebnis: nie ein falscher Wert,
   `sc4` 79/79 richtig, `ernte1` 91/152, `sc3` 0/46 (Zellen 5–7 über d_max),
   `auf2`/`auf3` alle abgelehnt (VALIDATION.md 2026-09-29).
4. `sc5` erledigt am 2026-09-29 (114 Proben, ROM 0), `sc3` mit korrigiertem
   Profil `sc3b` neu importiert (47). `loo` (c): nie falsch, `sc4` 79/79,
   `sc5` 114/114, `ernte1` 133/152, `sc3` 0/47 (VALIDATION.md 2026-09-29).
5. ~~Kontrastgefälle `sc3`~~: Normierung `ink_per_cell_v1` (Commits
   `021f8ab`, `8908fe4` nach Review). `loo` (e): nie falsch, `ernte1` 152/152, `sc3` 47/47, `sc4`
   79/79, `sc5` 114/114, `auf3` 61/73 (Rest mehrdeutig), `auf2` abgelehnt
   (VALIDATION.md 2026-09-29).
6. ~~Stufe 2 einfrieren~~ erledigt am 2026-09-29 (Code `47b8902`, Vorlagen
   sha256 `4524d6a1…`, VALIDATION.md „Stufe 2 eingefroren“).
7. ~~Abnahme `ab1`/`ab2`~~ am 2026-09-29: **nicht bestanden**, 0 falsch.
   `ab1` 99/99 richtig, `ab2` 0/83 (alle Ablehnungen in Zelle 8: Kante
   einer Glasspiegelung läuft durch die Leerzelle), gesamt 45,6 % abgelehnt
   (VALIDATION.md). `ab1`/`ab2` gehen ins Training.
8. ~~Entwicklungsrunde Spiegelkante~~ erledigt am 2026-09-29: Normierung
   `bg_closing_v1` (Commit `50d68d6`), Hintergrund je Punkt per
   Grauwert-Schließung. `loo` mit 942 Proben: 0 falsch, `ab2` 83/83, alle
   scharfen Gruppen vollständig richtig. `auf2` (unscharf) wird jetzt
   vollständig abgelehnt (vorher 63/76), VALIDATION.md.
   Stufe 2 neu eingefroren (Vorlagen `templates-stufe2b-2026-09-29.json`,
   sha256 `fc3b44bd…`, VALIDATION.md). **Nächster Schritt:** zwei **neue**
   Abnahme-Aufstellungen ernten (`ab3`, `ab4`), dann einmal `abnahme`.
9. ~~Einzelbilder `ab1-run`/`ab2-run`~~ gelöscht am 2026-09-29 (Nutzer-OK).
10. **Einrichtungsassistent** baut Codex parallel nach
    [Plan](docs/superpowers/plans/2026-09-29-einrichtungsassistent.md) im
    Worktree `/home/me-systeme/picam-ai-assist`, Branch
    `feat/einrichtungsassistent`, ohne Kamerazugriff und ohne in `var/` zu
    schreiben. Während jeder Aufnahme liegt
    `var/RECORDING_IN_PROGRESS` (von Claude angelegt und entfernt), dann
    lässt Codex die volle Testsuite ruhen. Claude reviewt und merged.
11. `sc6` erledigt am 2026-09-29 (88 Proben, ROM 0, Stufe 2 liest 88/88).
    `loo` mit 9 Gruppen: 0 falsch in 811 Proben, alle scharfen Gruppen
    vollständig richtig, `ab2` weiter 0/83 (VALIDATION.md „Aufstellung
    `sc6`“). Weitere Trainingsaufstellungen sind möglich, der Engpass
    bleibt aber Punkt 8.

Offene Befunde:
* **SD-Karte:** Eine Aufnahme mit 15 fps belegt 1,3–1,8 GB. Vor jeder
  Sitzung `df -h /` prüfen; alte Einzelbilder nach dem Import löschen oder
  auslagern. Keine Schreiblast (git worktree, Tests, tar) während Aufnahmen.
* **Verworfene Bilder (analysiert 2026-09-29):** Ursache sind Schreibhänger
  der SD-Karte (in `sc6` 14 Stillstände > 0,5 s, bis ~42 s; auch 200-Byte-
  Zeilen in `commands.jsonl` hingen 12–23 s), nicht die Kodierung (JPEG q95
  13 ms/Bild, GIL frei). Karte 7,1 MB/s mit fsync gegen 5,9 MB/s Bedarf.
  Nebenwirkung: `_log_event` im seriellen Thread verlängert GSV-Sendepausen
  → lange `telegrammluecke`. Vorschlag: (A) Aufnahme nach `/dev/shm`, danach
  kopieren; (C) `_log_event` über Writer-Queue; optional (B) Ernte mit 5 fps.
  Mitursache vermutlich Codex: 31 liegen gebliebene Kopien des
  repowise-Marketplace (je ~185 MB) in `~/.codex/.tmp/marketplaces/.staging`,
  am 2026-09-29 gelöscht (dazu Caches, 14 GB frei). Karte ist No-Name
  (`SD16G`, meldet 50 GiB) → Kapazität unklar, `var/` dringend auf ein
  anderes Medium sichern. Danach `sudo fstrim -v /`.
  **Umgesetzt 2026-09-29:** (A) `sync-record.py --staging-root`, von
  `harvest.py` mit `/dev/shm` genutzt, und (C) `commands.jsonl` über einen
  eigenen Schreiber (CHANGELOG). `fstrim` gelaufen, 14 GB frei.
  **Offen:** Probeernte an der Kamera. Prüfen: `frames_dropped_queue_full` = 0,
  weniger `telegrammluecke`, Kopierdauer. Ist der RAM knapp: Ernte mit 5 fps.
* **Glasdetektor (`propose`)** trifft an der StreamCam oft nicht das Glas
  (Blende, Drehung); das Quad kam aus einer Punktgitter-Homographie (Skript-
  Schnipsel im Sitzungsverlauf). Werkzeug dafür in `harvest-setup` einbauen,
  dazu ein Overlay der Abtastpunkte und eine Prüfung der 8-Zeilen-Konvention.
* **M-9 bestätigt:** Fokus-Sweep misst nach großen Sprüngen ein veraltetes
  Pufferbild; Nachmessung (1 s warten, 10 Bilder verwerfen) war jedes Mal
  nötig. Fix in `focus_sweep`.
* M-10 (eingefrorene Belichtung bei anderem Licht) ist ungeprüft.

Zurückgestellt: Werkbank-Kamera an die StreamCam anbinden (heute außer
Betrieb), Replay verliert die Zeitbasis (M-6).

## Sicherung für `var/` einrichten

`var/` gibt es nur einmal (gitignored, Worktree per Symlink). Nach der
Löschung vom 2026-09-25 ist wiederhergestellt, was ging (alle 389 Proben,
Profile, `devices.json`, Rückstellpunkt; `var/rescue-20260925/NOTES.md`).
Verloren: Einzelbilder der Ernte-Aufnahmen, die meisten Diagnosebilder.
`/home/me-systeme/picam-ai/.var_recovered` ist ausgewertet und kann weg.
Lokale Sicherungen (gleiche SD-Karte, nur gegen versehentliches Löschen):
`/home/me-systeme/var-backups/var-20260929-vor-sc3.tar` (Datensatz 389,
Profile, Kalibrierung) und `var-20260928-vor-import.tar`. Zu tun: regelmäßige Sicherung von mindestens
`var/workbench/datasets`, `var/diagnostics/*-profile*`, `var/calibration`
auf ein **anderes Medium**.

---

## Hintergrund Dot-Matrix-Leser

Leser fertig und geprüft (`rom_check_v2`, `auf3` neu bestätigt). Die vorab
festgelegte Messung brach bisher im Durchgang „nur weiche Aufstellungen im
Training" an der Gegenprobe ab; nie ein falscher Wert (VALIDATION.md
2026-09-25, OQ-42). Seit 2026-09-28 gibt es zwei scharfe StreamCam-
Aufstellungen dazu, siehe oben.

---

## Historisch (IMX500 außer Betrieb): Streamstarts sparen (OQ-22)

Am 2026-09-24 blockierte die Brücke beim 8. Start eines Boots; nach Neustart
liefen zwei Starts fehlerfrei. Jede Sitzung so planen, dass sie mit wenigen
Starts auskommt: Kamera nicht verstellen, ScalerCrop aus **einem** Vollbild,
Ernte direkt anschliessen.

---

## Wo wir stehen

* Sollwertkanal (RS232 ASCII vom GSV-2AS) steht seit 2026-09-22.
* Kamera seit 2026-09-25: Logitech StreamCam (IMX500 außer Betrieb).
  Aufnahme, Profil v3, Fokus per Software und Pflicht-Kalibrierung sind
  gebaut und an der Hardware geprüft.
* Task B (Versatz Telegramm ↔ Glas) hatte mit der IMX500 δ zwischen +80 und
  +116 ms und M 499–695 ms. Für die StreamCam wird beides neu gemessen.
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
* **Stand Abend 2026-09-24:** 389 Proben, 301 geerntet aus 98 Zeichenketten
  in 3 Aufstellungen, **Ziffernabdeckung vollständig** (VALIDATION.md,
  „Aufstellung 3"). Vor jeder Ernte die Stichprobe ansehen — so wurde der
  Zwei-Nullen-Fehler gefunden (OQ-41).
* **Schärfe vor jeder Ernte prüfen:** die Schwelle 2,6 px lässt unscharfe
  Aufstellungen durch. Fokus in einer eigenen Sitzung mit Ausschnitt und
  Schärfemesser, Kamera dabei nicht bewegen.
* Weitere Aufstellungen (Winkel, Abstand, Licht) für unabhängige Testgruppen;
  ≤ 7 Starts je Boot, danach Neustart.
* Weitere Ernten mit anderen `--seed`, um die Ziffernlücken je Zelle zu
  schliessen (OQ-39-Nachtrag). Solange die Kamera nicht bewegt wird, gilt
  `ernte1-profile/profile.json` weiter — dann ist jede Ernte **ein** Start.
* Prüfen, warum nur ≈ 28 statt ≈ 39 Bilder je Schritt gelabelt werden
  (`telegrammluecke` 1497): nur die Schreibpause oder auch zu knappe 800 ms?
* Phase 2: Zellen-Klassifikator ist auf dem Feature-Zweig in Tasks 1–7
  implementiert; echte Stufe-1-Messung und Freigabe stehen noch aus.

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
