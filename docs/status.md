# Status und Übergabe — 2026-11-27

## Sensorpakete (Branch feat/sensor-p0)

- GSV-2AS-Paket, Laufzeit, `picam sensor` und Konsolenassistent sind gebaut. Lokale Pakete sind vorläufig. [Paketformat und Bedienung](SENSOR_PACKAGES.md)
- T2/T4: 2.781 Golden-Proben byte-identisch. T4: 129 Backend-/Pakettests bestanden und Leseprobe auf archiviertem GSV-Bild belegt. [Validierung](VALIDATION.md#sensor-p0-2026-11-27)
- Außerhalb der Sandbox bestanden 394 gezielte Tests (Sensoren-Tab, Konsole, Eingabefokus, Onboarding-Backend, Pakete, Live-API, Installationskonfiguration) mit `-n 4`.
- raspi06: Paket ohne KI und mit Claude-Agent erzeugt, statisch geprüft und aktiviert. [Laborjournal](lab_journal.md#sensor-p0-onboarding-2026-11-27)
- Seit 27.11. auf `master` (Leonhards Freigabe): Sensorpakete, KI-Sensoreinrichtung und Marktplatz als optionales Experimentalfeature (Standard aus). Volle Suite: 5342 bestanden, 2 sporadische Oberflächentests (einzeln grün). Offen: Forgejo-Einrichtung für Einreichungen (Label, Maschinenkonto, `SENSOR_BOT_TOKEN`, Spiegelung von `sensor-katalog`), erster Lauf eines neuen Sensors mit Kamera am Aufbau, Konzept.md-Ergänzung (Freigabe Leonhard), helle Anzeigen (OQ-84).

## GitHub-Einstieg

Leonhard hat den GitHub-Quickstart für `master` freigegeben. Er führt vom
frischen Pi bis zum ersten Lauf mit Ausgabe **Aus**. README, Doku-Übersicht,
Installer- und Werkbank-Anleitung sowie GSVmulti-Seite führen direkt zu
den nächsten Bedien- und Diagnoseschritten. Die Bilder zeigen die
Abschlusskarte, den Konsolenassistenten und den Werkbank-Übungslauf
mit Beispieldaten.

## Veröffentlicht und integriert

- **picam 1.1.1 und GSVmulti-Brücke 1.1.0.** Der öffentliche Release
  enthält Installerarchiv und SHA-256-Prüfsumme für den Pi sowie
  Windows-Setup, portable EXE und deren Prüfsummen. picam 1.1.1 korrigiert
  die Rechte der Programmdateien bei Installation und Update.
  [Veröffentlichung v1.1.1](https://github.com/LeoMESysteme/picam-ai/releases/tag/v1.1.1) ·
  [Installationsanleitung](INSTALLER.md) · [Changelog](../CHANGELOG.md)
- **`master` enthält den Stand von Werkbank, Windows-Brücke und
  Verwaltungskonsole.** Die Arbeit aus den bisherigen Integrationszweigen
  ist im Hauptcheckout. Die Konsole führt unter anderem durch Update,
  Zertifikat, UART-Konfiguration und Timing-Kalibrierung. Die Brücke
  1.1.0 zeigt den vom Pi übermittelten Namen und protokolliert
  Verbindungsabbrüche, COM-Fehler und aufgefüllte oder ungültige Takte.
  Forgejo und GitHub führten am 26.11. dieselben 11 Branch-Namen.
  `master` stand auf beiden Servern am 27.11. auf `197959a`.
  [Arbeitsliste und verbleibende Repository-Aufgaben](../TODO.md)
- **Download und Update.** Der Bootstrap und `picam update` beziehen die
  neueste stabile Fassung vom öffentlichen GitHub-Mirror. Laut Arbeitsliste
  wurde v1.1.1 am 26.11. auch auf Forgejo manuell bereitgestellt. Der
  automatisierte Upload dorthin steht aus. [OQ-49](open-questions.md#oq-49) ·
  [Release-Verfahren](INSTALLER.md)

## Gerätebelege und nächste Prüfungen

| Bereich | Letzter Beleg | Nächste Prüfung |
| --- | --- | --- |
| Werkbank und Ausgabewege | Herr Kaulitz hat am 13.11. Werkbank, Netzwerk über Brücke, UART über Brücke und UART direkt für den geprüften Aufbau abgenommen. Der Pi-Dienst lief mit `5a31b41`. Für den Windows-Build von 14:50 vermutet der UX2-Bericht `c643f30`. [Smoketest](../windows/bridge/SMOKETEST-2026-11-13.md) · [UX2-Bericht](quellen/ux2-pruefung-2026-11-13/ux2-bericht.md) | UART-Rahmenfehler und Anmelde-Timeouts am Aufbau eingrenzen. Windows-Pakete und Sessionexport im Zielumfeld prüfen. [OQ-62](open-questions.md#oq-62) · [OQ-77](open-questions.md#oq-77) |
| Fokus, Raster und Nachführung | Die Prüfung vom 18.11. belegt Startablehnungen, schwache Beleuchtung und fortbestehende Trackingverluste. `master` enthält den gewarnten Start nach erfolgreicher Leseprobe bei begrenzter Fokusabweichung, die Lichtwarnung und die geprüften Rasteränderungen A1+B1. [Validierung](VALIDATION.md#workbench-2026-11-18) · [Rasterbericht](quellen/rahmen-raster-2026-11-13/REPORT-codex.md) | Bei Raumlicht neu einrichten, Kontrollläufe vergleichen und den Einbruch der Nachführung reproduzieren. [OQ-74](open-questions.md#oq-74) · [OQ-78](open-questions.md#oq-78) |
| raspi01 | Am 25.11. wurde die Timing-Kalibrierung mit `rc-51b620f` gemeldet. Später lief `rc-eaa4ad8`. Davor hatte das Update bei fehlerhafter UART-Porterkennung automatisch zurückgeschaltet. [Laborjournal](lab_journal.md) | Update auf 1.1.1. Konsolen-Kalibrierung mit sudo-Freigabe und Abbruch belegen. Freien Header-UART nach Neustart zuordnen. Für die Frischinstallation mit Onboarding und Messlauf frische Installationspfade oder ein separates System verwenden. [OQ-79](open-questions.md#oq-79) · [OQ-80](open-questions.md#oq-80) |
| raspi06 | Bei der systemd-Abfrage am 26.11. war kein `dispread*`-Werkbankdienst geladen. Am 25.11. wurde Tailscale-SSH mit `tailscale set --ssh=false` deaktiviert. Der Dienst `ssh` war aktiv, und der abgefragte ED25519-Hostschlüssel am Tailscale-Endpunkt entsprach dem OpenSSH-Hostschlüssel. | Login vom Client steht aus. Für NetworkManager-Sperren steht der [WLAN-Wächter](HOST_NETZWERK.md) bereit. |

Die vollständigen nächsten Aufgaben stehen in der [Arbeitsliste](../TODO.md).
Die [Roadmap](ROADMAP.md) führt die Abnahmekriterien je Phase und die
[offenen Fragen](open-questions.md) enthalten Belege und Prüfschritte.

## Teststufen und Security-Scans

- Branch `ci/stufen-einfuehrung` führt `scripts/ci.py <t0|t1|t2|t3|nightly>` ein
  (Hooks in `.githooks/`, Workflows `ci-fokussiert`, `ci-voll`, `ci-release`, `ci-nightly`),
  gitleaks und bandit (`scripts/security-scan.sh`) sowie `scripts/perf-report.py`.
  Stufen, Eskalationsregeln und Fehlerkatalog: [AGENTS.md](../AGENTS.md#teststufen) ·
  [ci-failures](ci-failures.md) · [Security-Scan](security-scan.md).
- Offen: `perf/baseline.json` ist noch vom Arbeitsbaum erzeugt (`-dirty`) und muss auf einem
  ruhigen Pi neu geschrieben werden (`./.venv/bin/python scripts/perf-report.py --update-baseline`).
  Der erste CI-Lauf auf dem Forgejo-Runner (SHA-Pins, gitleaks/bandit-Installation,
  Playwright-Browser, T3-Trockenlauf) ist noch nicht beobachtet.
  Die Runner-Kopie der Stufe-2c-Vorlage liegt unter `/var/lib/forgejo-runner/picam-templates/`.

## Doku-Abgleich und Integration

- Leonhard hat den Doku-Abgleich vom 26.–27.11. für `master` freigegeben.
  Basis ist `197959a`. Codex übernimmt Commit, Push und die Prüfung der
  Forgejo-Läufe „Doku-Seite“ und „Playwright Tests“ für den Ziel-Commit.
  Die Prüfergebnisse stehen in der Sitzungsübergabe.
- Der frühere Prüfstand vom 25.11. ist einschließlich geprüftem Softwarestand
  in der [Arbeitsliste](../TODO.md) festgehalten. Die Gerätebelege beziehen sich
  jeweils auf die dort oder oben genannten Versionen.
- Der Wiki-Sessionexport wird bei einem Push auf `master` oder manuell
  gestartet. Er wird bei einem offenen, kürzlich geänderten Messlauf
  verschoben. [Doku-Hosting](HOSTING.md#session-archiv-und-explorer)
