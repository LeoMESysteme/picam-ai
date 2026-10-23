# TODO — Stand 2026-10-21

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen stehen
in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
Diese Arbeitsliste kommt zuerst, danach `docs/status.md`.

---

## Stand 2026-09-30 nachmittags: Abnahme 3 bestanden

Der Dot-Matrix-Leser, Stufe 2 `templates-stufe2c-2026-09-30.json`
(`6f20dec4…`), hat Abnahme 3 über die neuen Aufstellungen `ab5` (frontal,
gedreht) und `ab6` (schräg von links) **bestanden**:
* 215/215 Proben richtig, 0 falsch, 0 abgelehnt,
* Obergrenze der Fehlerrate 3,5 % (85 Plateaus).

Details und Einschränkungen: VALIDATION.md 2026-09-30.

**2026-10-01:** Der Einrichtungsassistent ist gemergt und lief bei `sc7`
(frontal, nah) im ersten echten Kameralauf ohne Hilfe durch.
* `stufe2c` liest `sc7` mit 111/111 richtig, 0 falsch, 0 abgelehnt.
* Das ist kein formaler Abnahme-Lauf (VALIDATION.md 2026-10-01).
* Der erste Versuch `sc7a` (von oben) scheiterte an zwei falschen
  Ablehnungen. Nacharbeit 5 behebt sie und ist seit 2026-10-12 in
  `master`.

Offen:
1. **Einrichtungsassistent:** am 2026-10-01 gemergt; der erste echte
   Kameralauf (`sc7`) bestand. **Nacharbeit 5** ist am
   2026-10-12 nach `master` gemergt (offline geprüft): `sc7a`
   findet eine Startlage, schwache Punktschatten zählen nicht mehr als
   Cursor. Offen: eine Aufstellung leicht von oben
   mit `assist` gegenprüfen. Schräge Aufstellungen (wie `ab4`/`ab6`)
   lehnt `assist` noch ab (`startlage_mehrdeutig`/`keine_startlage`), die
   richtet man weiter von Hand mit `profile-regrid.py still` ein.
   Spätere Kleinigkeiten N1–N3 stehen im Plan unter Nacharbeit 4.
2. **Anbindung an den Messpfad** (Variante B): gebaut und am 2026-10-21 am
   Aufbau gelaufen (StreamCam über `CameraOwner`, Einrichtung, Bestätigung
   und Lauf auf `/live`, JSONL-Audit je Lauf, optionale serielle Referenz).
   Stand und nächste Schritte unter „Messpfad live (aktiv)“ unten; Zahlen
   in [VALIDATION](docs/VALIDATION.md#messpfad-live-langlauf-2026-10-21).
   Kein formaler Abnahme-Lauf. Weiter offen:
   * **Folgeschritte:** serielle Ausgabe an GSVmulti (OQ-07), alten
     7-Segment-Lesepfad samt ungenutzter Geometriehelfer entfernen und
     dessen CPU-Last im Messlauf erfassen. Der Werteplan-Lauf vom
     2026-10-21 zeigt nun Trackingverlust bei großen Wertwechseln (R13,
     [OQ-26](docs/open-questions.md#oq-26)); Abschlussdiagnose und eine
     vom Zifferninhalt unabhängige Trackerregion sind damit zu bearbeiten.
   * **Gebaut R13-16:** Live-Audits ohne Generationenrotation je Lauf;
     Platzprüfung und manuelles Aufräumen mit Vorschau (Kapitel 10).
     SD-Dauerbetrieb und Platzplanung vor längeren Läufen praktisch prüfen.
   * **Zurückgestellte Bedienpunkte:** Vorschau kann auf dem letzten Bild
     einfrieren; Streamstillstand beendet erst nach OpenCV-Select-Timeout
     (etwa 10–20 s) statt 2 s. Kamera-Neuverbindung nach Einrichtung behält
     Setup-Regler; Laufstopp lässt die Kamera für Vorschau an. Ein
     `tracking_lost`-Hinweis kann den Endfehler auf der Seite verdecken
     (in `session.json` erhalten). Bei tatsächlich hängendem Leser kann
     Laufstopp blockieren; dann Serverneustart nötig. Kamerastatus kann
     nach einem fehlgeschlagenen Neustart noch alte Quelldaten zeigen.
     Fehler beim Schreiben von `confirmation.json` lassen den Vorschlag
     zur erneuten Bestätigung stehen; diese Rückmeldung verbessern.
   * Freigabe bleibt auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V
     begrenzt. `raw_text` enthält die geparste Zahl, nicht 16 Zellen.
     `serve` hält die StreamCam bis zum Serverende (Harvest meldet „belegt“).
3. **Import bei schrägem Blick:** `zellen_inkonsistent` verwirft viel
   (`ab6` 42 %). Die Importprüfung vergleicht über alle Positionen hinweg.
   Prüfen, ob ein Vergleich je Position oder Halbzeile die Ausbeute hebt,
   ohne falsche Labels durchzulassen.
4. **Punktraster-Anpassung `latfit.py`:** lag bei jeder neuen Aufstellung
   0,2–0,4 Punktspalten daneben, `profile-regrid.py still` korrigiert das.
   Der Einrichtungsassistent (seit 2026-10-01 gemergt) prüft das mit 2j.
5. **Andere Lichtquelle** und weitere Geräte bzw. Einheiten sind nicht
   geprüft.
6. `auf3`: Das korrigierte Profil ist nicht bestätigt, niedrige Priorität.
7. **SD-Karte:** Das Codex-Leck in `~/.codex/.tmp/marketplaces/.staging`
   (etwa 200 MB alle 15 min, dazu I/O-Stillstände) ist seit 2026-10-21
   abgestellt: Ursache war der Block `[marketplaces.repowise]` in
   `~/.codex/config.toml` (entfernt, Sicherung `config.toml.bak-2026-10-21`).
   Tauchen wieder Kopien auf, prüfen, ob der Block zurück ist. `var/` hat
   weiterhin keine Sicherung auf einem anderen Medium.
8. Die Einzelbilder von `ab5-run`/`ab6-run` (je 1,6 GB) erst nach Rückfrage
   löschen.
9. **Projekt-Tour** (Doku): seit 2026-10-12 alle sechs Kapitel fertig.
   Pflege: Ändert sich gezeigtes Verhalten, Text und Szene
   (`docs-site/assets/tour*.js`) zusammen anpassen (AGENTS.md).
   Seit 2026-10-13 stehen 21 Szenen auch als Abbildung in Doku-Seiten:
   Verträge, Messpfad, Zeitstempel, Daten und Abnahme sowie die
   Anleitungskapitel 01, 02, 04, 07, 08 und 10. Das Glossar bleibt ohne,
   weil seine Einträge als kurze Vorschau auf anderen Seiten erscheinen.

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

Der [Plan Einrichtungsassistent](docs/superpowers/plans/2026-09-29-einrichtungsassistent.md)
ist mit dem Merge am 2026-10-01 abgeschlossen.

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

## Wo wir standen (2026-09-25)

Dieser Abschnitt hält den früheren Übergang zur StreamCam fest. Der
aktuelle Stand folgt unter „Messpfad live“; die StreamCam-Kalibrierung
vom 2026-09-29 ist inzwischen dokumentiert.

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

### Messpfad live (aktiv)

**Stand 2026-10-21 abends:** Der Messpfad läuft am Aufbau. Lesesperre,
schwankende Ziffern, Licht-Hinweis/Toleranz, Leser mit ~30 Bildern/s,
TRANSITION bei Wertwechseln und Referenzaufzeichnung sind gebaut und in
`master` (Plan
[2026-10-21 Tempo und Abschluss](docs/superpowers/plans/2026-10-21-messpfad-live-tempo-und-abschluss.md)
erledigt). Drei Läufe mit serieller Referenz, alle **0 Fehllesungen**:
streng 45 s (0/715), Toleranz ×1,8 5,6 min (0/6630), streng 12 min (0/8979,
29,8 Bilder/s, Wechsel im Median nach 232 ms); siehe
[VALIDATION](docs/VALIDATION.md#messpfad-live-langlauf-2026-10-21).

**Nächste Schritte, in Reihenfolge:**

1. **Nachführung bei großen Wertwechseln bearbeiten (R13)**
   — [freigegebener Plan](docs/superpowers/plans/2026-10-21-r13-strukturstabile-nachfuehrung.md),
   Umsetzung ab **2026-10-23** vorgesehen, noch nicht begonnen.
   ([OQ-26](docs/open-questions.md#oq-26)): Strenger Werteplan-Lauf
   `live-20261021T151835Z/run-01` abgeschlossen: 806 s, 0/11 137 Fehllesungen,
   aber 8074 Trackingverluste; bei Faktor 2 und 5 in stabilen
   Referenzfenstern kein VALID. Rückstellung bestätigt. Nachführung
   unabhängig vom Zifferninhalt untersuchen und große Sprünge erneut
   prüfen. Die berichtete Abdeckung ist zeitlich nicht eindeutig
   zuordenbar. [Zahlen](docs/VALIDATION.md#messpfad-live-werteplan-2026-10-21).
2. **~~Testlauf-Sicherung und Zeitbasis-Bezeichnung klären~~ (erledigt 2026-10-23):**
   [OQ-44](docs/open-questions.md#oq-44) ist umgesetzt: Gate-Freigaben werden
   vor dem Test-Audit als `UNREADABLE` ohne `value` unterdrückt;
   [OQ-45](docs/open-questions.md#oq-45) ist erledigt 2026-10-23:
   Ergebniszeiten aus `time.monotonic_ns()` tragen für jede Quelle
   `HOST_MONOTONIC`, Aufnahmezeitbasen bleiben unverändert. BOOTTIME nur
   über `to_boottime_ns` mit Sessionversatz und Suspend-Prüfung;
   alte Auditdateien behalten ihre Labels. Testlaufdaten bleiben für
   Messungen gesperrt.
3. **Toleranzlauf ≥ 10 min mit Werteplan** (siehe unten), mit der
   bedienenden Person; der Werteplan schreibt `set norm` und stellt danach
   zurück. Danach entscheiden, ob die Toleranz als validiert gilt (für
   diese Aufstellung).
4. **Serielle Ausgabe an GSVmulti** ([OQ-07](docs/open-questions.md#oq-07)):
   wartet auf eine Protokollbeschreibung von GSVmulti; `protocol/gsv_ascii`
   wirft bis dahin absichtlich. Kein Protokoll erfinden.
5. **UI/UX-Überarbeitung der Werkbank** (nicht prod-ready), einschließlich
   schnellerer Vorschau (Seite holt Bild und Status nur alle 0,5 s) und der
   zurückgestellten Bedienpunkte unter „Offen“ Punkt 2.
6. **Aufräumen im Messpfad:** alten 7-Segment-Lesepfad entfernen.
   Live-Audit ohne verlustbehaftete Rotation ist seit R13-16 gebaut.
7. **Rest aus Review Task 5** (nicht blockierend): `DEFAULT_RESTORE_POINT`
   wird relativ zum Arbeitsverzeichnis aufgelöst. Das Snippet in Anleitung
   Kapitel 10 liest Port/Baud seit dem Wiki-Abgleich aus dem Rückstellpunkt.

**Speicherbudget für den Betrieb (neu 2026-10-23):** Im Unternehmen läuft das
Werkzeug voraussichtlich auf einem Pi 5 mit 64-GB-SD-Karte, ohne SSD.
Messläufe deshalb weiter auf der SD-Karte testen. **Gebaut R13-16:**
Platzprüfung vor Einrichtung und Laufstart (2 GB Reserve, mit Diagnose
zusätzlich 0,6 GB), Status/Seite mit freiem Platz und Warnung unter 5 GB,
Diagnosebilder standardmäßig aus in Seite und API, vollständige Auditdatei
je Lauf ohne Generationenverlust und opt-in
`dispread live aufraeumen --aelter-als <tage> [--nur-diagnose] [--ausfuehren]`
mit Größen und Vorschau als Vorgabe. Keine automatische Löschung;
Profile/Setup und laufende Läufe bleiben geschützt. Ein 10-min-Lauf braucht
etwa 10 MB Audit, mit Diagnosebildern bis zu 0,6 GB zusätzlich.
**Offen:** längeren Betrieb auf der Produktions-SD praktisch validieren
und benötigte Daten vor manuellem Aufräumen sichern.
Für die Entwicklung kann eine NVMe-SSD (500 GB, vorhanden) Aufnahmen,
Datensätze und die fehlende `var/`-Sicherung aufnehmen, aber nicht die
Messläufe selbst.

**Pi-Betrieb (für ruhige Messläufe):**

* Die Forgejo-CI läuft auf demselben Pi. Jeder Push nach `master` startet
  Build und Playwright mit headless Chrome; am 2026-10-21 16:13–16:22 gab
  das 20–44 s Stillstand, SSH-Abbrüche, kurzes STALE auf `/live` und zwei
  Playwright-Zeitüberschreitungen (lokal danach 29/29 grün). **Nicht während
  eines Messlaufs nach `master` pushen.** Mittelfristig CI auf einen anderen
  Rechner oder während Läufen pausieren (Entscheidung der Person).
* Nächtlicher Lauf `maintain`: scheiterte 2026-10-19 bis 2026-10-21 früh,
  seit 2026-10-21 15:12 wieder grün (22. und 23.10. erfolgreich, letzter
  Codex-Lauf ohne Befund, Doku-Build ok; `sudo picam-codex-logs`). Ursache der
  drei Fehlschläge nicht mehr nachvollziehbar (keine Schritt-Logs per Token).
* Playwright-CI für `master` `109d360` (Roadmap-Karte, 2026-10-23) fehlgeschlagen,
  Build ok. Laut Wiki-Sitzung wahrscheinlich Last (Roadmap-Rad- und
  Tour-Abbildungstests wackeln unter Last); ihr Branch `feat/wiki-geruest`
  ersetzt Roadmap-Code und -Tests, daher nicht separat angefasst.
* Kein persistentes Journal; der Hänger 2026-10-21 14:08 ist deshalb nicht
  belegbar. Aktivieren:
  `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald`.
* Haupt-Checkout `~/picam-ai`: beim Wiki-Abgleich auf `master`
  (`339703d`). Der zuvor dokumentierte WIP liegt auf
  `wip/haupt-checkout-2026-10-21` (`a55ab1f`); dessen Integration gesondert
  prüfen. Uncommittierte Messdokumente der Person erhalten.
* Vier gemergte Remote-Branches können weg (`feat/einrichtungsassistent`,
  `feat/task-b-versatz-normierung`, `fix/docs-pin-pymdown`,
  `ocr-selbstkalibrierung`); MEM-6 (Pi-Hauswart, auf origin, nicht gemergt)
  entscheiden.

**Offen seit 2026-10-21: angepasste Lesetoleranz validieren.** Die Werkbank
bietet bei Gegenlesen WARNUNG eine Toleranz bis ×2,0 an (1,25 × gemessener
Abstand, nur mit seriellem Referenzwert, Werte als „nicht validiert“
markiert). Belegt: Einrichtungsstandbilder stimmen mit der Referenz,
synthetischer Sweep mit ×2,0 ohne falschen Wert, und ein erster Live-Lauf
×1,8 mit Referenz (`live-20261021T143419Z`, 5,6 min, 0 Fehllesungen bei 6630
entschiedenen VALID, 8978 Toleranzbilder; [VALIDATION](docs/VALIDATION.md#messpfad-live-toleranzlauf-2026-10-21)).
Ein strenger Lauf über 12 min (`live-20261021T144605Z`, 0/8979) belegt den
Dauerbetrieb, zählt aber nicht für die Toleranz.
Es fehlen ein Toleranzlauf ≥ 10 min mit bestätigtem Werteplan, eine zweite
Aufstellung und jeweils ein Abgleich mit
`PYTHONPATH=src ./.venv/bin/python scripts/live-reference-eval.py <run-dir>`
(Fehllesungen, Wechselanteile, Verzögerung und `tolerance_frames` in
`session.json`; siehe [Anleitung Kapitel 10](docs/anleitung/10-kamera-livevorschau.md#referenzaufzeichnung-und-abgleich)). Bis dahin keine Toleranz-Läufe für echte Kalibrierungen.

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
