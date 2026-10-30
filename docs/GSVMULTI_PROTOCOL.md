---
weg: entwickeln
---

# GSVmulti-Anbindung

**Vorher lesen:** [Messpfad und Freigabe](uebersicht/messpfad.md#ausgabe-und-fehlersuche)
und [Zeitstempel richtig lesen](uebersicht/zeitstempel.md#von-aufnahme-bis-gsvmulti).

## Stand: UserDefined-Prototyp gebaut, nicht freigegeben {#stand-das-format-ist-unbekannt}

**Stand 2026-10-28:** Das bereitgestellte PDF samt Beispiel-ZIP reicht als Grundlage für einen
**Transportprototyp**, noch nicht für eine freigegebene Messanbindung.
GSVmulti PRO bietet mit `UserDefined` einen konfigurierbaren seriellen
Zahlenimport. Ein Nachbau des GSV-2-/GSV-6-/GSV-8-Geräteprotokolls ist für
diesen Weg nicht erforderlich. Die vorherige Aussage „das Eingangsformat
ist vollständig unbekannt“ ist damit überholt
([OQ-01](open-questions.md#oq-01), [OQ-07](open-questions.md)).

Der Nutzer bestätigt Windows als Zielsystem. Das PDF dokumentiert dort
**GSVmulti 2.01 Pro**; die aktuelle Herstelleranleitung **v2.6 ist ein
Dokumentstand**, keine Bestätigung der Funktionen jeder Softwareversion.
Ein Empfangs- oder Aufzeichnungstest in dieser 2.01-Installation fehlt.
Die Dokumentation dieser Prüfung verändert weder Windows noch den Pi-Aufbau.

| Was lässt sich jetzt bauen? | Was bleibt nachzuweisen? |
| --- | --- |
| Eigenständiger Sender für endliche Demowerte mit festem Zahlenprofil | Annahme und Aufzeichnung in der konkreten 2.01-Pro-Installation |
| Neuer `TelegramFormatter` für einen freigegebenen DUT-Wert pro Zeile | Ungültig-/STALE-Verhalten in Anzeige, Datei und Kalibrierauswertung |
| Serielle Ausgabe mit vorhandenem `SerialSink` an einen passenden COM-Transport | Port, Treiber, Pufferung, Wiederanlauf und Dauerbetrieb |
| Geplante Einbindung in `/live` mit parallelem JSONL-Audit | Lebenszyklus, Freigabesicherung und Metadaten des tatsächlichen Laufs |

**Die vollständige Messfreigabe bleibt offen.** P4-1 (Formatter) und P4-2
(Demo-Sender) sind als Prototyp gebaut und mit pty/Fakes geprüft, **ungeprüft
am Windows-PC**. P4-3 (Live-Anbindung) ist nicht implementiert; die Phase ist
nicht abgenommen.

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
| `send_nan` | Annahme und Ungültigsemantik von `NaN` sind unbestätigt. |
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

Die Wahl ist noch offen ([OQ-47](open-questions.md#oq-47)). `COM20`,
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
live/session.py              aktueller Live-Lauf: nur JSONL, kein SerialSink
scripts/gsvmulti-demo-sender.py  eigenständiger Demo-Sender, kein Live-Lauf
```

<div class="wiki-seam" markdown="1">

| Trennstelle | `TelegramFormatter` (`sink/protocol`) |
| --- | --- |
| Vertrag | `capabilities(self) -> FormatterCapabilities` als `@property`; <code>format(self, record: ValueRecord) -&gt; bytes &#124; None</code> liefert Telegrammbytes oder `None`. Fähigkeiten nennen Formatkennung, Zeitstempel, Invalid-Policies, Gerätekommandos, Kanalzahl und `provisional`. |
| Darf geändert werden | `UserDefinedFormatter` aus `dispread.sink.protocol.userdefined` direkt importieren und gezielt an `SerialSink` übergeben; konkrete Formatter haben keine zentrale Registry. Für `/live` zusätzlich Start/Stopp, Fehler, Portfreigabe und Auditmetadaten integrieren (P4-3, noch offen). |
| Bleibt unverändert | Leser und Freigabe ohne Referenzparameter, Wert und Aufnahmezeit im `ValueRecord`, paralleles JSONL-Audit; `gsv_ascii.py` bleibt der werfende Platzhalter. |
| Tests | [Formatter und SerialSink am pty](../tests/test_userdefined_formatter.py), [Demo-Sender mit pty/Fakes](../tests/test_gsvmulti_demo_sender.py) und vorhandene [Gate-/Referenztests](../tests/test_gate_und_referenz.py); Windows-Abnahme und Live-Lebenszyklus weiterhin offen. |

</div>

Der neue Formatter deklariert einen Kanal, keine Gerätekommandos,
`format_id="gsvmulti_userdefined_v0"`, `carries_capture_timestamp=False`,
`timestamp_resolution_ns=None`, `provisional=True` und ausschließlich
`omit_record`. Diese Policy belegt die lokale Auslassung, **keine** sichere
Ungültigwirkung in GSVmulti. Präfix, ASCII und CRLF besitzen keine eigenen
Felder in `FormatterCapabilities`; die festen Formatregeln stehen im
Formatter-Docstring. Der Prototyp bleibt vorläufig;
`provisional` und die Fähigkeiten gehören in jedes Runartefakt. Beispiel 16
schreibt sie nach `report.json`; `Pipeline` erzeugt keinen allgemeinen
Laufbericht. Der aktuelle `/live`-Pfad hat noch keinen seriellen Formatter.
Die im PDF vorgeschlagene Funktion `read_values(t)` ersetzt bei picam-ai
weder Leser noch Freigabe. Der DUT-Wert kommt aus dem `ValueRecord`; ein
Referenzabgleich darf ihn nicht nachträglich korrigieren.

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

Der Sender schreibt nicht blockierend (`write_timeout=0`), ohne `flush()`
und ohne Retry. Bei Schreibstau, kurzem Write oder überschrittener
Schreibfrist wird der Ausgangspuffer verworfen und `status="dropped"` mit
`drop_reason` protokolliert. Die nächste Wartefrist beginnt nach Verarbeitung
und Audit neu; es gibt keinen Aufholburst. Ein Portfehler wird protokolliert
und beendet den Lauf mit Exitcode 1. `sent` bedeutet nur lokale Annahme;
`bytes_hex` sind die beabsichtigten Framebytes. Bei Abbruch/kurzem Write
können Teilbytes bereits unterwegs sein, und auch ein als `sent` belegter
Frame kann später beim Leeren eines gestauten Puffers verloren gehen.
Treiber-/USB-Puffer und tatsächlicher Empfang bleiben Teil der Windows-Abnahme.

## Abnahme und nächste Schritte {#abnahme}

**Prototypstatus:** Formatter und Demo-Sender sind gebaut, ungeprüft am
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
   und den absichtlichen Verlust der ersten Zeile je Bridge-Verbindung
   erklären. Ablehnungen, Pause, Burst, Streamstillstand, Kabel-/Netzabbruch
   und Neustarts getrennt auslösen. Keine ausgedachten Grenzzeiten als
   erfüllt markieren; Kriterien vorher mit OQ-02/OQ-06 festlegen.
4. **Aktuellen Live-Pfad anbinden:** nur freigegebene `ValueRecord`s, keine
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
