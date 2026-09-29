# TODO — Stand 2026-09-29

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
`docs/status.md` ist die erste Datei. Diese hier ist die Arbeitsliste daneben.

---

## Zuerst (2026-09-29): Kalibrierung C, dann `loo`

Stand: Kamerawechsel fertig und nach `master` gemergt. Aufstellung `sc3`
(Kamera fest auf dem Tisch) ist geerntet und importiert: 46 Proben, ROM-
Gegenprobe je Zeichen 0 Abweichungen. Datensatz 435 Proben, geerntet in 4
Gruppen (`ernte1` 152, `auf2` 76, `auf3` 73, `sc3` 46). Die Aufnahmen `sc1`/`sc2`
waren durch Kamerabewegung verschoben und sind verworfen (VALIDATION.md
2026-09-28/29).

1. **Kalibrieraufnahme C mit dem Nutzer** (Stimulus von Hand, 180 s) in `sc3`,
   **ohne Kamera oder Tisch zu berühren**:
   `sync-record.py --source camera --camera-settings var/diagnostics/sc3-profile
   --frame-rate 15 --image-format jpg --duration 180 --output var/diagnostics/sc3-cal-c`.
   Vorher mit `import-harvest`-Ausrichtung oder ORB prüfen, dass die Kamera
   noch zum `sc3`-Profilbild passt. Dann `display-offset.py --profile
   var/diagnostics/sc3-profile` auf `sc3-cal-a/b/c` und
   `timing-calibration.py` → neue `var/calibration/timing-streamcam.json`.
   Die jetzige (M = 1225,8 ms) stammt aus verschobenen Aufnahmen und ist
   vorläufig. A und B sind schon aufgenommen und ausgewertet: δ +99/+97 ms,
   σ 6/2 ms, M 289/271 ms (VALIDATION.md 2026-09-28/29). In A/B wurden viele Bilder
   wegen voller SD-Karte verworfen; bei Bedarf A/B wiederholen.
2. Mit neuem M ggf. `gate-label` für `sc3-run` neu laufen lassen (nur, wenn M
   deutlich kleiner wird: mehr Ausbeute; größeres M → neu labeln Pflicht).
3. Eine zweite feste Aufstellung (anderer Winkel/Abstand) ernten, damit zwei
   scharfe Gruppen vorliegen. Reflexe erst in voller Auflösung prüfen.
4. **OQ-42 entscheiden** (Nutzer), dann `dotmatrix-eval.py loo`.

Offene Befunde:
* **SD-Karte:** Eine Aufnahme mit 15 fps belegt 1,3–1,8 GB. Vor jeder
  Sitzung `df -h /` prüfen; alte Einzelbilder nach dem Import löschen oder
  auslagern. Keine Schreiblast (git worktree, Tests, tar) während Aufnahmen.
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
