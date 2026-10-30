# Status — Stand 2026-10-30

Dieser Snapshot fasst den belegten Stand zusammen; Hardware- und Messwerte
stammen aus den jeweils genannten Aufzeichnungen, nicht aus einer Live-Abfrage.
Arbeitsliste: [TODO.md](../TODO.md); Verlauf: [Changelog](../CHANGELOG.md),
[Projektgeschichte](project_history.md) und [Laborjournal](lab_journal.md).

## Neu: R13 in `master` (2026-10-30)

Leonhard hat den Zweig `feat/r13-display-haertung` am 2026-10-30 nach
`master` übernommen.
[Entscheidungsvorlage](superpowers/plans/2026-10-28-r13-merge-entscheidung.md).

* **Nachführung:** Der Rahmen-Tracker arbeitet unabhängig vom
  Zifferninhalt.
  * Ein zweiter Durchgang mit Grobschätzung folgt Bewegungen bis 20 px
    und 3° bei einem Maßstab von ±0,5 %.
  * R13-23 hat die Grobschätzung billiger gemacht: Der zweite Durchgang
    braucht im Median ≈ 7,5 ms statt 15 ms.
  * Ein synthetischer Durchlauf hat keinen vorher gefundenen Track
    verloren und 0 falsche Quads geliefert.
* **Displayhärtung:** Prüfungen für helle Kratzer und `displayfehler`,
  Kantenprüfung ohne Fehlalarm durch Nachbarzeichen. Die Belichtung wird
  auf die Anzeige abgestimmt, die Vorprüfung `belichtung` warnt unter
  Glaspegel 105.
* **Freigabesicherung:**
  * Ein Testlauf gibt technisch nie einen Wert frei
    ([OQ-44](open-questions.md#oq-44)).
  * Solange die Werkbank das Gerät selbst umschaltet, wird nichts
    freigegeben (R13-21).
  * Ein Streamstillstand beendet den Lauf nach 2 s statt nach 10–20 s
    (R13-22, nur mit Fakes geprüft).
* **Referenz:** Telegrammlücken zählen ab 800 ms statt 1 000 ms. Grundlage
  sind 74 min Live-Daten ([OQ-40](open-questions.md#oq-40)).
* **Betrieb:** Speicherbudget für eine 64-GB-SD, Diagnosebilder und
  Ereignismarken, Live-Audit je Lauf ohne Rotation.
* **Live-Belege** (offizielle Auswertung
  `scripts/live-reference-eval.py`, alle **0 Fehllesungen**):

  | Lauf | Umfang | Ergebnis |
  | --- | --- | --- |
  | `live-20261030T082502Z/run-01` | 42,8 min, Werteplan mit 280 Schritten | 0 / 45 702, 100 % VALID in stabilen Fenstern, kein Trackingverlust |
  | `live-20261028T150914Z/run-01` | 16,5 min, Werteplan | 0 / 14 785, 99,99 % VALID in stabilen Fenstern |
  | `live-20261028T150914Z/run-02` | Bewegungen bis 27 px | 0 / 3 274; Bewegungen über 20 px wurden korrekt abgelehnt |

  Den Langlauf hat Claude im Auftrag von Leonhard bestätigt und gestartet
  (Chat-Freigabe); [Laborjournal](lab_journal.md#langlauf-2026-10-30).
* **Nachtpflege:** Sie scheiterte am 19.–21.10. und am 24.–28.10. an der
  abgelaufenen Codex-Anmeldung des Runners. Seit dem Auth-Abgleich vom
  28.10. läuft sie grün.

## Gebauter Messpfad

`dispread serve` hält die Logitech StreamCam über `CameraOwner` für seine
gesamte Laufzeit. `/live` führt durch Einrichtung, namentliche Bestätigung
und Messlauf mit Dot-Matrix-Leser und Rahmen-Tracker. Bedienerläufe,
JSONL-Audit und die getrennte optionale Referenzaufzeichnung mit Werteplan
sind in [VALIDATION](VALIDATION.md) und im [Laborjournal](lab_journal.md)
dokumentiert. Die Referenz korrigiert keine DUT-Werte und wird Leser und
Gate nicht als Parameter übergeben.

Die reale Prüfung bleibt auf GSV-2AS / Displaytech 161A, Raumlicht und
mV/V begrenzt. Leser-Abnahme 3 ergab 215/215 richtige Proben. Nicht belegt
sind weitere Geräte, Vorzeichen, Einheiten, eine Abnahme an zwei
Aufstellungen mit dem neuen Rahmenvorschlag, Betrieb ohne Raumlicht und
die Belichtungsnachregelung am Gerät. Die Regelung musste bisher nie
eingreifen.

## GSVmulti-Anbindung

Die Herstelleranleitung v2.6 beschreibt `UserDefined` als konfigurierbaren
Zahlenimport über einen realen oder virtuellen Windows-COM-Port. Der
Prototyp ist gebaut, aber nicht freigegeben:

* P4-1: `UserDefinedFormatter`;
* P4-2: `scripts/gsvmulti-demo-sender.py`;
* P4-3: Opt-in-Ausgabe im Live-Lauf, API-Feld `output`, Standard aus.

Geprüft ist das nur mit pty. Nicht nachgewiesen sind der Empfang in der
eingesetzten Version, der Adapter und die Messfreigabe. Offen bleiben die
Ungültig- und Altwertbehandlung ([OQ-06](open-questions.md#oq-06)) und die
Zeitachse in GSVmulti. Details stehen in der
[Bewertung](GSVMULTI_PROTOCOL.md) mit
[Windows-Anleitung](GSVMULTI_PROTOCOL.md#windows-test),
[OQ-07](open-questions.md#oq-07) und [OQ-47](open-questions.md#oq-47).

## Session-Explorer

Die Dokumentationsseite kann abgeschlossene Messläufe mit Kennzahlen,
Verläufen und Originaldateien darstellen. Die Export- und Hostinggrenzen
sind in [Session-Explorer](session-explorer.md) und
[Doku-Hosting](HOSTING.md#session-archiv-und-explorer) beschrieben.

## Betrieb

* Die NVMe-SSD dient nur zur Entlastung: Dev-Daten liegen unter
  `/mnt/ssd/picam-dev` (`DISPREAD_DEV_DATA`). `var/` bleibt auf der SD, ohne
  Link auf die SSD ([HARDWARE_PROFILE](HARDWARE_PROFILE.md)).
* Forgejo-CI und Messpfad teilen sich den Pi. Während eines Messlaufs
  keine Builds, Browsertests oder Pushes nach `master`.
* Nach einem Lauf die Werkbank erst neu starten, wenn
  `/dev/shm/dispread-diagnose-*` verschwunden ist.
* Die unerklärten Neustarts vom 24. bis 26.10. sind offen. Das Journal
  liegt seit dem 28.10. dauerhaft vor; der MEHub-Watchdog, der den PCIe-Bus
  alle 10 min zurücksetzte, ist aus.

## Nächste Schritte

1. Abnahme an einer zweiten, neuen Aufstellung. Leonhard ist ab dem
   2026-10-30 dran.
2. GSVmulti-Test am Windows-PC ([Anleitung](GSVMULTI_PROTOCOL.md#windows-test)).
3. Am Gerät zeigen, dass die Belichtungsnachregelung eingreift (dunkleres
   Licht), und die Stillstandserkennung durch Abziehen der Kamera prüfen.
4. Aufräumen: alten 7-Segment-Lesepfad entfernen. Für den Import bei
   schrägem Blick die Ausbeute verbessern (`ab6` verwirft 42 %), siehe
   [TODO](../TODO.md).
