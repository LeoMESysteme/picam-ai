# Status — Stand 2026-10-31

Dieser Snapshot fasst den zuletzt dokumentierten Stand zusammen. Er ist keine
Live-Abfrage; Hardware- und Messwerte verweisen auf ihre Aufzeichnungen.
Die Arbeitsliste steht in [TODO.md](../TODO.md), Entscheidungen in der
[Projektgeschichte](project_history.md), Messnotizen im
[Laborjournal](lab_journal.md).

## Messpfad und belegte Grenzen

`dispread serve` hält die Logitech StreamCam über `CameraOwner` während der
Serverlaufzeit. Die `/live`-Werkbank führt durch Einrichtung, namentliche
Bestätigung und Messlauf mit Dot-Matrix-Leser und Rahmen-Tracker. JSONL-Audit
und optionale Referenzaufzeichnung sind getrennt; der Referenzwert korrigiert
weder DUT-Werte noch wird er Leser oder Freigabeprüfung übergeben. Details
und Messbelege stehen in [VALIDATION.md](VALIDATION.md) und im
[Laborjournal](lab_journal.md).

Die reale Prüfung ist auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V
begrenzt. Die dritte Leser-Abnahme ergab 215/215 richtige Proben. Für den
neuen Rahmenvorschlag fehlt eine Abnahme an zwei Aufstellungen; weitere
Geräte, Vorzeichen, Einheiten und Betrieb ohne Raumlicht sind ebenfalls
nicht belegt. Die Belichtungsnachregelung musste am Gerät bisher nicht
eingreifen. Das [Hardwareprofil](HARDWARE_PROFILE.md) nennt die StreamCam
als aktive Kamera; dortige sitzungsbezogene Werte sind datiert.

## R13-Stand in `master`

Die Entscheidungsvorlage dokumentiert die Übernahme von
`feat/r13-display-haertung` am 2026-10-30
([Merge-Entscheidung](superpowers/plans/2026-10-28-r13-merge-entscheidung.md)).
Der Rahmen-Tracker nutzt einen ziffernunabhängigen zweiten Durchgang. Die
Grobschätzung folgt Bewegungen bis 20 px und 3° bei ±0,5 % Maßstab; R13-23
senkte deren Medianlaufzeit von etwa 15 ms auf etwa 7,5 ms. Ein synthetischer
Durchlauf verlor keinen zuvor gefundenen Track und lieferte keine falschen
Quads. Das ist kein zusätzlicher Hardware-Abnahmenachweis
([Validierungsnachtrag](VALIDATION.md#r13-23-grobsuche-2026-10-30)).

Die Freigabe sperrt Testläufe technisch und unterdrückt Werte während
werkbankgesteuerter Geräteumschaltungen. Der Streamstillstand wird nach
2 Sekunden erkannt; diese Grenze ist bislang nur mit Fakes geprüft.
Referenztelegrammlücken werden ab 800 ms gezählt, gestützt auf 74 Minuten
Live-Daten ([OQ-40](open-questions.md#oq-40)). Weitere Details und Grenzen
führt die [Projektgeschichte](project_history.md).

Die ausgewerteten Live-Läufe meldeten keine Fehllesungen: 45.702 Records in
42,8 Minuten mit Werteplan, 14.785 Records in 16,5 Minuten sowie 3.274
Records bei Bewegungen bis 27 px. Im letzten Lauf wurden Bewegungen über
20 px abgelehnt. Diese Ergebnisse gelten für die dokumentierten Läufe und
ersetzen keine umfassende Systemabnahme. Der Langlauf ist im
[Laborjournal](lab_journal.md#langlauf-2026-10-30) belegt.

## GSVmulti

Der `UserDefined`-Zahlenimport ist dokumentiert. `UserDefinedFormatter`,
Demo-Sender und opt-in Live-Ausgabe (API-Feld `output`, standardmäßig aus)
sind gebaut. Geprüft wurde lokal mit pty; das belegt weder den Empfang in
der eingesetzten GSVmulti-Version noch den Adapter oder eine Messfreigabe.
Offen bleiben Ungültig- und Altwertbehandlung ([OQ-06](open-questions.md#oq-06)),
die Telegrammfrage ([OQ-07](open-questions.md#oq-07)) und die GSVmulti-Zeitachse
([OQ-47](open-questions.md#oq-47)). Die
[Protokollbewertung](GSVMULTI_PROTOCOL.md) beschreibt den Prototyp und den
[Windows-Test](GSVMULTI_PROTOCOL.md#windows-test).

## Betrieb und nächste belegte Arbeiten

Entwicklungsdaten können unter `/mnt/ssd/picam-dev` über
`DISPREAD_DEV_DATA` liegen; Produktdaten in `var/` bleiben auf der SD.
Während eines Messlaufs sollen auf dem gemeinsam genutzten Pi keine Builds,
Browsertests oder Pushes nach `master` laufen. Die im Journal dokumentierten
unerklärten Neustarts vom 24. bis 26. Oktober bleiben offen; der dort
beschriebene MEHub-Watchdog, der den PCIe-Bus alle zehn Minuten zurücksetzte,
ist abgeschaltet. Siehe [Hardwareprofil](HARDWARE_PROFILE.md) und
[Laborjournal](lab_journal.md).

Als nächste Arbeiten sind dokumentiert:

1. Abnahme an einer zweiten, neuen Aufstellung; Leonhard ist seit
   2026-10-30 dafür eingetragen.
2. GSVmulti-Test am Windows-PC gemäß
   [Testanleitung](GSVMULTI_PROTOCOL.md#windows-test).
3. Belichtungsnachregelung bei dunklerem Licht und Stillstandserkennung
   durch Abziehen der Kamera am Gerät prüfen.
4. Alten 7-Segment-Lesepfad aufräumen und die Importausbeute bei schrägem
   Blick verbessern; der TODO-Eintrag nennt für `ab6` 42 % verworfene Daten.
