# Status — Stand 2026-10-28

Dieser Snapshot fasst den belegten Stand zusammen; Hardware- und Messwerte
stammen aus den jeweils genannten Aufzeichnungen, nicht aus einer Live-Abfrage.
Arbeitsliste: [TODO.md](../TODO.md); Verlauf: [Changelog](../CHANGELOG.md),
[Projektgeschichte](project_history.md) und [Laborjournal](lab_journal.md).

## Gebauter Messpfad

Auf `master` hält `dispread serve` die Logitech StreamCam über
`CameraOwner` für seine gesamte Laufzeit. `/live` führt durch Einrichtung,
namentliche Bestätigung und Messlauf mit Dot-Matrix-Leser. Bedienerläufe,
JSONL-Audit und die getrennte optionale Referenzaufzeichnung sind dokumentiert
in [VALIDATION](VALIDATION.md) und im [Laborjournal](lab_journal.md).
Die Referenz korrigiert keine DUT-Werte und wird Leser/Gate nicht als Parameter
übergeben.

Die reale Prüfung bleibt auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V
begrenzt. Leser-Abnahme 3 ergab 215/215 richtige Proben; weitere Geräte,
Vorzeichen, Einheiten und eine allgemeine Systemabnahme sind nicht belegt.
Die dokumentierten Bedienerläufe und ihre Grenzen stehen in
[VALIDATION](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21).

## GSVmulti-Anbindung

Die Herstelleranleitung v2.6 beschreibt `UserDefined` als konfigurierbaren
Zahlenimport über einen realen oder virtuellen Windows-COM-Port. Ein Prototyp
ist damit planbar; Empfang in der eingesetzten Version, Adapter, Live-Ausgabe
und Messfreigabe sind nicht nachgewiesen. Ungültig-/Altwertbehandlung und die
von GSVmulti verwendete Zeitachse bleiben offen. Details und Grenzen stehen in
der [Bewertung](GSVMULTI_PROTOCOL.md), [OQ-07](open-questions.md#oq-07) und
[OQ-47](open-questions.md#oq-47).

## Session-Explorer

Die Dokumentationsseite kann abgeschlossene Messläufe mit Kennzahlen,
Verläufen und Originaldateien darstellen. Die Export- und Hostinggrenzen sind
in [Session-Explorer](session-explorer.md) und
[Doku-Hosting](HOSTING.md#session-archiv-und-explorer) beschrieben. Der
Katalog enthält derzeit keine veröffentlichten Sessions; daraus folgt keine
Aussage über nicht veröffentlichte lokale Dateien.

## Nächste Schritte

1. Nachführung unabhängig vom Zifferninhalt untersuchen und große
   Wertwechsel erneut prüfen ([OQ-26](open-questions.md#oq-26)).
2. Testlauf-Sicherung und Zeitbasis-Bezeichnung klären
   ([OQ-44](open-questions.md#oq-44), [OQ-45](open-questions.md#oq-45)).
3. GSVmulti-Prototyp, Windows-COM-Transport, Empfang und Verhalten bei
   ungültigen Werten prüfen ([OQ-06](open-questions.md#oq-06),
   [OQ-47](open-questions.md#oq-47)); danach folgen die im
   [TODO](../TODO.md) genannten Mess- und Aufräumarbeiten.

Keine Hardwareänderung und kein neuer Messlauf sind für diesen Doku-Abgleich
dokumentiert. Der aktuelle Laufzustand wurde nicht abgefragt.
