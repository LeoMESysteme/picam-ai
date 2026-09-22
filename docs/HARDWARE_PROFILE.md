# Hardware-Profil

Stand 2026-09-07, Gerät `raspi06`.

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

**Konsequenz aus 34 GB frei:** Datensätze und Diagnosebilder gehören auf
externen Speicher. Im Betrieb Ringpuffer mit harter Obergrenze — der
`JsonlSink` rotiert bei 64 MB und behält 5 Generationen.

## Kamera

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
belegt ist. `/dev/serial0` scheidet ohnehin aus (Debug-Header). Stand
2026-09-22 ist **kein** USB-Seriell-Adapter angesteckt (`/dev/ttyUSB*` fehlt);
der Benutzer ist bereits in `dialout`, Rechtearbeit entfällt. Für stabile
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

**`sudo` verlangt seit dem Reboot am 2026-09-07 ein Passwort.** Automatisierte
Paketinstallationen sind dadurch nicht möglich — siehe
[OQ-15](open-questions.md).

## Zeitsynchronisation

Aktuell `systemd-timesyncd`. Das liefert **keine protokollierbare Offset- und
Drift-Historie**. Für Messung M1 wird `chrony` gebraucht
([OQ-15](open-questions.md)) — ohne `chronyc tracking`-Log ist die Aussage
„Pi-Zeit gegen Referenz" nicht belegbar.

## Konfigurationsschlüssel

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
