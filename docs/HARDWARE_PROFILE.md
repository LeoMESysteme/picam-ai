# Hardware-Profil

> **Kamera seit 2026-09-25:** Logitech StreamCam (USB 3, UVC, `046d:0893`)
> statt Raspberry Pi AI Camera; die Kameraangaben unten beschreiben die
> IMX500 und sind historisch (`docs/project_history.md`, 2026-09-25).

Gerät `raspi06`. Rechner- und IMX500-Bestand unten: Stand 2026-09-07;
aktuelle StreamCam-Sitzung: 2026-10-21. Speicherplatz- und Paketangaben
sind datierte Schnappschüsse, keine laufende Zustandsanzeige.

## Datenorte: Produkt und Entwicklung (2026-11-04)

Die NVMe-SSD unter `/mnt/ssd` dient nur zur Entlastung bei Backups, Tests,
Training und Diagnoseaufnahmen. Das fertige Gerät läuft ohne SSD auf
SD-Karte. `var/` bleibt deshalb das Produktverzeichnis für Profile,
Kalibrierung, Vorlagen, aktuelle Live-Läufe und Werkbankdaten. Auch der
Geräte-Rückstellpunkt
`var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json` bleibt dort.

Für Tests und Entwicklungsskripte kann die Ablage gesetzt werden:

```bash
export DISPREAD_DEV_DATA=/mnt/ssd/picam-dev
```

Vorhandene Aufnahmen werden zuerst unter `var/<rel>` gesucht, danach unter
`$DISPREAD_DEV_DATA/<rel>`. Ausgelagert sind `diagnostics/` mit Ausnahme des
Rückstellpunkts sowie `live/`-Sitzungen vor `live-20261023…`. Die alten Ordner
`rescue-20260925`, `removed-20260928-sc` und `removed-20260929-sc3a` liegen
unter `$DISPREAD_DEV_DATA/altlasten/`. Fixture-Pfade behalten das relative
alte Schema; absolute SSD-Pfade gehören nicht in Fixtures oder Profile.

Seit 2026-11-04 liegen auch die Diagnoseordner aller aufgezeichneten
Live-Läufe unter `$DISPREAD_DEV_DATA/live/<sitzung>/<lauf>/diagnose/`
(19 Ordner, 6,4 GB, prüfsummengleich von der SD-Karte verschoben).
Records, `session.json`, `profile.json` und `setup/` der neueren Sitzungen
bleiben unter `var/live/`. Tests und Skripte lösen den Diagnoseordner eines
Laufs mit `scripts/_devdata.py:diagnose_dir(run_dir)` gesondert auf:
lokaler Ordner zuerst, danach Entwicklungsablage, unabhängig vom
Sitzungsdatum. Auch direkte `input_path`-Anfragen auf
`live/<sitzung>/<lauf>/diagnose[/...]` verwenden diese Reihenfolge.
Es werden keine Verzeichnisse oder Links von Produktpfaden auf die SSD
angelegt; neue Live-Läufe schreiben weiterhin nach `var/live/`.

Ohne Variable werden Tests mit fehlenden lokalen Aufnahmen übersprungen;
vorhandene lokale Aufnahmen bleiben nutzbar. Neue Diagnoseaufnahmen der
Skripte verwenden standardmäßig `$DISPREAD_DEV_DATA/diagnostics/`, sonst
wie bisher `var/diagnostics/`. Explizite Ausgabeorte bleiben maßgeblich.
Produktcode unter `src/` kennt weder diese Variable noch die SSD; die
Auflösung erfolgt ausschließlich in Tests und Skripten.

## Aktuelle StreamCam-Sitzung (2026-10-21)

Einrichtung `live-20261021T151835Z` vor dem strengen Werteplan-Lauf:
USB 3 mit 5000 Mbit/s, 1920×1080 YUYV bei angeforderten 30 Bildern/s.
Die automatische Einrichtung hat Fokus 42, Belichtung 300 (V4L2-Einheiten),
Gain 14 und Weißabgleich 4717 K gesetzt und zurückgelesen; Autofokus,
Belichtungs- und Weißabgleichsautomatik sind danach ausgeschaltet.
Das sind sitzungsbezogene Einstellungen, keine Vorgaben für andere
Aufstellungen. Diagnose unter
`$DISPREAD_DEV_DATA/diagnostics/messlauf-vorbereitung-20261021/`, Kameraregler unter
`$DISPREAD_DEV_DATA/live/live-20261021T151835Z/setup/camera-settings.json`
(seit 2026-10-28 ausgelagert, siehe Datenorte oben).
Die nachfolgenden Kameraabschnitte bleiben historischer IMX500-Stand.

## Rechner

| Größe | Wert |
| --- | --- |
| Modell | Raspberry Pi 5 Model B Rev 1.1 |
| RAM | 8 GB |
| Speicher | 49 GB, davon **34 GB frei** |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.12.34+rpt-rpi-2712 |
| Python | 3.13.5 |
| Bootloader | aktuell (Stand 2026-05-26) |

**Konsequenz aus dem damaligen Speicherstand:** Entwicklungsaufnahmen können
auf externen Speicher ausgelagert werden (siehe Datenorte oben). Produktdaten
bleiben auf SD. Im Betrieb Ringpuffer mit harter Obergrenze — der
`JsonlSink` rotiert bei 64 MB und behält 5 Generationen.

## Kamera (historisch: IMX500) { #kamera }

| Größe | Wert |
| --- | --- |
| Modul | Raspberry Pi AI Camera (Sony IMX500) |
| Anschluss | **CAM/DISP0** |
| Device-Tree-Knoten | `/axi/pcie@1000120000/rp1/i2c@88000/imx500@1a` |
| CAM-I2C-Busse | 6 und 10 (Grundausstattung ohne Kamera: 1, 13, 14) |
| Erkennung | über `camera_auto_detect=1`, **kein** explizites Overlay nötig |
| Sensor | 4056×3040, 10 bit, RGGB |
| Modi | 2028×1520 @ 30,02 fps · 4056×3040 @ 10,00 fps |
| Fokus | **manuell**, mit Fokuswerkzeug |
| Fokus-Controls in libcamera | **keine** — kein `AfMode`, `LensPosition`, `AfState` (gemessen 2026-09-08) |
| Fokusstellung | am 2026-09-08 eingestellt, Schärfe 216,6; Objektiv **nicht** gegen Verdrehen gesichert |
| Herstellerangabe Optik | f = 4,74 mm, F1.79, Fokusbereich ca. 20 cm – ∞ |

Gemessene Kenngrößen siehe [TIMING.md](TIMING.md): 6,8 s `.rpk`-Warmlauf,
15,0 Inferenzen/s mit SSD MobileNetV2 320×320, `SensorTimestamp` in
CLOCK_BOOTTIME.

## Serielle Schnittstellen

**Stand 2026-10-21:** Die GSV-2AS-Referenz wird über den bereits am
2026-09-22 dokumentierten PL2303-USB-RS232-Adapter an `/dev/ttyUSB0`
mit 38400 Baud, 8N1 gelesen. Sie dient sowohl der Datenernte als auch der
optionalen Live-Referenzaufzeichnung; sie ist kein GSVmulti-Ausgang.
Die folgende Portliste ist der frühere Bestand vom 2026-09-07.

| Gerät | Rolle |
| --- | --- |
| **`/dev/ttyAMA0`** | **Datenport für GSVmulti.** Aktiv durch `dtparam=uart0=on` |
| `/dev/ttyAMA10` = `/dev/serial0` | **3-Pin-Debug-Header** — ausdrücklich NICHT der Nutzdatenport |
| `/dev/ttyUSB*`, `/dev/ttyACM*` | nicht vorhanden, kein USB-Seriell-Adapter angeschlossen |

`serial-getty@ttyAMA10` ist disabled, beide Ports sind also frei.

**Elektrisch offen ([OQ-09](open-questions.md)):** Pi-GPIO-Pegel dürfen nicht
direkt mit RS-232 verbunden werden. Es braucht einen RS-232-/RS-485-Transceiver,
und die galvanische Trennung ist für den Laboraufbau zu bewerten. Ein virtueller
USB-COM-Port am Pi 5 darf nicht pauschal vorausgesetzt werden.

## Messverstärker GSV-2AS — Klemmenbelegung und Schnittstelle

Quelle: ME-Systeme, „DMS Messverstärker GSV-2 Bedienungsanleitung (GSV-2LS,
GSV-2AS, GSV-2FSD)", lokal unter
`var/datenblaetter/gsv2-bedienungsanleitung.pdf` (+ `.txt`), abgerufen
2026-09-22 von
`https://www.me-systeme.de/produkte/elektronik/gsv-2/anleitungen/gsv2-bedienungsanleitung.pdf`.
**`var/` ist gitignored** — die lokale Kopie überlebt keinen frischen Clone,
dauerhaft ist nur die URL. Das Laborgerät meldet beim Hochfahren
`GSV-2AS (GSV21 V1.3.07)`.

**5-polige Schraubklemme (RS232 / RS422):**

| Klemme | Standard | Bedeutung |
| --- | --- | --- |
| A | GNDC | Masse RS232 / RS422 |
| B | Rx | Datenleitung Rx (RS232) bzw. Rx− (RS422) |
| C | Tx | Datenleitung Tx (RS232) bzw. Tx− (RS422) |
| D | Rx+ | Rx+ (RS422) · bei CAN: CAN_GND |
| E | Tx+ | Tx+ (RS422) · bei CAN: CAN_L |

**15-polige Schraubklemme**, soweit für den Laboraufbau relevant: 1 = GNDB,
2…7 = Brückenanschluss (+US, +UF, +UD, −UD, −UF, −US), 8 = UE (Analogeingang
0…10 V), 9 = UA (Analogausgang ±5 V), 10 = GNDA, 11 = SW1, 12 = Tara
(Nullsetzeingang, wirkt auf seriellen **und** analogen Ausgang), 13 = SW2,
**14 = UB (Versorgung 12…24 V DC), 15 = GNDB**.

**Serielle Parameter:** Werkseinstellung 38400 Baud, 8N1. Der GSV „schreibt
seine Messwerte permanent auf die serielle Schnittstelle" — kein Polling
nötig; abschaltbar über Logger-Modus bzw. `GSVStop`. Zwei Ausgabeformate,
umschaltbar per `Set Mode` (38d): Binär (5 Byte je Messwert, 24 bit) oder
**ASCII**. Im ASCII-Modus entspricht die Zeichenkette der Displayanzeige;
Format ab Werk „Vorzeichen, 6 Stellen mit Dezimalpunkt, Leerzeichen, Einheit,
CR, LF". Maximale ASCII-Datenrate bei 38400 Baud: 200 Hz.

**Nicht verwechseln:** Diese Parameter beschreiben das **Messgerät**, nicht
das von GSVmulti erwartete Telegramm ([OQ-01](open-questions.md),
[OQ-07](open-questions.md)). Dass beide zusammenfallen, ist plausibel, aber
nicht belegt.

**Anschluss an den PC/Pi** (Anleitung, „Anschluss des Schnittstellenkabels"):

| GSV-Klemme | | 9-pol. Sub-D-Pin (PC-seitig) |
| --- | --- | --- |
| A | GND → GND | 5 |
| B | RX → TX | 3 |
| C | TX → RX | 2 |

„Die Datenleitungen RX und TX zwischen Verstärker und PC sind dabei gekreuzt."
Für das **GSV-2AS genügen diese drei Adern** — das vollständig beschaltete
Nullmodemkabel (RTS/CTS, DCD+DSR/DTR) verlangt die Anleitung nur für den
GSV-2TSD-DI. Ab 50 Hz Datenrate soll die Schirmung des RS232-Kabels auf die
Erdungsklemme des Gehäuses gelegt werden.

Ist das vorhandene Kabel nach dieser Tabelle konfektioniert, verhält sich sein
Steckverbinder wie ein Modem (DCE): Pin 2 = GSV-Tx, Pin 3 = GSV-Rx. Ein
USB-RS232-Adapter stellt eine PC-Schnittstelle (DTE) bereit, also Pin 2 = Rx
des Adapters. **Damit passt es gerade (straight-through), ohne Nullmodem.**
Kommt nichts an, ist ein 2↔3-Tausch der erste Versuch — das ist gefahrlos.

**Warum nicht direkt an Pi-GPIO ([OQ-09](open-questions.md)):** zwei
unabhängige Gründe.

1. **Spannung.** RS-232-Treiber schalten zwischen etwa −12 V und +12 V (die
   Norm erlaubt bis ±25 V). Pi-GPIO ist 3,3 V und **nicht einmal
   5-V-tolerant**. Positive Spitzen treiben Strom über die Klemmdioden in die
   3,3-V-Versorgung; negative Spannung öffnet die Substratdiode und speist
   Strom in das Substrat — das kann Latch-up auslösen und nicht nur den Pin,
   sondern den SoC zerstören. Ein Vorwiderstand macht das nicht zulässig.
2. **Invertierte Logik.** RS-232 ist gegenüber TTL-UART invertiert: Mark
   (logisch 1, Ruhezustand) ist **negativ**, Space (logisch 0) positiv. Ein
   TTL-UART ruht dagegen auf High. Selbst bei verträglichen Pegeln kämen die
   Bits verkehrt herum an.

Ein Transceiver erledigt **beides** — Pegelwandlung und Invertierung.

**Empfohlener Weg: USB-RS232-Adapter** (FTDI-Chipsatz, erscheint als
`/dev/ttyUSB0`). Gründe: kein Eingriff in die Verdrahtung, und vor allem
**keine Kollision mit `/dev/ttyAMA0`**, das als ausgehender GSVmulti-Datenport
vorgesehen ist. `/dev/serial0` scheidet ohnehin aus (Debug-Header). Vor dem
Anschluss am 2026-09-22 fehlte `/dev/ttyUSB*`; anschließend wurde der unten
dokumentierte PL2303 angeschlossen. Der Benutzer ist bereits in `dialout`.
Für stabile
Namen bei mehreren Adaptern eine udev-Regel auf die Seriennummer vorsehen.

Galvanische Trennung ist im Laboraufbau zu bewerten
([OQ-09](open-questions.md)); isolierte USB-RS232-Adapter gibt es fertig.

**Ist-Zustand des Laborgeräts (Stand 2026-09-22):**

| Einstellung | Wert | Herkunft |
| --- | --- | --- |
| Mode-Register | **`0x02`** (Bit 1 = Text-Modus/ASCII) | am 2026-09-22 von `0x00` umgestellt, **persistent** |
| Ausgabeformat | ASCII, `+0.46776 mV/V<CR><LF>`, 13 Zeichen + CRLF | gemessen |
| Zeilenrate | ≈ 1,8 /s | gemessen |
| Vollausschlag | **1,05 mV/V** (`FFFFFF` = 105 % des Bereichs) | rechnerisch aus Binär- und ASCII-Mitschnitt |
| Schnittstelle am Pi | `/dev/ttyUSB0`, PL2303 (`067b:2303`), 38400 8N1 | gemessen |

Die Modusänderung **überlebt das Ausschalten**. Wer das Gerät im Binärformat
erwartet (etwa eine ältere Auswertung oder GSV Control mit gespeichertem
Profil), muss das wissen. Rückweg: `Set Mode` (38) mit gelöschtem Bit 1.

**Fallstrick beim Lesen von Registern:** `Get Mode` (39) und verwandte
Lesebefehle antworten mit einem vorangestellten Semikolon `0x3B`. Die Spalte
„Länge der Befehlsantwort in Bytes" der Anleitung zählt nur die Datenbytes.
Wer nur ein Byte liest, bekommt `0x3B` statt des Registerwerts.

**`Set Range` (50) kennt nur 2 oder 3,5 mV/V**, der Vollausschlag endet also
auch im günstigsten Fall bei 3,675 mV/V. Eine Anzeige ab 10 ist nur über den
Normierungsfaktor (`set norm`, 16) erreichbar, nicht über den Messwert —
siehe [OQ-37](open-questions.md).

Verwendungszweck im Projekt: Sollwertquelle für den Datensatz-Sammelmodus,
siehe [OQ-38](open-questions.md).

**Nicht mit `SERIAL_PORT`/`SERIAL_BAUD` verwechseln.** Diese Schlüssel (unten)
beschreiben den **ausgehenden** Datenport nach GSVmulti (`/dev/ttyAMA0`). Der
GSV-2AS-Abgriff ist ein **zweiter, eingehender** Pfad über einen
USB-RS232-Adapter und gehört zum Sammelmodus — er bekommt **keine** Schlüssel
in `/etc/dispread/hardware.conf`. Die 38400 Baud aus der GSV-2-Anleitung
gelten für das Messgerät, nicht für `SERIAL_BAUD`.

## Bootkonfiguration

Relevante Zeilen in `/boot/firmware/config.txt`:

```
camera_auto_detect=1      # greift NUR beim Booten
display_auto_detect=1
dtparam=uart0=on          # aktiviert /dev/ttyAMA0
dtparam=i2c_arm=on
dtparam=pciex1
dtoverlay=vc4-kms-v3d
```

Nebenbefund: `auto_initramfs` ist auskommentiert, mit dem Hinweis auf einen
früheren Waveshare-Kernel 6.6.23. Für die Kamera unkritisch.

## Benutzer und Gruppen

`me-systeme` ist in `dialout`, `video`, `i2c`, `gpio`, `spi`, `render`, `sudo`.
Zugriff auf Kamera- und Serienports ist damit gegeben.

**Historisch, 2026-09-07:** `sudo` verlangte ein Passwort. Die damals
fehlenden Werkzeuge wurden am 2026-09-21 installiert;
[OQ-15](open-questions.md#oq-15) ist geklärt.

## Zeitsynchronisation

Seit 2026-09-21 ist `chrony` installiert und ersetzt `systemd-timesyncd`
([Abhängigkeiten](dependencies.md), [OQ-15](open-questions.md#oq-15)). Ein
24-Stunden-Nachweis für M1 sowie der Zeitvergleich zur Referenz M6 bleiben
offen; die Installation allein belegt weder Offset noch Drift.

## Konfigurationsschlüssel

Die folgende Tabelle ist der **historische IMX500-Planungsstand**. Insbesondere
`CAMERA_MODEL=imx500` ist kein aktueller Default der StreamCam. Der aktive
`v4l2://`-Pfad verlangt eine `camera.json` nach dem
[CameraSettings-Vertrag](../api/frames.md) mit USB-ID `046d:0893`, Bildformat,
Bildrate und den vier bestätigten UVC-Reglern.

Betriebliche Werte gehören nach `/etc/dispread/hardware.conf`. Regel wie bei
MEhub: **fehlende Datei oder fehlender Schlüssel ⇒ dokumentierter Default**,
kein Fehler.

| Schlüssel | Bedeutung | Default |
| --- | --- | --- |
| `CAM_PORT` | erwarteter CAM-Anschluss (0 oder 1) | 0 |
| `CAMERA_MODEL` | erwartetes Modul | `imx500` |
| `SERIAL_PORT` | Datenport | `/dev/ttyAMA0` |
| `SERIAL_BAUD` | Baudrate | offen ([OQ-01](open-questions.md)) |
| `SERIAL_TRANSCEIVER` | Typ des Pegelwandlers | offen ([OQ-09](open-questions.md)) |
| `HAS_ISOLATION` | galvanische Trennung vorhanden? | offen |
| `OCR_BACKEND` | `sevenseg` oder `tesseract_cli` | `sevenseg` |
| `IMX500_RPK` | Modell für die Detektion | keines (manual_roi ist Primärpfad) |

## Temporäre Vorschaukonfiguration (2026-09-08)

`examples/17_camera_display_preview.py`: Kameraindex 0, 960×720 RGB888,
15 Bilder/s angefordert, automatische Belichtung, kein IMX500-Inferenzmodell.
Diese Einstellungen gelten nur für den laufenden Prozess; keine Boot- oder
Hardwarekonfiguration geändert. Fokus und Aufbau unverändert.
Technischer Kurztest: [Laborjournal](lab_journal.md), 2026-09-08.

## Workbench-Controls (2026-09-08)

Nach Modularisierung gleicher temporärer Vorschauaufbau. Neue Liveabfrage:
ExposureTime 101..105904066 µs, AnalogueGain 1..22,26087, Contrast 0..32,
AeEnable unterstützt. Diese Treibergrenzen sind keine empfohlenen Messparameter;
insbesondere können sehr lange Belichtungen mit Vorschau-/Timeoutgrenzen
kollidieren. Tatsächlicher Kurztest und Metadaten: [Laborjournal](lab_journal.md).
Keine physische oder persistente Systemkonfiguration geändert.

## Fokus- und Kamera-Controls (2026-09-08 gemessen)

Vollständige Controlliste der laufenden Kamera: `AeConstraintMode`, `AeEnable`,
`AeExposureMode`, `AeFlickerMode`, `AeFlickerPeriod`, `AeMeteringMode`,
`AnalogueGain`, `AnalogueGainMode`, `AwbEnable`, `AwbMode`, `Brightness`,
`CnnEnableInputTensor`, `ColourCorrectionMatrix`, `ColourGains`,
`ColourTemperature`, `Contrast`, `ExposureTime`, `ExposureTimeMode`,
`ExposureValue`, `FrameDurationLimits`, `HdrMode`, `NoiseReductionMode`,
`Saturation`, `ScalerCrop`, `ScalerCrops`, `Sharpness`, `StatsOutputEnable`,
`SyncFrames`, `SyncMode`.

**Kein Fokus-Control.** `Sharpness` ist ISP-Nachschärfung und verstellt das
Objektiv nicht. Fokussiert wird ausschließlich mechanisch am Objektiv. Die
Fokusassistenz der Workbench vergrößert nur die bestätigte ROI und zeigt einen
relativen Schärfewert; sie bewegt nichts.

Ebenfalls sichtbar: `ExposureTimeMode`/`AnalogueGainMode` sind die neueren
libcamera-Controls neben dem älteren `AeEnable`. Die Workbench benutzt weiter
`AeEnable`; ob ein Wechsel nötig ist, ist nicht geprüft.

## Windows-Gegenstelle für GSVmulti — Rückmeldung 2026-11-04

Windows 11, GSVmulti 2.03 mit aktivierter PRO-Lizenz und verfügbarem
UserDefined; Python 3.15 x64. Die CIM-Abfrage identifiziert COM3 als Intel Active Management
Technology SOL (PCI), nicht als USB-TTL-Kabel. Ein realer Adapter-COM-Port
wurde anschließend per USB-PnP-Vergleich als COM4 mit Status OK identifiziert
(USB Serial Port, FTDIBUS VID_0403/PID_6001). Diese Angaben
stammen vom Nutzer, nicht von einer direkten Fernabfrage.

Die laut Nutzer signierte com0com-Ausgabe startet nicht: Beide konfigurierten
Busgeräte melden PnP-Code 52. Keine funktionsfähigen virtuellen COM-Ports
oder GSVmulti-Empfang bestätigt. Exaktes Paket/Zertifikat unbekannt.
Beleg: `var/diagnostics/gsvmulti/windows-com0com-pnp-20261104-03.txt`,
Deutung im [Laborjournal](lab_journal.md). Physische Pi-UART-Verdrahtung
ist durch diesen Softwarebefund nicht geprüft.

### Pi-UART-Vorprüfung für den direkten Demotest, 2026-11-04

Direkt lesend geprüft: `/dev/ttyAMA0` vorhanden, uart0 in der Bootdatei
aktiviert, `serial-getty@ttyAMA0` inaktiv. `pinctrl get 14-15` zeigt
GPIO14=TXD0 und GPIO15=RXD0; `fuser /dev/ttyAMA0` nennt keinen Prozess.
Beleg: `var/diagnostics/gsvmulti/pi-uart-preflight-20261104.txt`.
Keine serielle Ausgabe oder Pinänderung durchgeführt. Die Kabelbelegung
und dessen Windows-Port sind damit noch nicht bestätigt.

### Windows-USB-TTL-Port identifiziert, 2026-11-04

Nutzerrückmeldung beim Einstecken: `USB Serial Port (COM4)`, Klasse Ports,
Status OK, sowie `USB Serial Converter`, Klasse USB, Status OK. VID_0403,
PID_6001; Beleg `var/diagnostics/gsvmulti/windows-usb-ttl-20261104-05.txt`.
COM4 wird für den direkten UserDefined-Demotest verwendet. RXD/GND-Ader-
zuordnung und tatsächliche Datenübertragung sind noch nicht bestätigt.

### Vorgesehene Verdrahtung des einseitigen UART-Demotests

Nutzerrecherche 2026-11-04: Gelb=RXD, Schwarz=GND, Orange=TXD. Genaues
DELOCK-Modell und Internetquelle nicht unabhängig identifiziert; Schema
entspricht den üblichen FTDI-Kabelfarben. Für den Test wird folgende
Verbindung angeleitet, Durchführung noch nicht bestätigt:

| Pi, physischer Pin | Kabel |
| --- | --- |
| 8, GPIO14/TXD0 | Gelb, RXD laut Nutzerrecherche |
| 6, GND | Schwarz, GND laut Nutzerrecherche |

Orange/TXD, Rot/VCC, Braun/CTS und Grün/RTS bleiben frei. Kein Anschluss
der Kabelversorgung an den Pi. Pi-Pinpositionen:
[Raspberry-Pi-Dokumentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#pin-functions).
GPIO14=TXD0 am Pi erneut lesend geprüft; fuser nennt keinen UART-Nutzer.
Noch kein Telegramm gesendet.

### Anschlusskorrektur: gemeinsamer 6-poliger Kabelblock

Nutzerrückmeldung 2026-11-04: Die Kabelkontakte sitzen gemeinsam in einem
schwarzen 6-poligen Buchsenblock, beschriftet GND, CTS, VCC, TXD, RXD, RTS.
Die frühere Beschreibung als einzeln steckbare Female-Enden ist damit
überholt. Block-Pinfolge und Pi-GPIO-Pinfolge sind nicht deckungsgleich;
den Block nicht direkt auf die Pi-Leiste stecken.

Für den einseitigen Demotest zwei Male–Female-Jumper benutzen: Stecker
in Block GND und Buchse auf physischen Pi-Pin 6; Stecker in Block RXD
und Buchse auf physischen Pi-Pin 8 (GPIO14/TXD0). CTS/VCC/TXD/RTS bleiben
frei. Diese Anweisung nutzt die gemeldete Kontaktbeschriftung, nicht nur
Farben. Durchführung noch nicht bestätigt.

### Verdrahtung gemeldet, Empfangsbereitschaft offen

Nutzer meldet am 2026-11-04 die Pins als angeschlossen, nach obiger
Zwei-Jumper-Anweisung. Keine unabhängige Sichtprüfung. Vorbereitender
Read-only-Check bestätigt erneut GPIO14=TXD0, GPIO15=RXD0; fuser zeigt
keinen Portnutzer, Getty inaktiv. Noch kein Telegramm gesendet; zuerst
GSVmulti-UserDefined auf COM4 empfangsbereit machen.

### UART-Rohdatenempfang auf Windows belegt, 2026-11-04

Im direkten Versuch 03 mit geschlossenem GSVmulti bestätigt der vom Nutzer
kopierte PowerShell-Hex-Ausschnitt sechs erwartete Telegramme einschließlich
% und CRLF. COM4/115200/8N1, Pi ttyAMA0 und gemeldete Zwei-Jumper-Verbindung.
Belege und Grenzen: [VALIDATION](VALIDATION.md#uart-demo-20261104-03).
Keine allgemeine Leitungs-, GSVmulti-, Isolations- oder DUT-Freigabe.


### Direkter GSVmulti-Zahlenempfang sichtbar, 2026-11-04

Lauf 04 mit gleicher gemeldeter UART-Verbindung: Nach Einschalten von
Filter Out Non-Numeric zeigt GSVmulti 2.03 Pro auf COM4 Zahlen.
Pi-seitig 600 Telegramme/6600 Bytes, GSVmulti-Empfangsanzahl unbekannt.
Der Screenshot ist wegen möglicher Anzeigemittelung kein Einzelwertbeleg.
[Messung und Grenzen](VALIDATION.md#uart-demo-20261104-04).
Keine neue Verdrahtung und keine Freigabe realer DUT-Ausgabe.


### GSVmulti-Datenfrequenz auf 10 Hz gemeldet, 2026-11-04

Der gezeigte Change Data Rate-Dialog stand auf 1 Wert/s. Nach Anleitung
zur Eingabe von 10 und Bestätigung mit OK meldet der Nutzer 10 Hz als
eingetragen. Keine Änderung am Pi-UART oder der Verdrahtung. Snapshot
mit ursprünglichem Dialog und Nutzerrückmeldung:
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-06/receiver-setup.json`.
Wirkung auf die exportierte Zeitachse noch nicht bestätigt.


Der Nutzerexport aus Lauf 06 bestätigt Frequency=10 Hz in TXT und TDMS.
Zeitmodus bleibt `tf`, weshalb das Intervall aus Start/Ende/Werteanzahl
berechnet wird. Keine weitere Einstellung geändert.
[Auswertung](VALIDATION.md#uart-demo-20261104-06).


### Nominelle GSVmulti-Zeitachse für Sprungtest angeleitet, 2026-11-04

Advanced-Screenshot bestätigt Auto-Select mit Calculate dt from Final time.
Danach für den synthetischen Funktionstest Auto-Select aus und Use device
data rate (0,1 s bei 10 Hz) angeleitet; Nutzer meldet bereit. Noch keine
unabhängige Bestätigung durch neuen Export. Es ist eine nominelle Zeitachse,
kein Quellzeit-/Latenznachweis. Konfig-Snapshot unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-07/receiver-setup.json`.


Lauf 07 bestätigt im Nutzer-TXT/TDMS Frequency=10 Hz, dt mode=1/f0 und
nominelles Intervall 0,1 s nach der angeleiteten Umstellung. Alle acht
getesteten Sprünge sind in den gespeicherten Werten unverändert.
Keine neue Hardwareänderung und kein Nachweis tatsächlicher Quellzeiten.
[Auswertung](VALIDATION.md#uart-demo-20261104-07).


### Replace Missing Values nach Test als aktiv bestätigt, 2026-11-04

Nutzer prüft die Checkbox nach Lauf 10 ausdrücklich und bestätigt sie als
gesetzt. Bei ansonsten gleichem UserDefined-NaN-Stimulus keine Fehlwertmarker
in TDMS/TXT; Zeitraster verdichtet weiter. Kein neuer Hardwareumbau und keine
Freigabe echter DUT-Ausgabe. [Messung](VALIDATION.md#uart-demo-20261104-10).


### Einheit mV/V für Demolauf 11 angeleitet, 2026-11-04

Nutzer bestätigt Unit bei gestoppter Messung/Aufnahme als bedienbar.
Anleitung Unit=mV/V, User Scaling=1 und Save Session unter neuem Namen;
danach Bereitschaft zu Lauf 11 gemeldet. Auswahl noch nicht im Export
bestätigt. Konfig-Snapshot:
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-11/receiver-setup.json`.
Keine Hardwareänderung und keine reale DUT-Freigabe.


Lauf 11 bestätigt die Auswahl im Nutzerexport: TDMS unit_string und
NI_UnitDescription jeweils mV/V, Scaling=1. Die gespeicherte UCF enthält
Unit=mV/V, COM4/115200 und Frequency=10 Hz. TXT ohne eigene Einheitenangabe.
Kein Neuladeversuch und keine echte DUT-Freigabe.
[Messbeleg](VALIDATION.md#uart-demo-20261104-11).


### COM-Kanal nach Close nicht wieder geöffnet, Lauf 12 am 2026-11-04

Gleiche angeschlossene UART-Strecke, kein Kabel abgezogen. Nutzer bestätigt
Device Close, Wiederöffnen scheitert mit MEGSV-Fehler 805306614 (Port bereits
offen). Vollständiger GSVmulti-Neustart hilft laut Nutzer. COM4-Belegung gegen
internen DLL-Zustand noch nicht isoliert; keine aktuelle Prozesszuordnung
behaupten. Snapshot: `var/diagnostics/gsvmulti/uart-direct-demo-20261104-12/receiver-error.json`.
[Diagnose](GSVMULTI_PROTOCOL.md#userdefined-reopen-fehler).


### Experimentelles A-Präfix-Profil gespeichert, noch nicht gesendet, 2026-11-04

Neue UserDefined-UCF bestätigt Prefix65 (A), Separator0, Frequency10Hz,
UnitmV/V, COM4/115200 und ein Wert. Gegen Filter-aus-Profil aus Lauf14 ist
nur Prefix37→65 geändert. Keine Annahme über erfolgreiche Aktivierung oder
NaN-Unterstützung vor dem Sendeversuch. Snapshot
`var/diagnostics/gsvmulti/A-prefix-nan-preparation.json`.

## Option USB-Gadget, noch nicht aktiviert {#usb-gadget-option}

2026-11-04, ausschließlich lesend geprüft: lokaler Modellstring bestätigt
Pi5 ModelB Rev1.1, /sys/class/udc leer. Hersteller dokumentiert USB-Peripheral
am USB-C-Port; die normalen USB-A-Ports sind Host-Ports. Damit ist ein
CDC-ACM-Gadget grundsätzlich eine Option, kein bereits eingerichteter Port.
Snapshot mit unveränderter Bootkonfiguration unter
`var/diagnostics/gsvmulti/usb-gadget-feasibility-20261104/`.
Vorhandenes dwc2-host-Overlay steht in Abschnitt cm5 und belegt keinen aktiven
Pi5-Hostmodus. Keine Konfiguration oder Hardware geändert. Konkrete Versorgung
und ausreichende Leistungsreserve des USB-Hosts noch nicht erfasst
([OQ-56](open-questions.md#oq-56)); USB-C übernimmt zugleich die Stromzufuhr.
[Quellen und Nachweisgrenzen](GSVMULTI_PROTOCOL.md#usb-cdc-option).

### Versorgung über X1201 V1.1 laut Nutzer

2026-11-04: Nutzer nennt 5V UPS Shield X1201 V1.1 von SupTronics Technologies,
Ladeversorgung am eigenen USB-C des Shields; Produktion kann ohne UPS geplant
sein. Hersteller beschreibt5.1V/max5A und Pi-Kontaktierung über pogo pins;
keine unabhängige Foto-/Versorgungsmessung. Genaue Lade-Netzteilleistung noch
nicht belegt. [Herstellerhinweis](https://suptronics.com/Raspberrypi/Power_mgmt/x1201-v1.1.html):
keine zusätzliche Versorgung des Pi über dessen USB-C-Port. Das schränkt die
Gadget-Verkabelung ein; normalen PC-USB-Anschluss nicht parallel freigeben.
VBUS-getrennte Datenstrecke und Produktionsversorgung sind noch zu prüfen
([Umsetzung](GSVMULTI_PROTOCOL.md#usb-cdc-umsetzung), OQ-56). Keine Hardwareänderung.

### Virtuelles Windows-COM-Paar nach Buildvergleich erkannt

2026-11-04: Nutzer meldet nach angeleitetem Wechsel zur Vovsoft-verlinkten
com0com-Ausgabe beide Busse und vier Portgeräte mit Code0. Paar1 ist
CNCA1=COM5, CNCB1=COM6. Historischer Code52-Befund des CyberCircuits-Pakets
bleibt oben erhalten. Byteübertragung/GSVmulti noch nicht geprüft, aktuelle
Treiberdatei und Schutzstatus nach Installation noch nicht rückgelesen.
[Nachweisgrenzen](VALIDATION.md#com0com-pnp-ok-20261104). Keine Pi-Hardwareänderung.

**Folgeprobe am selben Tag:** COM5↔COM6 überträgt je eine exakt geprüfte
ASCII-Zeile. Aktueller Treiberhash passt zum Vovsoft-Kandidaten; SecureBoot
und Speicherintegrität bleiben aktiv. [Beleg](VALIDATION.md#com0com-pair-ok-20261104).
Noch keine GSVmulti-/Windows-Brücken-/Dauerlaufabnahme, keine Pi-Hardwareänderung.
