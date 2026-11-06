---
weg: entwickeln
---

# GSVmulti-Anbindung

**Vorher lesen:** [Messpfad und Freigabe](uebersicht/messpfad.md#ausgabe-und-fehlersuche)
und [Zeitstempel richtig lesen](uebersicht/zeitstempel.md#von-aufnahme-bis-gsvmulti).

## Stand: Software-Prototyp gebaut, nicht freigegeben; Brücken-DUT-Ausgabe gesperrt {#stand-das-format-ist-unbekannt}

**Stand 2026-10-30:** Das bereitgestellte PDF samt Beispiel-ZIP reicht als Grundlage für einen
**Transportprototyp**, noch nicht für eine freigegebene Messanbindung.
GSVmulti PRO bietet mit `UserDefined` einen konfigurierbaren seriellen
Zahlenimport. Ein Nachbau des GSV-2-/GSV-6-/GSV-8-Geräteprotokolls ist für
diesen Weg nicht erforderlich. Die vorherige Aussage „das Eingangsformat
ist vollständig unbekannt“ ist damit überholt
([OQ-01](open-questions.md#oq-01), [OQ-07](open-questions.md)).

**Stand 2026-11-04:** UserDefined-Formatter, gemeinsame Windows-Brücke und
Live-Konfiguration für Netzwerk oder UART sind als Software-Prototyp gebaut.
Die damalige Workbench bot **Aus / UART / Netzwerk**. Pro Lauf war ein Weg gewählt.
Ein erkannter Verbindungsabbruch unterbricht Kamera und lokales Audit nicht;
die Brücke versucht die Verbindung erneut aufzubauen. Das ist noch kein
Nachweis des Empfangs oder der Speicherung durch GSVmulti
([OQ-07](open-questions.md#oq-07)).

**Ausgabevertrag (Nutzerentscheidung 2026-11-06):** Pro Lauf gibt es genau
einen Ausgabeweg: `off` = Aus, `serial` = P4-3 direkt, `uart` = UART über
die Windows-Brücke oder `tcp` = Netzwerk über die Windows-Brücke.
Bestehende `output`-Objekte ohne `transport`, aber mit `port`, wählen
weiterhin `serial`. Testläufe erlauben keine externe Ausgabe; die
Brückenwege bleiben für echte DUT-Werte bis zum Ungültig-/Altwertnachweis
strukturell gesperrt. „UART direkt“ (P4-3) gibt weiter echte Werte aus, ist
aber dauerhaft als „Prototyp – nicht am Windows-PC abgenommen, keine
Messfreigabe“ gekennzeichnet und startet nur nach ausdrücklicher Bestätigung
dieses Hinweises (`acknowledge_unaccepted`). Ungültige Werte werden dort
ausgelassen; GSVmulti zeigt dann den letzten Wert unmarkiert weiter
([OQ-06](open-questions.md#oq-06)).

**Echte DUT-Ausgabe über die Brücke bleibt strukturell gesperrt.** Der Pi beantwortet
Brücken-Live-Abfragen ohne DUT-Zahlen; die Windows-Brücke lehnt nichtsynthetische
Messdaten ab. Es gibt keinen Freigabeschalter in der Oberfläche. Erst ein
belegter Umgang mit ungültigen Werten und Altwerten in den COM-Puffern
ermöglicht einen weiteren Freigabeschritt. Lokale Live-Läufe bleiben möglich.
[Arbeitsplan und Abnahme](superpowers/plans/2026-11-04-gsvmulti-anbindung.md).

GSVmulti PRO bietet mit `UserDefined` einen konfigurierbaren Zahlenimport.
Ein Nachbau des nativen GSV-Geräteprotokolls ist dafür nicht erforderlich.
Der Nutzer meldet am 2026-11-04 **Windows 11 und GSVmulti 2.03**; Python
3.15 x64 und der sichtbare Port COM3 wurden per PowerShell zurückgemeldet.
Nach Aktivierung der PRO-Lizenz bestätigt der Nutzer `UserDefined` als
verfügbar. Direkte UART-Demowerte und Einzelwertaufzeichnung sind inzwischen belegt;
die gemeinsame Windows-Brücke und der Umgang mit ungültigen Zeiträumen
bleiben zu prüfen. Das frühere
PDF dokumentierte 2.01 Pro und beschreibt damit nicht die aktuelle Installation.
Die Herstelleranleitung v2.6 ist ein Dokumentstand, kein Versionsnachweis.

| Gebaut | Noch offen |
| --- | --- |
| Einkanalige `UserDefinedFormatter` als `TelegramFormatter` für einen freigegebenen DUT-Wert pro Zeile, `provisional=True`; Brücken-Formatter erhält vorhandene Dezimalauflösung | Ungültig-/STALE-Verhalten in Anzeige, Datei und Kalibrierauswertung; ungültige Zeiträume und vollständige GSVmulti-Abnahme über die gemeinsame Brücke |
| Eigenständiger Sender für endliche Demowerte mit festem Zahlenprofil und gemeinsame TCP-/UART-Brücke | Ursprünglicher Prüfauftrag: Annahme und Aufzeichnung in der im PDF dokumentierten 2.01-Pro-Installation. Spätere Windows-Python-/TCP-Demobelege für 2.03 Pro stehen unten; vollständige Abnahme bleibt offen. Portpaar COM5/COM6 inzwischen bidirektional geprüft. |
| Serielle Ausgabe mit vorhandenem `SerialSink` an einen passenden COM-Transport; versionsgebundenes internes Brückenprotokoll mit Lauf-/Bildkennung und Invalidierungssperre | Port, Treiber, Pufferung, Wiederanlauf und Dauerbetrieb; NaN-/STALE-Verhalten, Puffernachlauf und Zeitachse in GSVmulti |
| Opt-in-Ausgabe in `/live`, Live-Auswahl und Verbindungsstatus mit parallelem vollständigem JSONL- und Tx-Audit | Tatsächlicher Transport, UART-Kabel/Pinbelegung sowie Hardware- und Ende-zu-Ende-Abnahme am Windows-PC |

**Die vollständige Messfreigabe bleibt offen.** P4-1 (Formatter) und P4-2
(Demo-Sender) sind als Prototyp gebaut und mit pty/Fakes geprüft, **ungeprüft
am Windows-PC**. P4-3 (Live-Anbindung) ist ebenfalls gebaut und lokal mit
pty/Fakes geprüft, am Windows-PC ungeprüft; die Phase ist nicht abgenommen.

## Windows-Brücke vorbereiten {#windows-bruecke}

Beide Wege benutzen dieselbe Brücke:

```text
Pi → TCP oder UART → Windows-Brücke → virtuelles COM-Portpaar → GSVmulti
```

Die kostenfreie Grundlage ist ein com0com-Portpaar. Nach Wechsel zur
[Vovsoft-verlinkten Ausgabe](https://vovsoft.com/blog/how-to-sniff-serial-port-communication/)
ist COM5↔COM6 auf dem Zielrechner bidirektional geprüft, SecureBoot und
Speicherintegrität bleiben aktiv. [Beleg](VALIDATION.md#com0com-pair-ok-20261104).
Die Brücke öffnet COM5, GSVmulti COM6. Windows-Python-Brücke und Empfang
durch GSVmulti über dieses Paar sind noch nicht abgenommen.

1. Windows-/GSVmulti-Version und PRO-Funktion festhalten; den belegten
   Treiberstand samt Hash sichern. Vorhandenes Paar CNCA1=COM5/CNCB1=COM6
   verwenden. Auf anderen Zielrechnern beide tatsächlichen Portnamen nachweisen.
2. Projekt auf Windows bereitstellen. Eine eigene Python-Umgebung mit
   Python 3.13 oder neuer und pySerial 3.5 verwenden. Die Brücke lädt keine
   Kamera-/OpenCV-Pakete; siehe [Abhängigkeiten](dependencies.md#windows-bruecke).
3. In GSVmulti den gegenüberliegenden Port als `UserDefined`, einen Wert,
   Präfix `%`, Dezimalpunkt und CRLF konfigurieren. Einheit und Skalierung
   gesondert auf mV/V prüfen. Keine bestätigten COM-Nummern durch die
   Beispiele `COM20`/`COM21` ersetzen.
4. Zunächst lokal Demodaten senden. Die folgenden Portnamen sind Beispiele:

```powershell
.\.venv\Scripts\python.exe scripts/gsv-bridge.py --demo --com-port COM20 --count 600 --rate-hz 10 --log bridge-demo.jsonl
```

Ohne COM ist der erzeugte Zahlenstrom auf dem Pi prüfbar:

```bash
./.venv/bin/python scripts/gsv-bridge.py --demo --stdout --count 3 --rate-hz 10 --log /tmp/bridge-demo.jsonl
```

Danach den Verbindungsweg prüfen. Auf dem Pi zuerst einen synthetischen
Publisher starten; für jeden Versuch ein neues Ausgabeverzeichnis verwenden:

```bash
./.venv/bin/python scripts/gsv-publisher-demo.py --transport tcp --out-dir var/gsv-demo-tcp --count 600 --rate-hz 10
./.venv/bin/python scripts/gsv-publisher-demo.py --transport uart --out-dir var/gsv-demo-uart --count 600 --rate-hz 10
```

Die beiden Befehle sind alternative Versuche. Der Publisher wartet
standardmäßig bis zu 30 Sekunden auf die Brücke. Er schreibt jeden
Demodatensatz vor Veröffentlichung ins Audit und zählt erst nach
COM-Schreibbestätigung weiter. Bleibt diese aus, wird der Versuch als
unvollständig abgeschlossen. Die Rate ist ein Ziel für den Versuch, kein
Nachweis über erreichten Durchsatz; synthetische Zeitangaben tragen keine
Latenzaussage. `session.json` hält Demomarkierung, angeforderte und bestätigte
Anzahl sowie Abschlussgrund fest.

Dann auf Windows den passenden Brückeneingang wählen:

```powershell
.\.venv\Scripts\python.exe scripts/gsv-bridge.py --tcp-host <PI-IP> --com-port COM20 --log bridge-tcp.jsonl
.\.venv\Scripts\python.exe scripts/gsv-bridge.py --uart-port <USB-TTL-COM> --com-port COM20 --log bridge-uart.jsonl
```

Im normalen Live-Lauf erscheint weiterhin die DUT-Ausgabesperre. Ein
geöffneter COM-Port oder die Brückenbestätigung `written` beweist nur den
Schreibvorgang zum Treiber, keine Übernahme durch GSVmulti. Für die
Zuordnung dienen Laufkennung und Bildnummer; Zeilennummern allein reichen
nach einer Lücke nicht aus.

### com0com: Code 52 des Originalpakets und aktueller Buildvergleich {#com0com-code52}

Am Zielrechner Windows 11 meldet der Nutzer für beide com0com-Busgeräte
`Status: Error` und `ConfigManagerErrorCode: 52`. Der Nutzer bestätigt,
die signierte Ausgabe installiert zu haben; Paketversion/Zertifikat wurden
nicht unabhängig geprüft. Nach
[Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/cm-prob-unsigned-driver)
bedeutet Code 52, dass Windows die erforderliche Treibersignatur nicht
akzeptiert und das Gerät nicht startet. Eine COM-Namensänderung behebt
diesen Startfehler nicht; die vorhandene Installation ist für diesen
Empfangstest noch nicht verwendbar. Die GUI-.NET-Meldung ist davon getrennt.

Nächste Wahl ist noch offen: VSPE lässt sich laut
[Hersteller](https://eterlogic.com/Products.VSPE_License.html) zunächst
erproben; für den geplanten dauerhaften/automatisierten Firmenbetrieb
ist eine passende Lizenz zu klären. HHD Free Virtual Serial Ports schließt
in den [Free-Version-Grenzen](https://freevirtualserialports.com/features)
kommerzielle Nutzung ausdrücklich aus und ist damit keine kostenlose
Standardlösung für diesen Laborbetrieb. Ein direkter UART-Demotest könnte
den UserDefined-Empfang ohne virtuellen COM-Treiber prüfen; dabei wären
Kabelbelegung und realer Windows-Adapterport vorher zu bestätigen. Das wäre
ein isolierter Empfangstest, kein Nachweis der gemeinsamen Netzwerk-/UART-
Brücke. Es wurde noch keine dieser Alternativen auf Windows installiert
oder abgenommen.

**Aktuelle Fortsetzung 2026-11-04:** Nach direktem UART-Test und USB-
Machbarkeitsuntersuchung wählt Nutzer erneut com0com. Nächster Schritt ist
lesendes PnP-/Treiberinventar: tatsächlicher Fehlercode, Version, Provider,
zugeordnete INF, IsSigned und Signer. Danach konkrete
[CodeIntegrity-Ereignisse](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/troubleshooting-driver-signing-installation)
korrelieren. Signiert-Metadatum allein belegt keine erfolgreiche
Kernel-Ladefreigabe. Kein Treiberwechsel oder Portpaarerfolg behauptet.

**Aktuelles Inventar:** Beide Geräte0000/0001 melden weiterhin
CM_PROB_UNSIGNED_DRIVER. Zugeordnet ist com0com3.0.0.0, Provider Vyacheslav
Frolov, `oem234.inf`, IsSigned=False, Signer leer. Nutzer nennt ZIP
com0com-3.0.0.0-i386-and-x64-signed. Das
[offizielle Projektarchiv](https://sourceforge.net/projects/com0com/files/com0com/3.0.0.0/)
enthält getrennte x86-/x64-Installer, lokal nur heruntergeladen und gelistet,
nicht ausgeführt. Welche EXE auf Windows lief und welche Katalogdatei dem
aktiven Paket zugeordnet ist, bleibt offen. Archivname allein beweist keine
Windows-Ladefreigabe. Als Nächstes aktive INF-Metadaten und passende
CodeIntegrity-Ereignisse lesen. Treiber können
[über einen Katalog signiert sein](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/catalog-files);
Datei-, Paket- und Kernel-Ladeprüfung nicht gleichsetzen. Keine Neuinstallation
oder Entfernung aus den bisherigen Metadaten allein ableiten.

**Installerwahl anschließend geklärt:** Nutzer führte die x86-EXE aus.
Beide offiziellen Installer rein statisch entpackt und com0com.sys-PE-Header
geprüft: x86-Paket Machine014c, x64-Paket8664. Der x86-Kerneltreiber ist für
den Intel-Windows11-Rechner ungeeignet; Microsoft beschreibt die
[Architekturgrenze](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/porting-your-driver-to-64-bit-windows).
Das beweist nicht die Architektur der aktuell gebundenen Windows-Datei oder
alle Ursachen von Code52. INF-Abfrage meldet oem234.inf nicht vorhanden;
der kombinierte Block bricht deshalb vor der CodeIntegrity-Abfrage ab.
Keine Ereignisausgabe oder neue Treiberzuordnung empfangen. INF-Dateinamen
nicht als dauerhaft fest behandeln, keine Zwangslöschung anhand alter Angaben.
Nächster Schritt: Setup_com0com_v3.0.0.0_W7_x64_signed.exe aus demselben ZIP
normal installieren und Geräte-/Paketstatus danach neu erfassen. Signatur-
akzeptanz bleibt zu prüfen; bei weiterem Fehler CodeIntegrity unabhängig von
der INF-Abfrage lesen. Noch keine Installation dieses Schritts bestätigt.

**Nach x64-Anleitung:** Nutzerinventar unverändert: zwei Geräte mit
CM_PROB_UNSIGNED_DRIVER und oem234.inf/IsSigned=False. Als Setup-Meldung
berichtet Nutzer erneut nur fehlende .NET2.0-GUI-Laufzeit. Keine erfolgreiche
Treiberbindung oder Kernel-Ladung daraus ableiten. Jetzt PnPUtil-Gerätedetails,
registrierten com0com-Treiberpfad und unabhängige CodeIntegrity-Ereignisse
lesen; nicht erneut anhand unveränderter Metadaten installieren.

**Konkreter CodeIntegrity-Befund:** PnPUtil erkennt jetzt CyberCircuits als
Signierer von oem234.inf, Gerät bleibt mit Code52/0xC0000428 blockiert.
Registrierter Treiber C:\windows\system32\drivers\com0com.sys, Dienst Stopped.
Zweimal3004: Image-Integrität nicht prüfbar, Dateihash im System nicht gefunden.
Älteres3076: Audit-Regel verletzt, Laden laut Meldung erlaubt. Dieses Ereignis
allein ist kein aktueller Sperrnachweis. [Mess-/Diagnosebeleg](VALIDATION.md#com0com-ci-20261104).
WMI-IsSigned=False, PnP-Katalogsignierer und Kernel-Verifikation sind getrennte
Befunde. Nächster Schritt: aktive Datei mit Original per SHA256 und Windows-
Authenticode vergleichen. Kein konkreter x86-Rest, Dateischaden, fehlender
Katalog oder Secure-Boot-Fehler isoliert bewiesen; nichts manuell in CatRoot
oder Zertifikatsspeicher kopieren. Keine Treiber-/Sicherheitsänderung erfolgt.

**Dateivergleich geklärt:** Nutzer-SHA256 der aktiven com0com.sys stimmt exakt
mit dem unabhängig gesicherten offiziellen x64-Original überein; Windows-
Authenticode meldet Valid/CyberCircuits. Ein x86-Rest oder abweichender Inhalt
an diesem Pfad ist damit ausgeschlossen. Kernelzulassung und Katalogzustand
sind separate Prüfungen. Microsoft beschreibt strengere
[Kerneltreiber-Signierungsanforderungen](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-).
Welche Richtlinie auf dem Zielgerät wirkt, ist noch nicht nachgewiesen.
Jetzt Windows-Build, Secure Boot und DeviceGuard/HVCI nur lesen. Keine
Zertifikatsablauf-/Secure-Boot-Ursache aus dem bisherigen Befund allein ableiten.

**Schutzstatus nun belegt:** Windows11 Pro10.0.26200, Secure Boot aktiv,
VBS/Speicherintegrität laufen, CI erzwungen. AuthenticodeValid des Original-
x64-Builds ist somit weiterhin kein Kernel-Ladenachweis. Welche konkrete
Prüfung ablehnt, bleibt unisoliert; keine Schutzfunktion ändern.

**Weiterer gezielter com0com-Kandidat:** [Vovsoft verlinkt selbst](https://vovsoft.com/blog/how-to-sniff-serial-port-communication/)
ein [kombiniertes Setup im eigenen Repository](https://github.com/vovsoft/com0com).
Statische Prüfung: x64-Treiber mit anderem Inhalt und Signierer Christos
Nikolaou, Zertifikat ab13.6.2012. Das liegt vor dem Altersstichtag der
[Microsoft-Ausnahmeregel für Cross-Signaturen](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-),
belegt aber keine Erfüllung aller Bedingungen oder HVCI-Kompatibilität.
Kein moderner Microsoft-WHQL-Build behauptet. Ein kontrollierter normaler
Installationsversuch nach Sicherung/normaler Entfernung des bisherigen
com0com ist vorbereitet. Installer-Hash
`ae0dd19472f92bab3165d370c3713616a3ffb708fad785684759b04653705a71`;
Treiber-Hash und Quellen im Diagnoseverzeichnis. Installerhülle ohne eigene
eingebettete Signatur, Treibersignatur separat vorhanden. Keine EXE ausgeführt,
kein Sicherheitswechsel oder erfolgreiches Windows-Portpaar belegt.

**Aktueller Erfolg nach angeleitetem Buildvergleich:** Nutzer meldet für
beide Busse und vier Portgeräte ConfigManagerErrorCode0. Paar1 ist
CNCA1=COM5 und CNCB1=COM6. Code52 ist damit im aktuellen PnP-Snapshot
überwunden. [Beleg](VALIDATION.md#com0com-pnp-ok-20261104).
Noch keine Byteübertragung, kein Windows-Brücken-/TCP-/GSVmulti-Nachweis.
Aktiver Hash und Schutzstatus nach Installation werden zusammen mit der
bidirektionalen Portprobe erneut erfasst; keine pauschale HVCI-Kompatibilität
ableiten. Für die Folgeversuche COM5 als Brückenseite, COM6 für GSVmulti
vorgesehen. GSVmulti während des reinen Porttests geschlossen lassen.

**Portpaar jetzt funktional bestätigt:** Je eine exakte ASCII-Zeile in beide
Richtungen, Ports nach Probe freigegeben. Aktueller Treiberhash entspricht
Vovsoft-Kandidat; SecureBoot und Speicherintegrität nach Installation erneut
aktiv bestätigt. Keine Durchsatz-/Dauerlauf-/Wiederanlauf-Abnahme.
[Beleg](VALIDATION.md#com0com-pair-ok-20261104). Nächster Schritt: portables
Windows-Paket per bestehendem SSH übertragen, isolierte Python3.15-Umgebung
mit pyserial3.5, zuerst --help prüfen. Danach lokale Brückendemo COM5→COM6,
anschließend TCP. Neues Paket/Manifest im Diagnoseverzeichnis gesichert;
kein öffentlich gehosteter Installer oder OQ-49-Abschluss.

### com0com-GUI meldet fehlendes .NET

Nutzerrückmeldung 2026-11-04: Trotz vorhandener Runtime/Developer-Pack
startet nur das Kommandozeilen-Setup. Die
[com0com-Quelltext-README](https://raw.githubusercontent.com/datamancer/com0com/master/com0com/ReadMe.txt)
nennt .NET Framework 2.0 als Voraussetzung der alten GUI. Das ist nicht
dasselbe wie ein aktuelles .NET-Runtime-/Developer-Pack; Framework 3.5
umfasst die 2.0-Laufzeit, Framework 4 ist eine andere Laufzeitfamilie
([Microsoft](https://learn.microsoft.com/en-us/dotnet/framework/install/versions-and-dependencies)).
Die genaue Ursache auf dem Zielrechner ist noch nicht nachgewiesen.

Das öffentliche3.0.0.0-Installerskript NSIS/install.nsi wurde zusätzlich
statisch geprüft: AdviseDotNETVersion enthält diese Warnung und wird dort in
.onInstSuccess aufgerufen. LaunchSetup fällt auf setupc.exe zurück. Die
Treiberoperationen erfolgen separat. Damit betrifft die Warnung den GUI-Pfad;
sie beweist keinen Treiberinstallationsfehler oder erfolgreichen Treiberstart.
Quell-/Archivnachweis im Diagnoseverzeichnis; exakte Zuordnung zum kompilierten
Signed-Installer nicht binär bewiesen. Keine Framework-Installation notwendig,
um die vorhandene CLI für die weitere Diagnose zu verwenden.

Für den Versuch genügt das mitgelieferte Setup Command Prompt. Am Prompt
`command>` zunächst `list` eingeben und die vorhandenen Paar-/Portnamen
sichern. Dies ist noch kein Nachweis eines geladenen Treibers oder
erfolgreichen Empfangs. Die
[Projektanleitung](https://com0com.sourceforge.net/doc/UsingCom0com.pdf)
beschreibt `list`, `install` und `change`. Die spätere automatische
Einrichtung soll dieses CLI verwenden; der extern abrufbare Bootstrap
ist noch geplant ([OQ-49](open-questions.md#oq-49)).

### Gewählter nächster Versuch: UART direkt

Der Nutzer wählt am 2026-11-04 nach der com0com-Code-52-Blockade zunächst
einen isolierten Empfangstest über die physische Strecke:

```text
Pi-UART TX → USB-TTL-Kabel RX → realer Windows-COM-Port → GSVmulti UserDefined
```

Der PnP-Vergleich identifiziert das USB-TTL-Kabel inzwischen als
`USB Serial Port (COM4)` mit Status OK (FTDIBUS, VID_0403/PID_6001). COM3
ist Intel AMT SOL und wird nicht verwendet. Kabel-RXD/GND-Belegung und
Empfang waren zunächst unbestätigt; der aktuelle Beleg folgt unten.

Gemeinsames GND ist erforderlich; VCC bleibt frei. Für diesen einseitigen
Demodatentest wird der TX-Ausgang des Kabels nicht benötigt. Vor Anschluss
Kabelbelegung und Windows-Port anhand der tatsächlichen Geräteangaben
bestätigen. Kein com0com und keine Windows-Python-Brücke für diesen Versuch.
Der vorhandene `send_demo`-Sender kann die endliche Zahlenfolge auf dem Pi
senden. Inzwischen ist sichtbarer Empfang im direkten Versuch 04 belegt;
dies prüft nicht die gemeinsame Netzwerk-/UART-Brücke oder echte DUT-Werte.

### Anschluss des gemeldeten 6-poligen Buchsenblocks

Der Nutzer beschreibt inzwischen einen gemeinsamen schwarzen Block,
beschriftet GND, CTS, VCC, TXD, RXD, RTS. Dies korrigiert die frühere
Annahme einzeln steckbarer Female-Enden. **Den Block nicht direkt auf die
Pi-GPIO-Leiste stecken:** Die Kontaktfolge ist nicht kompatibel.

Für den einseitigen Demotest zwei Male–Female-Jumper verwenden, jeweils
Stecker am Kabelblock und Buchse am Pi:

| Kontakt am Kabelblock | Physischer Pi-Pin |
| --- | --- |
| GND | 6 (GND) |
| RXD | 8 (GPIO14/TXD0) |

CTS, VCC, TXD und RTS bleiben frei. Beschriftete Kontakte statt einer
vermuteten Farbfolge verwenden. Nutzer meldet die Verdrahtung ausgeführt;
keine unabhängige Sichtprüfung. Rohdaten- und Zahlenempfang sind unten belegt.

### UART-Kabel vor dem Anschluss prüfen

Der Nutzer hat ein DELOCK-Kabel mit „3V“-Beschriftung und sechs einzelnen
Female-Anschlüssen: braun CTS, rot VCC, grün RTS sowie orange, gelb und
schwarz. Der AWM-Isolationsaufdruck identifiziert das Adaptermodell nicht.
Artikelnummer, Signalpegel und TX-/RX-/GND-Zuordnung vor dem Anschluss
bestätigen; aus den Farben allein keine Anschlussfreigabe ableiten.

Für den bidirektionalen Brückenweg werden TX, RX und gemeinsames GND
benötigt, TX jeweils zum RX der Gegenseite. VCC, CTS und RTS bleiben frei.
Der Pi-Ausgang ist `/dev/ttyAMA0`, nicht `/dev/serial0`; die konkreten
GPIO-Pins gegen das [Hardwareprofil](HARDWARE_PROFILE.md) und die aktive
Konfiguration prüfen. Der Referenzport `/dev/ttyUSB0` bleibt unberührt.
115200 Baud, 8N1 und kein Handshake sind die Prototypvorgaben. Eine neue
Verdrahtung wurde in dieser Software-Session nicht vorgenommen.

### Weiterlaufen, Wiederanlauf und Historie

Der Leser schreibt `records.jsonl` vor Veröffentlichung an die Brücke.
Das Lauf-Audit rotiert nicht mehr nach fünf Generationen alte Belege weg.
Bei einem erkannten Transportausfall liest und protokolliert der Pi weiter;
die Workbench zeigt den Fehler. Ein Audit-Schreibfehler bleibt ein harter
Stopp. Übertragungsereignisse stehen getrennt in `output.jsonl`, auf
Windows im mit `--log` gewählten Brücken-Audit.

Die Brücke verwendet begrenzte Nachrichten, eine ausstehende Anfrage und
Wiederverbindungsabstände von 1, 2, 4 und höchstens 8 Sekunden. Ein
unbestätigter ungültiger Zustand bleibt als Sperre erhalten und darf nicht
durch einen neuen gültigen Zahlenwert verdrängt werden. Nach Wiederverbindung
gibt es keinen historischen Aufholburst. Die vorläufige Altersgrenze von
1 Sekunde bezieht sich nur auf den COM-Schreibvorgang; sie ist kein
QM-Grenzwert und keine Zusage über den Verarbeitungszeitpunkt in GSVmulti.
Synthetische Demodaten belegen keine Latenz.

Ein historischer Import mit ursprünglichen Zeiten wird gesondert untersucht
([OQ-48](open-questions.md#oq-48)). Die im Handbuch beschriebenen
Logger-Textdateien und TDMS-Dateien sind Ausgangspunkte; ein generischer
CSV-Import mit korrekter Zeitachse ist dadurch nicht belegt.

## Quellen und Nachweisgrenzen {#quellen}

* [Bereitgestelltes PDF: GSVmulti und Raspberry Pi](quellen/GSVmulti_Raspberry_Pi_Sensoranbindung.pdf),
  28.10.2026, 16 Seiten. S. 3–5 beschreiben das Profil, S. 6–10 die
  Transporte, S. 13–16 Grenzen, Abnahme und Quellen. Diese Kopie wird im
  Repository mitgeführt und ist auch im Wiki erreichbar.
* [Nachgereichtes Beispiel-ZIP](quellen/GSVmulti_Raspberry_Pi_Beispiele.zip)
  mit `gsv_stream_demo.py`, `tcp_to_com.py`, `requirements.txt` und
  `README.txt`. Quelltext und elf Softwareprüfungen am 2026-10-28 ausgewertet;
  [Befunde und Nachweisgrenzen](#beispielcode).
* [ME-Bedienungsanleitung v2.6, S. 118–121](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf#page=118),
  direkt am 2026-10-28 gelesen und die abgebildeten DEFINE-Dialoge geprüft:
  Primärbeleg für `UserDefined`. S. 122 beschreibt Wiederanlauf mit
  gerätespezifischen Kommandos für native GSV-Verstärker; das ist keine
  Zusicherung desselben Ablaufs für UserDefined.
* [ME-Versionshistorie](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/gsvmulti_1.txt),
  direkt am 2026-10-28 geprüft: NetGSV ab 2.03 betrifft ME-Geräteserver und
  native Geräte. Daraus folgt keine allgemeine Raw-TCP-Schnittstelle für
  den eigenen Pi-Sender in 2.01.

Das PDF berichtet von Windows-Installation, Prozess und Nutzerbildern.
Diese Originalbilder und der Windows-Rechner wurden in dieser Prüfung
nicht separat untersucht. Das nachgereichte ZIP ermöglicht jetzt eine
eigenständige Prüfung des Beispielcodes. Das ersetzt keinen Test am
Windows-COM-Treiber oder in GSVmulti. Installations-, GPIO- und
Windows-Befehle im PDF wurden hier nicht ausgeführt.

## Prüfung des Beispielcodes {#beispielcode}

Der Sender ist als dreikanaliger **Demodatensender** brauchbar. Er erzeugt
ASCII mit `%`, Semikolon und CRLF, prüft drei endliche Zahlen und den
Bereich ±99999.999, formatiert auf drei Nachkommastellen und erkennt
kurze Schreibvorgänge. Stdout bleibt vom Diagnosekanal stderr getrennt.
Die serielle Konfiguration ist explizit 8N1 ohne Handshake. TCP bedient
einen Client; nach einer Trennung kann ein neuer verbinden. Das Paket
benötigt pySerial 3.5 bis kleiner 4; die vorhandene Projektversion 3.5
erfüllt dies. Keine neue Abhängigkeit oder Installation erforderlich.

**Elf Softwareprüfungen durchgeführt:** Framebytes, Wertebereich und
Fehlerwerte, echter Stdout-Aufruf, echter TCP-Aufruf nur über `127.0.0.1`,
fragmentierter Bridge-Empfang, ungültige Frames, unvollständige überlange
Zeile sowie die unten genannten Reproduktionen. Netzwerk/COM-Fehler und
ein Schreibstillstand wurden dabei mit Testdoubles simuliert. Keine
Messung von Sensorlatenz, Echtzeiteignung oder Windows-Kompatibilität.
Die elf Prüfungen bestätigen auch das Vorhandensein der Fehler; sie
sind **kein pauschales Gütesiegel**.

| Befund | Auswirkung und notwendige Klärung |
| --- | --- |
| **COM-Schreibfehler im falschen Fehlerzweig:** `relay()` wirft `OSError`/pySerial-Schreibfehler; der innere `except (OSError, ValueError)` in `main()` behandelt sie als TCP-Abbruch. | Reproduziert mit zwei Wiederholungen und nur einem geöffneten COM-Objekt. Der Port wird nicht neu geöffnet. Das widerspricht der pauschalen Aussage im PDF/README, ein COM-Ausfall führe zuverlässig zum Beenden. TCP- und COM-Fehler vor einer Übernahme trennen; [OQ-47](open-questions.md#oq-47). |
| **Größenprüfung nach dem Zerlegen:** `len(buffer) > 4096` wird erst nach Verarbeitung aller CRLF-Zeilen geprüft. | Eine vollständige 5007-Byte-Zeile mit numerischem Inhalt wurde im Test weitergeleitet. Nur eine noch unvollständige zu lange Zeile wird zuverlässig verworfen. Das ist keine belastbare maximale Framegröße. |
| **Python-Zahlenparser ist weiter als das empfohlene Profil:** `float()` akzeptiert z. B. `1_0`, Exponentialschreibweise und umgebende Leerzeichen. | `%1_0;2;3` passiert die Bridge; daraus folgt keine GSVmulti-Kompatibilität. Vor Übernahme Zahlenlexik, Feldlänge und Wertebereich explizit auf das vereinbarte Profil begrenzen. |
| **Erste Zeile jeder TCP-Verbindung wird verworfen**, auch wenn vollständig. | Drei gesendete vollständige Testframes ergaben zwei weitergeleitete. Bei 600 Frames sind ohne weitere Verluste 599 zu erwarten. Das ist ein bekannter Synchronisationsverlust, kein unbemerkter Erfolg aller Frames. |
| **Kein Altersnachweis oder Ablaufdatum:** Ein vor einem blockierten Schreibvorgang erzeugter Wert wird nach dessen Ende weitergesendet. | Mit kontrollierter Testuhr reproduziert. Kein historischer Aufholburst ist beabsichtigt; das verhindert dennoch keinen Altwert in Socket-/COM-Puffern. Für Messwerte fehlen begrenzte Warteschlangen, Altersprüfung und Rückbezug zum Audit. |
| **Fester Empfangstimeout von 5 s in der Bridge.** | Eine längere legitime Sendepause führt ebenfalls zum TCP-Wiederverbinden und erneutem Verwerfen der ersten Zeile. Für seltene/ausgelassene OCR-Werte passt das nicht automatisch; Timeout und Fehlerstrategie gemeinsam festlegen. |

Die Beispiele bleiben unverändert als Quellmaterial im ZIP. Vor einer
Produktübernahme braucht insbesondere die Bridge Korrekturen. Für einen
lokalen Demo-Versuch über UART wird diese optionale Windows-Bridge gar
nicht benötigt. Der Sender muss für picam-ai außerdem hinter Leser und
Freigabe an `ValueRecord` angebunden werden; `read_values()` liest bisher
keinen Sensor und keine Kamera.

## Das belegte UserDefined-Format {#userdefined-format}

Die Primärquelle beschreibt selbsttätig gesendete ASCII-/UTF-8-Zahlen über
eine echte oder virtuelle serielle Schnittstelle mit 8N1. Der Aufbau bleibt
während eines Laufs konstant. Dezimalpunkt und **CRLF, Bytes `0D 0A`**, sind
vorgegeben. Die vertauschten Kürzel „LF,CR“ an einer Stelle des Handbuchs
sind durch dessen Hexangabe und Beispiele eindeutig einzuordnen.

Unterstützte Bitraten laut Handbuch: 2400, 4800, 9600, 19200, 38400, 57600,
115200, 230400, 460800 und 921600. Die tatsächlich gewählte Rate muss zur
UART und zum Datenvolumen passen; sie ist keine Sensor-Abtastrate.

Präfix, Wertanzahl und Trennzeichen werden im DEFINE-Dialog eingestellt.
Kanalpositionen sind **Positionen von Zahlen im Frame**, keine GPIO-Nummern.
Die tatsächliche Gesamtzahl der Werte muss stimmen, auch wenn nur einige
als Kanäle geöffnet werden. Einheiten und Skalierung sind separat zu
bestätigen. Datei-/TDMS-Export und native `Value Mode`-Einstellungen sind
andere Schnittstellenfälle.

### Vorgeschlagener Einstieg für picam-ai

Ein einzelner optisch gelesener DUT-Wert braucht zunächst einen Kanal.
Für einen isolierten Transporttest genügt etwa:

```text
%+12.345\r\n
```

Hier stehen `\r\n` für zwei Steuerbytes; die Backslashes werden nicht
übertragen. Das ist ein **vorgeschlagenes Testprofil**, keine bereits
abgenommene Ausgabe. Drei Nachkommastellen sind nur ein Beispiel: Auflösung,
Rundung, Wertebereich und maximal zulässiger Darstellungsfehler müssen zum
bestätigten Geräteprofil passen. Ein gültiger Messwert darf dabei weder
begrenzt noch geglättet werden; nicht darstellbare Werte werden abgelehnt.

<div class="wiki-setting" markdown="1">

| Einstellung | UserDefined-Testprofil mit einem Wert |
| --- | --- |
| Wozu | Einen optisch gelesenen DUT-Wert über einen Windows-COM-Port übernehmen. |
| Im Hintergrund | `Device Type = UserDefined`; `Value String / DEFINE`: `Has Character Prefix`, `%`, `Number of values = 1`, Textfilter aus; Position 1 öffnen. CRLF und Dezimalpunkt im Sender. |
| Standard | Vorschlag für den ersten Transporttest: 115200 Baud, 8N1, kein Handshake; zunächst konstante Demowerte mit 10 Hz. Das ist noch keine vorhandene Live-Einstellung. |
| Ändern? | **Nur wenn** Geräteauflösung, Kanalbedarf oder Transport es verlangen; Profil und Windows-Session gemeinsam dokumentieren und erneut prüfen. |
| Quelle | [ME v2.6, S. 118–121](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf#page=118); eigenes einkanaliges Testprofil. |

</div>

Das PDF schlägt alternativ drei Zahlen vor:
`%+00012.345;+00023.456;-00000.250\r\n`. Dazu gehören Zeichenpräfix `%`,
drei Werte und Semikolon. Die festen Feldbreiten sind eine eigene
Entwurfswahl des PDFs. Nicht drei Kanäle erzeugen, wenn nur ein DUT-Wert
vorliegt; insbesondere die Referenz nicht als Korrektur oder Ersatz
hineinmischen.

Die Rechnung im PDF stimmt: dieses Dreikanalprofil hat 35 Bytes;
bei 8N1 sind das 3500 Bit/s bei 10 Hz und 35000 Bit/s bei 100 Hz.
115200 Baud wären bei 100 Hz rechnerisch zu rund 30,4 % belegt.
Das ist eine Kapazitätsrechnung, **kein gemessener Durchsatz**.
Maximale Feld-/Framegröße, Kanalzahl, Exponentialschreibweise und numerische
Parsergenauigkeit sind nicht verbindlich geklärt. Für den Einstieg kurze
gewöhnliche Dezimalzahlen verwenden und Grenzwerte gezielt testen.

## Was vorher geklärt sein muss (Konzept §8)

| Punkt | Stand am 2026-10-28 |
| --- | --- |
| konkrete GSVmulti-Version und unterstützte Geräteanbindung | Windows bestätigt; 2.01 Pro laut PDF, UserDefined laut Handbuch; praktischer Empfang offen |
| Beispieltelegramm oder verbindliche Protokollspezifikation | UserDefined dokumentiert; eigene Profile müssen dazu passen |
| Baudrate, Zeichenformat, Trennzeichen, Zeilenende | 8N1, CRLF und Dezimalpunkt belegt; 115200 und `%` als Testvorschlag |
| Vorzeichen, Einheit, Kanalzahl und numerische Auflösung | numerische Positionen belegt; DUT-Profil, Skalierung und Genauigkeit festlegen |
| Geräteidentifikation und Initialisierungskommandos | für selbsttätigen UserDefined-Strom kein natives GSV-Kommando erforderlich |
| Aufnahmezeit, ungültige und veraltete Werte | offen: M8 und [OQ-06](open-questions.md#oq-06) |
| Streaming und Wiederverbindung | Streaming belegt; konkreter Wiederanlauf offen: [OQ-47](open-questions.md#oq-47) |

## Die wichtigste Einzelfrage: M8

**Welche Zeitachse zeichnet GSVmulti für diesen UserDefined-Strom auf?**
Das einfache Zahlenprofil hat kein definiertes Feld für die
Aufnahmezeit des Kamerabilds. Eine zusätzliche Zahl wird zunächst ein
weiterer Kanal, nicht automatisch der Zeitstempel des DUT-Werts.
Empfangszeit, rekonstruierter Abtasttakt und Aufnahmezeit dürfen deshalb
nicht gleichgesetzt werden. Auch der gemeinsame Import mit einer
Referenz belegt noch keinen gemeinsamen physikalischen Messzeitpunkt.
Das einfache Profil trägt außerdem keine Bild-/Sequenzkennung. Nach
Auslassungen oder Datenverlust ist eine Zuordnung zur JSONL-Auditspur allein
über die Zeilennummer nicht gesichert.

Der frühere Vorschlag „Zeitstempel um 5 s verstellen“ ist nur ausführbar,
wenn ein tatsächlich unterstütztes Zeitstempelfeld nachgewiesen ist.
Für UserDefined zunächst Anzahl und Zeitachse bei bekannter Sendefolge,
kontrollierten Pausen und gebündeltem Empfang prüfen. Insbesondere kommen
OCR-Ergebnisse nach Freigabe nicht zwingend mit konstanten Abständen.
Verpasste Werte nicht durch Wiederholen des letzten Werts oder einen
Aufholburst als aktuelle Messwerte ersetzen.

Für das hier beschriebene Zahlenprofil wäre
`carries_capture_timestamp=False` und `timestamp_resolution_ns=None`
zutreffend. Das JSONL-Audit behält Aufnahmezeit, `TimeBaseKind`, Status und
Unsicherheit. Pi- und Windows-Uhr brauchen für einen Vergleich einen
belegten Bezug; unbekannte Unsicherheit bleibt `None`.

Wenn der Import keinen geeigneten Zeitbezug liefert, kommen eine
nachträgliche Zuordnung über JSONL, ein nachgewiesen ausreichend stabiles
Kalibrierfenster oder eine andere Integration infrage. Eine pauschale
konstante Verzögerung ist ohne Messbeleg keine Korrektur. Siehe
[Zeitmessprogramm](TIMING.md#messprogramm) und
[OQ-02](open-questions.md#oq-02).

## Ungültige Werte

Dies ist die wichtigste Freigabelücke des PDFs. Die vorhandenen Policies
sind im provisorischen Formatter implementiert; ihre Wirkung in GSVmulti
ist damit **nicht** belegt:

| Policy oder Vorschlag | Grenze bei UserDefined |
| --- | --- |
| `omit_record` | `TxReceipt.omitted=True` belegt die absichtliche Lücke nur im Pi-Audit; GSVmulti könnte den alten Wert weiter anzeigen oder die Zeitachse verdichten. |
| `send_nan` | Lauf 09: Im getesteten UserDefined-Profil mit Zahlenfilter keine NaN-Einträge in TXT/TDMS; nach Timeout gültige Zahlen ohne Zeitlücke. Keine Freigabe; andere Konfigurationen nicht geprüft. |
| `status_flag` | Der bisherige Textstatus und leere Wertfelder sind für das reine Zahlenprofil nicht nachgewiesen. |
| Separater Zahlenkanal für Gültigkeit | Ein weiterer Messkanal; sperrt nicht automatisch Anzeige oder Verwendung des DUT-Kanals. |
| Sender bei Fehler stoppen | Keine neuen Werte; rechtzeitige Kennzeichnung des Altwerts und sichere Beendigung der Auswertung bleiben nachzuweisen. |

Weder `0` noch ein wiederholter letzter gültiger Wert sind ein zulässiger
Ersatz für TRANSITION, UNREADABLE oder STALE. Bei einem mehrkanaligen Profil
muss außerdem feststehen, ob ein ungültiger Teilwert den ganzen Frame sperrt.
Eine Kalibrierauswertung darf ungültige Zeiträume nicht als aktuelle gültige
Messung verwenden. Solange das nicht durchgängig gesichert ist, nur
Transportversuche mit Demodaten, keine Messfreigabe
([OQ-06](open-questions.md#oq-06)).

## Transport und elektrische Ebene {#transport}

| Weg | Bewertung für den Prototyp |
| --- | --- |
| Pi-UART → 3,3-V-USB-UART am Windows-PC → COM | Einfacher lokaler Testweg bei bestätigter Port-/Pinzuordnung. TX→RX, gemeinsames GND, Adapter-VCC bei separater Versorgung frei; Trennung bewerten. |
| Pi-USB-UART → UART-Leitung → PC-USB-UART | Vermeidet GPIO-Konfiguration, benötigt zwei passende Adapter und eigene Gerätezuordnung. |
| Pi Raw-TCP-Server → Windows-VCOM → GSVmulti | Plausibler LAN-Weg; VCOM-Treiber, Lizenz, Puffer und Wiederanlauf sind zusätzliche Bestandteile. |
| USB-ACM-Gadget | Alternative nach Nachweis von Pi-Modell, Device-Port, OS und Windows-Treiber; kein automatisches Merkmal eines USB-Kabels. |

Gewählt sind Netzwerk und UART als pro Lauf alternative Eingänge derselben
eigenen Windows-Brücke mit com0com-Portpaar. Ihr Hardware-/Windows-Nachweis
bleibt offen ([OQ-47](open-questions.md#oq-47)). `COM20`,
`COM21`, IP und Port 5000 im PDF sind Beispiele, keine installierte
Konfiguration. Raw TCP und RFC2217 sind verschiedene Protokolle.
Eine pySerial-URL erzeugt keinen Windows-COM-Port. VSPE-Connector mit
TcpClient und ein virtuelles Portpaar mit Python-Bridge sind alternative
Aufbauten, keine hier geprüften Installationen. NetGSV ersetzt diesen
Nachweis nicht. Außerhalb eines passenden lokalen Netzes braucht das
unverschlüsselte Beispiel einen geschützten Transport wie VPN/SSH.

### Elektrische Ebene

Das [Hardwareprofil](HARDWARE_PROFILE.md) dokumentiert für diesen Pi 5
`/dev/ttyAMA0` als geplanten Ausgang; `/dev/serial0` zeigt dort auf den
Debug-UART `ttyAMA10`. Die generische PDF-Anleitung für `/dev/serial0`
nicht ungeprüft übernehmen oder vorhandene Overlays ersetzen.
GPIO-TTL darf nicht direkt an RS-232 angeschlossen werden.
Ein 3,3-V-USB-UART am PC ist eine andere Lösung als ein USB-RS232-Adapter.
[OQ-09](open-questions.md#oq-09) bleibt für Anschlusswahl und galvanische
Trennung offen; TCP erfordert keinen neuen GPIO-Transceiver.

Der vorhandene PL2303-USB-RS232-Adapter an `/dev/ttyUSB0`, 38400 8N1,
liest die **GSV-2AS-Referenz ein**. Ihn nicht gleichzeitig als DUT-Ausgang
belegen. Die eingehende Referenz belegt weder GPIO-Ausgang noch
GSVmulti-Kompatibilität.

## Die Naht im Code

```text
sink/protocol/__init__.py     TelegramFormatter + FormatterCapabilities
sink/protocol/ascii_csv.py    AsciiCsvFormatter, provisional=True
sink/protocol/userdefined.py  UserDefinedFormatter, provisional=True, ein Wert
sink/protocol/gsv_ascii.py    GsvAsciiFormatter wirft weiterhin absichtlich
sink/serial_out.py            SerialSink, unabhängig vom Format
sink/jsonl.py                 JsonlSink für das parallele Audit
live/session.py              Audit nach allen Sperren, danach optional LiveOutput oder Brücken-Publisher
live/output.py               begrenzter Senderthread, SerialSink, tx.jsonl
scripts/gsvmulti-demo-sender.py  eigenständiger Demo-Sender, kein Live-Lauf
sink/protocol/user_defined.py UserDefinedFormatter, provisional=True
gsv_transport.py             Pi-Publisher, Konfiguration, Brückenprotokoll
gsv_bridge.py                Windows-Brücke und endliche Demowerte
```

<div class="wiki-seam" markdown="1">

| Trennstelle | `TelegramFormatter` (`sink/protocol`) |
| --- | --- |
| Vertrag | `capabilities(self) -> FormatterCapabilities` als `@property`; <code>format(self, record: ValueRecord) -&gt; bytes &#124; None</code> liefert Telegrammbytes oder `None`. Fähigkeiten nennen Formatkennung, Zeitstempel, Invalid-Policies, Gerätekommandos, Kanalzahl und `provisional`. |
| Darf geändert werden | `UserDefinedFormatter` aus `dispread.sink.protocol.userdefined` direkt importieren und gezielt an `SerialSink` übergeben; konkrete Formatter haben keine zentrale Registry. P4-3 bindet ihn über `LiveOutput` an den Live-Lebenszyklus an; API-Option `output`, Standard aus. Der neue `UserDefinedFormatter` erhält Dezimalauflösung und prüft Zahlenlexik/Wertübereinstimmung. Die gemeinsame Brücke verwendet ihn für Demodaten; die echte DUT-Ausgabe bleibt bis zur Windows-Abnahme gesperrt. [Beispiel 16](../examples/16_end_to_end_headless.py) zeigt weiterhin den getrennten alten seriellen Testpfad. |
| Bleibt unverändert | Leser und Freigabe ohne Referenzparameter, Wert und Aufnahmezeit im `ValueRecord`, paralleles JSONL-Audit; `gsv_ascii.py` bleibt der werfende Platzhalter. Die neue Brücke ergänzt den vorhandenen Testpfad, ohne das native Geräteprotokoll zu erfinden. |
| Tests | [Formatter und SerialSink am pty](../tests/test_userdefined_formatter.py), [Demo-Sender mit pty/Fakes](../tests/test_gsvmulti_demo_sender.py) [Live-Ausgabe mit pty/Fakes](../tests/test_live_output.py) und vorhandene [Gate-/Referenztests](../tests/test_gate_und_referenz.py); Windows-Abnahme weiterhin offen. Vorhandene pty-Prüfungen in [tests/test_gate_und_referenz.py](../tests/test_gate_und_referenz.py), insbesondere `test_telegramme_erreichen_die_gegenstelle` und `test_ausgelassener_datensatz_wird_als_ausgelassen_belegt`; zusätzlich `test_gsv_transport.py`, `test_gsv_bridge.py` und `test_live_output.py`; Windows-Abnahme bleibt offen. |

</div>

Der P4-3-Formatter (`userdefined.py`) deklariert einen Kanal, keine Gerätekommandos,
`format_id="gsvmulti_userdefined_v0"`, `carries_capture_timestamp=False`,
`timestamp_resolution_ns=None`, `provisional=True` und ausschließlich
`omit_record`. Diese Policy belegt die lokale Auslassung, **keine** sichere
Ungültigwirkung in GSVmulti. Präfix, ASCII und CRLF besitzen keine eigenen
Felder in `FormatterCapabilities`; die festen Formatregeln stehen im
Formatter-Docstring. Der Prototyp bleibt vorläufig;
`provisional` und die Fähigkeiten gehören in jedes Runartefakt. Beispiel 16
schreibt sie nach `report.json`; `Pipeline` erzeugt keinen allgemeinen
Laufbericht. Der `/live`-Pfad verwendet ihn ausschließlich bei ausdrücklich gesetztem `output`.

Der einkanalige Brücken-Formatter (`user_defined.py`) deklariert einen Kanal und keine Gerätekommandos. Invalid-Policies dürfen nur als unterstützt gelten,
wenn ihre tatsächliche Wirkung belegt ist. Der Prototyp bleibt vorläufig;
`provisional` und die Fähigkeiten gehören in jedes Runartefakt. Beispiel 16
schreibt sie nach `report.json`; `Pipeline` erzeugt keinen allgemeinen
Laufbericht. Der aktuelle `/live`-Pfad speichert nun die Fähigkeiten der optionalen Brücke in `session.json`; die Zahlenweitergabe bleibt gesperrt.

Beide Formatter bleiben wegen unterschiedlicher Zahlenlexik und
Konsistenzprüfung getrennt; ihre gemeinsamen gültigen Dezimalprofile
liefern identische Telegramme. Die Unterschiede sind in den jeweiligen
Modul-Docstrings und [Vergleichstests](../tests/test_live_output.py) belegt.

Die im PDF vorgeschlagene Funktion `read_values(t)` ersetzt bei picam-ai
weder Leser noch Freigabe. Der DUT-Wert kommt aus dem `ValueRecord`; ein
Referenzabgleich darf ihn nicht nachträglich korrigieren.

### Opt-in im Live-Lauf (P4-3)

**Gebaut 2026-10-30, ungeprüft am Windows-PC, keine Messfreigabe.**
`LiveService.start_run(output=None)` lässt die bisherige Ausgabe unverändert.
Die API `POST /live/run/start` akzeptiert zum Beispiel (Port ist ein Platzhalter
für einen bestätigten freien Ausgang, die Werkbank-CSRF-Absicherung gilt weiter):

```json
{"reference": true, "output": {"port": "/dev/pts/123", "baudrate": 115200, "prefix": "%"}}
```

Port ist Pflicht; Baudrate und Präfix sind optional mit 115200 und `%`.
Live gilt `MIN_LIVE_BAUDRATE = 9600`: konservativ höchstens 16 Zeichen der
16-Zellen-Anzeige einschließlich Vorzeichen/Punkt plus ein Präfix und CRLF,
also 19 Byte × 10 Bit (8N1) = 190 Bit. Bei 2400/4800 Baud dauert das
79,17/39,58 ms und überschreitet den Bildabstand von 33 ms; bei 9600 Baud
sind es 19,79 ms. Nur belegte Baudraten ab 9600 sind zulässig. Längere
Telegramme sperren den Live-Ausgang mit Fehler, bevor Bytes geschrieben werden.

Referenzport `/dev/ttyUSB0`, Debugport `/dev/serial0` und auflösbare Aliasse
sind geschützt. Zusätzlich wird über die USB-Eltern im sysfs die Kennung des
Referenzadapters PL2303 (`067b:2303`, [Hardwareprofil](HARDWARE_PROFILE.md))
geprüft; damit bleibt er auch etwa als `/dev/ttyUSB1` gesperrt. Nur das
API-Feld `allow_reference_adapter: true` (Standard `false`) erlaubt den
Referenzadapter ausdrücklich. Der aufgelöste aktive Referenz-/Werteplan-Port
und der Debugport bleiben auch damit gesperrt. Die sysfs-Wurzel ist für
Fake-Tests injizierbar. Die Live-UI hat noch keinen Schalter.

`LiveSession.step()` schreibt erst den endgültigen Record nach R13-17 und
R13-21 ins Audit; erst nach erfolgreichem Audit wird er an `LiveOutput`
übergeben. Nicht-VALID und inkonsistente Texte entfallen über `omit_record`.
Testläufe senden auch später lesbare Frames nie. Ein eigener Thread mit
höchstens einem offenen Auftrag ruft `SerialSink` mit `write_timeout=1.0` auf.
Teilwrites setzen ausschließlich die Restbytes desselben Telegramms fort,
mit einer Gesamtfrist von einer Sekunde. Kein `reset_output_buffer()`, kein
`flush()`, keine eigenen O_NONBLOCK-Schreibversuche und kein Wiederverbinden.
Solange der Auftrag offen ist, werden neue gültige Records als `output_busy`
mit `bytes_written=0` verworfen. Liegen danach noch Treiberreste vor, entfällt
nur das neue Telegramm als `output_backlog`; der alte Puffer bleibt erhalten.
Bei Schreibfrist, fehlendem Fortschritt oder anderem Schreibfehler wird der
Ausgang für diesen Lauf gesperrt. Ein begonnenes Telegramm wird niemals durch
ein neues ergänzt. Stop verwirft noch nicht begonnene Aufträge, lässt den
laufenden Write bis Abschluss/Fehler auslaufen und schließt Thread, Datei und Port.

Ein Öffnungsfehler **lehnt den Laufstart klar ab** (HTTP 409); so entsteht
kein vermeintlich sendender Lauf. Der Ausgabeport öffnet **vor** Referenzrecorder
und Werteplan; bei Öffnungsfehler wird der Recorder weder gestartet noch
zurückgestellt. Ein späterer Port-, Senderthread- oder Tx-Auditfehler
sperrt die weitere Ausgabe für diesen Lauf, lässt Leser und Record-Audit
weiterlaufen und erscheint sofort unter `run.output` in `/live/status`.
`session.json` übernimmt den ersten Fehler beim nächsten Leseschritt (auch
beim Warten auf ein Bild), spätestens beim Stop. Der Beschäftigt-Zustand
wird auch nach unerwarteten Senderausnahmen gelöst.
`session.json.output` enthält Port, Baudrate, Präfix, Formatter-Fähigkeiten
mit `provisional: true`, `sent`, `omitted`, `dropped`, `errors` und
`first_error`. `omitted` zählt auch verworfene Records, `dropped` ist dessen
Teilmenge für Überlast/Transportverlust; Format-Auslassungen sind keine
Transportfehler.

`tx.jsonl` enthält je endgültigem Record den `TxReceipt` mit `provisional: true`, einschließlich
Frame-/Tx-Sequenz, beabsichtigter `wire_bytes` als Hex, `omitted`, `dropped`,
`drop_reason`, Fehler und soweit bekannt `bytes_written`. Die Zeilen können
wegen des Senderthreads in Abschlussreihenfolge stehen; nach Sequenzen
zuordnen, nicht nach Zeilennummer. `t_enqueue_ns` und `t_complete_ns` haben
`time_base="host_monotonic"` und unbekannte Unsicherheit (`null`), keine
Aufnahme- oder Windows-Zeit. SYNTHETIC/FILE_MTIME werden nicht für
Latenzaussagen benutzt. `sent` wird erst nach vollständiger lokaler Annahme
einschließlich CRLF gezählt.
Bei einem Verbindungsfehler können bereits unwiderruflich gesendete Teilbytes
übrig bleiben; danach folgen keine weiteren Telegramme. Meldet pySerial bei
einem fehlgeschlagenen Write keine Teilbytezahl, ist `bytes_written=null`;
`confirmed_bytes_written` im Fehlertext nennt die bestätigte Untergrenze aus
vorherigen Teilwrites. Bei Ablauf zwischen Calls ist die Bytezahl exakt.
Ein GSVmulti-Empfang folgt aus lokaler Annahme nicht. Ohne `output` entstehen weder dieser
Session-Block noch eine Tx-Datei; die bisherigen Record-Bytes bleiben gleich.

### Der Platzhalter — ausdrücklich nicht das GSVmulti-Format

```text
1;1;-12.500;N;valid;492076801394;synthetic
```

`AsciiCsvFormatter` sendet immer Kanal, Bildnummer und Wert; optional
Einheit, Textstatus, Aufnahmezeit und Zeitbasis. Das Abschalten der Optionen
macht daraus **keinen Ein-Wert-Frame**. Man könnte Zahlenpositionen für
einen reinen Transportversuch konfigurieren; diese zusätzlichen Felder
haben in GSVmulti jedoch keine zugesicherte Audit-/Zeitstempelsemantik.
Das Defaulttelegramm ist weiterhin kein geprüftes UserDefined-Profil.

Konfigurierbar sind `field_separator`, `decimal_separator`, `line_ending`,
`decimals`, `include_unit`, `include_status`, `include_capture_timestamp`,
`channel`, `invalid_policy` und `encoding`. `required_baudrate()` in
`serial_out.py` hilft bei der Durchsatzrechnung. Ein höherer Sendetakt
liefert keine zusätzlichen unabhängigen DUT-Messungen.

### UserDefined-Prototyp und Demo-Belege

`UserDefinedFormatter` sendet nur VALID: `<präfix><zahl>\r\n`, Standardpräfix
`%`. Das Präfix muss ein druckbares ASCII-Zeichen ohne Ziffer, `+`, `-`, `.`
oder Leerzeichen sein. Aus `raw_text` werden ausschließlich ASCII-Leerzeichen
entfernt. Erlaubt ist `[+-]?[0-9]+(\.[0-9]+)?`; keine Exponenten, Kommas,
Tabs oder Zeilenumbrüche. `Decimal(text)` muss `Decimal(str(record.value))`
entsprechen, der Wert muss endlich sein. Damit werden zusätzliche Dezimalstellen
nicht durch eine erneute Float-Rundung verdeckt. Es gibt keine Rundung oder
Begrenzung im Formatter. Nicht-VALID, unbekannter Text und Inkonsistenz liefern
`None` mit Loggrund; `SerialSink` belegt dies als `TxReceipt.omitted=True`.

Der eigenständige Demo-Sender erzeugt synthetische `ValueRecord`s mit
`profile_id="demo/<profil>"`. Profile: `constant` (`+12.345`), `staircase`
(`0,1,2,3,4,5,4,3,2,1`) und `boundaries` (Vorzeichen, Null und ±99999.999,
einschließlich ±0.001 und signierter Null). Die Folgen wiederholen sich.
±99999.999 sind **Demo-Profilgrenzen aus dem ZIP**, keine belegten Grenzen
des GSVmulti-Parsers oder eines DUT. Baudraten sind auf die oben belegte
Liste beschränkt. Standard: 600 Frames, 10 Hz, 115200 Baud; Port ohne Standard.
`/dev/ttyUSB0`, `/dev/serial0` und ihre auflösbaren Aliasse sind ohne
ausdrückliches `--allow-port` gesperrt.

`--output` (auch `--jsonl`) schreibt eine neue Datei; vorhandene Dateien werden
nicht überschrieben. Ohne Option geht JSONL nach stdout, Fehler nach stderr.
Jede Zeile enthält `sequence` (ab 1), `t_send_boottime_ns`,
`send_time_base="CLOCK_BOOTTIME"`, `bytes_hex`, `value_text`, `status`,
`bytes_written`, Demo-/Profil-/Formatdaten samt `provisional=True` und die
synthetische Aufnahmezeit mit unbekannter Unsicherheit. BOOTTIME bezeichnet
den lokalen **Sendeversuch**, keine Aufnahme, Empfangszeit oder Sensorlatenz.
Bei `--dry-run` wird kein Port geöffnet und `status="dry_run"` protokolliert.

Der Demo-Sender schreibt vollständig mit einer Gesamtfrist von einer Sekunde
(`write_timeout=1.0`); Teilwrites setzen nur das angefangene Telegramm fort.
Kein `flush()` und kein `reset_output_buffer()`: Bei vorhandenen Treiberresten
wird der **nächste**, noch unbegonnene Frame als `status="dropped"`,
`drop_reason="output_backlog"`, `bytes_written=0` belegt. Die nächste Wartefrist
beginnt nach Verarbeitung und Audit neu; es gibt keinen Aufholburst.
Timeout, fehlender Fortschritt und Portfehler werden mit Fehler und Bytezahl
belegt und beenden den Lauf mit Exitcode 1. Ein nach einem Teilwrite defekter
Transport erhält keinen weiteren Frame. Unbekannte Teilbytezahlen sind `null`,
die bestätigte Untergrenze steht im Fehlertext wie im Live-Beleg.
`sent` bedeutet vollständige lokale Annahme einschließlich CRLF;
`bytes_hex` sind die beabsichtigten Framebytes. Treiber-/USB-Puffer und
tatsächlicher Empfang bleiben Teil der Windows-Abnahme.

## Abnahme und nächste Schritte {#abnahme}

**Prototypstatus:** P4-1/2 und P4-3 sind gebaut, ungeprüft am
Windows-PC und nicht für Messungen freigegeben. pty/Fakes prüfen die lokale
Software; sie belegen weder GSVmulti-Empfang noch elektrische Eignung.

1. **Profil und Transport festlegen:** tatsächliche GSVmulti-Version/PRO,
   Ein-Wert-Definition, Einheit, Auflösung, Windows-Port, Treiberversion,
   Pi-Ausgang und Startreihenfolge dokumentieren. Das vorliegende ZIP ist
   eine Demogrundlage; der neue Demo-Sender steht für den lokalen Test bereit.
   Die ZIP-Bridge nicht mit den oben
   nachgewiesenen Fehlern als fertige Messkomponente übernehmen.
2. **Demodaten transportieren:** Bytefolge inklusive Präfix und CRLF
   mitschneiden; verschiedene Konstanten, Null, Vorzeichen und
   Bereichsgrenzen in Anzeige und Export vergleichen. Ein synthetischer
   negativer Wert prüft nur den Import, keine Freigabe des optischen Lesers.
3. **Zeit und Ausfälle prüfen:** etwa 600 Frames bei 10 Hz, gesendete und
   gespeicherte Werte je Kanal sowie Zeitachse vergleichen; Start-/Stoppränder
   und die erste vollständige Zeile jeder neuen Brückenverbindung prüfen
   (die neue Brücke verwirft sie nicht absichtlich). Ablehnungen, Pause, Burst, Streamstillstand, Kabel-/Netzabbruch
   und Neustarts getrennt auslösen. Keine ausgedachten Grenzzeiten als
   erfüllt markieren; Kriterien vorher mit OQ-02/OQ-06 festlegen.
4. **Gebauten Live-Pfad am Ziel prüfen:** nur freigegebene `ValueRecord`s, keine
   Referenzkorrektur, Glättung oder Altwertwiederholung; JSONL und
   Übertragungsbelege behalten. Testlaufdaten dürfen keine Messfreigabe
   erhalten ([OQ-44](open-questions.md#oq-44)).
5. **Ende-zu-Ende-Nachweis:** Anzeige, Datei und Kalibrierauswertung bei
   ungültig/veraltet prüfen; Session speichern/laden, Windows-/Pi-Neustart
   und Lauf mit Zielrate nachweisen. Messzahlen nach
   [VALIDATION.md](VALIDATION.md), Aufbau und Deutung ins
   [Laborjournal](lab_journal.md). Diese Prüfung ist noch kein Messlauf.

### Anleitung für den Windows-Test {#windows-test}

1. **Aufbau dokumentieren:** GSVmulti-Version/PRO und Treiber notieren,
   freien Pi-Ausgang und PC-COM-Port bestätigen. Für den lokalen Weg einen
   **3,3-V-USB-UART** am Windows-PC verwenden: Sender-TX → Adapter-RX und
   gemeinsames GND, VCC bei separater Versorgung frei. Bei zwei USB-UARTs
   entsprechend TX des Pi-Adapters → RX des PC-Adapters. Kein TTL direkt an
   RS-232; Port-/Pinzuordnung und Trennung zuvor klären ([OQ-09](open-questions.md#oq-09)).
2. **GSVmulti DEFINE:** `Device Type = UserDefined`, Zeichenpräfix aktiv,
   `%`, `Number of values = 1`, Position 1 öffnen, Textfilter aus.
   COM-Port auf **115200, 8N1, kein Handshake**, Dezimalpunkt und CRLF.
   Einheit/Skalierung separat dokumentieren. Die Handbuchvorgabe ist noch
   kein Funktionsnachweis in der vorhandenen 2.01-Pro-Installation.
3. **Vorschau ohne Leitung:** im Repo ausführen; die Datei muss neu sein:

   ```bash
   PYTHONPATH=src ./.venv/bin/python scripts/gsvmulti-demo-sender.py \
     --dry-run --profile boundaries --count 8 --output /tmp/gsv-preview.jsonl
   ```

4. **Aufzeichnung starten, dann senden:** `DEMO_PORT` auf den zuvor
   bestätigten freien Ausgang setzen. Für jedes Profil eine eigene neue
   JSONL-Datei und einen eigenen GSVmulti-Export verwenden:

   ```bash
   PYTHONPATH=src ./.venv/bin/python scripts/gsvmulti-demo-sender.py \
     --port "$DEMO_PORT" --baud 115200 --prefix '%' \
     --profile staircase --rate 10 --count 600 --output /tmp/gsv-staircase.jsonl
   ```

   Den Ablauf mit `constant` und `boundaries` wiederholen. Reservierte
   Referenz-/Debugports gehören nicht zum vorgeschlagenen Testaufbau.
5. **JSONL ↔ GSVmulti-Export vergleichen:** 600 Versuche, `sent`/`dropped`,
   empfangene Anzahl, Reihenfolge, Vorzeichen, Null, Auflösung und Ränder
   prüfen. Bei Pausen/Abbruch Zeitachse und Altwertanzeige gesondert sichern.
   Das Frame enthält keine Sequenznummer: nach Verlusten ist Zeilennummer
   allein kein Zuordnungsbeleg; besonders konstante Folgen sind mehrdeutig.
   JSONL, Export, DEFINE-Einstellungen, Version und Aufbau gemeinsam sichern.
   BOOTTIME ist keine Windows-Uhr; ohne belegten Uhrenbezug keine
   Übertragungslatenz daraus ableiten. Messzahlen und Deutung erst nach
   tatsächlichem Versuch in VALIDATION und Laborjournal eintragen.

<details class="wiki-layer wiki-layer--historisch" markdown="1">
<summary>Historisch: Beschaffungsstand vom September 2026</summary>

Am 2026-09-22 lagen unter dem gitignorierten `var/datenblaetter/` die
GSV-2-Geräteanleitung und eine zehnseitige GSVmulti-Anleitung von 2011 vor.
Die erste belegt das Protokoll des Messverstärkers, die zweite enthielt
keine UserDefined-Spezifikation. PDF-Abrufe funktionierten bereits damals;
die pauschale Aussage „alle automatischen Abrufe liefern HTTP 403“ war
falsch. Die damals fehlende v2.6 wurde durch den PDF-Hinweis jetzt gefunden.
Auch ältere Quellcode-Docstrings nennen noch den damaligen Beschaffungsstand;
die aktuelle Bewertung steht hier. Das Verhalten des Platzhalters bleibt
unverändert.

### Mitschnitt eines nativen GSV-Geräts {#der-beste-weg-zur-antwort-ist-ein-mitschnitt}

Ein echter Mitschnitt bleibt für einen späteren Nachbau des nativen
Geräteprotokolls geeignet. Für UserDefined ist die dokumentierte
Parserdefinition der Einstieg; der praktische Nachweis muss den eigenen
Zahlenstrom in der tatsächlichen Windows-Installation prüfen.

</details>

**Weiter mit:** [Verträge](anleitung/02-vertraege.md)


## Direkter UART-Demoempfang belegt, Einzelwertprüfung offen

Am 2026-11-04 zeigt GSVmulti 2.03 Pro nach Einschalten von
**Filter Out Non-Numeric** erstmals Zahlen: COM4, 115200/8N1, Präfix %,
ein Wert/Position 1. Der Pi hat im endlichen synthetischen Lauf 600
Telegramme mit Zielrate 10/s geschrieben. Das sind keine bestätigten
600 GSVmulti-Einzelwerte. [Messbeleg](VALIDATION.md#uart-demo-20261104-04).

Der Screenshot zeigt −0,134500 außerhalb des 0,001-Rasters der Sendefolge,
Datenfrequenz 1 Hz und keine Einheit. Die
[Herstelleranleitung, S. 34](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf)
beschreibt Mittelwertbildung für numerische Anzeigen auf vier Anzeigen/s.
Der Zahlenbildschirm belegt deshalb keine unveränderten Einzelwerte.
Aufzeichnung ohne Datenreduktion, Sendervergleich und passende
Datenfrequenz sind noch zu prüfen ([OQ-50](open-questions.md#oq-50)).
GSVmulti-Konfiguration über Save Session sichern; Einheit und Skalierung
weiter getrennt prüfen. DUT-Ausgabe bleibt gesperrt.


### Lauf 05: Gespeicherte Rampenwerte unverändert

Nutzer-TXT und TDMS enthalten 420 exakt passende Werte (−0,120 bis +0,299,
Senderindizes 180–599), ohne Lücken oder Duplikate im Ausschnitt. Negative
Werte, Null und positive Werte sind belegt. Die gespeicherten Rampenwerte
werden nicht gemittelt; abrupte Sprünge sind noch nicht geprüft. Der fehlende
Anfang passt zur später gestarteten Aufnahme, ist kein Beleg für einen
Verlust während der Aufnahme. [Messung](VALIDATION.md#uart-demo-20261104-05).

Die Frequenzmetadaten melden weiterhin 1 Hz, die Wellenform aber ein Intervall
von ca. 0,102407 s. Ihre Zeitspanne stimmt nicht mit der Pi-Schreibereignisspanne
derselben Werte überein. Eine gültige Aufnahmezeit-/Synchronitätsaussage ist
daraus nicht abgeleitet. OQ-50 bleibt teilweise offen. Einheit leer,
Skalierung 1; echte DUT-Ausgabe und gemeinsame Brücke weiter nicht abgenommen.


### Lauf 06: 10 Hz bestätigt, Zeitmodus aus Start und Ende

TXT und TDMS des Folgelaufs enthalten 467 unveränderte Werte von −0,167
bis +0,299, ohne Lücken/Duplikate im Ausschnitt. Frequency=10 Hz ist in den
Dateien bestätigt; der Zeitmodus bleibt `tf`. Die
[Anleitung, S. 73–74/155](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf)
ordnet dies der Berechnung dt=(Endzeit−Startzeit)/(Werteanzahl−1) zu;
die Formel passt zu den TDMS-Daten. Das ist keine Speicherung einzelner
Quellzeitstempel. Änderung von Frequency allein berichtigt daher die
beobachtete Zeitachse nicht. Advanced → Timestamp Calculation zunächst
prüfen; ein nominelles dt von 0,1 s wäre kein gemessener Zeitnachweis.
[Messwerte und Grenzen](VALIDATION.md#uart-demo-20261104-06).


### Lauf 07: Getestete Sprünge erhalten, Zeitraster nominell

TXT und TDMS enthalten 446 exakt passende Werte des Senderabschnitts
154–599: 46 Null-Vorlaufwerte und acht vollständige Blöcke zu je 50 Werten.
Alle acht Übergänge erfolgen direkt, auch −0,250 → +0,750. Kein zusätzlicher
Zwischenwert oder veränderte Blocklänge. GSVmulti 2.03 Pro bewahrt diese
getesteten Sprünge bei Record every value. Numerische Anzeige weiterhin
getrennt betrachten. [Beleg](VALIDATION.md#uart-demo-20261104-07).

Die Einstellung Use device data rate ist bestätigt: Frequency=10 Hz,
dt mode=`1/f0`, Wellenformintervall und TXT-Zeitschritte 0,1 s. Dieses Raster
ist nominell, keine Messung der Aufnahme-/Empfangszeiten. Einheit weiterhin
leer; reale DUT-Ausgabe gesperrt. Als nächstes sind Ungültig-/Altwertverhalten
und Wiederanlauf zu belegen; gemeinsamer Windows-Brückenpfad bleibt ungeprüft.


### Lauf 08: Timeout und Fortsetzung belegt, nominelle Zeitachse verliert Datenpause

GSVmulti zeigt bei einer 30-s-No-Byte-Pause timeout! während der Aufnahme.
Neue −0,750 erscheinen laut Nutzer ohne manuellen Eingriff. TXT und TDMS
enthalten genau die 500 gesendeten Zahlen: 300× +0,250, 200× −0,750.
Die 30,000983790 s Pi-Pause (HOST_MONOTONIC) steht im Export jedoch nur als
0,1-s-Abstand beider Wertblöcke, ohne Ungültigmarkierung. Der Zahlenkanal
ist scheinbar kontinuierlich. [Messbeleg](VALIDATION.md#uart-demo-20261104-08).

Damit ist Omit/Senderpause in Verbindung mit dem nominellen Raster keine
hinreichende Ungültigbehandlung für Kalibrierdaten. Timeout-Anzeige allein
schützt die exportierten Daten nicht. Eine explizite Ungültigmarkierung
muss getrennt erprobt werden; NaN bleibt bis dahin unbestätigt. Reale
DUT-Ausgabe bleibt gesperrt. Timeout-Verzögerung, Altwertanzeige vor Timeout,
physische Leitungs-/Prozessausfälle und gemeinsame Brücke sind nicht abgenommen.


### Lauf 09: NaN-Probe negativ, dokumentierte Empfängeroption noch zu prüfen

Trotz 200 gesendeter %NaN-Telegramme enthält Lauf 09 keine NaN-Einträge in
TXT oder TDMS. Nur 408 gültige Werte (+0,125 und −0,625), dazwischen 0,1 s
nomineller Abstand; GSVmulti zeigt während NaN Timeout. Zahlenfilter bleibt
aktiv, weshalb dies keine allgemeine Aussage gegen jede NaN-Konfiguration ist.
[Messung](VALIDATION.md#uart-demo-20261104-09).

Die [Anleitung S. 74](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf)
beschreibt Replace Missing values als Aufnahmeoption: fehlende Werte werden
per Timeout-Zählung mit 1E+300 markiert. Wirkung bei UserDefined unbekannt
([OQ-51](open-questions.md#oq-51)). Ein Vergleich mit unverändertem NaN-Sender
ist vorbereitet, noch nicht gestartet. Kein Senden dieser Markerzahl als
Protokollerfindung; keine Auswertung eines Markers als gültiger Messwert.
Manuelle Aufnahme und ein UserDefined-Kanal im Test; Herstellereinschränkungen
für Schwellenwert-Trigger und Software-Spezialsensoren beachten. Reale
DUT-Ausgabe bleibt gesperrt.


## Reproduzierbarer UserDefined-Fall: Ungültige Zeiträume fehlen {#userdefined-ungueltig-repro}

Windows 11, GSVmulti 2.03 Pro, UserDefined auf realem FTDI-COM4,
115200/8N1, Präfix %, ein Wert, Zahlenfilter ein. Aufnahme manuell,
Record every value, nominell 10 Hz (dt mode=1/f0), Text-Auto-Export.
Synthetische gültige Zahlen und abrupte Sprünge werden korrekt gespeichert.
Lauf 08: No-Byte-Pause wird sichtbar als Timeout gemeldet, aber im Export
verdichtet. Lauf 09: Gesendete %NaN-Telegramme erzeugen keine NaN-Einträge.
Lauf 10: Nach Aktivieren von Replace Missing Values dieselbe Sendefolge;
weiterhin keine Fehlwertmarker. Nutzer bestätigt den Haken nach dem Test.
[Belege](VALIDATION.md#uart-demo-20261104-10).

Minimaler Stimulus der Läufe 09/10: 300× `%+000.125\r\n`, dann
200× `%NaN\r\n`, danach 200× `%-000.625\r\n`, Zielrate 10/s.
Alle Payloads beider Läufe sind identisch. Ergebnis von Lauf 10:
228 gültige +0,125 und 200 gültige −0,625, keine Marker, beide Blöcke im
Export 0,1 s auseinander. Manuelle Aufnahme startet nach Senderbeginn;
der fehlende Zahlenanfang ist keine Aussage über Verlust innerhalb der Aufnahme.

Mit GSVmulti-Entwicklung zu klären:

1. Welche explizite Ungültigmarkierung unterstützt UserDefined, und wie wirkt
   Filter Out Non-Numeric darauf?
2. Gilt Replace Missing Values auch für UserDefined, und unter welchen
   Bedingungen werden Marker in TDMS/TXT erzeugt?
3. Welcher unterstützte Weg erhält ungültige Zeiträume, ohne den letzten
   gültigen Wert weiterzuverwenden oder die Zeitachse zu verdichten?

Es wurde keine Nachricht versandt. Das lokale Reproduktionspaket dient der
Prüfung, enthält Demowerte und keine echte DUT-Messung. Bis zur geklärten,
belegten Ungültigbehandlung bleibt reale Ausgabe gesperrt. Kein neues natives
Protokoll oder Zahlenersatz wird aus diesem Befund erfunden. OQ-06 und OQ-51
bleiben teilweise geklärt; P4 ist nicht abgenommen.


### Lauf 11: Einheit mV/V und Skalierung 1 gespeichert

510 gültige Rampenwerte (−0,210 bis +0,299, Senderindizes 90–599) sind in
TXT und TDMS exakt unverändert erhalten. TDMS trägt mV/V sowohl in
unit_string als auch NI_UnitDescription, Scaling=1. Die gespeicherte
`svmulti-uart-mvv-test.ucf` enthält ebenfalls Unit=mV/V. Ein Neuladen der
Session ist damit noch nicht getestet. Der TXT-Export trägt keine eigene
Einheit; zugehörige Metadaten gemeinsam aufbewahren.
[Beleg](VALIDATION.md#uart-demo-20261104-11).

OQ-01 ist damit für das gültige Zahlenprofil der eingesetzten 2.03-Pro-
Konfiguration geklärt. Das hebt weder provisional noch die DUT-Ausgabesperre
auf; fehlende Ungültigzeiträume, Quellzeit-/Latenznachweis und gemeinsame
Windows-Brücke bleiben offen.


## Wiederöffnen nach Device/Channel Close scheitert {#userdefined-reopen-fehler}

Lauf 12 sollte Altwertnachlauf nach COM-Schließen/Öffnen prüfen. Der Pi
sendet 900 eindeutige gültige Demowerte in drei unterscheidbaren Abschnitten;
der Empfänger öffnet nach Close aber nicht wieder. Screenshot:
Error 805306614 (0x300000F6), MEGSV.DLL: Comport requested for opening is
already open, Aufrufkette GS Vactivate Extended / OpenDevice2.vi.
Nutzer meldet, dass vollständiges Beenden/Neustarten von GSVmulti hilft.
[Versuch und Grenzen](VALIDATION.md#uart-demo-20261104-12).

Die [Herstellerreferenz einer verwandten DLL](https://www.me-systeme.de/produkte/elektronik/gsv-8/anleitungen/gsv86dll_referencemanual.pdf)
führt den Code als ERR_COM_ALREADY_OPEN. Das ist kein Beweis, welcher Prozess
einen Windows-Handle hält oder ob nur interne DLL-Verwaltung übrig bleibt.
OQ-52 trennt beides mit einer externen SerialPort.Open/Dispose-Probe im
Fehlerzustand und nach vollständigem GSVmulti-Ende. Kein Sender notwendig,
keine Bytes schreiben. Erst danach gezielt über Wiederanlauf oder Puffer
urteilen; dieser Versuch hat keinen erfolgreichen Wiederanlauf belegt.
Reale DUT-Ausgabe bleibt gesperrt.


Die externe COM4-Probe aus Lauf 12 ist bei weiter laufendem GSVmulti nach
Close verweigert und bei vollständig beendetem GSVmulti erfolgreich.
Das spricht für eine GSVmulti-/Bibliotheks-assoziierte Portbelegung;
Handle-Besitzer und interne Ursache sind nicht direkt erfasst.
[Vorher-/Nachher-Beleg](VALIDATION.md#uart-demo-20261104-12).
OQ-52 teilweise geklärt. Manueller kompletter Prozessneustart bleibt der
Nutzer-Workaround; kein erfolgreicher Wiederanlauf im selben Prozess belegt.


### Lauf 13: Filter-aus-Variante liefert keine gültigen Zahlen

Bei bytegleicher 700er-NaN-Folge meldet der Nutzer mit ausgeschaltetem
Zahlenfilter durchgehend Timeout, auch in den gültigen Abschnitten +0,125
und −0,625. Damit kein brauchbares Zahlen-/NaN-Profil nachgewiesen.
[Versuch](VALIDATION.md#uart-demo-20261104-13). Aktuelle geänderte Session
zuerst gegen die erfolgreiche mV/V-Session aus Lauf 11 vergleichen; interne
Ursache und isolierte NaN-Unterstützung bleiben offen. Möglicher UI-Test
Binärpräfix 25 hex würde dasselbe %-Byte senden, ein anderer Parserweg ist
nicht belegt. Reale DUT-Ausgabe bleibt gesperrt.


### UCF-Vergleich: Filter-aus-Versuch mit weiteren Konfigurationsänderungen

Die neue `svmulti-uart-mvv-test2.ucf` aus Lauf 13 unterscheidet sich von der
erfolgreichen mV/V-Session in genau drei Feldern: Unit leer statt mV/V,
Frequency 1 statt 10, Separator 0 statt 256. Port, Bitrate, Kanalposition,
Präfix37 und OpenFlags gleich. Die Bedeutung des Rohfelds Separator ist nicht
belegt; keine eigene Filterbit-/Trennzeichenspezifikation daraus erfinden.
[Vergleich](VALIDATION.md#uart-demo-20261104-13), [OQ-53](open-questions.md#oq-53).
Vor weiteren Versuchen die aktuelle Filter-aus-Definition mit 10 Hz/mV/V
und unveränderter Skalierung 1 neu speichern und UI/Datei abgleichen. Mehrere
geänderte Parameter beweisen keine einzelne Ursache der Timeouts.


### Lauf 14: Nach Konfigurationsabgleich weiterhin Timeout ohne Filter

Korrigierte UCF mit10Hz und mV/V stimmt bis auf Separator0 statt256 mit der
funktionierenden Lauf-11-UCF überein; Filter aus ist im UI bestätigt. Bei der
identischen 700er-NaN-Sendefolge aus Lauf 10 meldet Nutzer trotzdem durchgehend
Timeout einschließlich gültiger Zahlen. Das ergibt keinen isolierten NaN-
oder internen Parserbefund. Positive Kontrolle mit bekannter funktionierender
UCF und derselben Sendefolge ist vorbereitet, noch nicht ausgeführt.
[Beleg](VALIDATION.md#uart-demo-20261104-14), [OQ-53](open-questions.md#oq-53).


### Lauf 15: Filter-ein-Kontrolle liest gültige Zahlen, NaN bleibt unmarkiert

440 korrekte Zahlen in TXT/TDMS (240×+0,125 und200×−0,625), mV/V,
Skalierung1 und10Hz bestätigt. Die identische Sendefolge zum Filter-aus-Lauf14
enthält200 NaN-Marker, keiner ist in der Aufnahme erhalten. Die gültigen
Blöcke liegen nominell0,1 s auseinander. [Beleg](VALIDATION.md#uart-demo-20261104-15).
Aktuelle Replace-Missing-Values-Checkbox nicht separat bestätigt; die explizite
Bestätigung der negativen Optionentestwirkung stammt weiterhin aus Lauf10.

Gezielter nächster Vergleich zur Filter-aus-Konfiguration14: dokumentiertes
Zeichenpräfix A statt %, gleiche Zahlen und NaN, übrige UCF-Parameter gleich.
Nur der Präfixbytewert wird über einen eigenen synthetischen Demo-Formatter
geändert. Keine interne Parserursache oder NaN-Unterstützung voraussetzen;
vor Senden neue UCF prüfen und nach vollständigem GSVmulti-Neustart laden.
Experiment vorbereitet, kein A-Präfix-Lauf durchgeführt. Reale DUT-Ausgabe
weiter gesperrt.

### Lauf 16: A-Präfix behebt Filter-aus-Timeout nicht

Gegenüber korrigiertem Profil14 nur Prefix37→65 geändert, alle700 Frames
bis auf das erste Byte identisch geprüft. Nutzer bestätigt durchgehend
Timeout, bereits im gültigen Anfangsabschnitt. Kein isolierter NaN-Befund
und kein erfolgreicher Export. [Beleg](VALIDATION.md#uart-demo-20261104-16).
Der zuvor vorbereitete A-Vergleich ist damit abgeschlossen. Weitere
Konfigurationsvarianten zurückstellen und tatsächlich geladene Bibliotheks-
versionen erfassen ([OQ-54](open-questions.md#oq-54)). Öffentliches MEGSV-SDK
mit älterem Header ist nicht als diese Laufzeitbibliothek identifiziert.
Reale DUT-Ausgabe bleibt gesperrt.

### Geladene GSV-Bibliotheken {#geladene-gsv-bibliotheken}

Nutzer liefert am 2026-11-04 den laufenden Windows-Prozess-Snapshot aus
Get-Process -Module -FileVersionInfo, gefiltert nach GSV im Dateinamen.
Installationsbasis `C:\Program Files\GSV-Multichannel_v2.03`:

| Relativer Pfad | FileVersion | ProductVersion |
| --- | --- | --- |
| GSVmultichannel.exe | 2.3.4 | 2.3.4 |
| data\MEGSV4w32.dll | 1.20.0.64 | 1.20.0.64 |
| data\MEGSV.dll | 1.62.0.64 | 1.62.0.0 |
| data\MEGSV86w32.dll | 1.48.1.64 | 1.48.1.64 |
| data\GSV86CAN.dll | 1.17.7.64 | 1.17.7.64 |

Snapshot: `var/diagnostics/gsvmulti/windows-loaded-modules-20261104/modules.json`.
[OQ-54](open-questions.md#oq-54) damit geklärt. Dateiversion2.3.4 und
UI-Bezeichnung2.03 als getrennte Angaben erhalten; daraus keinen Versions-
konflikt ableiten. Parserzuständigkeit und interner Portbesitzer unbewiesen.

Die [Hersteller-Versionshistorie](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/gsvmulti_1.txt)
beschreibt ab2.02 Logging: in `C:\ProgramData\MEsystemeGSVmulti\config.ini`,
Abschnitt `[Config]`, LogLevel1 für Ereignisse, LogLevel2 zusätzlich für
Fehler der GSV-Hardwaretreiber (ausgenommen GSV-1A8). Ausgabe unter
`C:\GSVmultiLog`, LogLevel0 deaktiviert. Keine Garantie, dass jeder
UserDefined-Parserfehler dort erscheint. Nächster Schritt: vorhandenen
LogLevel und vorhandene Logdateien lesend prüfen, bevor eine gesicherte
Konfigurationsänderung und gezielte Reproduktion angeleitet werden.
Keine ausdrücklich benannte UserDefined-/NaN-Korrektur in der geprüften
Versionshistorie gefunden; keine Reparatur oder Updatewirkung behaupten.

**Istzustand am 2026-11-04:** Nutzerabfrage zeigt `[Config]`, keinen aktiven
LogLevel-Eintrag. Bestehende Logdateien und implizite Defaultwirkung ungemessen.
Aktivierung von LogLevel2 mit vorherigem vollständigem Prozessende und
Konfigurationssicherung vorbereitet. Noch keine erfolgreiche Aktivierung oder
UserDefined-Fehlererfassung behaupten. Zuerst bekannten Filter-ein-Stand laden
und Wiederöffnungsfehler einmal mitprotokollieren; Sender dafür nicht nötig.

**Folgestand:** Nutzer bestätigt Erfolg des gesicherten Konfigurationsblocks:
LogLevel2 gesetzt, Backup-Pfad im Laborjournal und Diagnose-Snapshot.
Wirksame Übernahme nach Neustart und tatsächliche Logausgabe noch unbewiesen;
noch kein protokollierter Close-/Reopen-Versuch.

### Laufzeit-Logging: Zwei getrennte Fehlerbefunde {#userdefined-logging-befund}

LogLevel2 ist jetzt durch eine tatsächliche Logausgabe belegt. Beim initialen
Open Session UserDevice COM4/Input1/Fdata10,000 tritt0xFFFFFFFF in
GS Vclear Buffer.vi auf. Später zweimal0x300000F6 bei GS Vactivate Extended
über OpenDevice2.vi/OpenSession.vi. Screenshot bestätigt already open.
[Beleg](VALIDATION.md#userdefined-logging-20261104). Kein Sender aktiv.
Kein kausaler Zusammenhang oder konkreter interner Ressourcenfehler bewiesen;
Close/Deaktivierung ist im gelieferten Logausschnitt nicht explizit enthalten.

Die [ältere MEGSV-Referenz S.171](https://www.me-systeme.de/produkte/software/megsv/ba-megsv-v2.0.pdf)
beschreibt mehrere mögliche GSVclearBuffer-Fehlerursachen. Der allgemeine
Code−1 erlaubt keine einzelne Diagnose für die aktuelle UserDefined-Version.
Neue [OQ-55](open-questions.md#oq-55). Gegenprobe ohne Sessionladen vorgesehen:
Programm startet laut Nutzer leer, dann identisches Profil direkt über Add
Channel anlegen; einmal Close und ebenfalls per Add Channel wieder anlegen.
Numerischer Timeout ohne Sender ist kein Aktivierungsfehlernachweis.

Lokales Belegpaket mit geprüftem Manifest/CRC:
`var/exports/gsvmulti-userdefined-reopen-logging-2026-11-04.zip`.
Original-Voll-Log nicht hochgeladen, nur Nutzer-Ausschnitt; kein Versand und
keine Reparatur behauptet. Echte DUT-Ausgabe bleibt gesperrt.

### Add Channel reproduziert die Fehlersignaturen ohne Sessionladen

Gegenprobe mit leerem Neustart, direktem Anlegen und Wiederanlegen über Add
Channel: initial einmal0xFFFFFFFF in GS Vclear Buffer, später zweimal
0x300000F6 über GS Vactivate Extended/OpenDevice2/AddChannel_v5. Screenshot
bestätigt Error805306614. Neues Log meldet1 Hz statt10 Hz im Sessionfall;
keine neue UCF. Beide Fehler benötigen somit kein Sessionladen, ihre Ursache
und ein kausaler Zusammenhang bleiben offen.
[Beleg](VALIDATION.md#userdefined-addchannel-logging-20261104).

Nutzer hat direkten Entwicklungskontakt. Nächster Schritt: tatsächliche
UserDevice-Initialisierungs-/Cleanup-Pfade dort prüfen, insbesondere
ClearBuffer-Unterstützung, COM-Handle/interne Portregistrierung und
Deaktivierungsfehler. Kein erneuter gleichartiger Versuch geplant.
Vergleichspaket beider Fälle lokal geprüft, ohne Versand:
`var/exports/gsvmulti-userdefined-reopen-comparison-2026-11-04.zip`.
Kein korrigierter Build oder erfolgreicher In-Prozess-Wiederanlauf belegt;
vollständiger Prozessneustart bleibt Workaround, reale DUT-Ausgabe gesperrt.

### Option: Direkter USB-COM-Port vom Pi 5 {#usb-cdc-option}

Nutzer fragt nach USB statt UART. Der aktuelle DELOCK-Aufbau benutzt bereits
USB auf Windows-Seite, Pi-seitig aber GPIO-UART. Ein direkter USB-Weg wäre
Pi5-USB-C im Peripheral/Gadget-Modus, als Serial CDC ACM konfiguriert, zu
Windows-COM und GSVmulti UserDefined. Das würde das com0com-Portpaar für
**diesen direkten Weg** vermeiden; kein Nachweis für Netzwerk oder gemeinsame
Brücke. Anwendungstelegramme bleiben Aufgabe eines TelegramFormatter.

Die [offizielle OTG-Anleitung, Abschnitt Raspberry Pi4/5 und Serial CDC ACM](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009276-WP-1-Using%20OTG%20mode%20on%20Raspberry%20Pi%20SBCs)
dokumentiert USB-C-Peripheral und acm.usb0. Die normalen Pi-USB-A-Ports sind
Host-Anschlüsse. [Microsofts Usbser-Dokumentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids)
beschreibt den integrierten Treiber für korrekt deklarierte CDC-Geräte;
konkrete Enumeration dieses Pi noch nicht geprüft. USB-Ethernet ist eine
andere Funktion und erzeugt keinen seriellen COM-Port.

USB-C wird auch zur Stromversorgung verwendet. Ausreichende Versorgung des
Pi5 mit Kamera/Peripherie über den gewählten Hostanschluss oder eine geeignete
alternative Versorgung muss vor Umbau geklärt werden. Keine generische
Y-Kabel-/GPIO-Stromlösung daraus ableiten. Lokaler Nur-Lese-Snapshot:
`var/diagnostics/gsvmulti/usb-gadget-feasibility-20261104/`. Kein UDC aktuell
sichtbar; Gadget/Bootkonfiguration nicht geändert. Nicht als ausgewählter
oder abgenommener Transport zählen. [OQ-56](open-questions.md#oq-56).
UserDefined-Fehler und ungültige Zeiträume bleiben separate Grenzen.

### Konkrete USB-Umsetzung geprüft, Versorgung noch zu entscheiden {#usb-cdc-umsetzung}

Nur-Lese-Untersuchung: dwc2 eingebaut, libcomposite/usb_f_acm/g_serial als
Module vorhanden; configfs gemountet, kein aktiver UDC/kein Gadget. ttyGS0-
Getty deaktiviert, keine Gadget-Konsole in cmdline. Keine Installation,
Modulladung oder Bootänderung. Firmware-Stromabfragen wegen fehlendem Zugriff
auf vcio_gencmd gescheitert; kein Last-/Unterspannungsbefund ableitbar.
Snapshots und ausführliche Untersuchung:
`var/diagnostics/gsvmulti/usb-gadget-feasibility-20261104/implementation-assessment.md`.

Nutzer nennt SupTronics X1201 V1.1, Versorgung über dessen eigenen USB-C;
Produktion möglicherweise ohne UPS. [Der exakte Herstellerhinweis](https://suptronics.com/Raspberrypi/Power_mgmt/x1201-v1.1.html)
untersagt zusätzliche Versorgung des Pi über dessen USB-C-Buchse. Daher kein
gewöhnliches PC-USB-Kabel parallel zur UPS als freigegebenen Aufbau ansehen.
Ein USB2-Power-Blocker mit unterbrochenem VBUS ist ein zu prüfender Kandidat;
[der Hersteller](https://portablepowersupplies.co.uk/product/usb-power-blocker)
warnt selbst vor ausbleibender Datenkommunikation bei vielen Geräten. Keine
Pi5/X1201-Kompatibilität oder galvanische Trennung daraus behaupten.
Für Produktion ohne UPS ist eine eigene Versorgungslösung zu bestimmen.
Raspberry Pi empfiehlt [5V/5A, bei3A standardmäßig600mA USB-Peripheriebudget](https://www.raspberrypi.com/documentation/computers/getting-started.html#power-supply).
Vorhandene StreamCam/Referenz bei der Lastprüfung berücksichtigen.

Vorgeschlagener Softwareweg: nach gesicherter Versorgung gezieltes Pi5-
Peripheral-Overlay, geplanter Neustart, genau ein CDC-ACM-Gadget über ConfigFS,
Windows-Usbser/COM-Erkennung und dann endliche synthetische Demo. CDC-Deskriptoren,
Seriennummer und VID/PID-Herkunft festlegen, keinen GSV-Gerätetyp imitieren.
[ConfigFS](https://docs.kernel.org/usb/gadget_configfs.html) erlaubt kontrollierten
Aufbau/Unbind; Legacy g_serial ist die einfachere Alternative mit weniger
Deskriptorkontrolle. USB-Ethernet erzeugt dagegen keinen direkten COM-Port.
Bestehende Demo-CLI kann ttyGS0 als com-port öffnen, noch nicht praktisch
geprüft. OutputConfig unterstützt weiterhin nur off/uart/tcp; USB-Live-Auswahl
ist nicht implementiert und nicht durch lockere Portprüfung zu ersetzen.
Systemd/Installer erst nach Erfolg der ersten USB-Demo planen; Rückbau eigener
Gadget-/Booteinträge, keine globalen USB-Hostmodule entfernen.
[OQ-56](open-questions.md#oq-56) bleibt teilweise geklärt; echte Ausgabe gesperrt.

### Windows-Python-Brücke importiert erfolgreich

SCP-Transfer, eigene Python3.15-Umgebung, pyserial3.5 und --help auf Windows
vom Nutzer bestätigt. [Beleg](VALIDATION.md#windows-bridge-help-20261104).
Nächster Schritt ist der vorhandene lokale Demomodus COM5→COM6/GSVmulti,
mit600 eindeutigen synthetischen Zahlen, Zielrate10Hz und eigenem Logordner.
Aufnahme und Export vor Senderstart vorbereiten; vor Datenbeginn ist ein
Timeout erwartbar, aber kein Beleg eines COM-Aktivierungsfehlers. Dieser
Demomodus prüft noch nicht den Pi-JSONL-/ACK-Austausch; TCP folgt danach.
Noch kein neuer Demolauf, keine echte DUT-Ausgabe.

### Lokale Windows-Demo vollständig, Takt und Zeitraster getrennt bewerten {#windows-demo-timing}

600/600 Werte aus Windows-Demomodus sind exakt und in vollständiger Reihenfolge
in TXT/TDMS auf COM6 gespeichert, mV/V/Scaling1 bestätigt.
[Beleg](VALIDATION.md#windows-local-demo-20261104-01). Kein Verlust und keine
Mittelung in dieser gespeicherten Folge. Lokaler Format-/COM-/Empfangspfad
somit belegt, gemeinsamer Pi-JSONL-/ACK-Pfad noch nicht getestet.

Tatsächliche Windows-Ereignisspanne66,1322657 s (HOST_MONOTONIC), Mittel9,0576Hz
bei Ziel10Hz. GSVmulti verwendet weiterhin1/f0 und nominell59,9 s. Weder
Ankunftszeiten noch Latenz daraus ableiten; OQ-50 bleibt teilweise geklärt,
Demo-Pacing als [OQ-57](open-questions.md#oq-57) separat nachführen.

Nächster TCP-Versuch: Pi liefert600 synthetische Werte bei Ziel10Hz;
Windows-Brücke fragt mit --rate-hz100 ab. Im Nicht-Demomodus steuert dieser
Parameter die Wartezeit zwischen Poll-Anfragen, nicht die Messwertquelle.
Unverändert COM5 für Brücke, COM6 für GSVmulti. Neue Aufnahme und eigener
Logordner, Pi-Publisher erst nach Empfangsbereitschaft starten. Kein laufender
TCP-Sender und keine echte DUT-Ausgabefreigabe.
