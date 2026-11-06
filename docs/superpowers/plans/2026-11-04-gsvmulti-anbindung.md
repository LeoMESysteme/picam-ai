# GSVmulti-Anbindung — Arbeitsplan und Abnahme

**Stand 2026-11-04.** Dieser Plan hält den gemeinsam gewählten Aufbau und
seine Nachweisgrenzen fest. Softwareprüfungen ersetzen die untenstehenden
Windows-/Hardwareversuche nicht. Softwareprüfung: 1805 Python-Tests bestanden,
76 übersprungen; Ruff und strikter Doku-Build grün. Alle 90 Doku-Browserfälle
(inklusive gezielter Wiederholung nach Korrekturen) und zwei Live-Browserfälle
bestanden. Sechzehn direkte UART-Demoversuche auf Windows 11/GSVmulti 2.03 Pro
liegen inzwischen vor. Die vollständige Windows-/Hardware-Abnahme bleibt offen,
weil ungültige Zeiträume in der getesteten Aufnahme nicht erhalten bleiben.
[Messbelege](../../VALIDATION.md#uart-demo-20261104-10).

## Ziel und Architektur

Ein optisch gelesener DUT-Kanal in mV/V soll GSVmulti erreichen. Pro Lauf
wählt der Bediener Aus, UART oder Netzwerk in der Workbench. Beide
Übertragungswege benutzen dieselbe eigene Windows-Brücke:

```text
Pi → TCP oder bidirektionale UART → Windows-Brücke → com0com-Portpaar → GSVmulti UserDefined
```

Bei einem erkannten Verbindungsabbruch warnt die Workbench; Kamera und
lokales Audit laufen weiter. Nach Wiederverbindung sollen frische Werte
weiterlaufen. Historische Daten bleiben separat erhalten. **Echte
DUT-Zahlen sind derzeit strukturell gesperrt**, bis GSVmulti ungültige und
alte Werte nachweislich richtig behandelt. Der Software-Prototyp besitzt
keinen Schalter zum Umgehen dieser Sperre.

## Etappen und Stand

| Etappe | Liefergegenstand | Stand |
| --- | --- | --- |
| 1 | Windows-/GSVmulti-Version, com0com-Portpaar und DELOCK-Kabel prüfen | teilweise: Windows 11/2.03 Pro und FTDI COM4 bestätigt; direkte TX/GND-Strecke funktioniert. nach Buildvergleich sechs com0com-Geräte Code0, Paar COM5/COM6 bidirektional geprüft, Schutz weiter aktiv; genaues Kabelmodell offen |
| 2 | Empfang, Einheit, Auflösung, NaN, Pausen und Altwertpuffer mit Demodaten prüfen | teilweise: Rampen und acht gespeicherte Sprünge korrekt; Timeout/Fortsetzung belegt. NaN/Pausen auch mit Replace Missing Values im Export unmarkiert; mV/V/Skalierung 1 in TDMS/Session belegt; Altwertpuffer offen |
| 3 | `UserDefinedFormatter` und versioniertes internes Brückenprotokoll | Software implementiert und geprüft; Format bleibt provisional, SEND_NAN nur Demo |
| 4 | Gemeinsame TCP-/UART-Brücke, begrenzte Nachrichten, Bestätigungen, Wiederanlauf | Software implementiert; TCP mit600/600 exakten Werten in TXT/TDMS belegt; Abbruch/Altwerte und gemeinsamer UART offen |
| 5 | Live-Auswahl, Warnung, Audit vor Veröffentlichung, Testlaufsperre | Software implementiert; echte Ausgabe bleibt gesperrt |
| 6 | Beide Wege am Aufbau prüfen | direkte UART-Demo teilweise belegt; gemeinsamer TCP-Demoweg600/600 exakt gespeichert, Abbruch/Altwerte und gemeinsamer UART offen. Je Weg mindestens 30 Minuten Live erst nach Freigabeschranke |
| 7 | Historischen Import mit ursprünglichen Zeiten untersuchen | offen, OQ-48; kein fertiger Historien-Konverter |

## Schnittstellen und Sicherungen

- Die strukturelle DUT-Sperre gilt nur für die Brückenwege; P4-3 direkt bleibt Opt-in mit ausdrücklicher Bestätigung der fehlenden Abnahme (Nutzerentscheidung 2026-11-06).

- Optionales `output` an `/live/run/start`, ohne Auswahl `off`.
  `/live/status` ergänzt Ausgabestatus; `session.json` hält Konfiguration,
  Formatterfähigkeiten und Sperrgrund fest.
- `OutputConfig`/`OutputPublisher` trennen Transport vom Leser.
  `UserDefinedFormatter` erhält `raw_text`-Dezimalauflösung und prüft die
  Übereinstimmung mit dem endlichen Zahlenwert. `gsv_ascii.py` bleibt
  der werfende native Platzhalter.
- Das eigene JSONL-Brückenprotokoll trägt Laufkennung, Bildnummer, Status
  und Aufnahmezeitbasis. Eine Brückenbestätigung belegt nur einen
  COM-Treiberschreibvorgang, keinen GSVmulti-Empfang.
- Höchstens eine Anfrage und ein jüngster Zahlenwert; unbestätigte
  Invalidierung bleibt separat verriegelt. Sie darf nicht durch einen
  folgenden gültigen Zahlenwert verschwinden. Kein historischer Aufholburst.
- Aufnahme-Audit wird vor Veröffentlichung geschrieben und je Lauf nicht
  wegrotiert. Fehler des Transportwegs lassen es weiterlaufen; Auditfehler
  bleiben ein harter Stopp. Testläufe mit übergangener Lesesperre geben
  auch bei späterem `VALID` keine externen Zahlen aus.
- Vorgaben: 115200 Baud, 8N1, kein Handshake; TCP-Port 5000; Prototypgrenze
  für das Alter bis zum COM-Schreibvorgang 1000 ms. Sie ist kein
  QM-Grenzwert. Synthetische Demowerte liefern keine Latenzaussage.

## Abnahme am Windows-PC und Aufbau

1. Tatsächliche Windows-/GSVmulti-Version und PRO-Funktion erfassen.
   UserDefined-Definition mit `%`, einem Wert, Dezimalpunkt und CRLF sichern;
   Einheit und Skalierung auf mV/V prüfen.
2. com0com-Originaltreiber und Portpaar prüfen, beide Portnamen festhalten.
   Brücke und GSVmulti öffnen unterschiedliche Seiten dieses Paars.
   Python-/pySerial-Einrichtung nach [Abhängigkeiten](../../dependencies.md#windows-bruecke).
3. Kabelartikel, 3,3-V-Signalpegel und Aderbelegung vor GPIO-Anschluss
   bestätigen. „DELOCK 3V“ und die AWM-Isolationsangabe sind kein vollständiger
   Modellnachweis. TX/RX über Kreuz und GND gemäß geprüfter Belegung;
   VCC/CTS/RTS frei. Pi `/dev/ttyAMA0`, Referenzeingang `/dev/ttyUSB0` frei lassen.
4. Endliche Folge von 600 eindeutigen Demowerten bei 10 Hz aufnehmen.
   `scripts/gsv-publisher-demo.py` stellt dafür einen synthetischen
   TCP-/UART-Quelllauf mit Audit und COM-Schreibbestätigungen bereit.
   Bytefolge, Vorzeichen, Null und Dezimalauflösung mit Anzeige und Export
   vergleichen. Erste vollständige Nachricht und kontrollierte Pausen prüfen.
5. Ungültige Zustände, NaN, STALE und fehlende Daten in Anzeige, Datei und
   späterer Auswertung prüfen. Blockierten Empfänger und Freigabe seiner
   Puffer untersuchen. Kein alter Wert darf unmarkiert als aktuell gültig
   erscheinen. Fehlt dieser Nachweis, bleibt echte DUT-Ausgabe gesperrt.
6. Beide Wege getrennt unterbrechen: Netz/Kabel, COM-Port, Windows-Brücke,
   GSVmulti und Pi-Neustart; verschiedene Startreihenfolgen, längere Pause
   und ACK-Verlust prüfen. Lokales Audit muss bei Transportfehler weiterlaufen.
   Warnung und Wiederanlauf dürfen keinen GSVmulti-Empfang erfinden.
7. Erst nach bestandenem Ungültig-/Altwertnachweis die weitere
   Freigabeimplementierung reviewen und je Weg mindestens 30 Minuten Live
   prüfen. Das ist keine allgemeine metrologische Kalibrierfreigabe.
8. Historischen Import anhand eines kontrollierten Ausfalls separat prüfen:
   ursprüngliche Zeiten, Einheit und ungültige Abschnitte erhalten. Logger-
   Text/TDMS im File Monitor sind nur Kandidaten; Ergebnis und Grenzen als
   Beispielbeleg dokumentieren (OQ-48).

Durchgeführte Messungen gehören am selben Tag nach VALIDATION und ins
Laborjournal; Hardwareänderungen zusätzlich ins Hardwareprofil, soweit
konfigurationswirksam. Die oben aktualisierten Teilbelege sind unter
[VALIDATION](../../VALIDATION.md#uart-demo-20261104-10) abgelegt; daraus folgt
keine vollständige Abnahme.

## Softwareprüfung und Abschluss

Formatter, fragmentierte/überlange Nachrichten, Invalidierungssperre,
ACK-Zuordnung, Freigabesicherung, Audit-Reihenfolge und Live-Lebenszyklus
werden mit Projekt-`.venv` geprüft. Dazu Ruff und Live-Browsertests.
Vor Merge der Doku: `./scripts/docs-site.sh build -s` sowie
`npx playwright test -c playwright.docs.config.ts`.
CHANGELOG, Entscheidungshistorie, offene Fragen samt erzeugtem Index und
Statussnapshot begleiten die Implementierung. Bestehende offene
Windows-/Hardwarefragen werden nicht durch Softwaretests geschlossen.


## Fortsetzung nach den direkten UART-Versuchen

Die Integration wird an unabhängig prüfbaren Punkten fortgesetzt. Reale
DUT-Ausgabe und mindestens 30-minütige Live-Abnahme warten auf die belegte
Ungültigbehandlung. Die Untersuchung von Senderpause, NaN und Replace Missing
Values wird anhand des [lokalen Reproduktionsfalls](../../GSVMULTI_PROTOCOL.md#userdefined-ungueltig-repro)
mit der GSVmulti-Entwicklung geklärt; keine Nachricht wurde versandt.

1. **Einheit mV/V belegt:** Lauf 11 speichert 510 unveränderte Zahlen,
   Scaling=1 und mV/V in TDMS und der gespeicherten Session. TXT ohne eigene
   Einheit; zusammen mit Metadaten aufbewahren. Neuladen der Session nicht
   getestet. [Beleg](../../VALIDATION.md#uart-demo-20261104-11).
   Keine neue Ungültig-/Zeitschranke wird durch diesen Versuch erfüllt.
2. **Altwert-/Puffernachlauf separat untersuchen:** Lauf 12 scheitert am
   Wiederöffnen nach Device/Channel Close (805306614, Port bereits offen).
   Externe COM4-Probe bei laufendem GSVmulti verweigert, nach vollständigem
   Prozessende erfolgreich. Das spricht für einen Prozess-/Bibliotheks-
   Ressourcenfehler; direkte Handle-Zuordnung fehlt
   ([OQ-52](../../open-questions.md#oq-52)). Kein erfolgreicher Puffervergleich.
   Erst nach vollständiger
   Vorbereitung ein synthetisches Versuchsschema mit unterscheidbaren
   Zahlenfolgen verwenden. Bislang belegt sind no-byte Pause und Fortsetzung
   bei offenem Port; weder physische Trennung noch Prozessneustart oder
   gemeinsame Brücke sind dadurch abgenommen.
3. **Gemeinsame Windows-Brücke:** com0com-Code-52-Problem bleibt offen.
   Direkten UART-Erfolg nicht als Brücken-/TCP-Abnahme zählen. Keine
   ungeprüfte Treiber- oder Sicherheitsänderung aus den Zahlenversuchen ableiten.

## Spätere vereinfachte Einrichtung (Nutzerwunsch 2026-11-04)

Extern abrufbarer Ein-Befehl-Bootstrap, ohne vorab geklontes Repo: vorhandene
Komponenten erkennen und wiederverwenden, Fehlendes herunterladen und
einrichten; anschließend Setup-TUI/CLI. SSH-Zielhost und dessen Plattform
ermitteln; Windows-COM-Einrichtung über CLI ohne GUI-Abhängigkeit. Zugang,
Release-Quelle und Versions-/Integritätsprüfung stehen in OQ-49. Dieser
Ausbau ersetzt den aktuellen manuellen Empfangstest noch nicht.

## Stand nach UART-Demo 16

Filter-ein-Kontrolle15 liest gültige Zahlen korrekt; NaN-Zeitraum bleibt im
Export unmarkiert verdichtet. A-Präfix mit Filter aus (16) bleibt durchgehend
auf Timeout, auch für gültige Zahlen. Damit ist kein nutzbares Filter-aus-
Profil gefunden. [Belege](../../VALIDATION.md#uart-demo-20261104-16).
Nächster Schritt ist ein lesendes Inventar tatsächlich geladener Windows-
GSV-Bibliotheken ([OQ-54](../../open-questions.md#oq-54)); keine weiteren
Präfixvarianten ohne neue Evidenz. Kein Sender aktiv, echte DUT-Ausgabe gesperrt.

## Aktuelle Priorität nach Nutzerentscheidung

GSVmulti-Fehler können derzeit nicht behoben werden; vollständiger Neustart
wird als vorläufiger Workaround akzeptiert. Keine weiteren gleichartigen
Close-/Open-Versuche. Nächste bestehende Etappe ist die gemeinsame Windows-
Brücke: zuerst funktionsfähiges virtuelles COM-Portpaar (com0com derzeit
Code52/OQ-47), dann gültige synthetische Demofolge über TCP und gesondert
UART durch dieselbe Brücke. Die direkte UART-Demo hat diese Strecke umgangen.
NaN-/Ungültig-/Altwert-/Zeitnachweis bleibt Freigabeschranke für echte Werte;
die Akzeptanz des Neustart-Workarounds hebt sie nicht auf. Kein neuer Versuch
oder Treiberwechsel durchgeführt. Späterer Bootstrap/TUI bleibt OQ-49.

## Stand nach com0com-Buildvergleich

Nutzer meldet sechs com0com-PnP-Geräte Code0, Paar1 COM5/COM6. Aktueller Code52-
Blocker überwunden, Datenübertragung und post-installierter Hash-/Schutzstatus
noch offen. Zuerst bidirektionale Portprobe mit garantiertem Schließen,
anschließend gemeinsame Windows-Brücke und TCP mit synthetischen Daten.
OQ-47 teilweise geklärt, keine vollständige Windows-/GSVmulti-Abnahme.

## Nächster Checkpoint: Windows-Python und lokale Brückendemo

COM5/COM6-Datenprobe und post-installierter Hash-/Schutzstatus sind jetzt
belegt. Nutzer besitzt Paket noch nicht auf Windows. Geprüftes portables ZIP
per bestehendem SSH übertragen, Python3.15-venv/pyserial3.5 einrichten und
zuerst --help prüfen. Danach synthetische Demo auf COM5, GSVmulti auf COM6
und Empfängerexport vergleichen. Keine weitere Treiberdiagnose ohne neuen
Fehler. TCP und tatsächlicher Pi-Publisher folgen nach lokalem Brückenerfolg.

## Checkpoint Windows-Python erreicht, lokale Demo als Nächstes

Nutzer bestätigt Pakettransfer, Python3.15/pyserial3.5 und --help. Jetzt
GSVmulti auf COM6 mit bekanntem gültigem Profil vorbereiten, Aufnahme starten,
dann vorhandene lokale600er-Demo auf COM5 und Export/Log vergleichen. Kein
Pi-Sender nötig. TCP-/JSONL-/ACK-Nachweis und echte DUT-Freigabe weiter offen.

## Checkpoint lokale Windows-Demo erreicht, TCP als Nächstes

600/600 Werte exakt in TXT/TDMS, mV/V/Scaling1/COM6 bestätigt. Lokaler
Windows-Demomodus belegt, gemeinsamer Pi-JSONL-/ACK-Austausch noch offen.
Demo-Takt9,0576Hz bei Ziel10Hz und nominelle Zeitachse getrennt dokumentiert
(OQ-57/OQ-50), kein Latenznachweis. Nächste Probe: Pi-TCP-Quelle600/Ziel10Hz,
Windows-Abfrage100Hz, bestehendes COM5/COM6-Paar, neue Aufnahme/Logs.
Windows-Brücke vorbereiten und erst nach Nutzer-bereit Pi-Publisher starten.
## Checkpoint gültiger TCP-Dateipfad erreicht

Pi-Audit,600 Angebote/ACKs und600 Windows-Payloads vollständig passend;
TXT/TDMS enthalten alle600 Werte exakt, mit mV/V/Scaling1 auf COM6.
[Beleg](../../VALIDATION.md#tcp-demo-20261104-01). Kein Verbindungsfehler
innerhalb der Zahlenfolge, Timeouts nur vor/nach dem endlichen Senderlauf.
Kein Nachweis für Wiederanlauf unter laufender Quelle oder Altwertpuffer.
Als Nächstes bestehende Abbruch-/Wiederanlaufprüfung mit synthetischen Werten,
UART über dieselbe Brücke separat. Keine neue Markerprobe oder DUT-Freigabe;
GSVmulti-Close/Open nicht wiederholen, akzeptierter Neustart-Workaround bleibt.

## Laufender Checkpoint: Brückenprozess unterbrechen, Quelle weiterführen

Nutzer stimmt dem nächsten Schritt zu. Der bisherige endliche Demopublisher
wartet pro Datensatz auf ACK; deshalb Throwaway-Quellgenerator mit unabhängig
weiterlaufenden600 synthetischen Werten/Ziel10Hz und Audit vor Publish.
Lokale TCP-/Memory-COM-Vorprobe bestanden, kein Windows-Nachweis.
Windows-Controller stoppt nur seinen eigenen Brückenprozess nach100 written-
Logeinträgen, wartet10s und startet ihn neu. Vorher-/Nachher- und Steuerlogs
getrennt; Quellpublikationen mit Pi-HOST_MONOTONIC, Steuerung mit Windows-
HOST_MONOTONIC. Kein Vergleich ungepaarter Uhren und kein physischer Frische-
beleg aus SYNTHETIC. GSVmulti-Kanal/Recorder bleiben offen; neue Aufnahme vor
Test, Pi-Start erst nach Nutzer-bereit. Archiv und neue TXT/TDMS danach gegen
Quellaudit und Wiederanlaufangebote vergleichen. Kein Produktcode geändert.

## Sessionende: Prozesswiederanlauf belegt, Übergabe statt weiterer Versuche

600 unabhängig erzeugte Quellwerte,510 COM-geschriebene Werte vollständig und
exakt in TXT/TDMS. Windows-Controller nach100 written beendet,10s Pause,
Neustart mit neuestem Angebot189 nach99; kein Zwischenhistorienpuffer, Anzeige
ohne Eingriff fortgesetzt. Quelle/TCP/COM-Nähte vollständig verknüpft.
[Beleg](../../VALIDATION.md#tcp-reconnect-20261104-01). Frame356 zusätzlich
vor Angebot ersetzt (OQ-58); kein Datenverlust nach COM-Schreiben. GSVmulti
verdichtet die Unterbrechung weiterhin auf0,1s, daher keine echte DUT-Ausgabe.
Nutzer beauftragt Dokumentation, Commit und Push; weitere Messungen ausgesetzt.
Fortsetzung über ../../status.md: vorhandene Workbench-Auswahl/Backendnaht
weiterverwenden, keine zweite Brücke bauen und keinen Freigabebypass ergänzen.
