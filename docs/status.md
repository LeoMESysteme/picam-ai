# Status und Übergabe — 2026-11-12

## Kurzfassung

- **Workbench-Blocker:** Alle offline behebbaren Punkte sind bearbeitet und im gemeinsamen Stand `feat/integration`. Der Pi-Dienst läuft darauf.
- **Leonhards Test am Freitag 2026-11-13:** [windows/bridge/SMOKETEST-2026-11-13.md](../windows/bridge/SMOKETEST-2026-11-13.md).
- **Keine Abnahme:** Die echte Hardware-Bestätigung der Fixes steht aus.

## Laufender Stand

- **Dienst:** `dispread-werkbank-bruecke` (systemd-run `--user`) aus `.worktrees/bruecke-run`, detached auf `feat/integration` 29359e3, seit 2026-11-12 15:52. Adresse `https://100.122.154.35:8082`, Pi-Identität und Kopplung unverändert. Neustartbefehl siehe Projekt-Memory bzw. `systemctl --user show`.
- **Gemeinsamer Branch:** `feat/integration` = EXE-Stand `feat/bruecke-merge` (Session picam-ai-65, UX2) + `feat/bruecke-ui` (Werkbank, Brückentakt, Blocker-Fixes). Weitere EXE-Arbeit baut darauf auf.
- **EXE:** muss Leonhard aus `feat/integration` bauen (`build-test.ps1`). Eine ältere EXE spricht weder Takt noch 460 800 Baud.

## Workbench-Blocker ([WORKBENCH_BLOCKER.md](WORKBENCH_BLOCKER.md))

Triage (`.superpowers/sdd/2026-11-11-gsvmulti-takt/blocker-triage.md`): **keine Regression**. Die Einrichtungsmodule waren in allen Ständen byte-identisch; die Fehler sind alte Lücken, die erst die neuen Aufstellungen sichtbar machten.

| OQ | Stand | Nachweis |
| --- | --- | --- |
| OQ-71 Sackgasse | behoben: FEHLER sperrt Bestätigen, „Neu einrichten“ immer erreichbar, Belege bleiben | Backend-, Node- und Playwright-Tests |
| OQ-74 Fokus | Teilbehebung: ROI aus der LCD-Hinweisbox, Endprüfung nach Neustart (Einrichtung **und** Laufstart), Diagnosebilder | Regressionen auf 7 Paketbildern; Motorverhalten nur am Aufbau prüfbar |
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
- Merge nach `master` erst mit Leonhards OK.
