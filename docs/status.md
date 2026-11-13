# Status und Übergabe — 2026-11-13

## Kurzfassung

- **Abnahme:** Herr Kaulitz hat am 2026-11-13 Werkbank und Ausgabewege (Netzwerk über Brücke, UART über Brücke, UART direkt) offiziell abgenommen. Grundlage: Smoketest und Windows-Prüfung UX2 ([Bericht](quellen/ux2-pruefung-2026-11-13/ux2-bericht.md)).
- **Heute behoben (alle auf `feat/integration`):** EXE-Selbsttest unter Windows, Empfangstest im Format der Session und verlustfrei mit klarem Ende, Kanal 1 hält bei ungültigem Takt (Entscheidung Leonhard), Wiederverbinden nach LAN-Ausfall, Kopplung je Weg, Laufstart gibt UART-Empfang frei, Diagnose mit Zeit und UART-Fehlercodes, Doppelklick-Build `build-test.cmd`.
- **Rahmen/Raster (Codex, von Claude reviewt, auf `feat/integration`):** Fokusprüfung am Laufstart zweiseitig, Band vorläufig 0,95–1,05, außerhalb wird der Start abgelehnt („neu einrichten“). Raster A1 (Leerzellengrenze) und B1 (zweite Unterkantenannahme) liefern 63/65 statt 58/65 Fits, kein alter Fit verloren. Details unten.
- **Kleine Backend-Punkte (Codex, von Claude reviewt, 13.11. nachts, `fix/kleine-backend`):** App zählt geschriebene Werte schon beim COM-Beleg statt erst nach der Pi-Antwort (Ursache 123/124); `details.jsonl` mit Weg/Port/App-Start, aktueller Start getrennt von früheren (`details-previous.jsonl`), Leerlauf beim Export verdichtet; Adapter- und Portwechsel im Journal; dreimal `uart_timeout` beim Verbinden ohne Hardware nur eingegrenzt, Messauftrag OQ-77.
- **Offen:** Fokusband am Aufbau kalibrieren (OQ-74), UART über Brücke mit Rahmenfehlern; EXE-Gestaltungsrunde 3; danach Installer/TUI. Reihenfolge und Details: [TODO.md](../TODO.md).

## Rahmenprüfung und Rasterbestimmung (13.11. abends)

Umsetzung des [Codex-Handoffs](superpowers/handoffs/2026-11-13-codex-rahmen-raster.md), Bericht unter
[quellen/rahmen-raster-2026-11-13/REPORT-codex.md](quellen/rahmen-raster-2026-11-13/REPORT-codex.md).

- **Aufgabe 1, Fokus:** Reale Laufstarts vergleichen die Schärfe nach dem Kameraneustart mit der Einrichtung. Liegt das Verhältnis außerhalb von 0,95–1,05 (vorläufig, aus 14 Laufstarts vom 13.11. mit 0,982–1,026), wird der Start mit Meldung abgelehnt und als `live-start-rejection/1` im Laufordner festgehalten. Fehlt die Referenz oder schlägt die Prüfung fehl, wird ebenfalls abgelehnt. **Bedienerfolge:** auch ein brauchbarer Start kann abgelehnt werden (ein guter Lauf vom 13.11. lag bei 1,418); Abhilfe ist neu einrichten. Zweitversuchsanteil und Maßstab stehen in Status, Inspektor und `session.json`. Residualgrenzen 0,35/0,65 px unverändert.
- **Aufgabe 2, A1:** Randminima im letzten Viertel der Lückenspalte zählen nicht mehr als Belegung der Leerzelle. Gegenprobe mit belegter Leerzelle bleibt abgelehnt.
- **Aufgabe 3, B1:** Erst wenn die Suche endgültig `keine_startlage` liefert, folgt ein zweiter Durchgang mit der Unterkante parallel zur Oberkante; Prüfungen unverändert.

| Standbilder | Baseline | Nur B1 | Nur A1 | A1+B1 |
| --- | ---: | ---: | ---: | ---: |
| ursprüngliche 65 | 58 | 59 | 61 | 63 |
| erweiterte 74 | 64 | 66 | 69 | 72 |

Kein bisheriger Fit verloren, maximale Eckverschiebung 0,52 px. Die acht neuen Fits wurden gegen den seriellen Text und Overlays geprüft; sechs behalten eine ROM-Offsetwarnung. Belege: [Korpus](quellen/raster-recherche-2026-11-13/korpus/README.md), [VALIDATION](VALIDATION.md), [Laborjournal](lab_journal.md).

## Laufender Stand

- **Dienst:** `dispread-werkbank-bruecke` (systemd-run `--user`) aus `.worktrees/bruecke-run`, detached auf `feat/integration` 95d0540 (Rahmen/Raster), seit 2026-11-13 ~19:35. Adresse `https://100.122.154.35:8082`, Pi-Identität und Kopplung unverändert. Neustartbefehl siehe Projekt-Memory bzw. `systemctl --user show`.
- **Gemeinsamer Branch:** `feat/integration` = EXE-Stand `feat/bruecke-merge` (Session picam-ai-65, UX2) + `feat/bruecke-ui` (Werkbank, Brückentakt, Blocker-Fixes). Weitere EXE-Arbeit baut darauf auf.
- **EXE:** muss Leonhard aus `feat/integration` bauen (`build-test.ps1`). Eine ältere EXE spricht weder Takt noch 460 800 Baud.

## Workbench-Blocker ([WORKBENCH_BLOCKER.md](WORKBENCH_BLOCKER.md))

Triage (`.superpowers/sdd/2026-11-11-gsvmulti-takt/blocker-triage.md`): **keine Regression**. Die Einrichtungsmodule waren in allen Ständen byte-identisch; die Fehler sind alte Lücken, die erst die neuen Aufstellungen sichtbar machten.

| OQ | Stand | Nachweis |
| --- | --- | --- |
| OQ-71 Sackgasse | behoben: FEHLER sperrt Bestätigen, „Neu einrichten“ immer erreichbar, Belege bleiben | Backend-, Node- und Playwright-Tests |
| OQ-74 Fokus | Teilbehebung: ROI aus der LCD-Hinweisbox, Endprüfung nach Neustart (Einrichtung **und** Laufstart), Diagnosebilder; seit 13.11. abends zweiseitiges Startband 0,95–1,05 mit Ablehnung | Regressionen auf 7 Paketbildern, Replay 216 Bilder; Band nur vorläufig, am Aufbau kalibrieren |
| OQ-70 einseitige Rahmenbereiche | behoben: Rahmen trotz Kerbe erkannt, sonst klare Meldung | 60/63 Vorschläge identisch, 3 besser |
| OQ-72 Kantenprüfung | geklärt: echte Reflexe, Grenzen bleiben; Meldung nennt Zelle, Lage und Abhilfe | alle Urteile bitgleich |
| OQ-69 Startlage | behoben: Schein-Plus an Glaskanten und Einzelartefakte in Leerzellen; unabhängiges Review mit Auflagen, erfüllt | 4 Fehlerbilder lösbar (2 danach berechtigt Kanten-FEHLER), 77/77 alte Fits erhalten |
| OQ-73 Trägheit, OQ-75 Ausfall 7 s | offen, nur am Aufbau messbar | Smoketest notiert Uhrzeiten |

## Weitere Arbeit seit 11.11.

- **GSVmulti-Vierkanal-Takt:** Telegramm `%wert;gültig;takt;zeit` mit festem Takt bis 10 Hz; ungültig = `gültig 0`, Kanal 1 hält seit 13.11. den letzten gültigen Wert (vorher Fehlwert `99999999.0`, Spec 3.5). Spec und Plan unter `docs/superpowers/{specs,plans}/2026-11-11-gsvmulti-takt-vierkanal*`.
  - Pi und alle drei Wege umgesetzt (B1, B2), Werkbank mit Formatwahl (U1), EXE-Vorgabe Vierkanal.
  - Brücken-UART auf 460 800 Baud.
  - Belegt sind nur die GSVmulti-Versuche vom 11.11.; ein Ende-zu-Ende-Lauf mit EXE steht aus.
- **Nachführung:** strengere Auswahl der Rahmenbereiche und automatische Stilllegung dauerhaft unstimmiger Bereiche mit Schutzprobe (TB). Zweifach reviewt, Testfreigabe.

## Prüfstand 2026-11-12 (`feat/integration` vor dem Smoketest-Commit)

- **Pi** mit `DISPREAD_DEV_DATA`: 4151 bestanden. 2 Brückentests wackelten unter Volllast, einzeln dreimal grün.
- **Windows** 641, **Node** 273, **Playwright** 64/65. Der eine Fehlschlag ist der bekannte Wackler „UART direkt ohne Haken“, einzeln grün. **ruff** sauber.

## Offen

- Hardware-Bestätigung aller Fixes, Fokusverhalten beim Kameraneustart, OQ-73 und OQ-75.
- EXE-Oberfläche für Taktzähler und Format-Abgleich (picam-ai-65).
- Merge nach `master`: freigegeben am 13.11. (autonomer Plan), erst nach grüner voller Suite und ohne Wiki-/Theme-Dateien der Wiki-Session anzufassen.
