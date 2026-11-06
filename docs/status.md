# Status und Übergabe — 2026-11-06

## Auftrag und Arbeitszweig

Windows-Brücke gemäß freigegebenem Entwurf: Codex erledigt den technischen
Kern; **EXE-GUI und sichtbare Workbench-Anpassungen übernimmt Claude**.
Konkreter Einstieg: [Claude-Übergabe](superpowers/handoffs/2026-11-06-windows-bruecke-claude.md)
mit APIs, Bedienaufgaben und offenen Nachweisen. Kein anderer Chat wurde angeschrieben.

Worktree `/home/me-systeme/.codex/worktrees/windows-bridge-core/picam-ai`,
Branch `codex/windows-bridge-core`, Basis `ea29e44`. Alter Redesign-Worktree
und laufender Labordienst bleiben erhalten. Kein Merge/Push, Deployment,
Hardwareeingriff oder neue Paketinstallation.

## Technischer Lieferstand

P1–P4: strikter v2-Vertrag, begrenzter Ausgabekern, hardwaregebundene
Pi-Identität und widerrufbare Kopplung, TLS-/WSS-Routen, Discovery, exklusiver
Hub und signierter UART. Identitäts-TLS und Listener werden ausdrücklich
aktiviert; hier keine Dienstumstellung.

W1/W2: gepinntes WSS, UART-Proof vor Zugangsdaten, DPAPI-/Zertifikatsbindung,
Readiness, dauerhaftes SQLite-COM-Journal, atomare Schreibzulassung und
SID-Instanzschutz. G1 integriert tatsächlichen Manager/Worker/Hub/SQLite
über lokales TLS mit Fake-COM. Gewöhnlicher Kanalverlust wartet auf die neue
validierte Generation; der Manager allein besitzt Backoff und Wiederanlauf.
Keine alten Werte, ACKs oder automatischen Demostarts. Ordentliches Laufende
hält die Verbindung bereit; Stop, Auditfehler und unklare Übergaben bleiben
terminal. COM und Konfiguration wechseln nicht.

N1–N3/W3: Build-/Runtime-Probe, USB-/Portpaaradapter, Original-UCF/TXT-
Provenienz und portabler Installer-/Updatekern vorhanden. Native
Deployment-/Treiberprovider, Produktpaket und Sessiongenerator fehlen bzw.
bleiben ohne echte Qualifikation gesperrt. **Noch keine fertige EXE.**

## Abschließender Prüfstand

- Eingefrorener betroffener Backendlauf: **430 bestanden, vier native
  Windows-Gates übersprungen**, 48,60 s. Gesamtes Windows-Testverzeichnis
  plus Bridge-Endintegration, Bestandstransport, Hub/Routen/Protokoll,
  OutputState, Kopplung und UART. Ruff für die G1-Dateien und Diff-Prüfung bestanden.
- P4 nach seinen letzten Änderungen: 97 betroffene Tests bestanden; der
  ursprüngliche sporadische UART-Fall zusätzlich zehnmal. Breiterer Lauf
  zuvor 837 bestanden und 158 Node-Tests; kein neu behaupteter eingefrorener
  837-Test-Lauf auf dem Abschlussstand. Unveränderte Live-/CV-Batches nicht wiederholt.
- Doku: strenger Build bestanden, gesamter Playwright-Lauf **91 bestanden**
  in 6,7 min. OQ-66 geklärt: Auswahlvorbedingung im Tastaturtest kontrolliert;
  drei gezielte Wiederholungen und unabhängiges Review bestanden. Wiki-UI unverändert.
- Gemeinsames G1-/Branchreview: ein wichtiger Statusfehler korrigiert.
  Windows reicht den geprüften Pi-Sperrgrund jetzt über den öffentlichen
  Snapshot weiter; Diagnose erhält die festen Wiederanlaufcodes. Einmalige
  Nachprüfung: beide Befunde behoben, kein neuer wichtiger Befund. Backend-
  Übergabe freigegeben. Ein nicht reproduzierter Zwischenlauf-Timeout des
  neuen kombinierten Testfalls bleibt als OQ-67 dokumentiert; die finale
  Zustandsprüfung und getrennte numerische Integration sind grün.

Diese Tests sind Software-/Fake-COM-Evidenz; keine Messung, native
Windows-Qualifikation oder GSVmulti-Empfangsabnahme.

## Nächste Arbeit und externe Gates

Claude: Qt-Onboarding/Tray, UART-/Netz-/Endpunktauswahl, Profil/Kopplung,
Anleitung in der Workbench und getrennte Statusanzeigen für Verbindung,
Treiber, Demo-Bereitschaft und belegten Empfang. Öffentliche Kern-APIs verwenden.

N1: Windows 11 x64 ohne Python sowie neben unverändertem Python 3.7,
qualifizierte Wheel-/Qt-Locks und Freeze. Die vier Linux-Skips betreffen
DPAPI, geschützten Store/DACL, Instanzschutz und tatsächliches Freeze-Artefakt.
N2/W3: konkreter signierter Treiber, HVCI/PnP und bidirektionales Portpaar,
vertrauenswürdiger nativer UAC-/Deploymentanbieter sowie echte Installations-,
Reboot-, Reparatur-, Rollback- und Deinstallationsläufe.
N3: genaue GSVmulti-/Dateiversion und kontrollierter Feld-/Import-/
Wiederöffnungs-/Empfangsroundtrip; automatische Sessionerzeugung bleibt blockiert.
Release-Key/Hosting/Versionspolitik OQ-65 offen; OQ-62/OQ-64 in Arbeit.

Physische G1-Abnahme: zwei Pi, UART/LAN/Tailscale, Abziehen/Prozessabbruch/
Standby, 30-Minuten-Demos und Vergleich originaler GSV-Dateien mit COM-/Quellaudit.
DUT-Ausgabe bleibt strukturell gesperrt. Synthetische Demos sind provisional
und tragen keine Latenz-/Altersaussage. COM-Erfolg belegt keinen GSVmulti-Empfang.
Direkte UART-Ausgabe behält ihren getrennten bestätigungspflichtigen Prototypstatus.

## Bisheriger Laborstand

T13 `live-20261106T112527Z/run-01`: 22:38 min, 39.886 Datensätze,
75,79 % VALID, 0 Abweichungen unter 10.773 eindeutig vergleichbaren Freigaben;
19.451 im Wechselschutz unentschieden und fünf ungedeckt. Keine vollständige
T13-Abnahme. Letzte 8284 Bilder nutzten Zweitfit, 6605 akzeptiert; kein
blockierter Lauf. Physischer Erstfit-Grund offen, Diagnosebilder fehlten:
[Auswertung](quellen/werkbank-t13-2026-11-06.md), OQ-63.

Vorhandene Werkbank weiter `https://100.122.154.35:8082/live`, Dienst
`dispread-werkbank-t13.service`; Beobachter beendet. Frühere UI-Prüfung:
229 Node- und 46 Workbench-Playwright-Tests bestanden. Neue Hardware-Abnahme
mit Diagnose/HUD, mindestens 30 Minuten und dokumentiertem Vorschau-/Lastvergleich.

UART-Versuch zurückgestellt, Pi-Demosender beendet. Windows zuletzt Python
3.15/.venv315, COM6 FTDI → Brücke COM5 → GSVmulti COM4. Nur GND/RXD
bestätigt; TXD zum physischen Pi-Pin 10 fehlt. Keine erfolgreiche UART-
Brückenübergabe behauptet. Vor Fortsetzung Verdrahtung bestätigen.
Aufbewahrung OQ-60, Nachberechnung OQ-59 und Altcontroller OQ-61 folgen laut [TODO](../TODO.md).
