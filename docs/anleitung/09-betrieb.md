# 9 — Betrieb: Installation, Dienst, Dauerlauf

Der [Release-Installer](../INSTALLER.md) richtet die Werkbank als Systemdienst,
Benutzerdienst oder portable Instanz ein. Das offene P6-Ziel ist ein
[72-Stunden-Dauerlauf](../ROADMAP.md#roadmap-schritte) mit provozierten
Störungen, ohne unmarkierten Altwert und mit stabilem Speicher.

## Installation und Dienst prüfen

Auf einem neuen Pi den [Installationsplan](../INSTALLER.md#installation-zuerst-planen)
prüfen und anschließend installieren. Der Systemmodus legt Programmversionen
unter `/opt/picam/releases/`, Daten unter `/var/lib/picam` und die Konfiguration
unter `/etc/picam/config.toml` ab. Die erzeugte Unit `picam-werkbank.service`
startet die Werkbank unter dem gewählten Bedienerkonto. Für einen
Entwicklungscheckout gibt es ein eigenes
[Dienstskript](10-kamera-livevorschau.md#werkbank-dienst).

Bei einer Release-Installation im System- oder Benutzermodus helfen die
[Verwaltungsbefehle](../INSTALLER.md#verwalten-mit-picam).

```bash
picam status
picam doctor
picam logs -n 40
```

`picam status` prüft den Dienst und nennt die Adresse. `picam doctor` zeigt
Voraussetzungen wie Kamera, Ports und Kalibrierung. Die HTTPS-Antwort von
`/live` belegt, dass der Webdienst antwortet. Bild, Einrichtung und
Messstart anschließend im Browser prüfen. Für Wartung zuerst eine laufende
Messung in der Werkbank beenden.

## UART am Zielrechner

Den Datenport im [Hardwareprofil](../HARDWARE_PROFILE.md#serielle-schnittstellen)
des Zielrechners prüfen. Der reservierte Debug-Port ist `/dev/ttyAMA10`.
Das Ziel von `/dev/serial0` hängt vom Rechner ab. Der
[UART-Dialog in `picam`](../INSTALLER.md#uart-ports-andern) zeigt die wählbaren
Pins und Referenzadapter und legt vor Änderungen an `config.txt` eine
Sicherung an. Für USB-Adapter einen stabilen `/dev/serial/by-id/`-Pfad wählen,
wenn das System ihn anbietet.

Der Pi-Header verwendet 3,3 V. Für RS-232 ist ein Pegelwandler nötig.
Die [Ausgabewege und ihre Belege](../GSVMULTI_PROTOCOL.md#transport) stehen
im Protokollkapitel. Die galvanische Trennung bleibt Bestandteil von
[OQ-09](../open-questions.md#oq-09).

## 72-Stunden-Dauerlauf {#teil-d-72-stunden-dauerlauf}

Die Prüfung erfolgt mit der vorgesehenen Kamera, bestätigter Einrichtung,
gültiger Timing-Kalibrierung und dem für die Abnahme gewählten Ausgabeweg.
Grenzwerte und zulässiges Verhalten vorab mit den
[Abnahmekriterien](../VALIDATION.md#abnahmekriterien) abgleichen.

| Größe | Nachweis |
| --- | --- |
| Unmarkierte Altwerte | Live-Status, `records.jsonl` und Empfangsaufzeichnung zusammen prüfen. Der Zähler für als gültig ausgegebene Altwerte bleibt 0. |
| Speicher | RSS des Dienstes und freier Platz im Datenverzeichnis in festen Abständen protokollieren. |
| Bild- und Ausgabelücken | Sequenzsprünge und Fehler in Audit, Dienstjournal und GSVmulti-Aufzeichnung zuordnen. Für Zeitvergleiche die dokumentierte Zeitbasis verwenden. |
| Dienstneustarts | `systemctl show picam-werkbank.service -p NRestarts` für den Systemdienst (im Benutzermodus mit `--user`). Neustarts zeitlich den Störungen zuordnen. |

Störungen einzeln auslösen und protokollieren. Dazu gehören eine getrennte
Gegenstelle, schlechte Beleuchtung, eine abgedeckte oder nichtnumerische
Anzeige und ein Dienstabbruch. Jeweils nachvollziehen, wann Freigabe und
Ausgabe aussetzen und wann gültige Erkennung wieder vorliegt. Im
GSVmulti-Vierkanalprofil den Gültigkeitskanal mit auswerten. Speicherfehler
nur in einer getrennten Testinstallation provozieren.

Auswertung und Messzahlen in [VALIDATION](../VALIDATION.md) ablegen.
Aufbau, Störfolge und Deutung gehören ins [Laborjournal](../lab_journal.md).

## Dokumentation prüfen

Nach Änderungen an der Betriebsanleitung die Prüfungen aus
[AGENTS.md](../../AGENTS.md) ausführen. Der strenge Build
(`./scripts/docs-site.sh build -s`) prüft unter anderem OQ-Index, Wiki und
Verweise. `npx playwright test -c playwright.docs.config.ts` prüft die
Dokumentationsseite im Browser.
