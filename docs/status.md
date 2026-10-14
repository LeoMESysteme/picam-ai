# Status — Stand 2026-10-14

Dieser Snapshot wird zum Sessionende überschrieben. Verlauf:
[Changelog](../CHANGELOG.md) und [Projektgeschichte](project_history.md);
Arbeitsliste: [TODO.md](../TODO.md).

## Messpfad live

Auf `feat/messpfad-live` sind Tasks 1–11 samt Final-Review-Korrekturen
gebaut. `dispread serve` hält die Logitech StreamCam über `CameraOwner`
für seine gesamte Laufzeit. `/live` führt durch Einrichtung, namentliche
Bestätigung und Messlauf mit Dot-Matrix-Leser; der Wert trägt
VALID, TRANSITION, UNREADABLE oder STALE. Die alte Werkbank bekommt
gedrosselte Bilder vom selben Owner; Kamerabedienung erfolgt nur über `/live`.
Andere Kameraprozesse, etwa Harvest-Skripte, bekommen währenddessen „belegt“.
Port 8080 ist auf diesem Pi durch MEhub belegt; die Werkbank lief mit
`dispread serve --port 8081`.

Einrichtung und Profil liegen unter `var/live/<sitzung>/`, einschließlich
`profile.json` und `confirmation.json` nach Bestätigung. Jeder Lauf schreibt
`records.jsonl` und `session.json` unter `var/live/<sitzung>/run-NN/`.
Lokal stehen `dispread live status|setup|stop|camera` zur Verfügung;
Bestätigung und Laufstart bleiben in der angemeldeten Oberfläche (Konzept §4).
Ohne Anmeldung führt `/live` zu `/login?next=/live` und danach zurück.

## Einrichtung am Aufbau, 2026-10-14

StreamCam frontal auf dem GSV-2AS / Displaytech 161A, Glas etwa 720 px breit,
Raumlicht, Zellentext seriell gelesen. Vor N7: **0/4** Einrichtungen,
`keine_startlage` sowie einmal 2j FEHLER auf einem falschen Raster.
Nach N7: **3/3** Vorschläge, Dauer **47/55/49 s**, jeweils Gesamt-WARNUNG:
Raster-Ersatzmaß WARNUNG wie bei `sc7`, Rasterversatz OK, Gegenlesen OK.
Das ist **kein formaler Abnahme-Lauf** und noch kein Messlauf.

Die Nacharbeit vom 2026-10-14 umfasst Fokus per Bergsteigen (5 statt 38
Messungen am Aufbau), Mittelung von acht Bildern je Standbild und bis zu
drei Suchversuche. Die Werkbank prüft Stabilität über 15 s; die Harvest-CLI
bleibt bei 30 s. `setup/cell-text.json` und `setup/failure.json` sichern
Zellentext und Fehlerdiagnose. Die Live-Oberfläche hat eine Playwright-Prüfung
(`npx playwright test -c playwright.live.config.ts`; vom Controller geprüft).

N7 behebt die an den Standbildern vom 2026-10-14 gefundene Ursache: Feste
0,7-px-Glättung erzeugte 1–4 zufällige Minima je scharfem LCD-Punkt;
ein um eine Zeile falsches Raster wurde angenommen und erst von 2j abgefangen.
Punkterkennung glättet nun in Punktgröße, `_MAX_RMS_ROWS` sinkt von 0,25
auf 0,15, die Startsuche ist gestuft. 2j und Gegenlesen bleiben maßgeblich.
Belege: [VALIDATION.md](VALIDATION.md#messpfad-live-einrichtung-2026-10-14),
[Live-Plan](superpowers/plans/2026-10-12-messpfad-live.md) und
[Nacharbeitsplan](superpowers/plans/2026-10-14-messpfad-live-nacharbeit.md)
mit den jeweiligen SDD-Ledgern (Final-Review/R13 und Bench-Re-Test).

## Grenzen und nächster Schritt

Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — andere Lichtquellen und Geräte nicht geprüft.
Die Leser-Abnahme 3 vom 2026-09-30 (215/215 richtig) und der `sc7`-Lesetest
(111/111 richtig) bleiben frühere Belege; sie ersetzen den Live-Messlauf nicht.
Serielle Ausgabe an GSVmulti fehlt weiterhin
([OQ-07](open-questions.md#oq-07)). ECC-Tracking bei Wertwechseln ist ungemessen.
`raw_text` enthält die geparste Zahl, nicht die 16 Displayzellen.
Ein stillstehender Stream beendet die Sitzung erst nach dem OpenCV-Select-
Timeout (etwa 10–20 s), nicht nach 2 s; die Wertanzeige wird zuvor STALE.
Die `JsonlSink`-Rotation würde nach etwa 7 h alte Auditgenerationen verwerfen.

Bestätigung durch die bedienende Person, Messlauf ≥ 10 min, Wertwechsel mit
`set norm` und 2 s Abdeckung stehen aus; vorgesehen für **2026-10-16**.
Danach Statuszählungen, Soll-/Lesewerte, Bildlücken und Leserate auswerten,
insbesondere `tracking_lost` und `track_score` bei Wertwechseln (R13).
`track_score` 0,0 bei `ecc_diverged` gesondert als Divergenz zählen.
Erst die Aufbauzahlen entscheiden über eine vom Anzeigewert unabhängige
Trackerregion. Ergebnis in VALIDATION und Laborjournal eintragen.

Weitere Aufgaben bleiben die 7-Segment-Bereinigung der alten Seite,
Audit-Aufbewahrung, andere Lichtquellen/Geräte/Einheiten und die Importprüfung
bei schrägem Blick. `var/` braucht weiterhin eine Sicherung auf anderem Medium;
ältere Hinweise zur knappen SD-Karte stehen in TODO und Laborjournal.
