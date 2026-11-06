# Status und Übergabe — 2026-11-06

## Aktueller Auftrag

Leonhard hat Entwurf und Ausführung der Windows-Brücke freigegeben.
Codex übernimmt Backend, Paketierung und testbare Vorarbeit mit Subagents.
**EXE-GUI und sämtliche sichtbaren Workbench-Anpassungen bleiben Claude
vorbehalten**, einschließlich Anleitung je Weg und Verbindung/Bereitschaft.
Die konkrete [Übergabe](superpowers/handoffs/2026-11-06-windows-bruecke-claude.md)
wird fortgeschrieben; noch keine Nachricht an einen anderen Chat versandt.

Isolierter Worktree:
`/home/me-systeme/.codex/worktrees/windows-bridge-core/picam-ai`, Branch
`codex/windows-bridge-core`, Basis `ea29e44`. Der vorhandene Redesign-Worktree
mit fremden Änderungen und laufendem Dienst bleibt unberührt. Kein Merge,
Deployment, Hardwareeingriff oder neue Paketinstallation vorgenommen.

## Technischer Lieferstand

| Teil | Stand und geprüfte Grenze |
| --- | --- |
| P1 | Strikter v2-Vertrag und begrenzter Ausgabekern, 70 relevante Tests; Taskreview sauber. |
| N1 | Isolierter Build/Probe mit an Freigabedaten gebundenen Hashes; 79 Tests inklusive Bestand, ein echter Windows-Test hier übersprungen; Reviewkorrekturen bestätigt. |
| N2 | PnP-/USB-Erkennung und Portpaaradapter, 48 Tests; fehlende Seriennummer fordert Auswahl; echter Treiberprovider bleibt unverifiziert und gesperrt. |
| N3 | Originale UCF/TXT samt Archivprovenienz und Inspektion, 17 Tests; unbekannte Dateiversion, keine freigegebenen Änderungsfelder, automatischer Export blockiert. |
| P2 | Hardwaregebundene Identität, portable Zertifikats-/Signaturprüfung, Einmalangebote und widerrufbare Tokens, lokale CLI; 26 gezielte Tests nach Reviewkorrekturen. |
| P3 | Profil/Operatoraktionen, gekoppelter WSS-Zugang und begrenzte Discovery; 163 relevante Tests, 2 bestehende Fixture-Skips nach Korrekturen; Nachprüfung sauber, echter Hub folgt. |
| W3 | Fortsetzbarer Installer-/Updatekern, 47 fokussierte Tests nach Auswahlkorrektur; Nachprüfung sauber. Native Installation und Release-Signierung ausstehend. |

Commitfolge bisher: `71f01cf` (P1), `4077cff` (N2), `c90a350` (N1),
`e3b67e1`/`3887907` (N3/Doku), `6e9e2e6` (P2); W3 `8b97697`. P3 wird mit diesem Status versioniert.
Die technische Umsetzung ist keine fertige EXE und keine Produktabnahme.
Die [Pläne](superpowers/plans/2026-11-06-windows-bruecke.md) unterscheiden
lokal geprüften Code und reale Abnahmeschritte.

Nächste Backend-Aufgaben nach P3-Nachprüfung: gemeinsamer
Hub mit Lease/UART und Live-Ausgabenaht (P4), Windows-Verbindung/geschützter
Speicher (W1), dauerhaftes Übergabejournal und Worker (W2), Backendintegration
(G1). GUI und sichtbare Workbench-Integration folgen bei Claude.

Vor Live-Integration: 493 bestehende Tests bestanden, einer scheitert im
frischen Worktree an der nicht versionierten Laufzeitdatei
`var/dotmatrix/templates-stufe2c-2026-09-30.json`. Isoliert reproduziert und
über den tatsächlichen Setupfehler eingegrenzt; kein Brückenregressionsbeleg.
Der betreffende Fake-Setup-Test soll seine Template-Abhängigkeit selbst
injizieren. Kein grüner Gesamtlauf behauptet.

## Offene externe Gates

N1: echte Windows-11-x64-Qualifikation ohne Python sowie neben Python 3.7,
passende Qt/Python-Locks und tatsächlicher Freeze. N2: konkretes signiertes
Treiberpaket, HVCI/PnP, Besitz und bidirektionaler Portnachweis. N3: genaue
GSVmulti-/Dateiversion, kontrollierte Feldänderungen und echter Import-/
Wiederöffnungs-/Empfangsroundtrip. Signierung, Release-Kanal und Windows-Runner
sind gesonderte Voraussetzungen. Keine erfundene Sessiondatei oder erfolgreiche
Installation als Ersatz. OQ-53 und externe Gates bleiben offen; OQ-62/OQ-64 in Arbeit, Releasepolitik OQ-65 offen.

DUT-Werte über Windows-Brücken bleiben strukturell gesperrt. Erlaubt sind
synthetische Demos mit provisional=true und ohne Zeitaussage. COM-Schreiben
belegt keine Annahme durch GSVmulti. Die getrennte direkte UART-Ausgabe
behält den bestätigungspflichtigen Prototypstatus. Testläufe senden nichts.

## Vorheriger Laborstand

Erster T13-Lauf `live-20261106T112527Z/run-01` beendet und
[ausgewertet](quellen/werkbank-t13-2026-11-06.md): 22:38 min,
39.886 Datensätze, 75,79 % VALID; 0 Abweichungen unter 10.773 eindeutig
vergleichbaren Referenzfreigaben, 19.451 im Wechsel-Schutzfenster unentschieden,
5 ungedeckt. Keine vollständige T13-Abnahme. Letzte 8284 Bilder verwendeten
den zweiten Fit, 6605 akzeptiert; kein blockierter Lauf. Physischer Grund
der dauerhaften Erstfit-Ablehnung offen (OQ-63), Diagnosebilder fehlten.

Beobachter beendet; bisherige Werkbank bleibt unter
`https://100.122.154.35:8082/live` zum Ansehen aktiv,
Dienst `dispread-werkbank-t13.service`. Vor neuer Abnahme Diagnose/HUD planen
und mindestens 30 Minuten mit dokumentiertem Vorschau-/Lastvergleich prüfen.
Vorherige UI-Fertigstellung: 229 Node- und 46 Workbench-Playwright-Tests
bestanden. Wiki-Gesamtlauf hatte einen Roadmap-Fehler; isoliert danach 3/3
bestanden, deshalb keine durchgehend grüne Wiki-Gesamtabnahme.

UART-Versuch zurückgestellt, Pi-Demosender beendet. Windows zuletzt Python
3.15 / .venv315, COM6 FTDI → Brücke COM5 → GSVmulti COM4. Nur GND/RXD
bestätigt; TXD-Rückleitung zum physischen Pi-Pin 10 fehlt. Keine erfolgreiche
UART-Brückenübergabe behauptet. Vor Fortsetzung Verdrahtung bestätigen.
Historische Windows-Demobelege vom 04.11. stehen in
[VALIDATION](VALIDATION.md) und [Protokoll](GSVMULTI_PROTOCOL.md).

Nach T13 bleiben Aufbewahrung/Export (OQ-60), Nachberechnung (OQ-59) und
Altcontroller-Bestandsaufnahme (OQ-61) gemäß [TODO](../TODO.md) spätere Arbeit.
