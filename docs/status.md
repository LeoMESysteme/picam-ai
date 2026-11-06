# Status und Übergabe — 2026-11-06

Die G1-Zusammenführung erhält P4-3-Direktausgabe und Windows-Brücke
unter einem Backend-Vertrag. Die datierten Übergaben unten bleiben als
Beleg des jeweiligen Arbeitsstands erhalten; ihre damaligen nächsten
Schritte und Prüfstände sind keine neue Abnahme.

**Ausgabevertrag (Nutzerentscheidung 2026-11-06):** Pro Lauf gibt es genau
einen Ausgabeweg: `off` = Aus, `serial` = P4-3 direkt, `uart` = UART über
die Windows-Brücke oder `tcp` = Netzwerk über die Windows-Brücke.
Bestehende `output`-Objekte ohne `transport`, aber mit `port`, wählen
weiterhin `serial`. Testläufe erlauben keine externe Ausgabe; die
Brückenwege bleiben für echte DUT-Werte bis zum Ungültig-/Altwertnachweis
strukturell gesperrt.

## Übergabe vom 2026-11-04 (GSVmulti-Brückenzweig)

Gesicherter GSVmulti-Arbeitsstand auf Branch `feat/gsvmulti-bridge`.
Nutzer beendet die Arbeit für einige Tage und hat Dokumentation, Commit und
Push beauftragt. Kein Merge nach master und keine weiteren Messversuche.
Einstieg für Fortsetzung durch Codex/Claude:
[Arbeitsplan](superpowers/plans/2026-11-04-gsvmulti-anbindung.md),
[Protokoll/Schranken](GSVMULTI_PROTOCOL.md#windows-bruecke),
[TODO](../TODO.md), [Belegarchiv](quellen/gsvmulti-validation-2026-11-04.md).

### Ergebnis der heutigen Hardware-/Windowsversuche

* Windows11 Pro Build26200, GSVmulti2.03 Pro (EXE2.3.4), Python3.15x64.
* com0com auf diesem Rechner funktionsfähig: CNCA1=COM5 (Brücke), CNCB1=COM6
  (GSVmulti). Bidirektionale Probe bestanden; SecureBoot/HVCI weiter aktiv.
  Aktiver x64-Treiberhash e61c4943fb534f932193a81e8fbcb2f453e4b073a14159f9c161537b38d2bc38,
  Vovsoft-verlinkter Build. Keine allgemeine Treiberzulassung behaupten.
* Lokaler Windows-Demoweg:600/600 Werte exakt in TXT/TDMS, mV/V/Scaling1.
  Tatsächliche Windows-Ereignisrate9,0576Hz bei Ziel10Hz, OQ-57.
* Gemeinsamer Pi→TCP→Windows-Brücke→COM5/com0com/COM6→GSVmulti-Dateipfad:
  600/600 Werte−0,300…+0,299 exakt in TXT/TDMS, alle ACK-/Request-/Run-/
  Frame-Zuordnungen und Payloads passend. [Beleg](VALIDATION.md#tcp-demo-20261104-01).
* Brückenprozessabbruch bei weiterlaufender Quelle:600 Quellwerte auditiert,
  510 angeboten/COM-geschrieben, alle510 exakt in TXT/TDMS. Nach100 written
  eigener Windows-Kindprozess beendet,10,0001885s Steuerpause, Neustart.
  Übergang Frame99=−0,201 → Frame189=−0,111, jüngste Veröffentlichung;
  89 Zwischenwerte nicht nachgesendet. Zusätzlich Frame356=+0,056 schon vor
  Angebot durch Latest-Auswahl ersetzt (OQ-58). Anzeige ohne Bedienereingriff
  fortgesetzt. Beide Kindprozesse absichtlich beendet, Controller completed.
  [Beleg](VALIDATION.md#tcp-reconnect-20261104-01).
* GSVmulti verdichtet weiterhin Ausfallzeiten:10,1779168s zwischen Windows-
  Schreibereignissen werden am Übergang in TXT zu0,1s, kein Fehlwertmarker.
  Gesamtraster50,9s gegenüber61,1879196s Windows-Ereignisspanne. Nominelles
  dt mode=1/f0 ist keine gemessene Quell-/Ankunftszeitachse.
* 16 direkte UART-Demoversuche belegen Rampen/Sprünge/Einheit, aber NaN/Pause
  verschwinden auch mit bestätigtem Replace Missing Values. Filter aus
  scheitert schon bei gültigen Zahlen, Gegenprobe mit Filter ein funktioniert.
  [Belege](VALIDATION.md#uart-demo-20261104-08).

Nur synthetische Demo, demo/provisional=true, time_claim=false. Ereigniszeiten
jeweils HOST_MONOTONIC auf eigenem Host, Pi und Windows nicht gepaart.
Keine physische Framealter-/Latenzaussage. Kein Kabel-/Netz-Blackout oder
Betriebssystem-Neustart und keine reale DUT-Abnahme. Echte Ausgabe bleibt
strukturell gesperrt. Keine Mittelung, keine Referenzkorrektur, keine Altwerte
unmarkiert weiterführen und keinen Freigabebypass ergänzen.

### Workbench ist bereits als Prototyp angeschlossen

Nicht erneut eine zweite Transportstrecke bauen. Vorhandene Nähte:

* src/dispread/sink/protocol/user_defined.py: UserDefinedFormatter erhält
  Rohtext-Dezimalauflösung und prüft Zahl/Wert. Format provisional; natives
  gsv_ascii.py wirft absichtlich. SEND_NAN ausschließlich Demo.
* src/dispread/gsv_transport.py: OutputConfig/OutputPublisher, TCP/UART,
  höchstens ein ausstehendes Angebot plus jüngster Wert; Invalidierungsbarriere
  getrennt, Run-/Frame-/Request-IDs. ACK nur COM-Treiberübergabe.
* src/dispread/gsv_bridge.py und scripts/gsv-bridge.py: gemeinsame Windows-
  Python-/pySerial-Brücke, nur synthetische Demowerte akzeptiert.
* src/dispread/live/session.py: Audit vor Publish, vollständiger Lauf ohne
  JSONL-Rotation, Ausgabestart/-stop und Konfiguration im session.json.
* src/dispread/live/service.py, workbench/live_api.py: optionale output-
  Konfiguration an /live/run/start, Ausgabestatus an /live/status;
  Test-Override erlaubt keine externe Ausgabe.
* workbench/static/live.html und live.js: Auswahl Aus/UART/Netzwerk,
  UART-Gerät/TCP-Port, Status/Warnung und Freigabesperre. Auswahl während Lauf
  gesperrt. Meldung unterscheidet COM-Bestätigung und GSVmulti-Empfang.

Die neue Workbench-Gestaltung kann diese Nähte übernehmen; UI-Umbau und echte
Messfreigabe bleiben getrennte Aufgaben. Browser-/Unitprüfungen ersetzen keinen
Live-DUT-Nachweis. Referenz bleibt Audit und korrigiert keinen DUT-Wert.

### Reihenfolge für die Fortsetzung

1. Belege/Code von diesem Branch übernehmen, Status und OQ-06/OQ-47/OQ-50/
   OQ-51 lesen. GSVmulti-Entwicklung muss Ungültig-/Zeitsemantik klären;
   Nutzer hat direkten Kontakt, Agent hat nichts versandt. Lokales Support-
   Vergleichspaket im Belegarchiv. Fehlerbehebung derzeit zurückgestellt.
2. OQ-58 isolieren: zusätzliche Latest-Ersetzung Frame356 während bestehender
   Verbindung anhand Quell-Publikationen/Poll-/ACK-Reihenfolge prüfen; kein
   Verlust nach COM-Schreiben. Keine ungepaarten Uhren subtrahieren.
3. UART über dieselbe gemeinsame Windows-Brücke prüfen. Direkter UART-Erfolg
   umgeht diese Strecke. Weitere Netz-/COM-/ACK-/Startreihenfolge-/Pufferfälle
   getrennt prüfen. Belegter Prozesswiederanlauf ersetzt sie nicht.
4. Workbench-Prototyp in die geplante Gestaltung übernehmen; Warnung,
   lokale Fortsetzung bei Abbruch, Audit vor Publish, Testlaufsperre und
   strukturelle DUT-Sperre erhalten. Native GSV-Protokolle nicht erfinden.
5. Erst nach belegter Ungültig-/Altwert-/Zeitbehandlung Freigabeimplementierung
   gesondert reviewen und je Weg mindestens30min Live-Abnahme. Historischer
   Import OQ-48 bleibt getrennt, keine alten Daten in aktuellen Stream nachholen.
6. Danach extern erreichbaren Ein-Befehl-Bootstrap/Setup-TUI/CLI für SSH
   umsetzen (OQ-49). SCP-Pilot ist kein veröffentlichter Installer.

### Wiederaufbau und bekannte Fallstricke

Pi raspi06/Pi5, SSH/TCP über Tailscale100.122.154.35; TCP-Port5000 zuletzt
frei, kein Demopublisher aktiv. Windows-Brückenordner:
C:\Users\EE-User-4\gsvmulti-demo-da3ed32a\bridge.
UserDefined COM6/115200/8N1, Zeichenpräfix%, ein Wert, Zahlenfilter ein,
Separator unused,10Hz,mV/V,Scaling1. Manuelle Aufnahme aller Werte, TXT-
Autoexport. Für neue Verbindung GSVmulti vollständig neu starten; Close/Open
scheitert mit Port already open (OQ-52/OQ-55), Workaround vom Nutzer akzeptiert.
LogLevel2 unter ProgramData/MEsystemeGSVmulti/config.ini, Logs C:\GSVmultiLog.
COM4 FTDI-USB-TTL; direkter Pi-UART ttyAMA0, RXD an physischem Pin8/TXD0,
GND an Pin6 laut Nutzer, übrige Kontakte frei. COM3 Intel AMT SOL.

Der endliche scripts/gsv-publisher-demo.py wartet pro Datensatz auf ACK;
für weiterlaufende Quelle bei Ausfall ungeeignet. Deshalb getrennter Throwaway-
Generator reconnect-source-spike.py unter var/diagnostics/gsvmulti/, ebenfalls
im Archiv. Windows-Controller unterbricht nur eigene Kindprozesse, keine
GSVmulti-Prozesse. Nicht als fertiges Produktionswerkzeug darstellen.

Originale/Rezepte weiter lokal unter var/diagnostics/gsvmulti/.292 relevante
Dateien zusätzlich versioniert im ZIP unter docs/quellen/ (Manifest/Hashes).
Drittanbieter-Treiber/Installer und npTDMS-Wheel nicht enthalten. Keine neue
Pi-Laufzeitabhängigkeit; .venv mit --system-site-packages, Installation --no-deps.
Reale Messbelege weiterhin nur GSV-2AS/Displaytech161A/Raumlicht/mV/V.
USB-C-Gadget auf Nutzerwunsch zurückgestellt: X1201V1.1 versorgt Pi; parallele
Pi-USB-C-Stromführung nicht freigegeben, kein Gadget aktiviert (OQ-56).

Unabhängige lokale Redesign-Entwürfe, Benutzer-Notizen und Synchronisations-
Dateien gehören nicht zum GSVmulti-Commit und bleiben im Arbeitsplatz erhalten.
Nachführung/Testlauf-Audit/alte Zeitbasis-Bezeichnungen (OQ-26/OQ-44/OQ-45)
weiter offen. Aktuelle Abschlussprüfungen und Commit stehen im Git-Verlauf;
keine vollständige Hardware-/Windows-Systemabnahme behaupten.

### Abschlussprüfung dieser Sicherung

87 gezielte GSV-/Live-Backendtests bestanden, Ruff grün,40 Node-Clienttests bestanden;
strikter Doku-Build und vollständige Wertevergleiche beider TCP-Versuche
bestanden. Vorheriger vollständiger Implementierungslauf:1805 Tests bestanden,
76 übersprungen,90 Doku-Browserfälle und2 Live-Browserfälle abgedeckt.
Die erneute vollständige pytest-/Doku-Browserwiederholung beim Sessionende
wurde auf ausdrücklichen Nutzerwunsch „werde jetzt fertig“ abgebrochen;
sie wird nicht als abgeschlossener grüner Lauf ausgegeben. Vor Merge die
vollständigen Doku-Browserprüfungen erneut abschließen. Kein Merge erfolgt.

## Snapshot vom 2026-10-31 (Messpfad und P4-3)

Dieser Snapshot fasst den zuletzt dokumentierten Stand zusammen. Er ist keine
Live-Abfrage; Hardware- und Messwerte verweisen auf ihre Aufzeichnungen.
Die Arbeitsliste steht in [TODO.md](../TODO.md), Entscheidungen in der
[Projektgeschichte](project_history.md), Messnotizen im
[Laborjournal](lab_journal.md).

### Messpfad und belegte Grenzen

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

### R13-Stand in `master`

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

### GSVmulti

Der `UserDefined`-Zahlenimport ist dokumentiert. `UserDefinedFormatter`,
Demo-Sender und opt-in Live-Ausgabe (API-Feld `output`, standardmäßig aus)
sind gebaut. Geprüft wurde lokal mit pty; das belegt weder den Empfang in
der eingesetzten GSVmulti-Version noch den Adapter oder eine Messfreigabe.
Offen bleiben Ungültig- und Altwertbehandlung ([OQ-06](open-questions.md#oq-06)),
die Telegrammfrage ([OQ-07](open-questions.md#oq-07)) und die GSVmulti-Zeitachse
([OQ-47](open-questions.md#oq-47)). Die
[Protokollbewertung](GSVMULTI_PROTOCOL.md) beschreibt den Prototyp und den
[Windows-Test](GSVMULTI_PROTOCOL.md#windows-test).

### Betrieb und nächste belegte Arbeiten

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
