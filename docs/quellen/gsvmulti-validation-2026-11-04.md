# GSVmulti-Belege und Übergabe vom 2026-11-04

Das [Belegarchiv](gsvmulti-validation-2026-11-04.zip) enthält292 Dateien:
synthetische Quellaudits, Windows-Brücken-/Steuerlogs, Nutzer-TXT/TDMS/UCF,
strukturierte Diagnosen, lokale Analyserezepte und die projektseitigen
Windows-/Reproduktionspakete. [SHA256](gsvmulti-validation-2026-11-04.sha256).
ZIP-CRC und jeder Eintrag gegen MANIFEST.json geprüft. Dateiarchiv mit
provisional/demo-Kennzeichnung; keine echte DUT-Freigabe und keine Latenz-
aussage. Einzelne historische Zwischenberichte entstanden vor späteren
Empfängeruploads: pro Versuch ist recording-comparison.json der abschließende
Dateivergleich, source-audit-comparison.json nur der Quellnachweis.

Die Verzeichnisstruktur beginnt mit var/diagnostics/gsvmulti/ bzw. var/exports/.
Für einen neuen Checkout das ZIP im Repositorywurzelverzeichnis entpacken.
Vorhandene lokale Belege zuerst gegen Manifest vergleichen und nicht ungeprüft
überschreiben. Im aktuellen Arbeitsplatz liegen die Originale bereits unter
var/. Das Archiv stellt sicher, dass sie auch nach Clone/Push vorhanden sind.

Wichtige Verzeichnisse:

* windows-local-demo-20261104-01:600/600 exakte Windows-Demowerte, abweichende
  tatsächliche Demo-Ereignisrate unter Windows (OQ-57).
* tcp-demo-20261104-01:600/600 Werte über gemeinsamen Pi-TCP-/JSONL-/ACK-Weg
  exakt in TXT/TDMS, mV/V/Scaling1/COM6.
* tcp-reconnect-20261104-01:600 Quellwerte,510 angebotene/COM-geschriebene
  Werte exakt in TXT/TDMS;89 Werte beim Prozessabbruch ausgelassen, Zusatz-
  frame356 vor Angebot ersetzt (OQ-58). GSVmulti verdichtet Ausfall auf0,1s.
* uart-direct-demo-20261104-01 bis -16: historische Einzelversuche und
  negative Ungültig-/Filter-/Wiederöffnungsbelege; nicht alle besitzen einen
  Empfängerexport. Keine erfolgreiche Abnahme allein aus Senderlog ableiten.
* com0com-driver-diagnosis-20261104: Versions-/Hash-/PnP-/Schutzstatus und
  Diagnoseberichte. Aktiver Vovsoft-verlinkter Treiber auf genau einem
  Windows11-PC mit SecureBoot/HVCI funktionsfähig, keine allgemeine Zulassung.

Drittanbieter-Installer, Treiberbinärdateien, extrahierte PE-Abschnitte und
Analyse-Wheel absichtlich nicht enthalten; Herkunft/Hashes stehen in den
Diagnoseberichten und [Abhängigkeiten](../dependencies.md). npTDMS1.13.0 wurde
nur isoliert aus Wheel mit Debian-NumPy importiert, nicht installiert.
Analyserezepte wurden im ursprünglichen Arbeitsplatz ausgeführt und tragen
zum Teil absolute Chat-Anhangspfade. Beim Wiederholen auf einem neuen Rechner
Eingabepfade auf die bereits archivierten Originale richten; Rohdaten/SHA256
und Rechenweg bleiben erhalten. Projekt-Python immer über .venv nutzen.

Als Einstieg für die Fortsetzung [Status/Übergabe](../status.md),
[Zahlen und Nachweisgrenzen](../VALIDATION.md#tcp-reconnect-20261104-01),
[Arbeitsplan](../superpowers/plans/2026-11-04-gsvmulti-anbindung.md).
