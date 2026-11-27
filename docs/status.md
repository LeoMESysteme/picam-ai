# Status und Übergabe — 2026-11-27

## Sensorpakete P0 im Worktree `sensor-p0`

Der Backend-Durchstich reicht von `picam sensor onboard` über Bedienerfragen
und Paketprüfung bis zur gespeicherten Auswahl `live.sensor`. Ein
Werkbank-Neustart übernimmt die Einstellung. Der Live-Status und das Audit
tragen bei lokalen Paketen den Status `provisional`. Probe und Messwert
aus einer archivierten GSV-2AS-Aufnahme stehen in der
[Validierung](VALIDATION.md#sensor-p0-2026-11-27). Der Golden-Vergleich
blieb für alle 2.781 GSV-2AS-Proben byte-identisch. Die gezielte
Backend-/Paketauswahl bestand 129 Tests. Sechs lokale HTTP-Tests und der
Browser-Testserver scheiterten beim Öffnen des TCP-Sockets in der Sandbox.
In der getrennten TUI-Prüfung meldete der Pilot-Test zum Fragenablauf
einen Klick außerhalb des sichtbaren Bereichs.

Die Entwicklung liegt auf `feat/sensor-p0` im Arbeitsbaum. Für die
Integration stehen der gemeinsame TUI-Durchlauf mit realem Agenten und der
erste Lauf am Aufbau aus. Der Paketgenerator verlangt für P0 ein festes
Plus in Zelle 0. [OQ-81](open-questions.md#oq-81)

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
